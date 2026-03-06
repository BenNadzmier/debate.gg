import asyncio
import discord
from discord.ext import commands
import random
from typing import Optional
import logging

from config import Config

logger = logging.getLogger('DebateBot.Matchmaking')
from utils.models import (
    MatchmakingQueue, DebateRound, DebateTeam, JudgePanel,
    TeamType, RoundType, FormatType, Party
)
from utils.embeds import EmbedBuilder


class PartyInviteView(discord.ui.View):
    """View sent in DMs for accepting/declining party invites."""

    def __init__(self, cog, host: discord.Member, invited_user: discord.Member):
        super().__init__(timeout=300)  # 5 min timeout
        self.cog = cog
        self.host = host
        self.invited_user = invited_user

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except:
                pass

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Accept the party invitation."""
        # Check if user is already in a party
        if self.invited_user.id in self.cog.member_to_party:
            await interaction.response.edit_message(
                content="You're already in a party. Use `/leaveparty` first.",
                embed=None, view=None
            )
            return

        # Check if host's party still exists
        party = self.cog.parties.get(self.host.id)
        if not party:
            await interaction.response.edit_message(
                content="This party no longer exists.",
                embed=None, view=None
            )
            return

        # Check if party is full
        if not party.add_member(self.invited_user):
            await interaction.response.edit_message(
                content="The party is already full (3/3).",
                embed=None, view=None
            )
            return

        # Track membership
        self.cog.member_to_party[self.invited_user.id] = self.host.id

        # Disable buttons
        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(
            content=f"You've joined **{self.host.display_name}**'s party!",
            embed=None, view=self
        )
        try:
            await self.host.send(
                embed=EmbedBuilder.create_success_embed(
                    "Invite Accepted",
                    f"**{self.invited_user.display_name}** has accepted your party invite!"
                )
            )
        except discord.Forbidden:
            pass

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger)
    async def decline_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Decline the party invitation."""
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(
            content="You declined the party invitation.",
            embed=None, view=self
        )


