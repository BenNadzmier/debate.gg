import asyncio
import discord
from discord.ext import commands
import logging
import time
from typing import Optional

from utils.models import DebateRound, RoundType, SpeakerScore, Ballot, JudgeRating, BallotDraft
from utils.embeds import EmbedBuilder
from config import Config

logger = logging.getLogger('DebateBot.Rounds')


class ParticipantConfirmationView(discord.ui.View):
    """View for participants to confirm or decline a round."""

    def __init__(self, rounds_cog, debate_round: DebateRound, matchmaking_cog):
        super().__init__(timeout=90)
        self.rounds_cog = rounds_cog
        self.debate_round = debate_round
        self.matchmaking_cog = matchmaking_cog
        self.confirmed_members: set[int] = set()
        self.declined: bool = False
        self.message: Optional[discord.Message] = None
        self.all_participant_ids: set[int] = {
            p.id for p in debate_round.get_all_participants()
        }

    async def on_timeout(self):
        """Handle timeout - cancel the round and re-queue."""
        if self.declined:
            return
        await self._cancel_round("Confirmation timed out.")

    async def _cancel_round(self, reason: str, excluded_member=None):
        """Cancel the round, re-queue participants, update message."""
        self.declined = True
        self.stop()

        # Re-queue all participants except the decliner (if any)
        self.matchmaking_cog.requeue_participants(self.debate_round, excluded_member=excluded_member)
        self.matchmaking_cog.current_round = None

        # Update lobby display and check thresholds
        await self.matchmaking_cog.update_lobby_display()
        await self.matchmaking_cog.check_matchmaking_threshold()

        # Disable buttons and update message
        for item in self.children:
            item.disabled = True

        embed = EmbedBuilder.create_round_cancelled_embed(reason)
        if self.message:
            try:
                await self.message.edit(embed=embed, view=self)
            except:
                pass

    async def _check_all_confirmed(self, interaction: discord.Interaction):
        """Check if all participants confirmed, and if so, create channels."""
        if self.confirmed_members == self.all_participant_ids:
            self.debate_round.confirmed = True
            self.stop()

            # Disable buttons
            for item in self.children:
                item.disabled = True

            # Update the confirmation message
            embed = EmbedBuilder.create_participant_confirmation_embed(
                self.debate_round, self.confirmed_members
            )
            try:
                await self.message.edit(embed=embed, view=self)
            except:
                pass

            # Create channels
            await self.rounds_cog.create_round_channels(
                interaction.guild, self.debate_round, self.matchmaking_cog
            )

            # Clear current_round so a new round can be started
            self.matchmaking_cog.current_round = None

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success)
    async def confirm_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Handle a participant confirming."""
        if interaction.user.id not in self.all_participant_ids:
            await interaction.response.send_message(
                "You are not a participant in this round.", ephemeral=True
            )
            return

        if interaction.user.id in self.confirmed_members:
            await interaction.response.send_message(
                "You have already confirmed.", ephemeral=True
            )
            return

        self.confirmed_members.add(interaction.user.id)

        # Update embed to show new confirmation status
        embed = EmbedBuilder.create_participant_confirmation_embed(
            self.debate_round, self.confirmed_members
        )
        await interaction.response.edit_message(embed=embed, view=self)

        # Check if all confirmed
        await self._check_all_confirmed(interaction)

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger)
    async def decline_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Handle a participant declining."""
        if interaction.user.id not in self.all_participant_ids:
            await interaction.response.send_message(
                "You are not a participant in this round.", ephemeral=True
            )
            return

        await interaction.response.send_message(
            "You declined the match. Use `/queue` again if you want to be matched.",
            ephemeral=True
        )
        await self._cancel_round(
            f"{interaction.user.mention} declined. Round cancelled.",
            excluded_member=interaction.user
        )


class SubmitBallotView(discord.ui.View):
    """Persistent view for submitting a ballot."""

    def __init__(self, rounds_cog, round_id: int):
        super().__init__(timeout=None)
        self.rounds_cog = rounds_cog
        self.round_id = round_id

        self.clear_items()
        btn = discord.ui.Button(
            label="Submit Ballot",
            style=discord.ButtonStyle.primary,
            custom_id=f"submit_ballot:{round_id}"
        )
        btn.callback = self.submit_ballot_callback
        self.add_item(btn)

    async def submit_ballot_callback(self, interaction: discord.Interaction):
        """Handle the ballot submission button click."""
        matchmaking_cog = self.rounds_cog.bot.get_cog("Matchmaking")
        debate_round = matchmaking_cog.active_rounds.get(self.round_id) if matchmaking_cog else None

        if not debate_round:
            await interaction.response.send_message("Round not found.", ephemeral=True)
            return

        judge_ids = {j.id for j in debate_round.judges.get_all_judges()}
        if interaction.user.id not in judge_ids:
            await interaction.response.send_message(
                "Only judges can submit the ballot.", ephemeral=True
            )
            return

        if debate_round.ballot is not None:
            await interaction.response.send_message(
                "A ballot has already been submitted for this round.", ephemeral=True
            )
            return

        draft = BallotDraft(
            ballot_view=self, debate_round=debate_round, judge=interaction.user
        )
        view = WinnerSelectView(draft)
        await interaction.response.send_message(
            "Select the winning side to begin the ballot.",
            view=view,
            ephemeral=True
        )


def _get_team_positions(team) -> list:
    """Get all position names for a team based on its type."""
    return [team.get_position_name(i) for i in range(len(team.members))]


def _build_member_options(members) -> list:
    """Build discord.SelectOption list from team members."""
    return [
        discord.SelectOption(label=m.display_name, value=str(m.id))
        for m in members
    ]


def _build_member_lookup(members) -> dict:
    """Build {str(member_id): member} lookup dict."""
    return {str(m.id): m for m in members}


class WinnerSelectView(discord.ui.View):
    """Ephemeral view for selecting the winning side."""

    def __init__(self, draft: BallotDraft):
        super().__init__(timeout=300)
        self.draft = draft
        self.is_1v1 = draft.debate_round.round_type == RoundType.PM_LO

        self.winner_select = discord.ui.Select(
            placeholder="Select the winning side",
            options=[
                discord.SelectOption(label="Government", value="Government"),
                discord.SelectOption(label="Opposition", value="Opposition"),
            ]
        )
        self.winner_select.callback = self._winner_callback
        self.add_item(self.winner_select)

        label = "Continue to Scores" if self.is_1v1 else "Next: Assign Gov Positions"
        self.next_btn = discord.ui.Button(
            label=label, style=discord.ButtonStyle.primary, disabled=True
        )
        self.next_btn.callback = self._next_callback
        self.add_item(self.next_btn)

    async def _winner_callback(self, interaction: discord.Interaction):
        selected = self.winner_select.values[0]
        self.draft.winner = selected
        for option in self.winner_select.options:
            option.default = (option.value == selected)
        self.winner_select.placeholder = f"Winner: {selected}"
        self.next_btn.disabled = False
        await interaction.response.edit_message(
            content=f"Winner: **{self.draft.winner}**. Click the button to continue.",
            view=self
        )

    async def _next_callback(self, interaction: discord.Interaction):
        if self.is_1v1:
            modal = ScoreModal1v1(self.draft)
            await interaction.response.send_modal(modal)
        else:
            view = GovAssignmentView(self.draft)
            await interaction.response.edit_message(
                content="Assign **Government** positions. Select which debater fills each role.",
                view=view
            )


