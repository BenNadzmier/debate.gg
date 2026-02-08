import discord
from typing import List
from utils.models import DebateRound, MatchmakingQueue, RoundType, TeamType


class EmbedBuilder:
    """Utility class for building Discord embeds."""

    COLOR_PRIMARY = 0x5865F2
    COLOR_SUCCESS = 0x57F287
    COLOR_WARNING = 0xFEE75C
    COLOR_DANGER = 0xED4245
    COLOR_GOV = 0x3498DB  # Blue for Government
    COLOR_OPP = 0xE74C3C  # Red for Opposition

    @staticmethod
    def create_lobby_embed(queue: MatchmakingQueue) -> discord.Embed:
        """Create the lobby embed showing queued users."""
        embed = discord.Embed(
            title="🎭 AP Debate Matchmaking Lobby",
            description="Join the queue to participate in a debate round!",
            color=EmbedBuilder.COLOR_PRIMARY
        )

        if queue.size() == 0:
            embed.add_field(
                name="Queue Status",
                value="*No one in queue*\nUse `/queue` to join!",
                inline=False
            )
        else:
            user_list = "\n".join([f"{i+1}. {user.mention}" for i, user in enumerate(queue.users)])
            embed.add_field(
                name=f"Queued Users ({queue.size()})",
                value=user_list,
                inline=False
            )

        # Show threshold information
        threshold_info = EmbedBuilder._get_threshold_info(queue.size())
        embed.add_field(
            name="Matchmaking Thresholds",
            value=threshold_info,
            inline=False
        )

        embed.set_footer(text="Use /queue to join • Use /leave to exit queue")
        return embed

    @staticmethod
    def _get_threshold_info(queue_size: int) -> str:
        """Get threshold information based on current queue size."""
        thresholds = [
            ("5 Players", "Double Iron Round (2v2 + 1 Judge)"),
            ("6 Players", "Single Iron Round (3v2 + 1 Judge)"),
            ("7+ Players", "Standard Round (3v3 + Judge(s))")
        ]

        lines = []
        for count, desc in thresholds:
            count_num = int(count.split()[0].rstrip('+'))
            if queue_size >= count_num:
                lines.append(f"✅ **{count}**: {desc}")
            else:
                lines.append(f"⬜ **{count}**: {desc}")

        return "\n".join(lines)

    @staticmethod
    def create_host_notification_embed(queue_size: int, round_type: RoundType) -> discord.Embed:
        """Create notification embed for the host channel."""
        embed = discord.Embed(
            title="🔔 Matchmaking Ready!",
            color=EmbedBuilder.COLOR_WARNING
        )

        if round_type == RoundType.DOUBLE_IRON:
            embed.description = f"**{queue_size} players** are ready for a **Double Iron Round** (2v2)!"
            embed.add_field(
                name="Configuration",
                value="• Government: 2 Debaters (Iron)\n• Opposition: 2 Debaters (Iron)\n• Judges: 1 Chair",
                inline=False
            )
        elif round_type == RoundType.SINGLE_IRON:
            embed.description = f"**{queue_size} players** are ready for a **Single Iron Round**!"
            embed.add_field(
                name="Configuration",
                value="• One Full Team: 3 Debaters\n• One Iron Team: 2 Debaters\n• Judges: 1 Chair",
                inline=False
            )
        elif round_type == RoundType.STANDARD:
            extra_judges = queue_size - 7
            embed.description = f"**{queue_size} players** are ready!"
            config_text = "• Government: 3 Debaters\n• Opposition: 3 Debaters\n• Judges: 1 Chair"
            if extra_judges > 0:
                config_text += f" + {extra_judges} Panelist{'s' if extra_judges > 1 else ''}"
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
            title="📋 Round Allocation",
            description="Review the allocations below. Use the controls to make adjustments.",
            color=EmbedBuilder.COLOR_PRIMARY
        )

        # Government Team
        gov_text = EmbedBuilder._format_team_text(debate_round.government)
        embed.add_field(
            name=f"🔵 Government Team ({debate_round.government.team_type.value.title()})",
            value=gov_text,
            inline=True
        )

        # Opposition Team
        opp_text = EmbedBuilder._format_team_text(debate_round.opposition)
        embed.add_field(
            name=f"🔴 Opposition Team ({debate_round.opposition.team_type.value.title()})",
            value=opp_text,
            inline=True
        )

        # Add spacer
        embed.add_field(name="\u200b", value="\u200b", inline=False)

        # Judges
        judge_text = EmbedBuilder._format_judge_text(debate_round.judges)
        embed.add_field(
            name="⚖️ Judging Panel",
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
            title="🎭 Debate Round Starting!",
            description=f"**Motion**: {motion}",
            color=EmbedBuilder.COLOR_SUCCESS
        )

        # Government Team
        gov_text = EmbedBuilder._format_team_text(debate_round.government)
        embed.add_field(
            name=f"🔵 Government Team",
            value=gov_text,
            inline=True
        )

        # Opposition Team
        opp_text = EmbedBuilder._format_team_text(debate_round.opposition)
        embed.add_field(
            name=f"🔴 Opposition Team",
            value=opp_text,
            inline=True
        )

        # Add spacer
        embed.add_field(name="\u200b", value="\u200b", inline=False)

        # Judges
        judge_text = EmbedBuilder._format_judge_text(debate_round.judges)
        embed.add_field(
            name="⚖️ Judging Panel",
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
    def create_error_embed(title: str, message: str) -> discord.Embed:
        """Create an error embed."""
        embed = discord.Embed(
            title=f"❌ {title}",
            description=message,
            color=EmbedBuilder.COLOR_DANGER
        )
        return embed

    @staticmethod
    def create_success_embed(title: str, message: str) -> discord.Embed:
        """Create a success embed."""
        embed = discord.Embed(
            title=f"✅ {title}",
            description=message,
            color=EmbedBuilder.COLOR_SUCCESS
        )
        return embed