class ObserveRequestView(discord.ui.View):
    """View sent in DMs to ask a participant if they accept an observation request."""

    def __init__(self, cog, observer: discord.Member, target: discord.Member):
        super().__init__(timeout=300)
        self.cog = cog          # Matchmaking cog
        self.observer = observer
        self.target = target
        self.message = None

    async def on_timeout(self):
        if self.message:
            for item in self.children:
                item.disabled = True
            try:
                await self.message.edit(view=self)
            except discord.NotFound:
                pass
        try:
            await self.observer.send(embed=EmbedBuilder.create_error_embed(
                "Observation Request Expired",
                f"**{self.target.display_name}** did not respond to your observation request."
            ))
        except discord.Forbidden:
            pass

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer()
        for item in self.children:
            item.disabled = True
        await interaction.edit_original_response(
            embed=EmbedBuilder.create_success_embed(
                "Request Accepted",
                f"You have accepted **{self.observer.display_name}**'s request to observe your round."
            ),
            view=self
        )

        rounds_cog = self.cog.bot.get_cog("Rounds")
        guild = self.cog.bot.get_guild(Config.GUILD_ID)
        target_round = self.cog._find_member_active_round(self.target)

        if target_round:
            await rounds_cog.add_observer_to_round(target_round, self.observer, guild)
            try:
                await self.observer.send(embed=EmbedBuilder.create_success_embed(
                    "Observation Request Accepted",
                    f"**{self.target.display_name}** accepted! You now have access to Round {target_round.round_id}."
                ))
            except discord.Forbidden:
                pass
        elif self.cog._is_member_in_queue(self.target):
            self.cog.pending_observers.setdefault(self.target.id, []).append(self.observer)
            try:
                await self.observer.send(embed=EmbedBuilder.create_success_embed(
                    "Observation Request Accepted",
                    f"**{self.target.display_name}** accepted! You'll be granted access when their round starts."
                ))
            except discord.Forbidden:
                pass
        else:
            try:
                await self.observer.send(embed=EmbedBuilder.create_error_embed(
                    "Observation Request Accepted (Too Late)",
                    f"**{self.target.display_name}** accepted, but they are no longer in a round or queue."
                ))
            except discord.Forbidden:
                pass
        self.stop()

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger)
    async def decline_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer()
        for item in self.children:
            item.disabled = True
        await interaction.edit_original_response(
            embed=EmbedBuilder.create_error_embed(
                "Request Declined",
                f"You declined **{self.observer.display_name}**'s request to observe your round."
            ),
            view=self
        )
        try:
            await self.observer.send(embed=EmbedBuilder.create_error_embed(
                "Observation Request Declined",
                f"**{self.target.display_name}** declined your request to observe their round."
            ))
        except discord.Forbidden:
            pass
        self.stop()


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
        self.cog._cancel_queue_timeout(interaction.user.id)

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
        # Party system
        self.parties: dict[int, Party] = {}        # host_id -> Party
        self.member_to_party: dict[int, int] = {}  # member_id -> host_id
        # Observer system
        self.pending_observers: dict[int, list] = {}  # observed_user_id → [observer Members]
        # Queue timeouts
        self.queue_timeouts: dict[int, asyncio.Task] = {}  # user_id → running timeout task

    def _get_queue(self, format_name: str) -> MatchmakingQueue:
        """Get the queue for a given format."""
        return self.queue_1v1 if format_name == "1v1" else self.queue_ap

    def _get_max_party_size(self, queue: MatchmakingQueue) -> int:
        """Get the size of the largest party among queued debaters."""
        max_size = 1
        for debater in queue.debaters:
            host_id = self.member_to_party.get(debater.id)
            if host_id and host_id in self.parties:
                max_size = max(max_size, self.parties[host_id].size)
        return max_size

    def _disband_party(self, host_id: int):
        """Disband a party and clean up all references."""
        party = self.parties.pop(host_id, None)
        if party:
            for member in party.members:
                self.member_to_party.pop(member.id, None)

    def add_active_round(self, debate_round: DebateRound):
        """Track an active round."""
        self.active_rounds[debate_round.round_id] = debate_round

    def remove_active_round(self, round_id: int):
        """Remove a completed round."""
        self.active_rounds.pop(round_id, None)

    def _is_member_in_queue(self, member: discord.Member) -> bool:
        """Check if a member is in any queue."""
        return (member in self.queue_1v1.debaters or
                member in self.queue_1v1.judges or
                member in self.queue_ap.debaters or
                member in self.queue_ap.judges)

    def _find_member_active_round(self, member: discord.Member):
        """Return the active DebateRound the member is in, or None."""
        for debate_round in self.active_rounds.values():
            if member in debate_round.get_all_participants():
                return debate_round
        return None

    def _start_queue_timeout(self, member: discord.Member):
        """Start (or restart) a 15-minute queue timeout task for a member."""
        self._cancel_queue_timeout(member.id)
        task = self.bot.loop.create_task(self._queue_timeout_task(member))
        self.queue_timeouts[member.id] = task

    def _cancel_queue_timeout(self, member_id: int):
        """Cancel a member's queue timeout task if one is running."""
        task = self.queue_timeouts.pop(member_id, None)
        if task:
            task.cancel()

    async def _queue_timeout_task(self, member: discord.Member):
        """Background task: removes a user from the queue after 15 minutes of inactivity."""
        await asyncio.sleep(900)  # 15 minutes

        # Guard against race condition where task was cancelled but not yet GC'd
        if not (self.queue_1v1.is_in_queue(member) or self.queue_ap.is_in_queue(member)):
            return

        self.queue_1v1.remove_user(member)
        self.queue_ap.remove_user(member)
        self.queue_timeouts.pop(member.id, None)

        # Party handling
        party_host_id = self.member_to_party.get(member.id)
        if party_host_id and party_host_id == member.id:
            # User is the party host — remove all other party members too
            party = self.parties.get(party_host_id)
            if party:
                for m in list(party.members):
                    if m.id != member.id:
                        self.queue_1v1.remove_user(m)
                        self.queue_ap.remove_user(m)
                        self._cancel_queue_timeout(m.id)
                        try:
                            await m.send(embed=EmbedBuilder.create_error_embed(
                                "Removed from Queue",
                                f"Your party host **{member.display_name}**'s queue timed out after 15 minutes. "
                                "Use `/queue` again when you're ready."
                            ))
                        except discord.Forbidden:
                            pass
        elif party_host_id:
            # User is a non-host party member — remove from party too
            party = self.parties.get(party_host_id)
            if party:
                party.remove_member(member)
            self.member_to_party.pop(member.id, None)

        try:
            await member.send(embed=EmbedBuilder.create_error_embed(
                "Queue Timed Out",
                "You have been in the queue for 15 minutes without finding a match. "
                "Use `/queue` again when you're ready to play."
            ))
        except discord.Forbidden:
            pass

        await self.update_lobby_display()
        await self.check_matchmaking_threshold()

    def requeue_participants(self, debate_round: DebateRound, excluded_member=None):
        """Return all participants to their original queue, skipping the decliner if any."""
        if not debate_round.format_label:
            return
        queue = self._get_queue(debate_round.format_label)
        roles = debate_round.get_original_queue_roles()
        for member, role in roles.items():
            if excluded_member and member.id == excluded_member.id:
                continue
            if role == "debater":
                queue.add_debater(member)
            else:
                queue.add_judge(member)
            self._start_queue_timeout(member)

    async def cog_load(self):
        """Called when the cog is loaded."""
        logger.info("Matchmaking cog loaded")
        logger.info("Registering slash commands: /queue, /leave, /clearqueue, /guide, /invite, /party, /leaveparty")
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
            max_party_size = self._get_max_party_size(queue) if format_label == "AP" else 1
            round_type = queue.get_threshold_type(max_party_size)
            if round_type:
                # Auto-create round with random allocation
                debaters = list(queue.debaters)
                judges = list(queue.judges)
                debate_round = self.create_round_allocation(debaters, judges, round_type)
                self.current_round = debate_round
                debate_round.format_label = format_label
                # Cancel timeouts before clearing so they don't fire during confirmation
                for member in list(queue.debaters) + list(queue.judges):
                    self._cancel_queue_timeout(member.id)
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

    def _build_allocation_units(self, debaters: list) -> list:
        """Group debaters into allocation units. Party members stay together."""
        units = []
        assigned = set()

        for debater in debaters:
            if debater.id in assigned:
                continue
            host_id = self.member_to_party.get(debater.id)
            if host_id and host_id in self.parties:
                party = self.parties[host_id]
                party_unit = [m for m in party.members if m in debaters and m.id not in assigned]
                for m in party_unit:
                    assigned.add(m.id)
                if party_unit:
                    units.append(party_unit)
            else:
                assigned.add(debater.id)
                units.append([debater])
        return units

    def create_round_allocation(self, debaters: list, judges: list, round_type: RoundType) -> DebateRound:
        """Create a debate round allocation from queued debaters and judges."""
        self.round_counter += 1

        # Shuffle judges for random chair assignment
        shuffled_judges = judges.copy()
        random.shuffle(shuffled_judges)

        # Initialize judge panel
        judge_panel = JudgePanel()
        for judge in shuffled_judges:
            judge_panel.add_judge(judge)

        if round_type == RoundType.PM_LO:
            # 1v1: no parties, simple shuffle
            shuffled_debaters = debaters.copy()
            random.shuffle(shuffled_debaters)

            gov_team = DebateTeam("Government", TeamType.SOLO)
            opp_team = DebateTeam("Opposition", TeamType.SOLO)
            gov_team.members = [shuffled_debaters[0]]
            opp_team.members = [shuffled_debaters[1]]

        elif round_type == RoundType.DOUBLE_IRON:
            # 2v2: party-aware allocation
            units = self._build_allocation_units(debaters)
            random.shuffle(units)

            gov_members, opp_members = [], []
            for unit in units:
                if len(gov_members) + len(unit) <= 2:
                    gov_members.extend(unit)
                elif len(opp_members) + len(unit) <= 2:
                    opp_members.extend(unit)

            gov_team = DebateTeam("Government", TeamType.IRON)
            opp_team = DebateTeam("Opposition", TeamType.IRON)
            gov_team.members = gov_members
            opp_team.members = opp_members

        elif round_type == RoundType.SINGLE_IRON:
            # 3v2 or 2v3: party-aware allocation
            gov_is_iron = random.choice([True, False])
            gov_size = 2 if gov_is_iron else 3
            opp_size = 3 if gov_is_iron else 2

            units = self._build_allocation_units(debaters)
            random.shuffle(units)

            gov_members, opp_members = [], []
            for unit in units:
                if len(gov_members) + len(unit) <= gov_size:
                    gov_members.extend(unit)
                elif len(opp_members) + len(unit) <= opp_size:
                    opp_members.extend(unit)

            gov_team = DebateTeam("Government", TeamType.IRON if gov_is_iron else TeamType.FULL)
            opp_team = DebateTeam("Opposition", TeamType.FULL if gov_is_iron else TeamType.IRON)
            gov_team.members = gov_members
            opp_team.members = opp_members

        else:  # STANDARD (3v3)
            units = self._build_allocation_units(debaters)
            random.shuffle(units)

            gov_members, opp_members = [], []
            for unit in units:
                if len(gov_members) + len(unit) <= 3:
                    gov_members.extend(unit)
                elif len(opp_members) + len(unit) <= 3:
                    opp_members.extend(unit)

            gov_team = DebateTeam("Government", TeamType.FULL)
            opp_team = DebateTeam("Opposition", TeamType.FULL)
            gov_team.members = gov_members
            opp_team.members = opp_members

        return DebateRound(
            round_id=self.round_counter,
            round_type=round_type,
            government=gov_team,
            opposition=opp_team,
            judges=judge_panel
        )

    # ─── Slash Commands ────────────────────────────────────────────

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

        # Party checks
        party_host_id = self.member_to_party.get(ctx.author.id)
        if party_host_id:
            party = self.parties.get(party_host_id)
            if party:
                # Non-host party members can't queue individually
                if ctx.author.id != party_host_id:
                    await ctx.respond(
                        embed=EmbedBuilder.create_error_embed(
                            "In a Party",
                            "You're in a party. Ask your party host to queue, or use `/leaveparty` first."
                        )
                    )
                    return

                # Party host: enforce AP debater only
                if debate_format == "1v1":
                    await ctx.respond(
                        embed=EmbedBuilder.create_error_embed(
                            "Party Not Supported",
                            "Parties are only supported in AP format. Use `/leaveparty` to disband first."
                        )
                    )
                    return

                if role == "judge":
                    await ctx.respond(
                        embed=EmbedBuilder.create_error_embed(
                            "Party Host",
                            "As a party host, you can only queue as a debater. Use `/leaveparty` to disband first."
                        )
                    )
                    return

                # Queue all party members as debaters in AP
                queue = self.queue_ap
                other_queue = self.queue_1v1

                for member in party.members:
                    other_queue.remove_user(member)
                    queue.add_debater(member)
                    self._start_queue_timeout(member)

                await ctx.respond(
                    embed=EmbedBuilder.create_success_embed(
                        f"Party Joined AP Queue",
                        f"You and your party ({party.size} members) have joined the AP debater queue.\n"
                        f"**Debaters:** {queue.debater_count()} | **Judges:** {queue.judge_count()}"
                    ),
                    ephemeral=True
                )
                for member in party.members:
                    if member.id != ctx.author.id:
                        try:
                            await member.send(
                                embed=EmbedBuilder.create_success_embed(
                                    "Added to Queue",
                                    f"Your party host **{ctx.author.display_name}** has queued your party for AP.\n"
                                    f"You'll be matched when there are enough players."
                                )
                            )
                        except discord.Forbidden:
                            pass
                await self.update_lobby_display()
                await self.check_matchmaking_threshold()
                return

        # Standard (non-party) queue flow
        queue = self._get_queue(debate_format)
        other_queue = self.queue_ap if debate_format == "1v1" else self.queue_1v1

        # Remove from the other format's queue if present
        other_queue.remove_user(ctx.author)

        # Add user to appropriate queue
        if role == "debater":
            success = queue.add_debater(ctx.author)
        else:
            success = queue.add_judge(ctx.author)
        self._start_queue_timeout(ctx.author)

        format_display = "1v1" if debate_format == "1v1" else "AP"

        if success:
            await ctx.respond(
                embed=EmbedBuilder.create_success_embed(
                    f"Joined {format_display} Queue as {role.title()}",
                    f"You have been added to the {format_display} {role} queue.\n"
                    f"**Debaters:** {queue.debater_count()} | **Judges:** {queue.judge_count()}"
                ),
                ephemeral=True
            )
        else:
            await ctx.respond(
                embed=EmbedBuilder.create_success_embed(
                    f"Switched to {role.title()} in {format_display}",
                    f"You have been moved to {role} in the {format_display} queue.\n"
                    f"**Debaters:** {queue.debater_count()} | **Judges:** {queue.judge_count()}"
                ),
                ephemeral=True
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

        # If party host, remove all party members from queue
        party_host_id = self.member_to_party.get(ctx.author.id)
        if party_host_id and ctx.author.id == party_host_id:
            party = self.parties.get(party_host_id)
            if party:
                removed = False
                for member in party.members:
                    if self.queue_1v1.remove_user(member):
                        removed = True
                    if self.queue_ap.remove_user(member):
                        removed = True
                    self._cancel_queue_timeout(member.id)
                if removed:
                    await ctx.respond(
                        embed=EmbedBuilder.create_success_embed(
                            "Party Left Queue",
                            "Your party has been removed from the queue."
                        ),
                        ephemeral=True
                    )
                    await self.update_lobby_display()
                    await self.check_matchmaking_threshold()
                else:
                    await ctx.respond(
                        embed=EmbedBuilder.create_error_embed(
                            "Not in Queue",
                            "Your party is not in the matchmaking queue."
                        ),
                        ephemeral=True
                    )
                return

        # If party member (not host), leave queue + leave party
        if party_host_id:
            party = self.parties.get(party_host_id)
            if party:
                party.remove_member(ctx.author)
                self.member_to_party.pop(ctx.author.id, None)

        removed_1v1 = self.queue_1v1.remove_user(ctx.author)
        removed_ap = self.queue_ap.remove_user(ctx.author)
        self._cancel_queue_timeout(ctx.author.id)

        if removed_1v1 or removed_ap:
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
        self.queue_1v1.clear()
        self.queue_ap.clear()
        await self.update_lobby_display()
        await ctx.respond(
            embed=EmbedBuilder.create_success_embed(
                "Queue Cleared",
                "All matchmaking queues have been cleared."
            ),
            ephemeral=True
        )

    @discord.slash_command(
        name="guide",
        description="Learn how the debate bot works",
        default_member_permissions=None
    )
    async def guide_command(self, ctx: discord.ApplicationContext):
        """Show the guide for how the bot works."""
        embed = EmbedBuilder.create_guide_embed()
        await ctx.respond(embed=embed, ephemeral=True)

    # ─── Party Commands ────────────────────────────────────────────

    @discord.slash_command(
        name="invite",
        description="Invite a user to your debate party (AP format)",
        default_member_permissions=None
    )
    @discord.option("user", description="The user to invite to your party", required=True)
    async def invite_command(
        self,
        ctx: discord.ApplicationContext,
        user: discord.Member,
    ):
        """Invite a user to your party."""
        logger.info(f"User {ctx.author} ({ctx.author.id}) used /invite for {user}")

        # Can't invite yourself
        if user.id == ctx.author.id:
            await ctx.respond(
                embed=EmbedBuilder.create_error_embed("Invalid Invite", "You can't invite yourself."),
                ephemeral=True
            )
            return

        # Can't invite bots
        if user.bot:
            await ctx.respond(
                embed=EmbedBuilder.create_error_embed("Invalid Invite", "You can't invite a bot."),
                ephemeral=True
            )
            return

        # Check if inviter is a non-host party member
        existing_host_id = self.member_to_party.get(ctx.author.id)
        if existing_host_id and existing_host_id != ctx.author.id:
            await ctx.respond(
                embed=EmbedBuilder.create_error_embed(
                    "Not Party Host",
                    "Only the party host can invite members. Use `/leaveparty` to leave your current party first."
                ),
                ephemeral=True
            )
            return

        # Check if invited user is already in a party
        if user.id in self.member_to_party:
            await ctx.respond(
                embed=EmbedBuilder.create_error_embed(
                    "Already in a Party",
                    f"{user.mention} is already in a party. They must `/leaveparty` first."
                ),
                ephemeral=True
            )
            return

        # Create party if host doesn't have one
        if ctx.author.id not in self.parties:
            party = Party(host=ctx.author)
            self.parties[ctx.author.id] = party
            self.member_to_party[ctx.author.id] = ctx.author.id
        else:
            party = self.parties[ctx.author.id]

        # Check party size
        if party.size >= 3:
            await ctx.respond(
                embed=EmbedBuilder.create_error_embed(
                    "Party Full",
                    "Your party is already full (3/3)."
                ),
                ephemeral=True
            )
            return

        # Send DM to invited user
        try:
            embed = EmbedBuilder.create_party_invite_embed(ctx.author, party.members)
            view = PartyInviteView(self, ctx.author, user)
            view.message = await user.send(embed=embed, view=view)

            await ctx.respond(
                embed=EmbedBuilder.create_success_embed(
                    "Invite Sent",
                    f"Invitation sent to {user.mention}. They'll receive a DM to accept or decline."
                ),
                ephemeral=True
            )
        except discord.Forbidden:
            await ctx.respond(
                embed=EmbedBuilder.create_error_embed(
                    "Cannot Send DM",
                    f"{user.mention} has DMs disabled. They need to enable DMs from server members."
                ),
                ephemeral=True
            )

    @discord.slash_command(
        name="party",
        description="View your current party",
        default_member_permissions=None
    )
    async def party_command(self, ctx: discord.ApplicationContext):
        """View current party status."""
        host_id = self.member_to_party.get(ctx.author.id)
        if not host_id or host_id not in self.parties:
            await ctx.respond(
                embed=EmbedBuilder.create_error_embed(
                    "No Party",
                    "You're not in a party. Use `/invite @user` to create one."
                ),
                ephemeral=True
            )
            return

        party = self.parties[host_id]
        in_queue = any(m in self.queue_ap.debaters for m in party.members)
        embed = EmbedBuilder.create_party_status_embed(party, in_queue)
        await ctx.respond(embed=embed)

    @discord.slash_command(
        name="leaveparty",
        description="Leave your current party (host: disbands party)",
        default_member_permissions=None
    )
    async def leaveparty_command(self, ctx: discord.ApplicationContext):
        """Leave or disband a party."""
        host_id = self.member_to_party.get(ctx.author.id)
        if not host_id or host_id not in self.parties:
            await ctx.respond(
                embed=EmbedBuilder.create_error_embed(
                    "No Party",
                    "You're not in a party."
                ),
                ephemeral=True
            )
            return

        party = self.parties[host_id]

        if ctx.author.id == host_id:
            # Host disbands: remove all members from queue + party
            for member in party.members:
                self.queue_1v1.remove_user(member)
                self.queue_ap.remove_user(member)
            self._disband_party(host_id)

            await ctx.respond(
                embed=EmbedBuilder.create_success_embed(
                    "Party Disbanded",
                    "Your party has been disbanded and all members removed from queue."
                )
            )
        else:
            # Member leaves: remove from party + queue
            party.remove_member(ctx.author)
            self.member_to_party.pop(ctx.author.id, None)
            self.queue_1v1.remove_user(ctx.author)
            self.queue_ap.remove_user(ctx.author)

            await ctx.respond(
                embed=EmbedBuilder.create_success_embed(
                    "Left Party",
                    "You've left the party and have been removed from the queue."
                )
            )

        await self.update_lobby_display()
        await self.check_matchmaking_threshold()

    @discord.slash_command(
        name="observe",
        description="Request to observe a user's debate round.",
        guild_ids=[Config.GUILD_ID]
    )
    @discord.option("user", discord.Member, description="The participant you want to observe", required=True)
    async def observe_command(self, ctx: discord.ApplicationContext, user: discord.Member):
        """Request permission to observe another user's round."""
        if user.id == ctx.author.id:
            await ctx.respond(embed=EmbedBuilder.create_error_embed(
                "Invalid Target", "You cannot observe yourself."
            ), ephemeral=True)
            return
        if user.bot:
            await ctx.respond(embed=EmbedBuilder.create_error_embed(
                "Invalid Target", "You cannot observe a bot."
            ), ephemeral=True)
            return

        target_round = self._find_member_active_round(user)
        in_queue = self._is_member_in_queue(user)

        if not target_round and not in_queue:
            await ctx.respond(embed=EmbedBuilder.create_error_embed(
                "User Not Available",
                f"**{user.display_name}** is not currently in a round or queue."
            ), ephemeral=True)
            return

        if target_round and ctx.author in target_round.get_all_participants():
            await ctx.respond(embed=EmbedBuilder.create_error_embed(
                "Already a Participant",
                "You are already a participant in this round."
            ), ephemeral=True)
            return

        if target_round and ctx.author in target_round.observers:
            await ctx.respond(embed=EmbedBuilder.create_error_embed(
                "Already Observing",
                f"You are already observing **{user.display_name}**'s round."
            ), ephemeral=True)
            return

        if user.id in self.pending_observers and ctx.author in self.pending_observers[user.id]:
            await ctx.respond(embed=EmbedBuilder.create_error_embed(
                "Request Already Sent",
                f"You already have a pending observation request for **{user.display_name}**."
            ), ephemeral=True)
            return

        view = ObserveRequestView(self, ctx.author, user)
        try:
            view.message = await user.send(
                embed=EmbedBuilder.create_observe_request_embed(ctx.author), view=view
            )
        except discord.Forbidden:
            await ctx.respond(embed=EmbedBuilder.create_error_embed(
                "Cannot Send DM",
                f"**{user.display_name}** has DMs disabled and cannot receive the request."
            ), ephemeral=True)
            return

        await ctx.respond(embed=EmbedBuilder.create_success_embed(
            "Observation Request Sent",
            f"A request has been sent to **{user.display_name}**. Waiting for their response."
        ), ephemeral=True)


def setup(bot):
    bot.add_cog(Matchmaking(bot))