class ScoreModal1v1(discord.ui.Modal):
    """Modal for 1v1 scores (no reply, positions implicit)."""

    def __init__(self, draft: BallotDraft):
        super().__init__(title="Submit Ballot — Scores")
        self.draft = draft

        gov_member = draft.debate_round.government.members[0]
        opp_member = draft.debate_round.opposition.members[0]

        self.pm_input = discord.ui.InputText(
            label=f"Prime Minister ({gov_member.display_name})",
            placeholder="50-100",
            style=discord.InputTextStyle.short,
            required=True
        )
        self.add_item(self.pm_input)

        self.lo_input = discord.ui.InputText(
            label=f"Leader of Opposition ({opp_member.display_name})",
            placeholder="50-100",
            style=discord.InputTextStyle.short,
            required=True
        )
        self.add_item(self.lo_input)

    async def callback(self, interaction: discord.Interaction):
        gov_member = self.draft.debate_round.government.members[0]
        opp_member = self.draft.debate_round.opposition.members[0]

        try:
            pm_score = int(self.pm_input.value.strip())
        except ValueError:
            await interaction.response.send_message(
                "Invalid PM score. Enter a number between 50-100.", ephemeral=True
            )
            return

        try:
            lo_score = int(self.lo_input.value.strip())
        except ValueError:
            await interaction.response.send_message(
                "Invalid LO score. Enter a number between 50-100.", ephemeral=True
            )
            return

        ballot = Ballot(
            judge=self.draft.judge,
            winner=self.draft.winner,
            gov_scores=[SpeakerScore(member=gov_member, position_name="Prime Minister", score=pm_score)],
            opp_scores=[SpeakerScore(member=opp_member, position_name="Leader of Opposition", score=lo_score)],
        )
        error = ballot.validate()
        if error:
            await interaction.response.send_message(f"Validation error: {error}", ephemeral=True)
            return

        await interaction.response.defer()
        await self.draft.ballot_view.rounds_cog.finalize_ballot(
            interaction, self.draft.debate_round, ballot, self.draft.ballot_view
        )


class GovAssignmentView(discord.ui.View):
    """Ephemeral view for assigning government positions and reply speaker."""

    def __init__(self, draft: BallotDraft):
        super().__init__(timeout=300)
        self.draft = draft
        team = draft.debate_round.government
        self.positions = _get_team_positions(team)
        self.member_lookup = _build_member_lookup(team.members)
        self.assignments = {}  # position_name -> member_id (str)
        self.reply_member_id = None

        member_options = _build_member_options(team.members)

        for pos_name in self.positions:
            select = discord.ui.Select(
                placeholder=f"Who is {pos_name}?",
                options=[discord.SelectOption(label=o.label, value=o.value) for o in member_options],
            )
            select.callback = self._make_pos_callback(pos_name, select)
            self.add_item(select)

        self.reply_select = discord.ui.Select(
            placeholder="Who gives the Gov Reply speech?",
            options=[discord.SelectOption(label=o.label, value=o.value) for o in member_options],
        )
        self.reply_select.callback = self._reply_callback
        self.add_item(self.reply_select)

        self.next_btn = discord.ui.Button(
            label="Next: Assign Opp Positions", style=discord.ButtonStyle.primary
        )
        self.next_btn.callback = self._next_callback
        self.add_item(self.next_btn)

    def _make_pos_callback(self, pos_name: str, select: discord.ui.Select):
        async def callback(interaction: discord.Interaction):
            selected_id = interaction.data["values"][0]
            self.assignments[pos_name] = selected_id
            for option in select.options:
                option.default = (option.value == selected_id)
            selected_label = next(o.label for o in select.options if o.value == selected_id)
            select.placeholder = f"{pos_name}: {selected_label}"
            await interaction.response.edit_message(view=self)
        return callback

    async def _reply_callback(self, interaction: discord.Interaction):
        selected_id = interaction.data["values"][0]
        self.reply_member_id = selected_id
        for option in self.reply_select.options:
            option.default = (option.value == selected_id)
        selected_label = next(o.label for o in self.reply_select.options if o.value == selected_id)
        self.reply_select.placeholder = f"Gov Reply: {selected_label}"
        await interaction.response.edit_message(view=self)

    async def _next_callback(self, interaction: discord.Interaction):
        # Validate all positions filled
        if len(self.assignments) < len(self.positions):
            await interaction.response.send_message(
                "Please assign all positions before continuing.", ephemeral=True
            )
            return

        # Validate no duplicates
        assigned_ids = list(self.assignments.values())
        if len(set(assigned_ids)) != len(assigned_ids):
            await interaction.response.send_message(
                "Each debater must be assigned to exactly one position.", ephemeral=True
            )
            return

        # Validate reply selected
        if not self.reply_member_id:
            await interaction.response.send_message(
                "Please select the reply speaker.", ephemeral=True
            )
            return

        # Validate reply speaker is not whip
        reply_position = None
        for pos, mid in self.assignments.items():
            if mid == self.reply_member_id:
                reply_position = pos
                break
        if reply_position and "Whip" in reply_position:
            await interaction.response.send_message(
                "The reply speaker cannot be the Whip. Please reassign.", ephemeral=True
            )
            return

        # Store in draft
        self.draft.gov_assignments = {
            pos: self.member_lookup[mid] for pos, mid in self.assignments.items()
        }
        self.draft.gov_reply_member = self.member_lookup[self.reply_member_id]

        view = OppAssignmentView(self.draft)
        await interaction.response.edit_message(
            content="Assign **Opposition** positions. Select which debater fills each role.",
            view=view
        )


class OppAssignmentView(discord.ui.View):
    """Ephemeral view for assigning opposition positions and reply speaker."""

    def __init__(self, draft: BallotDraft):
        super().__init__(timeout=300)
        self.draft = draft
        team = draft.debate_round.opposition
        self.positions = _get_team_positions(team)
        self.member_lookup = _build_member_lookup(team.members)
        self.assignments = {}
        self.reply_member_id = None

        member_options = _build_member_options(team.members)

        for pos_name in self.positions:
            select = discord.ui.Select(
                placeholder=f"Who is {pos_name}?",
                options=[discord.SelectOption(label=o.label, value=o.value) for o in member_options],
            )
            select.callback = self._make_pos_callback(pos_name, select)
            self.add_item(select)

        self.reply_select = discord.ui.Select(
            placeholder="Who gives the Opp Reply speech?",
            options=[discord.SelectOption(label=o.label, value=o.value) for o in member_options],
        )
        self.reply_select.callback = self._reply_callback
        self.add_item(self.reply_select)

        self.next_btn = discord.ui.Button(
            label="Continue to Scores", style=discord.ButtonStyle.primary
        )
        self.next_btn.callback = self._next_callback
        self.add_item(self.next_btn)

    def _make_pos_callback(self, pos_name: str, select: discord.ui.Select):
        async def callback(interaction: discord.Interaction):
            selected_id = interaction.data["values"][0]
            self.assignments[pos_name] = selected_id
            for option in select.options:
                option.default = (option.value == selected_id)
            selected_label = next(o.label for o in select.options if o.value == selected_id)
            select.placeholder = f"{pos_name}: {selected_label}"
            await interaction.response.edit_message(view=self)
        return callback

    async def _reply_callback(self, interaction: discord.Interaction):
        selected_id = interaction.data["values"][0]
        self.reply_member_id = selected_id
        for option in self.reply_select.options:
            option.default = (option.value == selected_id)
        selected_label = next(o.label for o in self.reply_select.options if o.value == selected_id)
        self.reply_select.placeholder = f"Opp Reply: {selected_label}"
        await interaction.response.edit_message(view=self)

    async def _next_callback(self, interaction: discord.Interaction):
        if len(self.assignments) < len(self.positions):
            await interaction.response.send_message(
                "Please assign all positions before continuing.", ephemeral=True
            )
            return

        assigned_ids = list(self.assignments.values())
        if len(set(assigned_ids)) != len(assigned_ids):
            await interaction.response.send_message(
                "Each debater must be assigned to exactly one position.", ephemeral=True
            )
            return

        if not self.reply_member_id:
            await interaction.response.send_message(
                "Please select the reply speaker.", ephemeral=True
            )
            return

        reply_position = None
        for pos, mid in self.assignments.items():
            if mid == self.reply_member_id:
                reply_position = pos
                break
        if reply_position and "Whip" in reply_position:
            await interaction.response.send_message(
                "The reply speaker cannot be the Whip. Please reassign.", ephemeral=True
            )
            return

        # Store in draft
        self.draft.opp_assignments = {
            pos: self.member_lookup[mid] for pos, mid in self.assignments.items()
        }
        self.draft.opp_reply_member = self.member_lookup[self.reply_member_id]

        # Open gov score modal
        modal = GovScoreModal(self.draft)
        await interaction.response.send_modal(modal)


