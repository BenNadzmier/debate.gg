import discord
from typing import List
from utils.models import DebateRound, MatchmakingQueue, RoundType, TeamType, FormatType


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
    def create_host_notification_embed(debater_count: int, judge_count: int, round_type: RoundType) -> discord.Embed:
        """Create notification embed for the host channel."""
        total = debater_count + judge_count
        embed = discord.Embed(
            title="Matchmaking Ready!",
            color=EmbedBuilder.COLOR_WARNING
        )

        if round_type == RoundType.PM_LO:
            embed.description = f"**{debater_count} debaters + {judge_count} judge(s)** ({total} total) ready for a **1v1 Round** (PM vs LO)!"
            embed.add_field(
                name="Configuration",
                value=f"Government: 1 Debater (PM)\nOpposition: 1 Debater (LO)\nJudge: {judge_count}",
                inline=False
            )
        elif round_type == RoundType.DOUBLE_IRON:
            embed.description = f"**{debater_count} debaters + {judge_count} judge(s)** ({total} total) ready for a **Double Iron Round** (2v2)!"
            embed.add_field(
                name="Configuration",
                value=f"Government: 2 Debaters (Iron)\nOpposition: 2 Debaters (Iron)\nJudges: {judge_count} (Chair" + (f" + {judge_count-1} Panelist(s)" if judge_count > 1 else "") + ")",
                inline=False
            )
        elif round_type == RoundType.SINGLE_IRON:
            embed.description = f"**{debater_count} debaters + {judge_count} judge(s)** ({total} total) ready for a **Single Iron Round**!"
            embed.add_field(
                name="Configuration",
                value=f"One Full Team: 3 Debaters\nOne Iron Team: 2 Debaters\nJudges: {judge_count} (Chair" + (f" + {judge_count-1} Panelist(s)" if judge_count > 1 else "") + ")",
                inline=False
            )
        elif round_type == RoundType.STANDARD:
            embed.description = f"**{debater_count} debaters + {judge_count} judge(s)** ({total} total) ready for a **Standard Round**!"
            config_text = f"Government: 3 Debaters\nOpposition: 3 Debaters\nJudges: {judge_count} (Chair"
            if judge_count > 1:
                config_text += f" + {judge_count-1} Panelist{'s' if judge_count > 2 else ''}"
            config_text += ")"
            embed.add_field(
                name="Configuration",
                value=config_text,
                inline=False
            )

        embed.set_footer(text="Click a button below to start the round")
        return embed

    @staticmethod
    def create_allocation_embed(debate_round: DebateRound) -> discord.Embed:
        """Create the allocation embed showing team and judge assignments."""
        embed = discord.Embed(
            title="Round Allocation",
            description="Review the allocations below. Use the controls to make adjustments.",
            color=EmbedBuilder.COLOR_PRIMARY
        )

        # Government Team
        gov_text = EmbedBuilder._format_team_text(debate_round.government)
        embed.add_field(
            name=f"Government Team ({debate_round.government.team_type.value.title()})",
            value=gov_text,
            inline=True
        )

        # Opposition Team
        opp_text = EmbedBuilder._format_team_text(debate_round.opposition)
        embed.add_field(
            name=f"Opposition Team ({debate_round.opposition.team_type.value.title()})",
            value=opp_text,
            inline=True
        )

        # Add spacer
        embed.add_field(name="\u200b", value="\u200b", inline=False)

        # Judges
        judge_text = EmbedBuilder._format_judge_text(debate_round.judges)
        embed.add_field(
            name="Judging Panel",
            value=judge_text,
            inline=False
        )

        embed.set_footer(text="Use the controls below to adjust allocations")
        return embed

    @staticmethod
    def _format_team_text(team) -> str:
        """Format team member text with positions."""
        if not team.members:
            return "*No members assigned*"

        lines = []
        for i, member in enumerate(team.members):
            position = team.get_position_name(i)
            lines.append(f"**{position}**\n{member.mention}")

        return "\n\n".join(lines)

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
    def create_confirmed_round_embed(debate_round: DebateRound, motion: str) -> discord.Embed:
        """Create the final confirmed round embed."""
        embed = discord.Embed(
            title="Debate Round Starting!",
            description=f"**Motion**: {motion}",
            color=EmbedBuilder.COLOR_SUCCESS
        )

        # Government Team
        gov_text = EmbedBuilder._format_team_text(debate_round.government)
        embed.add_field(
            name="Government Team",
            value=gov_text,
            inline=True
        )

        # Opposition Team
        opp_text = EmbedBuilder._format_team_text(debate_round.opposition)
        embed.add_field(
            name="Opposition Team",
            value=opp_text,
            inline=True
        )

        # Add spacer
        embed.add_field(name="\u200b", value="\u200b", inline=False)

        # Judges
        judge_text = EmbedBuilder._format_judge_text(debate_round.judges)
        embed.add_field(
            name="Judging Panel",
            value=judge_text,
            inline=False
        )

        # Mention all participants
        all_participants = debate_round.get_all_participants()
        participant_mentions = " ".join([p.mention for p in all_participants])
        embed.add_field(
            name="Participants",
            value=participant_mentions,
            inline=False
        )

        embed.set_footer(text="Good luck to all debaters!")
        return embed

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
                "When enough players queue, a host is notified to start the round. "
                "The host can review and adjust allocations before confirming. "
                "Once a motion is set, the round begins!"
            ),
            inline=False
        )

        embed.set_footer(text="Use /queue to get started!")
        return embed

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
