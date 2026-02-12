import discord
from discord.ext import commands
from discord import SlashCommandGroup
import random
from typing import Optional
import logging

from config import Config

logger = logging.getLogger('DebateBot.Matchmaking')
from utils.models import (
    MatchmakingQueue, DebateRound, DebateTeam, JudgePanel,
    TeamType, RoundType
)
from utils.embeds import EmbedBuilder


class HostControlView(discord.ui.View):
    """View for host controls to start rounds."""

    def __init__(self, cog, round_type: RoundType, queue_debaters: list, queue_judges: list):
        super().__init__(timeout=None)
        self.cog = cog
        self.round_type = round_type
        self.queue_debaters = queue_debaters
        self.queue_judges = queue_judges

        # Add buttons based on round type
        if round_type == RoundType.DOUBLE_IRON:
            self.add_item(StartRoundButton(
                label="Start Double Iron Round (2v2)",
                style=discord.ButtonStyle.primary,
                round_type=round_type,
                cog=cog,
                queue_debaters=queue_debaters,
                queue_judges=queue_judges
            ))
        elif round_type == RoundType.SINGLE_IRON:
            self.add_item(StartRoundButton(
                label="Start Single Iron Round",
                style=discord.ButtonStyle.primary,
                round_type=round_type,
                cog=cog,
                queue_debaters=queue_debaters,
                queue_judges=queue_judges
            ))
        elif round_type == RoundType.STANDARD:
            self.add_item(StartRoundButton(
                label="Start Standard Round (3v3)",
                style=discord.ButtonStyle.success,
                round_type=round_type,
                cog=cog,
                queue_debaters=queue_debaters,
                queue_judges=queue_judges
            ))
            self.add_item(WaitForPanelistsButton(cog=cog))


class StartRoundButton(discord.ui.Button):
    """Button to start a debate round."""

    def __init__(self, label: str, style: discord.ButtonStyle, round_type: RoundType, cog, queue_debaters: list, queue_judges: list):
        super().__init__(label=label, style=style)
        self.round_type = round_type
        self.cog = cog
        self.queue_debaters = queue_debaters
        self.queue_judges = queue_judges

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()

        # Create the round allocation
        debate_round = self.cog.create_round_allocation(self.queue_debaters, self.queue_judges, self.round_type)

        # Store the round
        self.cog.current_round = debate_round

        # Clear the queue
        self.cog.queue.clear()
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
            "✅ Continuing to wait for additional panelists. The queue remains open.",
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
        if self.cog.queue.remove_user(interaction.user):
            await interaction.response.send_message("✅ You have left the queue.", ephemeral=True)
            await self.cog.update_lobby_display()
            await self.cog.check_matchmaking_threshold()
        else:
            await interaction.response.send_message("❌ You are not in the queue.", ephemeral=True)