class GovScoreModal(discord.ui.Modal):
    """Modal for entering government substantive + reply scores."""

    def __init__(self, draft: BallotDraft):
        super().__init__(title="Gov Scores")
        self.draft = draft

        self.score_inputs = []  # (InputText, position_name, member)
        for pos_name, member in draft.gov_assignments.items():
            inp = discord.ui.InputText(
                label=f"{pos_name} ({member.display_name})",
                placeholder="50-100",
                style=discord.InputTextStyle.short,
                required=True
            )
            self.add_item(inp)
            self.score_inputs.append((inp, pos_name, member))

        self.reply_input = discord.ui.InputText(
            label=f"Reply ({draft.gov_reply_member.display_name})",
            placeholder="25-50",
            style=discord.InputTextStyle.short,
            required=True
        )
        self.add_item(self.reply_input)

    async def callback(self, interaction: discord.Interaction):
        gov_scores = []
        for inp, pos_name, member in self.score_inputs:
            try:
                score = int(inp.value.strip())
            except ValueError:
                await interaction.response.send_message(
                    f"Invalid score for {pos_name}. Enter a number between 50-100.", ephemeral=True
                )
                return
            gov_scores.append(SpeakerScore(member=member, position_name=pos_name, score=score))

        try:
            reply_score = int(self.reply_input.value.strip())
        except ValueError:
            await interaction.response.send_message(
                "Invalid reply score. Enter a number between 25-50.", ephemeral=True
            )
            return

        # Find the reply speaker's assigned position for validation
        reply_pos = None
        for pos_name, member in self.draft.gov_assignments.items():
            if member.id == self.draft.gov_reply_member.id:
                reply_pos = pos_name
                break

        self.draft.gov_scores = gov_scores
        self.draft.gov_reply_score = SpeakerScore(
            member=self.draft.gov_reply_member,
            position_name=reply_pos or "Reply",
            score=reply_score
        )

        view = OppScoreContinueView(self.draft)
        await interaction.response.send_message(
            "Government scores recorded. Click below to enter Opposition scores.",
            view=view,
            ephemeral=True
        )


class OppScoreContinueView(discord.ui.View):
    """Ephemeral bridge view between GovScoreModal and OppScoreModal."""

    def __init__(self, draft: BallotDraft):
        super().__init__(timeout=300)
        self.draft = draft

    @discord.ui.button(label="Continue to Opposition Scores", style=discord.ButtonStyle.primary)
    async def continue_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        modal = OppScoreModal(self.draft)
        await interaction.response.send_modal(modal)


class OppScoreModal(discord.ui.Modal):
    """Modal for entering opposition substantive + reply scores, then finalizing."""

    def __init__(self, draft: BallotDraft):
        super().__init__(title="Opp Scores")
        self.draft = draft

        self.score_inputs = []
        for pos_name, member in draft.opp_assignments.items():
            inp = discord.ui.InputText(
                label=f"{pos_name} ({member.display_name})",
                placeholder="50-100",
                style=discord.InputTextStyle.short,
                required=True
            )
            self.add_item(inp)
            self.score_inputs.append((inp, pos_name, member))

        self.reply_input = discord.ui.InputText(
            label=f"Reply ({draft.opp_reply_member.display_name})",
            placeholder="25-50",
            style=discord.InputTextStyle.short,
            required=True
        )
        self.add_item(self.reply_input)

    async def callback(self, interaction: discord.Interaction):
        opp_scores = []
        for inp, pos_name, member in self.score_inputs:
            try:
                score = int(inp.value.strip())
            except ValueError:
                await interaction.response.send_message(
                    f"Invalid score for {pos_name}. Enter a number between 50-100.", ephemeral=True
                )
                return
            opp_scores.append(SpeakerScore(member=member, position_name=pos_name, score=score))

        try:
            reply_score = int(self.reply_input.value.strip())
        except ValueError:
            await interaction.response.send_message(
                "Invalid reply score. Enter a number between 25-50.", ephemeral=True
            )
            return

        # Find the reply speaker's assigned position
        reply_pos = None
        for pos_name, member in self.draft.opp_assignments.items():
            if member.id == self.draft.opp_reply_member.id:
                reply_pos = pos_name
                break

        opp_reply = SpeakerScore(
            member=self.draft.opp_reply_member,
            position_name=reply_pos or "Reply",
            score=reply_score
        )

        ballot = Ballot(
            judge=self.draft.judge,
            winner=self.draft.winner,
            gov_scores=self.draft.gov_scores,
            opp_scores=opp_scores,
            gov_reply=self.draft.gov_reply_score,
            opp_reply=opp_reply,
        )
        error = ballot.validate()
        if error:
            await interaction.response.send_message(f"Validation error: {error}", ephemeral=True)
            return

        await interaction.response.defer()
        await self.draft.ballot_view.rounds_cog.finalize_ballot(
            interaction, self.draft.debate_round, ballot, self.draft.ballot_view
        )


class PostBallotRoundCompleteView(discord.ui.View):
    """Persistent view for deleting channels after ballot is submitted."""

    def __init__(self, rounds_cog, round_id: int):
        super().__init__(timeout=None)
        self.rounds_cog = rounds_cog
        self.round_id = round_id

        self.clear_items()
        btn = discord.ui.Button(
            label="Mark Round as Complete",
            style=discord.ButtonStyle.danger,
            custom_id=f"post_ballot_complete:{round_id}"
        )
        btn.callback = self.complete_callback
        self.add_item(btn)

    async def complete_callback(self, interaction: discord.Interaction):
        matchmaking_cog = self.rounds_cog.bot.get_cog("Matchmaking")
        debate_round = matchmaking_cog.active_rounds.get(self.round_id) if matchmaking_cog else None

        # Verify user is a judge
        if debate_round:
            judge_ids = {j.id for j in debate_round.judges.get_all_judges()}
            if interaction.user.id not in judge_ids:
                await interaction.response.send_message(
                    "Only judges can mark the round as complete.", ephemeral=True
                )
                return

        confirm_view = ChannelDeletionConfirmView(self.rounds_cog, self.round_id)
        await interaction.response.send_message(
            "Are you sure you want to delete all round channels? This cannot be undone.",
            view=confirm_view,
            ephemeral=True
        )


class ChannelDeletionConfirmView(discord.ui.View):
    """Ephemeral confirmation view for deleting round channels."""

    def __init__(self, rounds_cog, round_id: int):
        super().__init__(timeout=60)
        self.rounds_cog = rounds_cog
        self.round_id = round_id

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger)
    async def confirm_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer()

        matchmaking_cog = self.rounds_cog.bot.get_cog("Matchmaking")
        debate_round = matchmaking_cog.active_rounds.get(self.round_id) if matchmaking_cog else None

        # Cancel prep/veto timers if still running
        if debate_round:
            if hasattr(debate_round, '_prep_task') and debate_round._prep_task:
                debate_round._prep_task.cancel()
            if hasattr(debate_round, '_veto_task') and debate_round._veto_task:
                debate_round._veto_task.cancel()

        # Delete channels and category
        await self.rounds_cog.delete_round_channels(interaction.guild, self.round_id)

        # Remove from active rounds
        if matchmaking_cog:
            matchmaking_cog.remove_active_round(self.round_id)

        # Post completion in lobby channel
        lobby_channel = self.rounds_cog.bot.get_channel(Config.LOBBY_CHANNEL_ID)
        if lobby_channel:
            embed = EmbedBuilder.create_round_complete_embed(self.round_id)
            await lobby_channel.send(embed=embed)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.edit_message(content="Channel deletion cancelled.", view=None)


class RateJudgeView(discord.ui.View):
    """DM view for debaters to rate the judge."""

    def __init__(self, rounds_cog, debate_round: DebateRound, debater: discord.Member):
        super().__init__(timeout=None)
        self.rounds_cog = rounds_cog
        self.debate_round = debate_round
        self.debater = debater

    @discord.ui.button(label="Rate Judge", style=discord.ButtonStyle.primary)
    async def rate_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        # Check if already rated
        if self.debater.id in self.debate_round.rated_debater_ids:
            await interaction.response.send_message("You have already rated the judge.", ephemeral=True)
            return

        modal = RateJudgeModal(self.rounds_cog, self.debate_round, self.debater, self)
        await interaction.response.send_modal(modal)


