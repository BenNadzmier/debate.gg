import discord
from discord.ext import commands
import random
from typing import Optional
import logging

from config import Config

logger = logging.getLogger('DebateBot.Matchmaking')
from utils.models import (
    MatchmakingQueue, DebateRound, DebateTeam, JudgePanel,
    TeamType, RoundType, LobbyManager
)
from utils.embeds import EmbedBuilder


class LobbyView(discord.ui.View):
    """Persistent view for a lobby with a leave button."""

    def __init__(self, cog, lobby_name: str):
        super().__init__(timeout=None)
        self.cog = cog
        self.lobby_name = lobby_name

    @discord.ui.button(label="Leave Queue", style=discord.ButtonStyle.danger, custom_id="leave_queue")
    async def leave_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Handle leave queue button press."""
        lobby = self.cog.lobby_manager.get_lobby(self.lobby_name)
        if lobby and lobby.remove_user(interaction.user):
            await interaction.response.send_message(
                f"✅ You have left **{lobby.name}**.", ephemeral=True
            )
            await self.cog.update_lobby_display(lobby)
        else:
            await interaction.response.send_message("❌ You are not in this queue.", ephemeral=True)


class Matchmaking(commands.Cog):
    """Cog handling matchmaking queues and round initialization."""

    def __init__(self, bot):
        self.bot = bot
        self.lobby_manager = LobbyManager()
        self.current_round: Optional[DebateRound] = None
        self.round_counter = 0

    async def cog_load(self):
        """Called when the cog is loaded."""
        logger.info("Matchmaking cog loaded")
        logger.info("Registering slash commands: /createqueue, /cq, /join, /leave, /lobby, /lobbies, /start, /end, /clearqueue")

    async def update_lobby_display(self, lobby: MatchmakingQueue):
        """Update the lobby embed with current queue status."""
        if not lobby.lobby_message:
            return

        try:
            embed = EmbedBuilder.create_lobby_embed(lobby)
            view = LobbyView(self, lobby.name)
            await lobby.lobby_message.edit(embed=embed, view=view)
        except discord.NotFound:
            lobby.lobby_message = None
        except Exception as e:
            logger.error(f"Error updating lobby display for {lobby.name}: {e}")

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
        if round_type == RoundType.PM_LO:
            gov_team = DebateTeam("Government", TeamType.SOLO)
            opp_team = DebateTeam("Opposition", TeamType.SOLO)
            gov_team.members = shuffled_debaters[0:1]
            opp_team.members = shuffled_debaters[1:2]
            for judge in shuffled_judges:
                judge_panel.add_judge(judge)

        elif round_type == RoundType.DOUBLE_IRON:
            gov_team = DebateTeam("Government", TeamType.IRON)
            opp_team = DebateTeam("Opposition", TeamType.IRON)
            gov_team.members = shuffled_debaters[0:2]
            opp_team.members = shuffled_debaters[2:4]
            for judge in shuffled_judges:
                judge_panel.add_judge(judge)

        elif round_type == RoundType.SINGLE_IRON:
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

    # ── /createqueue (alias /cq) ─────────────────────────────────────

    @discord.slash_command(
        name="createqueue",
        description="Create a new matchmaking lobby (Host only)",
        default_member_permissions=None
    )
    async def createqueue_command(
        self,
        ctx: discord.ApplicationContext,
        name: str = discord.Option(description="Name for the lobby", required=True)
    ):
        """Create a new named lobby."""
        await self._do_createqueue(ctx, name)

    @discord.slash_command(
        name="cq",
        description="Create a new matchmaking lobby — shorthand for /createqueue (Host only)",
        default_member_permissions=None
    )
    async def cq_command(
        self,
        ctx: discord.ApplicationContext,
        name: str = discord.Option(description="Name for the lobby", required=True)
    ):
        """Shorthand alias for /createqueue."""
        await self._do_createqueue(ctx, name)

    async def _do_createqueue(self, ctx: discord.ApplicationContext, name: str):
        """Shared implementation for /createqueue and /cq."""
        logger.info(f"User {ctx.author} ({ctx.author.id}) used /createqueue with name={name}")

        # Check if user is host
        is_host = False
        if Config.HOST_ROLE_ID:
            is_host = any(role.id == Config.HOST_ROLE_ID for role in ctx.author.roles)
        if not is_host:
            await ctx.respond(
                embed=EmbedBuilder.create_error_embed(
                    "Permission Denied",
                    "Only the host can create a lobby."
                ),
                ephemeral=False
            )
            return

        # Try to create lobby
        lobby = self.lobby_manager.create_lobby(name, ctx.author)
        if lobby is None:
            await ctx.respond(
                embed=EmbedBuilder.create_error_embed(
                    "Lobby Already Exists",
                    f"A lobby named **{name}** already exists. Choose a different name."
                ),
                ephemeral=False
            )
            return

        # Post lobby embed in the current channel
        embed = EmbedBuilder.create_lobby_embed(lobby)
        view = LobbyView(self, lobby.name)
        lobby.lobby_message = await ctx.channel.send(embed=embed, view=view)

        await ctx.respond(
            embed=EmbedBuilder.create_success_embed(
                "Lobby Created",
                f"**{ctx.author.display_name}** started a queue: **{name}**\n"
                f"Use `/join {name} <debater|judge>` to participate!"
            ),
            ephemeral=False
        )

    # ── /join ────────────────────────────────────────────────────────

    @discord.slash_command(
        name="join",
        description="Join a matchmaking lobby as a debater or judge",
        default_member_permissions=None
    )
    async def join_command(
        self,
        ctx: discord.ApplicationContext,
        name: str = discord.Option(description="Name of the lobby to join", required=True),
        role: str = discord.Option(
            description="Join as a debater or judge",
            choices=["debater", "judge"],
            required=True
        )
    ):
        """Join a lobby as debater or judge."""
        logger.info(f"User {ctx.author} ({ctx.author.id}) used /join {name} as {role}")

        lobby = self.lobby_manager.get_lobby(name)
        if lobby is None:
            await ctx.respond(
                embed=EmbedBuilder.create_error_embed(
                    "Lobby Not Found",
                    f"No lobby named **{name}** exists. Use `/lobbies` to see available lobbies."
                ),
                ephemeral=False
            )
            return

        if role == "debater":
            success = lobby.add_debater(ctx.author)
            role_text = "debater"
        else:
            success = lobby.add_judge(ctx.author)
            role_text = "judge"

        if success:
            await ctx.respond(
                embed=EmbedBuilder.create_success_embed(
                    f"Joined {lobby.name} as {role_text.title()}",
                    f"You have been added to **{lobby.name}** as a {role_text}.\n"
                    f"**Debaters:** {lobby.debater_count()} | **Judges:** {lobby.judge_count()}"
                ),
                ephemeral=False
            )
            await self.update_lobby_display(lobby)
        else:
            current_role = lobby.get_user_role(ctx.author)
            await ctx.respond(
                embed=EmbedBuilder.create_success_embed(
                    f"Switched to {role_text.title()}",
                    f"You have been moved to {role_text} in **{lobby.name}**.\n"
                    f"**Debaters:** {lobby.debater_count()} | **Judges:** {lobby.judge_count()}"
                ),
                ephemeral=False
            )
            await self.update_lobby_display(lobby)

    # ── /leave ───────────────────────────────────────────────────────

    @discord.slash_command(
        name="leave",
        description="Leave a matchmaking lobby",
        default_member_permissions=None
    )
    async def leave_command(
        self,
        ctx: discord.ApplicationContext,
        name: str = discord.Option(description="Name of the lobby to leave", required=True)
    ):
        """Leave a specific lobby."""
        logger.info(f"User {ctx.author} ({ctx.author.id}) used /leave {name}")

        lobby = self.lobby_manager.get_lobby(name)
        if lobby is None:
            await ctx.respond(
                embed=EmbedBuilder.create_error_embed(
                    "Lobby Not Found",
                    f"No lobby named **{name}** exists."
                ),
                ephemeral=False
            )
            return

        if lobby.remove_user(ctx.author):
            await ctx.respond(
                embed=EmbedBuilder.create_success_embed(
                    "Left Lobby",
                    f"You have been removed from **{lobby.name}**."
                ),
                ephemeral=False
            )
            await self.update_lobby_display(lobby)
        else:
            await ctx.respond(
                embed=EmbedBuilder.create_error_embed(
                    "Not in Lobby",
                    f"You are not in **{lobby.name}**."
                ),
                ephemeral=False
            )

    # ── /lobby ───────────────────────────────────────────────────────

    @discord.slash_command(
        name="lobby",
        description="Show info for a specific lobby",
        default_member_permissions=None
    )
    async def lobby_command(
        self,
        ctx: discord.ApplicationContext,
        name: str = discord.Option(description="Name of the lobby to view", required=True)
    ):
        """Show the lobby infobox for a specific lobby."""
        logger.info(f"User {ctx.author} ({ctx.author.id}) used /lobby {name}")

        lobby = self.lobby_manager.get_lobby(name)
        if lobby is None:
            await ctx.respond(
                embed=EmbedBuilder.create_error_embed(
                    "Lobby Not Found",
                    f"No lobby named **{name}** exists."
                ),
                ephemeral=False
            )
            return

        embed = EmbedBuilder.create_lobby_embed(lobby)
        await ctx.respond(embed=embed, ephemeral=False)

    # ── /lobbies ─────────────────────────────────────────────────────

    @discord.slash_command(
        name="lobbies",
        description="List all lobbies you are currently part of",
        default_member_permissions=None
    )
    async def lobbies_command(self, ctx: discord.ApplicationContext):
        """List all lobbies the user is in."""
        logger.info(f"User {ctx.author} ({ctx.author.id}) used /lobbies")

        user_lobbies = self.lobby_manager.get_user_lobbies(ctx.author)
        embed = EmbedBuilder.create_lobbies_list_embed(user_lobbies, ctx.author)
        await ctx.respond(embed=embed, ephemeral=False)

    # ── /start ───────────────────────────────────────────────────────

    @discord.slash_command(
        name="start",
        description="Start a debate round from a lobby (Host only)",
        default_member_permissions=None
    )
    async def start_command(
        self,
        ctx: discord.ApplicationContext,
        name: str = discord.Option(description="Name of the lobby to start", required=True)
    ):
        """Start a debate round from a specific lobby."""
        logger.info(f"User {ctx.author} ({ctx.author.id}) used /start {name}")

        # Check if user is host
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

        lobby = self.lobby_manager.get_lobby(name)
        if lobby is None:
            await ctx.respond(
                embed=EmbedBuilder.create_error_embed(
                    "Lobby Not Found",
                    f"No lobby named **{name}** exists."
                ),
                ephemeral=False
            )
            return

        # Verify this user is the lobby's host
        if lobby.host != ctx.author:
            await ctx.respond(
                embed=EmbedBuilder.create_error_embed(
                    "Permission Denied",
                    f"Only the host of **{lobby.name}** can start this round."
                ),
                ephemeral=False
            )
            return

        # Check minimum requirements: 2 debaters + 1 judge (PM-LO)
        debaters = lobby.debater_count()
        judges = lobby.judge_count()

        if debaters < 2 or judges < 1:
            needed = []
            if debaters < 2:
                needed.append(f"**{2 - debaters}** more debater(s)")
            if judges < 1:
                needed.append(f"**1** judge")
            await ctx.respond(
                embed=EmbedBuilder.create_error_embed(
                    "Not Enough Players",
                    f"Cannot start **{lobby.name}**. Need at least **2 debaters** and **1 judge**.\n"
                    f"Currently: **{debaters}** debater(s), **{judges}** judge(s).\n"
                    f"Still need: {', '.join(needed)}."
                ),
                ephemeral=False
            )
            return

        round_type = lobby.get_threshold_type()
        if round_type is None:
            await ctx.respond(
                embed=EmbedBuilder.create_error_embed(
                    "Cannot Start",
                    "The current queue composition doesn't match any round type."
                ),
                ephemeral=False
            )
            return

        await ctx.respond(
            embed=EmbedBuilder.create_success_embed(
                "Starting Round",
                f"Creating a **{round_type.value.replace('_', ' ').title()}** round from **{lobby.name}** with "
                f"**{debaters}** debaters and **{judges}** judge(s)..."
            ),
            ephemeral=False
        )

        debate_round = self.create_round_allocation(
            list(lobby.debaters),
            list(lobby.judges),
            round_type
        )
        self.current_round = debate_round

        # Clean up the lobby
        if lobby.lobby_message:
            try:
                await lobby.lobby_message.delete()
            except:
                pass
        self.lobby_manager.remove_lobby(name)

        await self.show_allocation_interface(ctx.channel, debate_round)

    # ── /end ─────────────────────────────────────────────────────────

    @discord.slash_command(
        name="end",
        description="Disband a lobby (Host only)",
        default_member_permissions=None
    )
    async def end_command(
        self,
        ctx: discord.ApplicationContext,
        name: str = discord.Option(description="Name of the lobby to disband", required=True)
    ):
        """Disband a lobby. Only the lobby's host can do this."""
        logger.info(f"User {ctx.author} ({ctx.author.id}) used /end {name}")

        lobby = self.lobby_manager.get_lobby(name)
        if lobby is None:
            await ctx.respond(
                embed=EmbedBuilder.create_error_embed(
                    "Lobby Not Found",
                    f"No lobby named **{name}** exists."
                ),
                ephemeral=False
            )
            return

        # Check if user is the lobby host
        if lobby.host != ctx.author:
            await ctx.respond(
                embed=EmbedBuilder.create_error_embed(
                    "Permission Denied",
                    f"Only the host of **{lobby.name}** can disband it."
                ),
                ephemeral=False
            )
            return

        # Delete lobby message if it exists
        if lobby.lobby_message:
            try:
                await lobby.lobby_message.delete()
            except:
                pass

        self.lobby_manager.remove_lobby(name)

        await ctx.respond(
            embed=EmbedBuilder.create_success_embed(
                "Lobby Disbanded",
                f"**{name}** has been disbanded by {ctx.author.display_name}."
            ),
            ephemeral=False
        )

    # ── /clearqueue (admin) ──────────────────────────────────────────

    @discord.slash_command(
        name="clearqueue",
        description="Clear a specific lobby's queue (Admin only)"
    )
    @commands.has_permissions(administrator=True)
    async def clear_queue_command(
        self,
        ctx: discord.ApplicationContext,
        name: str = discord.Option(description="Name of the lobby to clear", required=True)
    ):
        """Clear a specific lobby's queue."""
        lobby = self.lobby_manager.get_lobby(name)
        if lobby is None:
            await ctx.respond(
                embed=EmbedBuilder.create_error_embed(
                    "Lobby Not Found",
                    f"No lobby named **{name}** exists."
                ),
                ephemeral=False
            )
            return

        lobby.clear()
        await self.update_lobby_display(lobby)
        await ctx.respond(
            embed=EmbedBuilder.create_success_embed(
                "Queue Cleared",
                f"The queue for **{lobby.name}** has been cleared."
            ),
            ephemeral=False
        )

    # ── /about ───────────────────────────────────────────────────────

    @discord.slash_command(
        name="about",
        description="Learn about the AP Matchmaking Bot and its commands",
        default_member_permissions=None
    )
    async def about_command(self, ctx: discord.ApplicationContext):
        """Show bot info, commands, and round mechanics."""
        logger.info(f"User {ctx.author} ({ctx.author.id}) used /about")

        embed = discord.Embed(
            title="AP Matchmaking Bot",
            description="Automated matchmaking for AP-style parliamentary debate rounds.",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="📋 Commands",
            value=(
                "**/createqueue <name>** (or **/cq**) — Create a new lobby *(Host)*\n"
                "**/join <name> <role>** — Join a lobby as **debater** or **judge**\n"
                "**/leave <name>** — Leave a lobby\n"
                "**/lobby <name>** — View a lobby's status\n"
                "**/lobbies** — List all lobbies you're in\n"
                "**/start <name>** — Start a round from a lobby *(Host)*\n"
                "**/end <name>** — Disband a lobby *(Host)*\n"
                "**/clearqueue <name>** — Clear a lobby's queue *(Admin)*\n"
                "**/about** — This message"
            ),
            inline=False
        )

        embed.add_field(
            name="⚙️ How Rounds Work",
            value=(
                "A host creates a lobby with **/createqueue**, then players "
                "**/join** as debaters or judges. When the host runs **/start**, "
                "the bot checks whether there are enough players and determines "
                "the round format automatically:\n\n"
                "• **PM-LO Speech (1v1)** — 2 debaters + 1 judge (minimum to start)\n"
                "• **Double Iron (2v2)** — 4 debaters + 1 judge\n"
                "• **Single Iron (3v2 or 2v3)** — 5 debaters + 1 judge\n"
                "• **Standard (3v3)** — 6+ debaters + 1+ judges\n\n"
                "Debaters are randomly shuffled into Government and Opposition "
                "teams and assigned speaking positions (PM, DPM, GW / LO, DLO, OW). "
                "Extra participants beyond what the round needs are placed as judges."
            ),
            inline=False
        )

        embed.add_field(
            name="🔧 After Allocation",
            value=(
                "The host receives an interactive panel to adjust the allocation — "
                "swap members between teams, toggle team sizes "
                "(Full ↔ Iron ↔ Solo), or move players between debater and judge "
                "roles — before confirming the final round."
            ),
            inline=False
        )

        embed.set_footer(text="AP Matchmaking Bot • debate.gg")
        await ctx.respond(embed=embed, ephemeral=False)


def setup(bot):
    bot.add_cog(Matchmaking(bot))
