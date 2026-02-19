import discord
from typing import List
from utils.models import DebateRound, MatchmakingQueue, RoundType, TeamType, FormatType, Ballot, JudgeRating


class EmbedBuilder:
    """Utility class for building Discord embeds."""

    COLOR_PRIMARY = 0x5865F2
    COLOR_SUCCESS = 0x57F287
    COLOR_WARNING = 0xFEE75C
    COLOR_DANGER = 0xED4245
    COLOR_GOV = 0x3498DB  # Blue for Government
    COLOR_OPP = 0xE74C3C  # Red for Opposition

    @staticmethod
    def create_lobby_embed(queue_1v1: MatchmakingQueue, queue_ap: MatchmakingQueue) -> discord.Embed:
        """Create the lobby embed showing both format queues."""
        embed = discord.Embed(
            title="Debate Matchmaking Lobby",
            description="Use `/queue` to join a format. Use `/guide` for help.",
            color=EmbedBuilder.COLOR_PRIMARY
        )

        # 1v1 section
        members_1v1 = EmbedBuilder._format_queue_members(queue_1v1)
        status_1v1 = EmbedBuilder._get_format_status(queue_1v1)
        embed.add_field(
            name="1v1 Format (PM vs LO)",
            value=f"{members_1v1}\n{status_1v1}",
            inline=False
        )

        # AP section
        members_ap = EmbedBuilder._format_queue_members(queue_ap)
        status_ap = EmbedBuilder._get_format_status(queue_ap)
        embed.add_field(
            name="AP Format (Asian Parliamentary)",
            value=f"{members_ap}\n{status_ap}",
            inline=False
        )

        embed.set_footer(text="/queue <role> <format> to join | /leave to exit")
        return embed

    @staticmethod
    def _format_queue_members(queue: MatchmakingQueue) -> str:
        """Format queue members into a compact display."""
        if queue.debater_count() > 0:
            debater_mentions = ", ".join(u.mention for u in queue.debaters)
            debater_line = f"Debaters ({queue.debater_count()}): {debater_mentions}"
        else:
            debater_line = "Debaters (0): --"

        if queue.judge_count() > 0:
            judge_mentions = ", ".join(u.mention for u in queue.judges)
            judge_line = f"Judges ({queue.judge_count()}): {judge_mentions}"
        else:
            judge_line = "Judges (0): --"

        return f"{debater_line}\n{judge_line}"

    @staticmethod
    def _get_format_status(queue: MatchmakingQueue) -> str:
        """Get status line for a format queue."""
        threshold = queue.get_threshold_type()
        if threshold is not None:
            labels = {
                RoundType.PM_LO: "1v1 (PM vs LO)",
                RoundType.DOUBLE_IRON: "Double Iron (2v2)",
                RoundType.SINGLE_IRON: "Single Iron (3v2)",
                RoundType.STANDARD: "Standard (3v3)",
            }
            return f"**Ready for {labels[threshold]}!**"

        debaters = queue.debater_count()
        judges = queue.judge_count()

        if queue.format_type == FormatType.ONE_V_ONE:
            need_d = max(0, 2 - debaters)
            need_j = max(0, 1 - judges)
        else:
            need_d = max(0, 4 - debaters)
            need_j = max(0, 1 - judges)

        parts = []
        if need_d > 0:
            parts.append(f"{need_d} more debater{'s' if need_d != 1 else ''}")
        if need_j > 0:
            parts.append(f"{need_j} more judge{'s' if need_j != 1 else ''}")

        if parts:
            return f"Need {' and '.join(parts)}"
        return ""

    @staticmethod
    def _format_team_text(team) -> str:
        """Format team member text (no positions — teams decide their own speaker order)."""
        if not team.members:
            return "*No members assigned*"
        return "\n".join(member.mention for member in team.members)

    @staticmethod
    def _format_judge_text(judges) -> str:
        """Format judge text with roles."""
        if not judges.chair:
            return "*No judges assigned*"

        lines = []
        lines.append(f"**Chair Judge**\n{judges.chair.mention}")

        if judges.panelists:
            lines.append("")  # Spacer
            for i, panelist in enumerate(judges.panelists):
                lines.append(f"**Panelist {i+1}**\n{panelist.mention}")

        return "\n\n".join(lines)

    @staticmethod
    def create_guide_embed() -> discord.Embed:
        """Create the guide embed explaining how the bot works."""
        embed = discord.Embed(
            title="Debate Bot Guide",
            description="Everything you need to know about using the debate matchmaking bot.",
            color=EmbedBuilder.COLOR_PRIMARY
        )

        embed.add_field(
            name="How to Queue",
            value=(
                "Use `/queue` and select your **role** (debater or judge) "
                "and **format** (1v1 or AP).\n"
                "Use `/leave` to exit the queue."
            ),
            inline=False
        )

        embed.add_field(
            name="1v1 Format (PM vs LO)",
            value=(
                "A quick head-to-head debate.\n"
                "**Requires:** 2 debaters + 1 judge\n"
                "**Positions:** Prime Minister vs Leader of Opposition\n"
                "One debater argues for the motion, one argues against."
            ),
            inline=False
        )

        embed.add_field(
            name="AP Format (Asian Parliamentary)",
            value=(
                "Full parliamentary-style team debate.\n"
                "**Double Iron (2v2):** 4 debaters + 1 judge\n"
                "**Single Iron (3v2):** 5 debaters + 1 judge\n"
                "**Standard (3v3):** 6 debaters + 1 judge\n\n"
                "**Government:** PM, DPM, Whip\n"
                "**Opposition:** LO, DLO, OW\n"
                "(Iron teams use PM + Whip or LO + OW)"
            ),
            inline=False
        )

        embed.add_field(
            name="What Happens Next",
            value=(
                "When enough players queue, the bot automatically creates a round "
                "with random team allocations. All participants must confirm, then "
                "the chair judge enters the motion and starts prep time. "
                "After prep, debaters are moved to the debate channel automatically."
            ),
            inline=False
        )

        embed.set_footer(text="Use /queue to get started!")
        return embed

    @staticmethod
    def create_participant_confirmation_embed(debate_round, confirmed_ids: set) -> discord.Embed:
        """Create embed for participant confirmation with allocation and status checkmarks."""
        all_participants = debate_round.get_all_participants()
        embed = discord.Embed(
            title="Round Confirmation Required",
            description=(
                "A match has been found! All participants must confirm their availability.\n"
                "Click **Confirm** to accept or **Decline** to cancel."
            ),
            color=EmbedBuilder.COLOR_WARNING
        )

        # Show team allocation
        gov_text = EmbedBuilder._format_team_text(debate_round.government)
        embed.add_field(
            name=f"Government ({debate_round.government.team_type.value.title()})",
            value=gov_text,
            inline=True
        )

        opp_text = EmbedBuilder._format_team_text(debate_round.opposition)
        embed.add_field(
            name=f"Opposition ({debate_round.opposition.team_type.value.title()})",
            value=opp_text,
            inline=True
        )

        embed.add_field(name="\u200b", value="\u200b", inline=False)

        judge_text = EmbedBuilder._format_judge_text(debate_round.judges)
        embed.add_field(
            name="Judging Panel",
            value=judge_text,
            inline=False
        )

        # Confirmation status
        status_lines = []
        for p in all_participants:
            icon = "\u2705" if p.id in confirmed_ids else "\u23f3"
            status_lines.append(f"{icon} {p.mention}")

        embed.add_field(
            name=f"Confirmation ({len(confirmed_ids)}/{len(all_participants)})",
            value="\n".join(status_lines),
            inline=False
        )

        embed.set_footer(text="This confirmation will expire in 90 seconds.")
        return embed

    @staticmethod
    def create_round_cancelled_embed(reason: str) -> discord.Embed:
        """Create embed shown when a round is cancelled."""
        return discord.Embed(
            title="Round Cancelled",
            description=f"{reason}\nAll participants have been returned to the queue.",
            color=EmbedBuilder.COLOR_DANGER
        )

    @staticmethod
    def create_round_text_channel_embed(debate_round) -> discord.Embed:
        """Create the initial embed posted in the round's text channel."""
        embed = discord.Embed(
            title=f"Round {debate_round.round_id}",
            color=EmbedBuilder.COLOR_SUCCESS
        )

        if debate_round.motion:
            embed.description = f"**Motion:** {debate_round.motion}"
        else:
            embed.description = "*Waiting for chair judge to enter the motion...*"

        gov_text = EmbedBuilder._format_team_text(debate_round.government)
        embed.add_field(
            name=f"Government ({debate_round.government.team_type.value.title()})",
            value=gov_text,
            inline=True
        )

        opp_text = EmbedBuilder._format_team_text(debate_round.opposition)
        embed.add_field(
            name=f"Opposition ({debate_round.opposition.team_type.value.title()})",
            value=opp_text,
            inline=True
        )

        embed.add_field(name="\u200b", value="\u200b", inline=False)

        judge_text = EmbedBuilder._format_judge_text(debate_round.judges)
        embed.add_field(
            name="Judging Panel",
            value=judge_text,
            inline=False
        )

        if debate_round.motion:
            embed.set_footer(text="When the round is over, a judge can submit the ballot below.")
        else:
            embed.set_footer(text="Chair judge: use the controls below to set the motion and start prep.")
        return embed

    @staticmethod
    def create_chair_control_embed(debate_round) -> discord.Embed:
        """Create embed for the chair judge control panel."""
        if not debate_round.motion:
            return discord.Embed(
                title="Chair Judge Controls",
                description=(
                    f"**Chair:** {debate_round.judges.chair.mention}\n\n"
                    "Enter the debate motion to get started."
                ),
                color=EmbedBuilder.COLOR_PRIMARY
            )
        else:
            return discord.Embed(
                title="Chair Judge Controls",
                description=(
                    f"**Chair:** {debate_round.judges.chair.mention}\n"
                    f"**Motion:** {debate_round.motion}\n\n"
                    "Start prep time when all participants are ready."
                ),
                color=EmbedBuilder.COLOR_PRIMARY
            )

    @staticmethod
    def create_prep_started_embed(debate_round, end_timestamp: int) -> discord.Embed:
        """Create embed shown when prep time starts."""
        prep_minutes = 15 if debate_round.round_type == RoundType.PM_LO else 30
        embed = discord.Embed(
            title="Prep Time Started!",
            description=(
                f"**Motion:** {debate_round.motion}\n\n"
                f"You have **{prep_minutes} minutes** to prepare.\n"
                f"Prep ends <t:{end_timestamp}:R> (<t:{end_timestamp}:T>)\n\n"
                "Move to your prep channels now!"
            ),
            color=EmbedBuilder.COLOR_WARNING
        )
        embed.add_field(
            name="Government",
            value="Join the **gov-prep** voice channel",
            inline=True
        )
        embed.add_field(
            name="Opposition",
            value="Join the **opp-prep** voice channel",
            inline=True
        )
        return embed

    @staticmethod
    def create_debate_started_embed(debate_round) -> discord.Embed:
        """Create embed shown when prep ends and debate begins."""
        return discord.Embed(
            title="Debate Has Begun!",
            description=(
                f"**Motion:** {debate_round.motion}\n\n"
                "Prep time is over. All debaters have been moved to the debate voice channel.\n"
                "Good luck to both sides!"
            ),
            color=EmbedBuilder.COLOR_SUCCESS
        )

    @staticmethod
    def create_prep_dm_embed(debate_round, side: str, end_timestamp: int) -> discord.Embed:
        """Create a DM embed sent to debaters when prep starts."""
        prep_minutes = 15 if debate_round.round_type == RoundType.PM_LO else 30
        return discord.Embed(
            title=f"Round {debate_round.round_id} — Prep Time",
            description=(
                f"**Side:** {side}\n"
                f"**Motion:** {debate_round.motion}\n\n"
                f"You have **{prep_minutes} minutes** to prepare.\n"
                f"Prep ends <t:{end_timestamp}:R> (<t:{end_timestamp}:T>)"
            ),
            color=EmbedBuilder.COLOR_PRIMARY
        )

    @staticmethod
    def create_round_complete_embed(round_id: int) -> discord.Embed:
        """Create embed shown when a round completes."""
        return discord.Embed(
            title="Round Complete",
            description=f"Round {round_id} has been marked as complete. Channels have been deleted.",
            color=EmbedBuilder.COLOR_SUCCESS
        )

    @staticmethod
    def create_party_invite_embed(host: discord.Member, party_members: list) -> discord.Embed:
        """Create DM embed for a party invitation."""
        members_text = "\n".join(f"- {m.display_name}" for m in party_members)
        return discord.Embed(
            title="Party Invitation",
            description=(
                f"**{host.display_name}** has invited you to join their debate party!\n\n"
                f"**Current Members:**\n{members_text}\n\n"
                "Click **Accept** to join or **Decline** to reject."
            ),
            color=EmbedBuilder.COLOR_PRIMARY
        )

    @staticmethod
    def create_party_status_embed(party, in_queue: bool) -> discord.Embed:
        """Create embed showing party status."""
        members_text = "\n".join(
            f"{'**[Host]** ' if m == party.host else ''}{m.mention}"
            for m in party.members
        )
        status = "In Queue" if in_queue else "Not Queued"
        return discord.Embed(
            title="Your Party",
            description=(
                f"**Members ({party.size}/3):**\n{members_text}\n\n"
                f"**Status:** {status}\n\n"
                "Use `/invite @user` to add members.\n"
                "Use `/leaveparty` to leave."
            ),
            color=EmbedBuilder.COLOR_PRIMARY
        )

    @staticmethod
    def create_ballot_results_embed(debate_round) -> discord.Embed:
        """Create full ballot results embed showing winner, all speaker scores, and totals."""
        ballot = debate_round.ballot
        winner_color = EmbedBuilder.COLOR_GOV if ballot.winner == "Government" else EmbedBuilder.COLOR_OPP

        embed = discord.Embed(
            title=f"Round {debate_round.round_id} — Ballot Results",
            description=f"**Motion:** {debate_round.motion}",
            color=winner_color
        )

        # Government scores
        gov_lines = []
        for s in ballot.gov_scores:
            gov_lines.append(f"**{s.position_name}** ({s.member.display_name}): **{s.score}**")
        if ballot.gov_reply:
            gov_lines.append(f"**Reply** ({ballot.gov_reply.member.display_name}): **{ballot.gov_reply.score}**")
        gov_lines.append(f"\nTotal: **{ballot.gov_total}**")
        win_tag = " ✦ WINNER" if ballot.winner == "Government" else ""
        embed.add_field(
            name=f"Government{win_tag}",
            value="\n".join(gov_lines),
            inline=True
        )

        # Opposition scores
        opp_lines = []
        for s in ballot.opp_scores:
            opp_lines.append(f"**{s.position_name}** ({s.member.display_name}): **{s.score}**")
        if ballot.opp_reply:
            opp_lines.append(f"**Reply** ({ballot.opp_reply.member.display_name}): **{ballot.opp_reply.score}**")
        opp_lines.append(f"\nTotal: **{ballot.opp_total}**")
        win_tag = " ✦ WINNER" if ballot.winner == "Opposition" else ""
        embed.add_field(
            name=f"Opposition{win_tag}",
            value="\n".join(opp_lines),
            inline=True
        )

        embed.set_footer(text=f"Judged by {ballot.judge.display_name}")
        return embed

    @staticmethod
    def create_ballot_ready_dm_embed(debate_round) -> discord.Embed:
        """Create DM embed telling debaters the ballot is ready and they need to rate the judge."""
        return discord.Embed(
            title=f"Round {debate_round.round_id} — Ballot Ready",
            description=(
                "The judge has submitted the ballot for your round.\n\n"
                "**Rate the judge to see your results.** Click the button below to submit your rating."
            ),
            color=EmbedBuilder.COLOR_PRIMARY
        )

    @staticmethod
    def create_judge_ratings_embed(debate_round, ratings: list) -> discord.Embed:
        """Create DM embed for the judge showing aggregated debater ratings."""
        if not ratings:
            avg_score = 0
        else:
            avg_score = sum(r.score for r in ratings) / len(ratings)

        embed = discord.Embed(
            title=f"Round {debate_round.round_id} — Your Judge Ratings",
            description=f"**Average Score:** {avg_score:.1f} / 10",
            color=EmbedBuilder.COLOR_PRIMARY
        )

        feedback_lines = []
        for r in ratings:
            line = f"**{r.debater.display_name}:** {r.score}/10"
            if r.feedback:
                line += f"\n> {r.feedback}"
            feedback_lines.append(line)

        if feedback_lines:
            embed.add_field(
                name="Individual Ratings",
                value="\n\n".join(feedback_lines),
                inline=False
            )

        embed.set_footer(text="Thank you for judging!")
        return embed

    @staticmethod
    def create_ballot_submitted_embed(round_id: int) -> discord.Embed:
        """Create embed posted in text channel after ballot submission."""
        return discord.Embed(
            title="Ballot Submitted",
            description=f"The ballot for Round {round_id} has been submitted. Debaters have been notified.",
            color=EmbedBuilder.COLOR_SUCCESS
        )

    @staticmethod
    def create_post_ballot_channel_embed(round_id: int) -> discord.Embed:
        """Create embed accompanying the Mark Round as Complete button after ballot."""
        return discord.Embed(
            title="Round Channels",
            description=(
                f"The ballot for Round {round_id} has been submitted.\n"
                "When you're ready, click below to delete the round channels."
            ),
            color=EmbedBuilder.COLOR_PRIMARY
        )

    @staticmethod
    def create_error_embed(title: str, message: str) -> discord.Embed:
        """Create an error embed."""
        embed = discord.Embed(
            title=f"{title}",
            description=message,
            color=EmbedBuilder.COLOR_DANGER
        )
        return embed

    @staticmethod
    def create_success_embed(title: str, message: str) -> discord.Embed:
        """Create a success embed."""
        embed = discord.Embed(
            title=f"{title}",
            description=message,
            color=EmbedBuilder.COLOR_SUCCESS
        )
        return embed

    @staticmethod
    def create_round_confirmed_dm_embed(debate_round) -> discord.Embed:
        """Create a DM embed sent to all participants when round channels are ready."""
        embed = discord.Embed(
            title=f"Round {debate_round.round_id} — Your Room Is Ready!",
            description=(
                f"Your debate round has been confirmed and channels have been created.\n\n"
                f"**Format:** {debate_round.format_label}\n"
                f"**Text Channel:** <#{debate_round.channel_ids['text']}>\n\n"
                "Click the button below to jump to your debate room."
            ),
            color=EmbedBuilder.COLOR_SUCCESS
        )
        embed.set_footer(text="DMs must stay enabled to receive prep and ballot notifications.")
        return embed

    @staticmethod
    def create_welcome_dm_embed(guild_name: str) -> discord.Embed:
        """Create a welcome DM embed for new server members."""
        embed = discord.Embed(
            title=f"Welcome to {guild_name}!",
            description=(
                "This server uses a debate matchmaking bot to organize rounds. "
                "Queue up, get matched, and debate!"
            ),
            color=EmbedBuilder.COLOR_PRIMARY
        )

        embed.add_field(
            name="How It Works",
            value=(
                "1. Join a queue as a **debater** or **judge**\n"
                "2. Once enough players queue, a round is created\n"
                "3. All participants confirm, then channels are set up\n"
                "4. The chair judge enters the motion and starts prep time\n"
                "5. After prep, debate in the voice channel\n"
                "6. The judge submits the ballot with scores and results"
            ),
            inline=False
        )

        embed.add_field(
            name="Formats",
            value=(
                "**1v1** — PM vs LO with 1 judge\n"
                "**AP (Asian Parliamentary)** — 3v3, 2v2, or mixed teams with judges"
            ),
            inline=False
        )

        embed.add_field(
            name="Commands",
            value=(
                "`/queue` — Join a debate queue\n"
                "`/leave` — Leave the queue\n"
                "`/invite @user` — Invite someone to your party (AP)\n"
                "`/party` — View your current party\n"
                "`/leaveparty` — Leave your party\n"
                "`/guide` — Full guide with details"
            ),
            inline=False
        )

        embed.set_footer(text="DMs must be enabled to receive round notifications.")
        return embed
