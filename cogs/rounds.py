import asyncio
import discord
from discord.ext import commands
import logging
import time
from typing import Optional

from utils.models import DebateRound, RoundType, SpeakerScore, Ballot, JudgeRating
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

    async def _cancel_round(self, reason: str):
        """Cancel the round, re-queue participants, update message."""
        self.declined = True
        self.stop()

        # Re-queue all participants
        self.matchmaking_cog.requeue_participants(self.debate_round)
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

        await interaction.response.defer()
        await self._cancel_round(
            f"{interaction.user.mention} declined. Round cancelled."
        )


class SubmitBallotView(discord.ui.View):
    """Persistent view for submitting a ballot."""

    def __init__(self, rounds_cog, round_id: int):
        super().__init__(timeout=None)
        self.rounds_cog = rounds_cog
        self.round_id = round_id
        # Temporary storage for page 1 data during two-page flow
        self.pending_winner: Optional[str] = None
        self.pending_gov_scores: list = []

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

        # Verify user is a judge
        judge_ids = {j.id for j in debate_round.judges.get_all_judges()}
        if interaction.user.id not in judge_ids:
            await interaction.response.send_message(
                "Only judges can submit the ballot.", ephemeral=True
            )
            return

        # Check if ballot already submitted
        if debate_round.ballot is not None:
            await interaction.response.send_message(
                "A ballot has already been submitted for this round.", ephemeral=True
            )
            return

        modal = BallotPage1Modal(self, debate_round, interaction.user)
        await interaction.response.send_modal(modal)


class BallotPage1Modal(discord.ui.Modal):
    """Modal for entering winner and government speaker scores."""

    def __init__(self, ballot_view: SubmitBallotView, debate_round: DebateRound, judge: discord.Member):
        super().__init__(title="Submit Ballot — Page 1")
        self.ballot_view = ballot_view
        self.debate_round = debate_round
        self.judge = judge
        self.is_1v1 = debate_round.round_type == RoundType.PM_LO

        # Winner field
        self.winner_input = discord.ui.InputText(
            label="Winner",
            placeholder="Government or Opposition",
            style=discord.InputTextStyle.short,
            required=True
        )
        self.add_item(self.winner_input)

        # Gov speaker score fields
        self.gov_inputs = []
        for i, member in enumerate(debate_round.government.members):
            position = debate_round.government.get_position_name(i)
            inp = discord.ui.InputText(
                label=f"{position} Score ({member.display_name})",
                placeholder="50-100",
                style=discord.InputTextStyle.short,
                required=True
            )
            self.add_item(inp)
            self.gov_inputs.append((inp, member, position))

        # For 1v1, also include the single opp speaker
        self.opp_inputs = []
        if self.is_1v1:
            for i, member in enumerate(debate_round.opposition.members):
                position = debate_round.opposition.get_position_name(i)
                inp = discord.ui.InputText(
                    label=f"{position} Score ({member.display_name})",
                    placeholder="50-100",
                    style=discord.InputTextStyle.short,
                    required=True
                )
                self.add_item(inp)
                self.opp_inputs.append((inp, member, position))

    async def callback(self, interaction: discord.Interaction):
        # Parse winner
        winner_raw = self.winner_input.value.strip().lower()
        if winner_raw in ("gov", "government"):
            winner = "Government"
        elif winner_raw in ("opp", "opposition"):
            winner = "Opposition"
        else:
            await interaction.response.send_message(
                "Invalid winner. Please enter 'Government' or 'Opposition'.", ephemeral=True
            )
            return

        # Parse gov scores
        gov_scores = []
        for inp, member, position in self.gov_inputs:
            try:
                score = int(inp.value.strip())
            except ValueError:
                await interaction.response.send_message(
                    f"Invalid score for {position}. Please enter a number between 50-100.", ephemeral=True
                )
                return
            gov_scores.append(SpeakerScore(member=member, position_name=position, score=score))

        if self.is_1v1:
            # Parse opp scores and finalize immediately
            opp_scores = []
            for inp, member, position in self.opp_inputs:
                try:
                    score = int(inp.value.strip())
                except ValueError:
                    await interaction.response.send_message(
                        f"Invalid score for {position}. Please enter a number between 50-100.", ephemeral=True
                    )
                    return
                opp_scores.append(SpeakerScore(member=member, position_name=position, score=score))

            ballot = Ballot(judge=self.judge, winner=winner, gov_scores=gov_scores, opp_scores=opp_scores)
            error = ballot.validate()
            if error:
                await interaction.response.send_message(f"Validation error: {error}", ephemeral=True)
                return

            await interaction.response.defer()
            await self.ballot_view.rounds_cog.finalize_ballot(
                interaction, self.debate_round, ballot, self.ballot_view
            )
        else:
            # Store page 1 data, show continue button for page 2
            self.ballot_view.pending_winner = winner
            self.ballot_view.pending_gov_scores = gov_scores

            continue_view = BallotPage2ContinueView(
                self.ballot_view, self.debate_round, self.judge
            )
            await interaction.response.send_message(
                "Government scores recorded. Click below to enter Opposition scores.",
                view=continue_view,
                ephemeral=True
            )


class BallotPage2ContinueView(discord.ui.View):
    """Ephemeral view with a button to open the second ballot modal."""

    def __init__(self, ballot_view: SubmitBallotView, debate_round: DebateRound, judge: discord.Member):
        super().__init__(timeout=300)
        self.ballot_view = ballot_view
        self.debate_round = debate_round
        self.judge = judge

    @discord.ui.button(label="Continue to Opposition Scores", style=discord.ButtonStyle.primary)
    async def continue_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        modal = BallotPage2Modal(self.ballot_view, self.debate_round, self.judge)
        await interaction.response.send_modal(modal)


