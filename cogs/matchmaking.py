import discord
from discord.ext import commands
from discord import SlashCommandGroup
import random
from typing import Optional

from config import Config
from utils.models import (
    MatchmakingQueue, DebateRound, DebateTeam, JudgePanel,
    TeamType, RoundType
)
from utils.embeds import EmbedBuilder


class HostControlView(discord.ui.View):
    """View for host controls to start rounds."""

    def __init__(self, cog, round_type: RoundType, queue_users: list):
        super().__init__(timeout=None)
        self.cog = cog
        self.round_type = round_type
        self.queue_users = queue_users

        # Add buttons based on round type
        if round_type == RoundType.DOUBLE_IRON:
            self.add_item(StartRoundButton(
                label="Start Double Iron Round (2v2)",
                style=discord.ButtonStyle.primary,
                round_type=round_type,
                cog=cog,
                queue_users=queue_users
            ))
        elif round_type == RoundType.SINGLE_IRON:
            self.add_item(StartRoundButton(
                label="Start Single Iron Round",
                style=discord.ButtonStyle.primary,
                round_type=round_type,
                cog=cog,
                queue_users=queue_users
            ))
        elif round_type == RoundType.STANDARD:
            self.add_item(StartRoundButton(
                label="Start Standard Round (3v3)",
                style=discord.ButtonStyle.success,
                round_type=round_type,
                cog=cog,
                queue_users=queue_users
            ))
            self.add_item(WaitForPanelistsButton(cog=cog))


class StartRoundButton(discord.ui.Button):
    """Button to start a debate round."""

    def __init__(self, label: str, style: discord.ButtonStyle, round_type: RoundType, cog, queue_users: list):
        super().__init__(label=label, style=style)
        self.round_type = round_type
        self.cog = cog
        self.queue_users = queue_users

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()

        # Create the round allocation
        debate_round = self.cog.create_round_allocation(self.queue_users, self.round_type)

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
        print("Matchmaking cog loaded")
        # Initialize lobby display
        await self.initialize_lobby()

    async def initialize_lobby(self):
        """Initialize or update the lobby display."""
        try:
            lobby_channel = self.bot.get_channel(Config.LOBBY_CHANNEL_ID)
            if not lobby_channel:
                print(f"Warning: Lobby channel {Config.LOBBY_CHANNEL_ID} not found")
                return

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

        except Exception as e:
            print(f"Error initializing lobby: {e}")

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

            embed = EmbedBuilder.create_host_notification_embed(self.queue.size(), round_type)
            view = HostControlView(self, round_type, list(self.queue.users))

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

    def create_round_allocation(self, users: list, round_type: RoundType) -> DebateRound:
        """Create a debate round allocation from queued users."""
        self.round_counter += 1

        # Shuffle users for random allocation
        shuffled_users = users.copy()
        random.shuffle(shuffled_users)

        # Initialize teams and judges
        if round_type == RoundType.DOUBLE_IRON:
            # 5 people: 2v2 + 1 judge
            gov_team = DebateTeam("Government", TeamType.IRON)
            opp_team = DebateTeam("Opposition", TeamType.IRON)
            judge_panel = JudgePanel()

            gov_team.members = shuffled_users[0:2]
            opp_team.members = shuffled_users[2:4]
            judge_panel.chair = shuffled_users[4]

        elif round_type == RoundType.SINGLE_IRON:
            # 6 people: One full team (3), one iron team (2), 1 judge
            # Randomly decide which team is iron
            gov_is_iron = random.choice([True, False])

            gov_team = DebateTeam("Government", TeamType.IRON if gov_is_iron else TeamType.FULL)
            opp_team = DebateTeam("Opposition", TeamType.FULL if gov_is_iron else TeamType.IRON)
            judge_panel = JudgePanel()

            if gov_is_iron:
                gov_team.members = shuffled_users[0:2]
                opp_team.members = shuffled_users[2:5]
            else:
                gov_team.members = shuffled_users[0:3]
                opp_team.members = shuffled_users[3:5]

            judge_panel.chair = shuffled_users[5]

        else:  # STANDARD
            # 7+ people: 3v3 + judges
            gov_team = DebateTeam("Government", TeamType.FULL)
            opp_team = DebateTeam("Opposition", TeamType.FULL)
            judge_panel = JudgePanel()

            gov_team.members = shuffled_users[0:3]
            opp_team.members = shuffled_users[3:6]

            # Remaining users are judges
            for judge in shuffled_users[6:]:
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
        description="Join the matchmaking queue for a debate round"
    )
    async def queue_command(self, ctx: discord.ApplicationContext):
        """Join the matchmaking queue."""
        if self.queue.add_user(ctx.author):
            await ctx.respond(
                embed=EmbedBuilder.create_success_embed(
                    "Joined Queue",
                    f"You have been added to the queue. Position: {self.queue.size()}"
                ),
                ephemeral=True
            )
            await self.update_lobby_display()
            await self.check_matchmaking_threshold()
        else:
            await ctx.respond(
                embed=EmbedBuilder.create_error_embed(
                    "Already in Queue",
                    "You are already in the matchmaking queue."
                ),
                ephemeral=True
            )

    @discord.slash_command(
        name="leave",
        description="Leave the matchmaking queue"
    )
    async def leave_command(self, ctx: discord.ApplicationContext):
        """Leave the matchmaking queue."""
        if self.queue.remove_user(ctx.author):
            await ctx.respond(
                embed=EmbedBuilder.create_success_embed(
                    "Left Queue",
                    "You have been removed from the queue."
                ),
                ephemeral=True
            )
            await self.update_lobby_display()
            await self.check_matchmaking_threshold()
        else:
            await ctx.respond(
                embed=EmbedBuilder.create_error_embed(
                    "Not in Queue",
                    "You are not in the matchmaking queue."
                ),
                ephemeral=True
            )

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
            ephemeral=True
        )


def setup(bot):
    bot.add_cog(Matchmaking(bot))
