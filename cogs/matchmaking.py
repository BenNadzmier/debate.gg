import discord
from discord.ext import commands
import random
from typing import Optional
import logging

from config import Config

logger = logging.getLogger('DebateBot.Matchmaking')
from utils.models import (
    MatchmakingQueue, DebateRound, DebateTeam, JudgePanel,
    TeamType, RoundType, FormatType
)
from utils.embeds import EmbedBuilder


class LobbyView(discord.ui.View):
    """Persistent view for the lobby with join/leave buttons."""

    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="Leave Queue", style=discord.ButtonStyle.danger, custom_id="leave_queue")
    async def leave_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Handle leave queue button press."""
        removed_1v1 = self.cog.queue_1v1.remove_user(interaction.user)
        removed_ap = self.cog.queue_ap.remove_user(interaction.user)

        if removed_1v1 or removed_ap:
            await interaction.response.send_message("You have left the queue.", ephemeral=True)
            await self.cog.update_lobby_display()
            await self.cog.check_matchmaking_threshold()
        else:
            await interaction.response.send_message("You are not in the queue.", ephemeral=True)


class Matchmaking(commands.Cog):
    """Cog handling matchmaking queue and round initialization."""

    def __init__(self, bot):
        self.bot = bot
        self.queue_1v1 = MatchmakingQueue(format_type=FormatType.ONE_V_ONE)
        self.queue_ap = MatchmakingQueue(format_type=FormatType.AP)
        self.lobby_message: Optional[discord.Message] = None
        self.current_round: Optional[DebateRound] = None
        self.round_counter = 0
        self.active_rounds: dict[int, DebateRound] = {}

    def _get_queue(self, format_name: str) -> MatchmakingQueue:
        """Get the queue for a given format."""
        return self.queue_1v1 if format_name == "1v1" else self.queue_ap

    def add_active_round(self, debate_round: DebateRound):
        """Track an active round."""
        self.active_rounds[debate_round.round_id] = debate_round

    def remove_active_round(self, round_id: int):
        """Remove a completed round."""
        self.active_rounds.pop(round_id, None)

    def requeue_participants(self, debate_round: DebateRound):
        """Return all participants to their original queue."""
        if not debate_round.format_label:
            return
        queue = self._get_queue(debate_round.format_label)
        roles = debate_round.get_original_queue_roles()
        for member, role in roles.items():
            if role == "debater":
                queue.add_debater(member)
            else:
                queue.add_judge(member)

    async def cog_load(self):
        """Called when the cog is loaded."""
        logger.info("Matchmaking cog loaded")
        logger.info("Registering slash commands: /queue, /leave, /clearqueue, /guide")
        await self.initialize_lobby()

    async def initialize_lobby(self):
        """Initialize or update the lobby display."""
        try:
            logger.info(f"Initializing lobby in channel {Config.LOBBY_CHANNEL_ID}")
            lobby_channel = self.bot.get_channel(Config.LOBBY_CHANNEL_ID)
            if not lobby_channel:
                logger.warning(f"Warning: Lobby channel {Config.LOBBY_CHANNEL_ID} not found")
                logger.warning("Make sure the bot has access to this channel and the ID is correct")
                return

            logger.info(f"Found lobby channel: {lobby_channel.name}")

            if self.lobby_message:
                try:
                    await self.lobby_message.delete()
                except:
                    pass

            embed = EmbedBuilder.create_lobby_embed(self.queue_1v1, self.queue_ap)
            view = LobbyView(self)
            self.lobby_message = await lobby_channel.send(embed=embed, view=view)
            logger.info("Lobby embed created successfully")

        except Exception as e:
            logger.error(f"Error initializing lobby: {e}", exc_info=True)

    async def update_lobby_display(self):
        """Update the lobby embed with current queue status."""
        if not self.lobby_message:
            await self.initialize_lobby()
            return

        try:
            embed = EmbedBuilder.create_lobby_embed(self.queue_1v1, self.queue_ap)
            view = LobbyView(self)
            await self.lobby_message.edit(embed=embed, view=view)
        except discord.NotFound:
            await self.initialize_lobby()
        except Exception as e:
            print(f"Error updating lobby display: {e}")

    async def check_matchmaking_threshold(self):
        """Check if either queue has reached a matchmaking threshold and auto-start a round."""
        if self.current_round:
            return

        for format_label, queue in [("1v1", self.queue_1v1), ("AP", self.queue_ap)]:
            round_type = queue.get_threshold_type()
            if round_type:
                # Auto-create round with random allocation
                debaters = list(queue.debaters)
                judges = list(queue.judges)
                debate_round = self.create_round_allocation(debaters, judges, round_type)
                self.current_round = debate_round
                debate_round.format_label = format_label
                queue.clear()
                await self.update_lobby_display()

                # Send confirmation to lobby channel
                rounds_cog = self.bot.get_cog("Rounds")
                lobby_channel = self.bot.get_channel(Config.LOBBY_CHANNEL_ID)
                if rounds_cog and lobby_channel:
                    await rounds_cog.send_participant_confirmation(
                        lobby_channel, debate_round, self
                    )
                break  # Only start one round at a time

    def create_round_allocation(self, debaters: list, judges: list, round_type: RoundType) -> DebateRound:
        """Create a debate round allocation from queued debaters and judges."""
        self.round_counter += 1

        # Shuffle debaters and judges separately for random allocation
        shuffled_debaters = debaters.copy()
        shuffled_judges = judges.copy()
        random.shuffle(shuffled_debaters)
        random.shuffle(shuffled_judges)

        # Initialize judge panel
        judge_panel = JudgePanel()

        # Allocate teams based on round type
        if round_type == RoundType.PM_LO:
            # 1v1: 1 debater per side, 1+ judges
            gov_team = DebateTeam("Government", TeamType.SOLO)
            opp_team = DebateTeam("Opposition", TeamType.SOLO)

            gov_team.members = [shuffled_debaters[0]]
            opp_team.members = [shuffled_debaters[1]]

            for judge in shuffled_judges:
                judge_panel.add_judge(judge)

        elif round_type == RoundType.DOUBLE_IRON:
            # 4 debaters: 2v2, 1+ judges
            gov_team = DebateTeam("Government", TeamType.IRON)
            opp_team = DebateTeam("Opposition", TeamType.IRON)

            gov_team.members = shuffled_debaters[0:2]
            opp_team.members = shuffled_debaters[2:4]

            for judge in shuffled_judges:
                judge_panel.add_judge(judge)

        elif round_type == RoundType.SINGLE_IRON:
            # 5 debaters: One full team (3), one iron team (2), 1+ judges
            gov_is_iron = random.choice([True, False])

            gov_team = DebateTeam("Government", TeamType.IRON if gov_is_iron else TeamType.FULL)
            opp_team = DebateTeam("Opposition", TeamType.FULL if gov_is_iron else TeamType.IRON)

            if gov_is_iron:
                gov_team.members = shuffled_debaters[0:2]
                opp_team.members = shuffled_debaters[2:5]
            else:
                gov_team.members = shuffled_debaters[0:3]
                opp_team.members = shuffled_debaters[3:5]

            for judge in shuffled_judges:
                judge_panel.add_judge(judge)

        else:  # STANDARD
            # 6+ debaters: 3v3, 1+ judges
            gov_team = DebateTeam("Government", TeamType.FULL)
            opp_team = DebateTeam("Opposition", TeamType.FULL)

            gov_team.members = shuffled_debaters[0:3]
            opp_team.members = shuffled_debaters[3:6]

            for judge in shuffled_judges:
                judge_panel.add_judge(judge)

        return DebateRound(
            round_id=self.round_counter,
            round_type=round_type,
            government=gov_team,
            opposition=opp_team,
            judges=judge_panel
        )

    @discord.slash_command(
        name="queue",
        description="Join the matchmaking queue for a debate round",
        default_member_permissions=None
    )
    async def queue_command(
        self,
        ctx: discord.ApplicationContext,
        role: str = discord.Option(
            description="Queue as a debater or judge",
            choices=["debater", "judge"],
            required=True
        ),
        debate_format: str = discord.Option(
            name="format",
            description="Debate format",
            choices=["1v1", "AP"],
            required=True
        )
    ):
        """Join the matchmaking queue as debater or judge for a specific format."""
        logger.info(f"User {ctx.author} ({ctx.author.id}) used /queue as {role} for {debate_format}")

        queue = self._get_queue(debate_format)
        other_queue = self.queue_ap if debate_format == "1v1" else self.queue_1v1

        # Remove from the other format's queue if present
        other_queue.remove_user(ctx.author)

        # Add user to appropriate queue
        if role == "debater":
            success = queue.add_debater(ctx.author)
        else:
            success = queue.add_judge(ctx.author)

        format_display = "1v1" if debate_format == "1v1" else "AP"

        if success:
            await ctx.respond(
                embed=EmbedBuilder.create_success_embed(
                    f"Joined {format_display} Queue as {role.title()}",
                    f"You have been added to the {format_display} {role} queue.\n"
                    f"**Debaters:** {queue.debater_count()} | **Judges:** {queue.judge_count()}"
                )
            )
        else:
            await ctx.respond(
                embed=EmbedBuilder.create_success_embed(
                    f"Switched to {role.title()} in {format_display}",
                    f"You have been moved to {role} in the {format_display} queue.\n"
                    f"**Debaters:** {queue.debater_count()} | **Judges:** {queue.judge_count()}"
                )
            )

        await self.update_lobby_display()
        await self.check_matchmaking_threshold()

    @discord.slash_command(
        name="leave",
        description="Leave the matchmaking queue",
        default_member_permissions=None
    )
    async def leave_command(self, ctx: discord.ApplicationContext):
        """Leave the matchmaking queue."""
        logger.info(f"User {ctx.author} ({ctx.author.id}) used /leave command")

        removed_1v1 = self.queue_1v1.remove_user(ctx.author)
        removed_ap = self.queue_ap.remove_user(ctx.author)

        if removed_1v1 or removed_ap:
            await ctx.respond(
                embed=EmbedBuilder.create_success_embed(
                    "Left Queue",
                    "You have been removed from the queue."
                ),
                ephemeral=False
            )
            await self.update_lobby_display()
            await self.check_matchmaking_threshold()
        else:
            await ctx.respond(
                embed=EmbedBuilder.create_error_embed(
                    "Not in Queue",
                    "You are not in the matchmaking queue."
                ),
                ephemeral=False
            )

    @discord.slash_command(
        name="clearqueue",
        description="Clear the entire matchmaking queue (Admin only)"
    )
    @commands.has_permissions(administrator=True)
    async def clear_queue_command(self, ctx: discord.ApplicationContext):
        """Clear the entire queue."""
        self.queue_1v1.clear()
        self.queue_ap.clear()
        await self.update_lobby_display()
        await ctx.respond(
            embed=EmbedBuilder.create_success_embed(
                "Queue Cleared",
                "All matchmaking queues have been cleared."
            ),
            ephemeral=False
        )

    @discord.slash_command(
        name="guide",
        description="Learn how the debate bot works",
        default_member_permissions=None
    )
    async def guide_command(self, ctx: discord.ApplicationContext):
        """Show the guide for how the bot works."""
        embed = EmbedBuilder.create_guide_embed()
        await ctx.respond(embed=embed)


def setup(bot):
    bot.add_cog(Matchmaking(bot))