class RateJudgeModal(discord.ui.Modal):
    """Modal for debaters to rate the judge."""

    def __init__(self, rounds_cog, debate_round: DebateRound, debater: discord.Member, rate_view: RateJudgeView):
        super().__init__(title="Rate the Judge")
        self.rounds_cog = rounds_cog
        self.debate_round = debate_round
        self.debater = debater
        self.rate_view = rate_view

        self.score_input = discord.ui.InputText(
            label="Score (1-10)",
            placeholder="1-10",
            style=discord.InputTextStyle.short,
            required=True
        )
        self.add_item(self.score_input)

        self.feedback_input = discord.ui.InputText(
            label="Feedback for the judge (optional)",
            placeholder="Any comments for the judge...",
            style=discord.InputTextStyle.long,
            required=False
        )
        self.add_item(self.feedback_input)

    async def callback(self, interaction: discord.Interaction):
        # Parse score
        try:
            score = int(self.score_input.value.strip())
        except ValueError:
            await interaction.response.send_message("Invalid score. Please enter a number between 1-10.", ephemeral=True)
            return

        if not (1 <= score <= 10):
            await interaction.response.send_message("Score must be between 1 and 10.", ephemeral=True)
            return

        feedback = self.feedback_input.value.strip() if self.feedback_input.value else None

        # Record the rating
        rating = JudgeRating(debater=self.debater, score=score, feedback=feedback)
        self.debate_round.judge_ratings.append(rating)
        self.debate_round.rated_debater_ids.add(self.debater.id)

        # Disable the Rate Judge button in the DM
        for item in self.rate_view.children:
            item.disabled = True
        if hasattr(self.rate_view, 'message') and self.rate_view.message:
            try:
                await self.rate_view.message.edit(view=self.rate_view)
            except:
                pass

        # Send the debater the full ballot results
        ballot_embed = EmbedBuilder.create_ballot_results_embed(self.debate_round)
        await interaction.response.send_message(embed=ballot_embed)

        # Check if all debaters have rated
        all_debater_ids = {
            m.id for m in self.debate_round.government.members + self.debate_round.opposition.members
        }
        if self.debate_round.rated_debater_ids >= all_debater_ids:
            # All debaters have rated — send aggregated ratings to judge
            await self.rounds_cog.send_judge_ratings(self.debate_round)


class MotionInputModal(discord.ui.Modal):
    """Modal for entering the debate motion."""

    def __init__(self, chair_view):
        super().__init__(title="Enter Debate Motion")
        self.chair_view = chair_view

        self.motion_input = discord.ui.InputText(
            label="Motion",
            placeholder="Enter the debate motion...",
            style=discord.InputTextStyle.long,
            required=True
        )
        self.add_item(self.motion_input)

        self.infoslide_input = discord.ui.InputText(
            label="Infoslide (Optional)",
            placeholder="Enter context/background information for the motion...",
            style=discord.InputTextStyle.long,
            required=False
        )
        self.add_item(self.infoslide_input)

    async def callback(self, interaction: discord.Interaction):
        motion = self.motion_input.value.strip()
        if not motion:
            await interaction.response.send_message(
                "Motion cannot be empty.", ephemeral=True
            )
            return

        debate_round = self.chair_view.debate_round
        debate_round.motion = motion
        infoslide = self.infoslide_input.value.strip() if self.infoslide_input.value else None
        debate_round.infoslide = infoslide or None

        # Update round info embed with the motion
        if self.chair_view.round_info_message:
            round_embed = EmbedBuilder.create_round_text_channel_embed(debate_round)
            try:
                await self.chair_view.round_info_message.edit(embed=round_embed)
            except:
                pass

        # Update chair control view: replace Enter Motion with Start Prep
        self.chair_view.show_start_prep()
        chair_embed = EmbedBuilder.create_chair_control_embed(debate_round)
        await interaction.response.edit_message(embed=chair_embed, view=self.chair_view)


class APSingleMotionModal(discord.ui.Modal):
    """Modal for entering one AP motion and its optional infoslide."""

    def __init__(self, motion_index: int, chair_view):
        letter = ['A', 'B', 'C'][motion_index]
        super().__init__(title=f"Enter Motion {letter}")
        self.motion_index = motion_index
        self.chair_view = chair_view

        self.motion_input = discord.ui.InputText(
            label="Motion",
            style=discord.InputTextStyle.long,
            required=True
        )
        self.infoslide_input = discord.ui.InputText(
            label="Infoslide (Optional)",
            style=discord.InputTextStyle.long,
            required=False
        )
        self.add_item(self.motion_input)
        self.add_item(self.infoslide_input)

    async def callback(self, interaction: discord.Interaction):
        motion_text = self.motion_input.value.strip()
        infoslide_val = self.infoslide_input.value.strip() if self.infoslide_input.value else None

        self.chair_view.pending_motions[self.motion_index] = (motion_text, infoslide_val)
        self.chair_view._update_motion_buttons()

        embed = EmbedBuilder.create_ap_motion_input_embed(self.chair_view.pending_motions)
        await interaction.response.edit_message(embed=embed, view=self.chair_view)


class VetoView(discord.ui.View):
    """View posted in text channel with Gov and Opp veto submission buttons."""

    def __init__(self, debate_round: DebateRound, rounds_cog):
        super().__init__(timeout=None)
        self.debate_round = debate_round
        self.rounds_cog = rounds_cog
        self.message: Optional[discord.Message] = None

        self.gov_btn = discord.ui.Button(
            label="Gov: Submit Veto",
            style=discord.ButtonStyle.primary
        )
        self.opp_btn = discord.ui.Button(
            label="Opp: Submit Veto",
            style=discord.ButtonStyle.danger
        )
        self.gov_btn.callback = self._gov_callback
        self.opp_btn.callback = self._opp_callback
        self.add_item(self.gov_btn)
        self.add_item(self.opp_btn)

    async def _gov_callback(self, interaction: discord.Interaction):
        if interaction.user not in self.debate_round.government.members:
            await interaction.response.send_message(
                "Only Government members can submit the Gov veto.", ephemeral=True
            )
            return
        if self.debate_round.gov_veto is not None:
            await interaction.response.send_message(
                "Your team has already submitted their veto.", ephemeral=True
            )
            return
        await interaction.response.send_modal(
            VetoModal('gov', self.debate_round, self, self.rounds_cog)
        )

    async def _opp_callback(self, interaction: discord.Interaction):
        if interaction.user not in self.debate_round.opposition.members:
            await interaction.response.send_message(
                "Only Opposition members can submit the Opp veto.", ephemeral=True
            )
            return
        if self.debate_round.opp_veto is not None:
            await interaction.response.send_message(
                "Your team has already submitted their veto.", ephemeral=True
            )
            return
        await interaction.response.send_modal(
            VetoModal('opp', self.debate_round, self, self.rounds_cog)
        )