class BallotPage2Modal(discord.ui.Modal):
    """Modal for entering opposition speaker scores (page 2)."""

    def __init__(self, ballot_view: SubmitBallotView, debate_round: DebateRound, judge: discord.Member):
        super().__init__(title="Submit Ballot — Opposition Scores")
        self.ballot_view = ballot_view
        self.debate_round = debate_round
        self.judge = judge

        self.opp_inputs = []
        for i, member in enumerate(debate_round.opposition.members):
            position = debate_round.opposition.get_position_name(i)
            inp = discord.ui.InputText(
                label=f"{position} Score ({member.display_name})",
                placeholder="50-100",
                style=discord.InputTextStyle.short,
                required=True
            )
            self.add_item(inp)
            self.opp_inputs.append((inp, member, position))

    async def callback(self, interaction: discord.Interaction):
        opp_scores = []
        for inp, member, position in self.opp_inputs:
            try:
                score = int(inp.value.strip())
            except ValueError:
                await interaction.response.send_message(
                    f"Invalid score for {position}. Please enter a number between 50-100.", ephemeral=True
                )
                return
            opp_scores.append(SpeakerScore(member=member, position_name=position, score=score))

        ballot = Ballot(
            judge=self.judge,
            winner=self.ballot_view.pending_winner,
            gov_scores=self.ballot_view.pending_gov_scores,
            opp_scores=opp_scores
        )
        error = ballot.validate()
        if error:
            await interaction.response.send_message(f"Validation error: {error}", ephemeral=True)
            return

        await interaction.response.defer()
        await self.ballot_view.rounds_cog.finalize_ballot(
            interaction, self.debate_round, ballot, self.ballot_view
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

        # Cancel prep timer if still running
        if debate_round and hasattr(debate_round, '_prep_task') and debate_round._prep_task:
            debate_round._prep_task.cancel()

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

    async def callback(self, interaction: discord.Interaction):
        motion = self.motion_input.value.strip()
        if not motion:
            await interaction.response.send_message(
                "Motion cannot be empty.", ephemeral=True
            )
            return

        debate_round = self.chair_view.debate_round
        debate_round.motion = motion

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


class ChairJudgeControlView(discord.ui.View):
    """View for chair judge to control the round (enter motion, start prep)."""

    def __init__(self, rounds_cog, debate_round: DebateRound, round_info_message: discord.Message):
        super().__init__(timeout=None)
        self.rounds_cog = rounds_cog
        self.debate_round = debate_round
        self.round_info_message = round_info_message
        self.message: Optional[discord.Message] = None
        self.chair_id = debate_round.judges.chair.id

        # Start with "Enter Motion" button
        self._setup_enter_motion()

    def _setup_enter_motion(self):
        """Show the Enter Motion button."""
        self.clear_items()
        btn = discord.ui.Button(
            label="Enter Motion",
            style=discord.ButtonStyle.primary
        )
        btn.callback = self._enter_motion_callback
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
        """Handle Enter Motion button click."""
        if interaction.user.id != self.chair_id:
            await interaction.response.send_message(
                "Only the chair judge can enter the motion.", ephemeral=True
            )
            return

        modal = MotionInputModal(self)
        await interaction.response.send_modal(modal)

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

        # Auto-move participants to their prep/judge VCs
        guild = interaction.guild
        gov_prep_vc = guild.get_channel(self.debate_round.channel_ids["gov_prep"])
        opp_prep_vc = guild.get_channel(self.debate_round.channel_ids["opp_prep"])
        judges_vc = guild.get_channel(self.debate_round.channel_ids["judges"])

        for member in self.debate_round.government.members:
            try:
                if member.voice:
                    await member.move_to(gov_prep_vc)
            except Exception:
                pass

        for member in self.debate_round.opposition.members:
            try:
                if member.voice:
                    await member.move_to(opp_prep_vc)
            except Exception:
                pass

        for member in self.debate_round.judges.get_all_judges():
            try:
                if member.voice:
                    await member.move_to(judges_vc)
            except Exception:
                pass

        # DM debaters with motion, side, and prep end time
        await self.rounds_cog.send_prep_dms(self.debate_round, end_timestamp)

        # Start background prep timer
        task = self.rounds_cog.bot.loop.create_task(
            self.rounds_cog.run_prep_timer(guild, self.debate_round, text_channel, duration)
        )
        self.debate_round._prep_task = task


class Rounds(commands.Cog):
    """Cog handling round lifecycle: confirmation, channels, completion."""

    def __init__(self, bot):
        self.bot = bot

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

            debate_round.channel_ids = {
                "text": text_channel.id,
                "debate": debate_vc.id,
                "gov_prep": gov_prep_vc.id,
                "opp_prep": opp_prep_vc.id,
                "judges": judges_vc.id
            }

            # Track as active round
            matchmaking_cog.add_active_round(debate_round)

            # Register persistent ballot view
            ballot_view = SubmitBallotView(self, round_id)
            self.bot.add_view(ballot_view)

            # Post round info + ballot button in text channel
            round_embed = EmbedBuilder.create_round_text_channel_embed(debate_round)
            round_info_message = await text_channel.send(embed=round_embed, view=ballot_view)

            # Post chair judge controls
            chair_view = ChairJudgeControlView(self, debate_round, round_info_message)
            chair_embed = EmbedBuilder.create_chair_control_embed(debate_round)
            chair_view.message = await text_channel.send(embed=chair_embed, view=chair_view)

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