class Matchmaking(commands.Cog):
    """Cog handling matchmaking queue and round initialization."""

    def __init__(self, bot):
        self.bot = bot
        self.queue = MatchmakingQueue()
        self.current_round: Optional[DebateRound] = None
        self.round_counter = 0
        self.host_notification_message: Optional[discord.Message] = None

    async def cog_load(self):
        """Called when the cog is loaded."""
        logger.info("Matchmaking cog loaded")
        logger.info("Registering slash commands: /queue, /leave, /clearqueue")
        # Initialize lobby display
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

            logger.info(f"✓ Found lobby channel: {lobby_channel.name}")

            # Check if we already have a lobby message
            if self.queue.lobby_message:
                try:
                    await self.queue.lobby_message.delete()
                except:
                    pass

            # Create new lobby message
            embed = EmbedBuilder.create_lobby_embed(self.queue)
            view = LobbyView(self)
            self.queue.lobby_message = await lobby_channel.send(embed=embed, view=view)
            logger.info("✓ Lobby embed created successfully")

        except Exception as e:
            logger.error(f"Error initializing lobby: {e}", exc_info=True)

    async def update_lobby_display(self):
        """Update the lobby embed with current queue status."""
        if not self.queue.lobby_message:
            await self.initialize_lobby()
            return

        try:
            embed = EmbedBuilder.create_lobby_embed(self.queue)
            view = LobbyView(self)
            await self.queue.lobby_message.edit(embed=embed, view=view)
        except discord.NotFound:
            # Message was deleted, reinitialize
            await self.initialize_lobby()
        except Exception as e:
            print(f"Error updating lobby display: {e}")

    async def check_matchmaking_threshold(self):
        """Check if queue has reached a matchmaking threshold."""
        threshold = self.queue.get_threshold_type()

        if threshold is None:
            # Clear host notification if it exists and queue is below threshold
            if self.host_notification_message:
                try:
                    await self.host_notification_message.delete()
                except:
                    pass
                self.host_notification_message = None
            return

        # Send or update host notification
        await self.send_host_notification(threshold)

    async def send_host_notification(self, round_type: RoundType):
        """Send notification to host channel about ready queue."""
        try:
            host_channel = self.bot.get_channel(Config.HOST_CHANNEL_ID)
            if not host_channel:
                print(f"Warning: Host channel {Config.HOST_CHANNEL_ID} not found")
                return

            embed = EmbedBuilder.create_host_notification_embed(
                self.queue.debater_count(),
                self.queue.judge_count(),
                round_type
            )
            view = HostControlView(
                self,
                round_type,
                list(self.queue.debaters),
                list(self.queue.judges)
            )

            # Delete old notification if exists
            if self.host_notification_message:
                try:
                    await self.host_notification_message.delete()
                except:
                    pass

            # Ping host role if configured
            content = None
            if Config.HOST_ROLE_ID:
                content = f"<@&{Config.HOST_ROLE_ID}>"

            self.host_notification_message = await host_channel.send(
                content=content,
                embed=embed,
                view=view
            )

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

        # Initialize teams and judge panel
        judge_panel = JudgePanel()

        # Allocate teams based on round type
        if round_type == RoundType.DOUBLE_IRON:
            # 4 debaters: 2v2, 1+ judges
            gov_team = DebateTeam("Government", TeamType.IRON)
            opp_team = DebateTeam("Opposition", TeamType.IRON)

            gov_team.members = shuffled_debaters[0:2]
            opp_team.members = shuffled_debaters[2:4]

            # Assign judges
            for judge in shuffled_judges:
                judge_panel.add_judge(judge)

        elif round_type == RoundType.SINGLE_IRON:
            # 5 debaters: One full team (3), one iron team (2), 1+ judges
            # Randomly decide which team is iron
            gov_is_iron = random.choice([True, False])

            gov_team = DebateTeam("Government", TeamType.IRON if gov_is_iron else TeamType.FULL)
            opp_team = DebateTeam("Opposition", TeamType.FULL if gov_is_iron else TeamType.IRON)

            if gov_is_iron:
                gov_team.members = shuffled_debaters[0:2]
                opp_team.members = shuffled_debaters[2:5]
            else:
                gov_team.members = shuffled_debaters[0:3]
                opp_team.members = shuffled_debaters[3:5]

            # Assign judges
            for judge in shuffled_judges:
                judge_panel.add_judge(judge)

        else:  # STANDARD
            # 6+ debaters: 3v3, 1+ judges
            gov_team = DebateTeam("Government", TeamType.FULL)
            opp_team = DebateTeam("Opposition", TeamType.FULL)

            gov_team.members = shuffled_debaters[0:3]
            opp_team.members = shuffled_debaters[3:6]

            # Assign all judges
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
        # Import here to avoid circular import
        from cogs.adjustment import AllocationAdjustmentView

        embed = EmbedBuilder.create_allocation_embed(debate_round)
        view = AllocationAdjustmentView(self, debate_round)
        await channel.send(embed=embed, view=view)

    @discord.slash_command(
        name="queue",
        description="Join the matchmaking queue for a debate round",
        default_member_permissions=None  # Allow everyone to use this command
    )
    async def queue_command(
        self,
        ctx: discord.ApplicationContext,
        role: str = discord.Option(
            description="Queue as a debater or judge",
            choices=["debater", "judge"],
            required=True
        )
    ):
        """Join the matchmaking queue as debater or judge."""
        logger.info(f"User {ctx.author} ({ctx.author.id}) used /queue command as {role}")

        # Add user to appropriate queue
        if role == "debater":
            success = self.queue.add_debater(ctx.author)
            role_text = "debater"
        else:
            success = self.queue.add_judge(ctx.author)
            role_text = "judge"

        if success:
            # RESPOND IMMEDIATELY to avoid interaction timeout
            await ctx.respond(
                embed=EmbedBuilder.create_success_embed(
                    f"Joined Queue as {role_text.title()}",
                    f"You have been added to the {role_text} queue.\n"
                    f"**Debaters:** {self.queue.debater_count()} | **Judges:** {self.queue.judge_count()}"
                )
            )

            # Then update lobby and check threshold AFTER responding
            await self.update_lobby_display()
            await self.check_matchmaking_threshold()
        else:
            # User switched roles - this shouldn't normally happen but handle it
            current_role = self.queue.get_user_role(ctx.author)
            await ctx.respond(
                embed=EmbedBuilder.create_success_embed(
                    f"Switched to {role_text.title()}",
                    f"You have been moved from {current_role} to {role_text} queue.\n"
                    f"**Debaters:** {self.queue.debater_count()} | **Judges:** {self.queue.judge_count()}"
                )
            )

    @discord.slash_command(
        name="leave",
        description="Leave the matchmaking queue",
        default_member_permissions=None  # Allow everyone to use this command
    )
    async def leave_command(self, ctx: discord.ApplicationContext):
        """Leave the matchmaking queue."""
        logger.info(f"User {ctx.author} ({ctx.author.id}) used /leave command")

        # Remove user from queue
        if self.queue.remove_user(ctx.author):
            # RESPOND IMMEDIATELY to avoid interaction timeout
            await ctx.respond(
                embed=EmbedBuilder.create_success_embed(
                    "Left Queue",
                    "You have been removed from the queue."
                ),
                ephemeral=False
            )

            # Then update lobby and check threshold AFTER responding
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
        name="lobby",
        description="Show the AP Debate Matchmaking Lobby info",
        default_member_permissions=None
    )
    async def lobby_command(self, ctx: discord.ApplicationContext):
        """Show the lobby infobox with current queue status."""
        logger.info(f"User {ctx.author} ({ctx.author.id}) used /lobby command")
        embed = EmbedBuilder.create_lobby_embed(self.queue)
        await ctx.respond(embed=embed, ephemeral=False)

    @discord.slash_command(
        name="start",
        description="Start a debate round from the current queue (Host only)",
        default_member_permissions=None
    )
    async def start_command(self, ctx: discord.ApplicationContext):
        """Start a debate round. Only the host can use this command."""
        logger.info(f"User {ctx.author} ({ctx.author.id}) used /start command")

        # Check if user is the host
        is_host = False
        if Config.HOST_ROLE_ID:
            is_host = any(role.id == Config.HOST_ROLE_ID for role in ctx.author.roles)
        if not is_host:
            await ctx.respond(
                embed=EmbedBuilder.create_error_embed(
                    "Permission Denied",
                    "Only the host can start a debate round."
                ),
                ephemeral=False
            )
            return

        # Check minimum requirements: at least 4 debaters and 1 judge
        debaters = self.queue.debater_count()
        judges = self.queue.judge_count()

        if debaters < 4 or judges < 1:
            needed = []
            if debaters < 4:
                needed.append(f"**{4 - debaters}** more debater(s)")
            if judges < 1:
                needed.append(f"**1** judge")
            await ctx.respond(
                embed=EmbedBuilder.create_error_embed(
                    "Not Enough Players",
                    f"Cannot start a round. Need at least **4 debaters** and **1 judge**.\n"
                    f"Currently: **{debaters}** debater(s), **{judges}** judge(s).\n"
                    f"Still need: {', '.join(needed)}."
                ),
                ephemeral=False
            )
            return

        # Determine round type from queue
        round_type = self.queue.get_threshold_type()
        if round_type is None:
            await ctx.respond(
                embed=EmbedBuilder.create_error_embed(
                    "Cannot Start",
                    "The current queue composition doesn't match any round type."
                ),
                ephemeral=False
            )
            return

        # Acknowledge the command
        await ctx.respond(
            embed=EmbedBuilder.create_success_embed(
                "Starting Round",
                f"Creating a **{round_type.value.replace('_', ' ').title()}** round with "
                f"**{debaters}** debaters and **{judges}** judge(s)..."
            ),
            ephemeral=False
        )

        # Create the round allocation
        debate_round = self.create_round_allocation(
            list(self.queue.debaters),
            list(self.queue.judges),
            round_type
        )

        # Store the round
        self.current_round = debate_round

        # Clear the queue and update lobby
        self.queue.clear()
        await self.update_lobby_display()

        # Delete host notification if it exists
        if self.host_notification_message:
            try:
                await self.host_notification_message.delete()
            except:
                pass
            self.host_notification_message = None

        # Show allocation interface in the same channel
        await self.show_allocation_interface(ctx.channel, debate_round)

    @discord.slash_command(
        name="clearqueue",
        description="Clear the entire matchmaking queue (Admin only)"
    )
    @commands.has_permissions(administrator=True)
    async def clear_queue_command(self, ctx: discord.ApplicationContext):
        """Clear the entire queue."""
        self.queue.clear()
        await self.update_lobby_display()
        await self.check_matchmaking_threshold()
        await ctx.respond(
            embed=EmbedBuilder.create_success_embed(
                "Queue Cleared",
                "The matchmaking queue has been cleared."
            ),
            ephemeral=False
        )


def setup(bot):
    bot.add_cog(Matchmaking(bot))