class VetoModal(discord.ui.Modal):
    """Modal for a team to rank the 3 motions (1 = most favored, 3 = least)."""

    def __init__(self, team: str, debate_round: DebateRound, veto_view: VetoView, rounds_cog):
        team_label = "Government" if team == "gov" else "Opposition"
        super().__init__(title=f"Submit {team_label} Veto")
        self.team = team
        self.debate_round = debate_round
        self.veto_view = veto_view
        self.rounds_cog = rounds_cog

        self.rank_inputs = []
        for i in range(3):
            inp = discord.ui.InputText(
                label=f"Motion {i + 1} — Rank (1 = best, 3 = worst)",
                placeholder="Type 1, 2, or 3",
                max_length=1,
                required=True
            )
            self.add_item(inp)
            self.rank_inputs.append(inp)

    async def callback(self, interaction: discord.Interaction):
        # Parse ranks
        try:
            ranks = [int(inp.value.strip()) for inp in self.rank_inputs]
        except ValueError:
            await interaction.response.send_message(
                "Ranks must be numbers (1, 2, or 3).", ephemeral=True
            )
            return

        if set(ranks) != {1, 2, 3}:
            await interaction.response.send_message(
                "You must assign each rank exactly once: one motion ranked 1, one 2, one 3.",
                ephemeral=True
            )
            return

        # Guard against race condition (two members submit simultaneously)
        if self.team == 'gov':
            if self.debate_round.gov_veto is not None:
                await interaction.response.send_message(
                    "Your team already submitted!", ephemeral=True
                )
                return
            self.debate_round.gov_veto = ranks
            self.veto_view.gov_btn.label = "Gov: Submitted ✓"
            self.veto_view.gov_btn.disabled = True
        else:
            if self.debate_round.opp_veto is not None:
                await interaction.response.send_message(
                    "Your team already submitted!", ephemeral=True
                )
                return
            self.debate_round.opp_veto = ranks
            self.veto_view.opp_btn.label = "Opp: Submitted ✓"
            self.veto_view.opp_btn.disabled = True

        await interaction.response.send_message(
            "Your veto has been submitted!", ephemeral=True
        )

        # Update the public veto message to show the submitted state
        try:
            await self.veto_view.message.edit(view=self.veto_view)
        except Exception:
            pass

        # If both teams have now submitted, cancel timer and resolve
        if self.debate_round.gov_veto is not None and self.debate_round.opp_veto is not None:
            if hasattr(self.debate_round, '_veto_task') and self.debate_round._veto_task:
                self.debate_round._veto_task.cancel()
            await self.rounds_cog.process_veto(self.debate_round, interaction.guild)


class CoinTossView(discord.ui.View):
    """View posted in text channel for the coin toss tie-breaker."""

    def __init__(self, debate_round: DebateRound, rounds_cog, tied_indices: list,
                 gov_preferred_idx: int, opp_preferred_idx: int):
        super().__init__(timeout=120)
        self.debate_round = debate_round
        self.rounds_cog = rounds_cog
        self.tied_indices = tied_indices
        self.gov_preferred_idx = gov_preferred_idx
        self.opp_preferred_idx = opp_preferred_idx
        self.gov_call: Optional[str] = None
        self.opp_call: Optional[str] = None
        self.message: Optional[discord.Message] = None

        self.gov_heads = discord.ui.Button(label="Gov: Heads", style=discord.ButtonStyle.primary, row=0)
        self.gov_tails = discord.ui.Button(label="Gov: Tails", style=discord.ButtonStyle.primary, row=0)
        self.opp_heads = discord.ui.Button(label="Opp: Heads", style=discord.ButtonStyle.danger, row=1)
        self.opp_tails = discord.ui.Button(label="Opp: Tails", style=discord.ButtonStyle.danger, row=1)

        self.gov_heads.callback = self._make_call_callback('gov', 'heads')
        self.gov_tails.callback = self._make_call_callback('gov', 'tails')
        self.opp_heads.callback = self._make_call_callback('opp', 'heads')
        self.opp_tails.callback = self._make_call_callback('opp', 'tails')

        self.add_item(self.gov_heads)
        self.add_item(self.gov_tails)
        self.add_item(self.opp_heads)
        self.add_item(self.opp_tails)

    def _make_call_callback(self, team: str, call: str):
        async def callback(interaction: discord.Interaction):
            gov_members = self.debate_round.government.members
            opp_members = self.debate_round.opposition.members

            if team == 'gov':
                if interaction.user not in gov_members:
                    await interaction.response.send_message(
                        "Only Government members can call for Gov.", ephemeral=True
                    )
                    return
                if self.gov_call:
                    await interaction.response.send_message(
                        "Government has already called!", ephemeral=True
                    )
                    return
                self.gov_call = call
                self.gov_heads.disabled = True
                self.gov_tails.disabled = True
                # Force opp to call the opposite side
                if call == 'heads':
                    self.opp_heads.disabled = True
                else:
                    self.opp_tails.disabled = True
            else:
                if interaction.user not in opp_members:
                    await interaction.response.send_message(
                        "Only Opposition members can call for Opp.", ephemeral=True
                    )
                    return
                if self.opp_call:
                    await interaction.response.send_message(
                        "Opposition has already called!", ephemeral=True
                    )
                    return
                self.opp_call = call
                self.opp_heads.disabled = True
                self.opp_tails.disabled = True
                # Force gov to call the opposite side
                if call == 'heads':
                    self.gov_heads.disabled = True
                else:
                    self.gov_tails.disabled = True

            await interaction.response.edit_message(view=self)

            if self.gov_call and self.opp_call:
                await self.rounds_cog.flip_coin(
                    self.debate_round, interaction.guild, self, interaction.message
                )
        return callback

    async def on_timeout(self):
        """Auto-resolve with random motion if teams don't call within 2 minutes."""
        import random
        motion_index = random.choice(self.tied_indices)
        guild = self.rounds_cog.bot.get_guild(Config.GUILD_ID)
        if guild:
            await self.rounds_cog.resolve_veto_result(
                self.debate_round, guild, motion_index, reason="timeout"
            )


class ChairJudgeControlView(discord.ui.View):
    """View for chair judge to control the round (enter motion, start prep)."""

    def __init__(self, rounds_cog, debate_round: DebateRound, round_info_message: discord.Message):
        super().__init__(timeout=None)
        self.rounds_cog = rounds_cog
        self.debate_round = debate_round
        self.round_info_message = round_info_message
        self.message: Optional[discord.Message] = None
        self.chair_id = debate_round.judges.chair.id

        # AP motion input state (populated before Release Motions is clicked)
        self.pending_motions: list = [None, None, None]  # each entry: (motion_text, infoslide_or_None)
        self._motion_buttons: list = []
        self._release_btn: Optional[discord.ui.Button] = None

        # Start with "Enter Motion" button (or AP 4-button layout)
        self._setup_enter_motion()

    def _setup_enter_motion(self):
        """Show the motion entry UI (format-aware)."""
        self.clear_items()
        if self.debate_round.format_label == "AP":
            self._setup_ap_motion_buttons()
        else:
            btn = discord.ui.Button(label="Enter Motion", style=discord.ButtonStyle.primary)
            btn.callback = self._enter_motion_callback
            self.add_item(btn)

    def _setup_ap_motion_buttons(self):
        """Show Input Motion A/B/C buttons + disabled Release Motions button."""
        self.clear_items()
        self._motion_buttons = []
        for i, letter in enumerate(['A', 'B', 'C']):
            btn = discord.ui.Button(
                label=f"Input Motion {letter}",
                style=discord.ButtonStyle.primary,
                row=0
            )
            btn.callback = self._make_motion_button_callback(i)
            self.add_item(btn)
            self._motion_buttons.append(btn)

        self._release_btn = discord.ui.Button(
            label="Release Motions",
            style=discord.ButtonStyle.success,
            disabled=True,
            row=1
        )
        self._release_btn.callback = self._release_motions_callback
        self.add_item(self._release_btn)

    def _make_motion_button_callback(self, index: int):
        """Return a callback that opens APSingleMotionModal for the given motion index."""
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.chair_id:
                await interaction.response.send_message(
                    "Only the chair judge can enter motions.", ephemeral=True
                )
                return
            await interaction.response.send_modal(APSingleMotionModal(index, self))
        return callback

    def _update_motion_buttons(self):
        """Update button labels/styles after a motion is entered; enable Release when all 3 done."""
        letters = ['A', 'B', 'C']
        for i, btn in enumerate(self._motion_buttons):
            if self.pending_motions[i]:
                btn.label = f"Motion {letters[i]} ✓"
                btn.style = discord.ButtonStyle.secondary
            else:
                btn.label = f"Input Motion {letters[i]}"
                btn.style = discord.ButtonStyle.primary
        self._release_btn.disabled = not all(self.pending_motions)

    async def _release_motions_callback(self, interaction: discord.Interaction):
        """Handle Release Motions button — commit motions to the round and start veto."""
        if interaction.user.id != self.chair_id:
            await interaction.response.send_message(
                "Only the chair judge can release motions.", ephemeral=True
            )
            return

        debate_round = self.debate_round
        debate_round.motions = [m[0] for m in self.pending_motions]
        debate_round.motion_infoslides = [m[1] for m in self.pending_motions]

        self.show_prep_in_progress()
        duration = Config.PREP_TIME_AP
        end_timestamp = int(time.time()) + duration
        debate_round._prep_end_timestamp = end_timestamp

        chair_embed = EmbedBuilder.create_chair_control_embed(debate_round)
        chair_embed.description += f"\n\nPrep ends <t:{end_timestamp}:R>"
        await interaction.response.edit_message(embed=chair_embed, view=self)

        await self.rounds_cog.release_motions(debate_round, interaction.guild, duration)

    def set_waiting_for_veto(self):
        """Replace buttons with a disabled waiting indicator during veto."""
        self.clear_items()
        btn = discord.ui.Button(
            label="Veto In Progress...",
            style=discord.ButtonStyle.secondary,
            disabled=True
        )
        self.add_item(btn)

    def show_prep_in_progress(self):
        """Replace buttons with a disabled Prep In Progress indicator."""
        self.clear_items()
        btn = discord.ui.Button(
            label="Prep In Progress",
            style=discord.ButtonStyle.secondary,
            disabled=True
        )
        self.add_item(btn)

    def show_start_prep(self):
        """Replace buttons with Start Prep button."""
        self.clear_items()
        btn = discord.ui.Button(
            label="Start Prep",
            style=discord.ButtonStyle.success
        )
        btn.callback = self._start_prep_callback
        self.add_item(btn)

    async def _enter_motion_callback(self, interaction: discord.Interaction):
        """Handle Enter Motion button click (1v1 only)."""
        if interaction.user.id != self.chair_id:
            await interaction.response.send_message(
                "Only the chair judge can enter the motion.", ephemeral=True
            )
            return
        await interaction.response.send_modal(MotionInputModal(self))

    async def _start_prep_callback(self, interaction: discord.Interaction):
        """Handle Start Prep button click."""
        if interaction.user.id != self.chair_id:
            await interaction.response.send_message(
                "Only the chair judge can start prep time.", ephemeral=True
            )
            return

        # Disable buttons
        self.clear_items()
        btn = discord.ui.Button(
            label="Prep In Progress",
            style=discord.ButtonStyle.secondary,
            disabled=True
        )
        self.add_item(btn)

        # Calculate prep duration and end timestamp
        if self.debate_round.round_type == RoundType.PM_LO:
            duration = Config.PREP_TIME_1V1
        else:
            duration = Config.PREP_TIME_AP

        end_timestamp = int(time.time()) + duration

        # Update chair control embed
        chair_embed = EmbedBuilder.create_chair_control_embed(self.debate_round)
        chair_embed.description += f"\n\nPrep ends <t:{end_timestamp}:R>"
        await interaction.response.edit_message(embed=chair_embed, view=self)

        # Post prep started message
        text_channel = interaction.channel
        prep_embed = EmbedBuilder.create_prep_started_embed(self.debate_round, end_timestamp)
        await text_channel.send(embed=prep_embed)

        # DM debaters with motion, side, and prep end time
        await self.rounds_cog.send_prep_dms(self.debate_round, end_timestamp)

        # Start background prep timer
        task = self.rounds_cog.bot.loop.create_task(
            self.rounds_cog.run_prep_timer(interaction.guild, self.debate_round, text_channel, duration)
        )
        self.debate_round._prep_task = task


