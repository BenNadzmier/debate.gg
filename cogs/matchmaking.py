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


class HostControlView(discord.ui.View):
    """View for host controls to start rounds."""

    def __init__(self, cog, round_type: RoundType, queue_debaters: list, queue_judges: list, format_label: str):
        super().__init__(timeout=None)
        self.cog = cog
        self.round_type = round_type
        self.queue_debaters = queue_debaters
        self.queue_judges = queue_judges
        self.format_label = format_label

        # Add buttons based on round type
        if round_type == RoundType.PM_LO:
            self.add_item(StartRoundButton(
                label="Start 1v1 Round (PM vs LO)",
                style=discord.ButtonStyle.primary,
                round_type=round_type,
                cog=cog,
                queue_debaters=queue_debaters,
                queue_judges=queue_judges,
                format_label=format_label
            ))
        elif round_type == RoundType.DOUBLE_IRON:
            self.add_item(StartRoundButton(
                label="Start Double Iron Round (2v2)",
                style=discord.ButtonStyle.primary,
                round_type=round_type,
                cog=cog,
                queue_debaters=queue_debaters,
                queue_judges=queue_judges,
                format_label=format_label
            ))
        elif round_type == RoundType.SINGLE_IRON:
            self.add_item(StartRoundButton(
                label="Start Single Iron Round",
                style=discord.ButtonStyle.primary,
                round_type=round_type,
                cog=cog,
                queue_debaters=queue_debaters,
                queue_judges=queue_judges,
                format_label=format_label
            ))
        elif round_type == RoundType.STANDARD:
            self.add_item(StartRoundButton(
                label="Start Standard Round (3v3)",
                style=discord.ButtonStyle.success,
                round_type=round_type,
                cog=cog,
                queue_debaters=queue_debaters,
                queue_judges=queue_judges,
                format_label=format_label
            ))
            self.add_item(WaitForPanelistsButton(cog=cog))


class StartRoundButton(discord.ui.Button):
    """Button to start a debate round."""

    def __init__(self, label: str, style: discord.ButtonStyle, round_type: RoundType, cog, queue_debaters: list, queue_judges: list, format_label: str):
        super().__init__(label=label, style=style)
        self.round_type = round_type
        self.cog = cog
        self.queue_debaters = queue_debaters
        self.queue_judges = queue_judges
        self.format_label = format_label

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()

        # Create the round allocation
        debate_round = self.cog.create_round_allocation(self.queue_debaters, self.queue_judges, self.round_type)

        # Store the round
        self.cog.current_round = debate_round

        # Clear the correct queue
        queue = self.cog._get_queue(self.format_label)
        queue.clear()
        await self.cog.update_lobby_display()

        # Disable this view
        self.view.stop()
        for item in self.view.children:
            item.disabled = True
        await interaction.message.edit(view=self.view)

        # Show allocation embed with adjustment controls
        await self.cog.show_allocation_interface(interaction.channel, debate_round)


class WaitForPanelistsButton(discord.ui.Button):
    """Button to wait for more panelists."""

    def __init__(self, cog):
        super().__init__(label="Wait for Panelists", style=discord.ButtonStyle.secondary)
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "Continuing to wait for additional panelists. The queue remains open.",
            ephemeral=True
        )


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
        self.host_notification_1v1: Optional[discord.Message] = None
        self.host_notification_ap: Optional[discord.Message] = None

    def _get_queue(self, format_name: str) -> MatchmakingQueue:
        """Get the queue for a given format."""
        return self.queue_1v1 if format_name == "1v1" else self.queue_ap

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
        """Check if either queue has reached a matchmaking threshold."""
        # Check 1v1 queue
        threshold_1v1 = self.queue_1v1.get_threshold_type()
        if threshold_1v1:
            await self.send_host_notification(threshold_1v1, self.queue_1v1, "1v1")
        else:
            if self.host_notification_1v1:
                try:
                    await self.host_notification_1v1.delete()
                except:
                    pass
                self.host_notification_1v1 = None

        # Check AP queue
        threshold_ap = self.queue_ap.get_threshold_type()
        if threshold_ap:
            await self.send_host_notification(threshold_ap, self.queue_ap, "AP")
        else:
            if self.host_notification_ap:
                try:
                    await self.host_notification_ap.delete()
                except:
                    pass
                self.host_notification_ap = None

    async def send_host_notification(self, round_type: RoundType, queue: MatchmakingQueue, format_label: str):
        """Send notification to host channel about ready queue."""
        try:
            host_channel = self.bot.get_channel(Config.HOST_CHANNEL_ID)
            if not host_channel:
                print(f"Warning: Host channel {Config.HOST_CHANNEL_ID} not found")
                return

            embed = EmbedBuilder.create_host_notification_embed(
                queue.debater_count(),
                queue.judge_count(),
                round_type
            )
            view = HostControlView(
                self,
                round_type,
                list(queue.debaters),
                list(queue.judges),
                format_label
            )

            # Delete old notification for this format
            if format_label == "1v1":
                old_msg = self.host_notification_1v1
            else:
                old_msg = self.host_notification_ap

            if old_msg:
                try:
                    await old_msg.delete()
                except:
                    pass

            # Ping host role if configured
            content = None
            if Config.HOST_ROLE_ID:
                content = f"<@&{Config.HOST_ROLE_ID}>"

            msg = await host_channel.send(
                content=content,
                embed=embed,
                view=view
            )

            if format_label == "1v1":
                self.host_notification_1v1 = msg
            else:
                self.host_notification_ap = msg

        except Exception as e:
            print(f"Error sending host notification: {e}")

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

    async def show_allocation_interface(self, channel, debate_round: DebateRound):
        """Show the allocation interface with adjustment controls."""
        from cogs.adjustment import AllocationAdjustmentView

        embed = EmbedBuilder.create_allocation_embed(debate_round)
        view = AllocationAdjustmentView(self, debate_round)
        await channel.send(embed=embed, view=view)

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
            current_role = queue.get_user_role(ctx.author)
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
        await self.check_matchmaking_threshold()
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