class Rounds(commands.Cog):
    """Cog handling round lifecycle: confirmation, channels, completion."""

    def __init__(self, bot):
        self.bot = bot
        self._chair_views: dict = {}   # round_id → ChairJudgeControlView
        self._veto_views: dict = {}    # round_id → VetoView

    async def cog_load(self):
        """Called when the cog is loaded."""
        logger.info("Rounds cog loaded")

    @commands.Cog.listener()
    async def on_ready(self):
        """Re-register persistent views after bot restart."""
        await self._register_persistent_views()

    async def _register_persistent_views(self):
        """Register persistent views for active rounds."""
        matchmaking_cog = self.bot.get_cog("Matchmaking")
        if matchmaking_cog and hasattr(matchmaking_cog, 'active_rounds'):
            for round_id, debate_round in matchmaking_cog.active_rounds.items():
                if debate_round.ballot is not None:
                    view = PostBallotRoundCompleteView(self, round_id)
                else:
                    view = SubmitBallotView(self, round_id)
                self.bot.add_view(view)
                logger.info(f"Re-registered persistent view for round {round_id}")

    async def send_participant_confirmation(
        self,
        channel: discord.TextChannel,
        debate_round: DebateRound,
        matchmaking_cog
    ):
        """Send the participant confirmation embed and view to a channel."""
        all_participants = debate_round.get_all_participants()
        mentions = " ".join(p.mention for p in all_participants)

        view = ParticipantConfirmationView(self, debate_round, matchmaking_cog)
        embed = EmbedBuilder.create_participant_confirmation_embed(
            debate_round, view.confirmed_members
        )

        view.message = await channel.send(
            content=mentions,
            embed=embed,
            view=view
        )

    async def create_round_channels(
        self,
        guild: discord.Guild,
        debate_round: DebateRound,
        matchmaking_cog
    ):
        """Create the category and all channels for a confirmed round."""
        round_id = debate_round.round_id
        round_label = self._get_round_label(debate_round)

        all_participants = debate_round.get_all_participants()
        gov_members = debate_round.government.members
        opp_members = debate_round.opposition.members
        judge_members = debate_round.judges.get_all_judges()

        everyone_role = guild.default_role

        deny_all = discord.PermissionOverwrite(
            view_channel=False,
            connect=False
        )
        allow_view_connect = discord.PermissionOverwrite(
            view_channel=True,
            connect=True,
            send_messages=True,
            read_message_history=True
        )
        bot_perms = discord.PermissionOverwrite(
            view_channel=True,
            connect=True,
            send_messages=True,
            manage_channels=True,
            read_message_history=True,
            move_members=True
        )

        # Category: all participants can see
        category_overwrites = {everyone_role: deny_all, guild.me: bot_perms}
        for member in all_participants:
            category_overwrites[member] = allow_view_connect

        try:
            category = await guild.create_category(
                name=f"Round {round_id} - {round_label}",
                overwrites=category_overwrites
            )
            debate_round.category_id = category.id

            # Text channel (inherits from category)
            text_channel = await category.create_text_channel(
                name=f"round-{round_id}-text"
            )

            # Debate voice (inherits from category)
            debate_vc = await category.create_voice_channel(
                name=f"round-{round_id}-debate"
            )

            # Gov prep voice (gov team only)
            gov_overwrites = {everyone_role: deny_all, guild.me: bot_perms}
            for member in gov_members:
                gov_overwrites[member] = allow_view_connect
            gov_prep_vc = await category.create_voice_channel(
                name=f"round-{round_id}-gov-prep",
                overwrites=gov_overwrites
            )

            # Opp prep voice (opp team only)
            opp_overwrites = {everyone_role: deny_all, guild.me: bot_perms}
            for member in opp_members:
                opp_overwrites[member] = allow_view_connect
            opp_prep_vc = await category.create_voice_channel(
                name=f"round-{round_id}-opp-prep",
                overwrites=opp_overwrites
            )

            # Judge deliberation voice (judges only)
            judge_overwrites = {everyone_role: deny_all, guild.me: bot_perms}
            for member in judge_members:
                judge_overwrites[member] = allow_view_connect
            judges_vc = await category.create_voice_channel(
                name=f"round-{round_id}-judges",
                overwrites=judge_overwrites
            )

            # Judges-only text channel (chair controls + ballot button hidden from debaters)
            judge_text_overwrites = {everyone_role: deny_all, guild.me: bot_perms}
            for member in judge_members:
                judge_text_overwrites[member] = allow_view_connect
            judges_text_channel = await category.create_text_channel(
                name=f"round-{round_id}-judges-text",
                overwrites=judge_text_overwrites
            )

            debate_round.channel_ids = {
                "text": text_channel.id,
                "debate": debate_vc.id,
                "gov_prep": gov_prep_vc.id,
                "opp_prep": opp_prep_vc.id,
                "judges": judges_vc.id,
                "judges_text": judges_text_channel.id,
            }

            # Track as active round
            matchmaking_cog.add_active_round(debate_round)

            # Post round info embed in shared text channel (no ballot button — judges-only)
            round_embed = EmbedBuilder.create_round_text_channel_embed(debate_round)
            round_info_message = await text_channel.send(embed=round_embed)

            # Post ballot button in judges-only text channel
            ballot_view = SubmitBallotView(self, round_id)
            self.bot.add_view(ballot_view)
            ballot_embed = EmbedBuilder.create_success_embed(
                f"Round {round_id} — Judge Controls",
                "Use the button below to submit your ballot when the debate is complete."
            )
            await judges_text_channel.send(embed=ballot_embed, view=ballot_view)

            # Post chair judge controls in judges-only text channel
            chair_view = ChairJudgeControlView(self, debate_round, round_info_message)
            if debate_round.format_label == "AP":
                chair_embed = EmbedBuilder.create_ap_motion_input_embed(chair_view.pending_motions)
            else:
                chair_embed = EmbedBuilder.create_chair_control_embed(debate_round)
            chair_view.message = await judges_text_channel.send(embed=chair_embed, view=chair_view)
            self._chair_views[debate_round.round_id] = chair_view

            await self.send_round_confirmed_dms(debate_round)
            await self.move_to_prep_channels(guild, debate_round)

            logger.info(f"Created channels for round {round_id} in category {category.name}")

        except discord.Forbidden:
            logger.error("Bot lacks Manage Channels permission")
            lobby_channel = self.bot.get_channel(Config.LOBBY_CHANNEL_ID)
            if lobby_channel:
                await lobby_channel.send(
                    embed=EmbedBuilder.create_error_embed(
                        "Channel Creation Failed",
                        "The bot does not have permission to create channels. "
                        "Please grant the Manage Channels permission."
                    )
                )
        except Exception as e:
            logger.error(f"Error creating round channels: {e}", exc_info=True)

    async def move_to_prep_channels(self, guild: discord.Guild, debate_round: DebateRound):
        """Move all participants to their assigned prep/judge VCs."""
        gov_prep_vc = guild.get_channel(debate_round.channel_ids["gov_prep"])
        opp_prep_vc = guild.get_channel(debate_round.channel_ids["opp_prep"])
        judges_vc = guild.get_channel(debate_round.channel_ids["judges"])

        for member in debate_round.government.members:
            try:
                if member.voice:
                    await member.move_to(gov_prep_vc)
            except Exception:
                pass

        for member in debate_round.opposition.members:
            try:
                if member.voice:
                    await member.move_to(opp_prep_vc)
            except Exception:
                pass

        for member in debate_round.judges.get_all_judges():
            try:
                if member.voice:
                    await member.move_to(judges_vc)
            except Exception:
                pass

    async def send_round_confirmed_dms(self, debate_round: DebateRound):
        """DM all participants (debaters + judges) with the debate room link."""
        text_channel_id = debate_round.channel_ids["text"]
        channel_url = f"https://discord.com/channels/{Config.GUILD_ID}/{text_channel_id}"

        embed = EmbedBuilder.create_round_confirmed_dm_embed(debate_round)

        view = discord.ui.View()
        view.add_item(discord.ui.Button(
            style=discord.ButtonStyle.link,
            label="Go to Debate Room",
            url=channel_url
        ))

        for member in debate_round.get_all_participants():
            try:
                await member.send(embed=embed, view=view)
            except discord.Forbidden:
                pass

    async def release_motions(self, debate_round: DebateRound, guild: discord.Guild, duration: int):
        """Post motions to text channel, create veto view, and start both timers (veto + prep)."""
        text_channel = guild.get_channel(debate_round.channel_ids['text'])
        end_timestamp = int(time.time()) + 300

        # Post motions released embed
        motions_embed = EmbedBuilder.create_motions_released_embed(debate_round, end_timestamp)
        await text_channel.send(embed=motions_embed)

        # Post veto buttons
        veto_view = VetoView(debate_round, self)
        veto_embed = EmbedBuilder.create_veto_prompt_embed(debate_round)
        veto_view.message = await text_channel.send(embed=veto_embed, view=veto_view)
        self._veto_views[debate_round.round_id] = veto_view

        # Update round info embed to reflect veto-in-progress state
        chair_view = self._chair_views.get(debate_round.round_id)
        if chair_view and chair_view.round_info_message:
            try:
                await chair_view.round_info_message.edit(
                    embed=EmbedBuilder.create_round_text_channel_embed(debate_round)
                )
            except Exception:
                pass

        # Start 5-minute veto timer
        task = self.bot.loop.create_task(self.run_veto_timer(debate_round, guild))
        debate_round._veto_task = task

        # Start 30-minute prep timer concurrently (veto resolves within this window)
        task = self.bot.loop.create_task(self.run_prep_timer(guild, debate_round, text_channel, duration))
        debate_round._prep_task = task

    async def run_veto_timer(self, debate_round: DebateRound, guild: discord.Guild):
        """5-minute background task; auto-resolves veto if teams don't submit in time."""
        try:
            await asyncio.sleep(300)
        except asyncio.CancelledError:
            return  # Both teams submitted; process_veto already called

        import random
        text_channel = guild.get_channel(debate_round.channel_ids['text'])

        if debate_round.gov_veto is None and debate_round.opp_veto is None:
            # Neither submitted → random pick
            motion_index = random.randrange(len(debate_round.motions))
            if text_channel:
                await text_channel.send(embed=EmbedBuilder.create_veto_timeout_embed("both"))
            await self.resolve_veto_result(debate_round, guild, motion_index)
        elif debate_round.gov_veto is None:
            # Only Opp submitted → Opp's rank-1 motion wins
            motion_index = debate_round.opp_veto.index(1)
            if text_channel:
                await text_channel.send(embed=EmbedBuilder.create_veto_timeout_embed("gov"))
            await self.resolve_veto_result(debate_round, guild, motion_index)
        elif debate_round.opp_veto is None:
            # Only Gov submitted → Gov's rank-1 motion wins
            motion_index = debate_round.gov_veto.index(1)
            if text_channel:
                await text_channel.send(embed=EmbedBuilder.create_veto_timeout_embed("opp"))
            await self.resolve_veto_result(debate_round, guild, motion_index)
        # else: both submitted already — process_veto was already called

    async def process_veto(self, debate_round: DebateRound, guild: discord.Guild):
        """Determine the debated motion from both teams' veto rankings."""
        gov_veto = debate_round.gov_veto
        opp_veto = debate_round.opp_veto
        n = len(debate_round.motions)

        # Non-vetoed: neither team ranked this motion as 3 (least favored)
        non_vetoed = [i for i in range(n) if gov_veto[i] != 3 and opp_veto[i] != 3]

        if len(non_vetoed) == 1:
            # Clear winner
            await self.resolve_veto_result(debate_round, guild, non_vetoed[0])
        elif len(non_vetoed) >= 2:
            # Tie: both teams vetoed the same motion
            gov_preferred = min(non_vetoed, key=lambda i: gov_veto[i])
            opp_preferred = min(non_vetoed, key=lambda i: opp_veto[i])
            if gov_preferred == opp_preferred:
                # Both teams prefer the same tied motion — no coin toss needed
                await self.resolve_veto_result(debate_round, guild, gov_preferred)
            else:
                await self.start_coin_toss(debate_round, guild, non_vetoed, gov_preferred, opp_preferred)
        else:
            # Fallback (mathematically shouldn't occur): pick lowest combined rank sum
            sums = [gov_veto[i] + opp_veto[i] for i in range(n)]
            await self.resolve_veto_result(debate_round, guild, sums.index(min(sums)))

    async def start_coin_toss(self, debate_round: DebateRound, guild: discord.Guild,
                               tied_indices: list, gov_preferred: int, opp_preferred: int):
        """Post coin toss view in text channel."""
        text_channel = guild.get_channel(debate_round.channel_ids['text'])
        coin_embed = EmbedBuilder.create_coin_toss_embed(
            debate_round, tied_indices, gov_preferred, opp_preferred
        )
        view = CoinTossView(debate_round, self, tied_indices, gov_preferred, opp_preferred)
        view.message = await text_channel.send(embed=coin_embed, view=view)

    async def flip_coin(self, debate_round: DebateRound, guild: discord.Guild,
                        view: CoinTossView, message: discord.Message):
        """Flip the coin and resolve the veto based on the result."""
        import random
        result = random.choice(['heads', 'tails'])
        winner_team = 'Government' if view.gov_call == result else 'Opposition'
        motion_index = view.gov_preferred_idx if view.gov_call == result else view.opp_preferred_idx
        winning_motion = debate_round.motions[motion_index]

        result_embed = EmbedBuilder.create_coin_toss_result_embed(
            debate_round, result, winner_team, view.gov_call, view.opp_call, winning_motion
        )
        try:
            await message.edit(embed=result_embed, view=None)
        except Exception:
            pass
        await self.resolve_veto_result(debate_round, guild, motion_index, reason="coin_toss")

    async def resolve_veto_result(self, debate_round: DebateRound, guild: discord.Guild,
                                   motion_index: int, reason: str = "veto"):
        """Set the final motion, post results, and re-enable chair controls."""
        debate_round.motion = debate_round.motions[motion_index]
        debate_round.debated_motion_index = motion_index
        # Propagate the winning motion's infoslide so downstream code (prep DMs, etc.) works unchanged
        if debate_round.motion_infoslides:
            debate_round.infoslide = debate_round.motion_infoslides[motion_index]

        text_channel = guild.get_channel(debate_round.channel_ids['text'])

        # Post veto results embed (skip if coin toss already announced the winner)
        if reason != "coin_toss" and text_channel:
            result_embed = EmbedBuilder.create_veto_results_embed(debate_round)
            await text_channel.send(embed=result_embed)

        # Update round info embed (now shows the single resolved motion)
        chair_view = self._chair_views.get(debate_round.round_id)
        if chair_view and chair_view.round_info_message:
            try:
                await chair_view.round_info_message.edit(
                    embed=EmbedBuilder.create_round_text_channel_embed(debate_round)
                )
            except Exception:
                pass

        # Post prep started embed and DM debaters now that the winning motion is known
        end_ts = getattr(debate_round, '_prep_end_timestamp', None)
        if end_ts and text_channel:
            prep_embed = EmbedBuilder.create_prep_started_embed(debate_round, end_ts)
            await text_channel.send(embed=prep_embed)
            await self.send_prep_dms(debate_round, end_ts)

        # Disable veto view buttons if still visible
        veto_view = self._veto_views.pop(debate_round.round_id, None)
        if veto_view and veto_view.message:
            for child in veto_view.children:
                child.disabled = True
            try:
                await veto_view.message.edit(view=veto_view)
            except Exception:
                pass

    async def send_prep_dms(self, debate_round: DebateRound, end_timestamp: int):
        """DM each debater with their side, the motion, and prep end time."""
        for member in debate_round.government.members:
            try:
                embed = EmbedBuilder.create_prep_dm_embed(
                    debate_round, "Government", end_timestamp
                )
                await member.send(embed=embed)
            except discord.Forbidden:
                pass  # DMs disabled

        for member in debate_round.opposition.members:
            try:
                embed = EmbedBuilder.create_prep_dm_embed(
                    debate_round, "Opposition", end_timestamp
                )
                await member.send(embed=embed)
            except discord.Forbidden:
                pass  # DMs disabled

    async def finalize_ballot(
        self,
        interaction: discord.Interaction,
        debate_round: DebateRound,
        ballot: Ballot,
        ballot_view: SubmitBallotView
    ):
        """Finalize a ballot submission: store, DM judge, DM debaters, post in channel."""
        debate_round.ballot = ballot

        # Cancel prep timer if still running
        if hasattr(debate_round, '_prep_task') and debate_round._prep_task:
            debate_round._prep_task.cancel()

        # Disable the Submit Ballot button
        ballot_view.clear_items()
        btn = discord.ui.Button(
            label="Ballot Submitted",
            style=discord.ButtonStyle.secondary,
            disabled=True,
            custom_id=f"submit_ballot:{ballot_view.round_id}"
        )
        ballot_view.add_item(btn)

        # Find the text channel
        text_channel = interaction.guild.get_channel(debate_round.channel_ids.get("text"))

        # Try to update the original ballot button message
        if text_channel:
            # We can't easily get the original message, so just post updates
            pass

        # DM the judge with full ballot results
        try:
            ballot_embed = EmbedBuilder.create_ballot_results_embed(debate_round)
            await ballot.judge.send(embed=ballot_embed)
        except discord.Forbidden:
            pass

        # DM each debater with "ballot ready" + Rate Judge button
        all_debaters = debate_round.government.members + debate_round.opposition.members
        for debater in all_debaters:
            try:
                embed = EmbedBuilder.create_ballot_ready_dm_embed(debate_round)
                rate_view = RateJudgeView(self, debate_round, debater)
                rate_view.message = await debater.send(embed=embed, view=rate_view)
            except discord.Forbidden:
                pass

        # Post ballot submitted embed in text channel
        if text_channel:
            embed = EmbedBuilder.create_ballot_submitted_embed(debate_round.round_id)
            await text_channel.send(embed=embed)

            # Post the "Mark Round as Complete" button
            complete_view = PostBallotRoundCompleteView(self, debate_round.round_id)
            self.bot.add_view(complete_view)
            channel_embed = EmbedBuilder.create_post_ballot_channel_embed(debate_round.round_id)
            await text_channel.send(embed=channel_embed, view=complete_view)

        logger.info(f"Ballot finalized for round {debate_round.round_id}")

    async def send_judge_ratings(self, debate_round: DebateRound):
        """Send aggregated debater ratings to the judge."""
        judge = debate_round.ballot.judge
        try:
            embed = EmbedBuilder.create_judge_ratings_embed(debate_round, debate_round.judge_ratings)
            await judge.send(embed=embed)
        except discord.Forbidden:
            pass
        logger.info(f"Sent aggregated judge ratings for round {debate_round.round_id}")

    async def run_prep_timer(self, guild: discord.Guild, debate_round: DebateRound, text_channel: discord.TextChannel, duration: int):
        """Run the prep timer and auto-move debaters when done."""
        try:
            await asyncio.sleep(duration)

            # Auto-move debaters from prep VCs to debate VC
            debate_vc = guild.get_channel(debate_round.channel_ids.get("debate"))
            if debate_vc:
                all_debaters = debate_round.government.members + debate_round.opposition.members
                for member in all_debaters:
                    try:
                        if member.voice:
                            await member.move_to(debate_vc)
                    except Exception as e:
                        logger.warning(f"Could not move {member.display_name}: {e}")

            # Post debate started embed
            embed = EmbedBuilder.create_debate_started_embed(debate_round)
            try:
                await text_channel.send(embed=embed)
            except:
                pass

            logger.info(f"Prep timer ended for round {debate_round.round_id}, debaters moved to debate VC")

        except asyncio.CancelledError:
            logger.info(f"Prep timer cancelled for round {debate_round.round_id}")

    async def delete_round_channels(self, guild: discord.Guild, round_id: int):
        """Delete all channels and category for a round."""
        matchmaking_cog = self.bot.get_cog("Matchmaking")
        debate_round = matchmaking_cog.active_rounds.get(round_id) if matchmaking_cog else None

        category = None
        if debate_round and debate_round.category_id:
            category = guild.get_channel(debate_round.category_id)

        # Fallback: search by name if category reference is lost
        if not category:
            for cat in guild.categories:
                if cat.name.startswith(f"Round {round_id} -"):
                    category = cat
                    break

        if category:
            for channel in category.channels:
                try:
                    await channel.delete(reason=f"Round {round_id} complete")
                except Exception as e:
                    logger.error(f"Error deleting channel {channel.name}: {e}")

            try:
                await category.delete(reason=f"Round {round_id} complete")
            except Exception as e:
                logger.error(f"Error deleting category: {e}")

            logger.info(f"Deleted channels for round {round_id}")

    def _get_round_label(self, debate_round: DebateRound) -> str:
        """Generate a human-readable label for the round type."""
        labels = {
            "pm_lo": "PM vs LO",
            "double_iron": "Double Iron",
            "single_iron": "Single Iron",
            "standard": "Standard"
        }
        return labels.get(debate_round.round_type.value, "Debate")


def setup(bot):
    bot.add_cog(Rounds(bot))
