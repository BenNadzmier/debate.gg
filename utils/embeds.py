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
        host_name = queue.host.display_name if queue.host else "Unknown"
        embed = discord.Embed(
            title=f"🎭 {queue.name}",
            description=f"**{host_name}** started a queue\nUse `/join {queue.name} <debater|judge>` to participate!",
            color=EmbedBuilder.COLOR_PRIMARY
        )

        embed.add_field(
            name="Host",
            value=queue.host.mention if queue.host else "*Unknown*",
            inline=True
        )

        embed.add_field(
            name="\u200b",
            value="\u200b",
            inline=True
        )

        embed.add_field(
            name="Lobby Name",
            value=queue.name,
            inline=True
        )

        if queue.size() == 0:
            embed.add_field(
                name="Queue Status",
                value="*No one in queue*",
                inline=False
            )
        else:
            # Debaters list
            if queue.debater_count() > 0:
                debater_list = "\n".join([f"{i+1}. {user.mention}" for i, user in enumerate(queue.debaters)])
            else:
                debater_list = "*No debaters in queue*"

            embed.add_field(
                name=f"🗣️ Debaters ({queue.debater_count()})",
                value=debater_list,
                inline=True
            )

            # Judges list
            if queue.judge_count() > 0:
                judge_list = "\n".join([f"{i+1}. {user.mention}" for i, user in enumerate(queue.judges)])
            else:
                judge_list = "*No judges in queue*"

            embed.add_field(
                name=f"⚖️ Judges ({queue.judge_count()})",
                value=judge_list,
                inline=True
            )

        # Show threshold information
        threshold_info = EmbedBuilder._get_threshold_info(queue.debater_count(), queue.judge_count())
        embed.add_field(
            name="Matchmaking Thresholds",
            value=threshold_info,
            inline=False
        )

        embed.set_footer(text=f"Use /join {queue.name} <debater|judge> to join • Use /leave {queue.name} to exit")
        return embed

    @staticmethod
    def create_lobbies_list_embed(lobbies: list, user: 'discord.Member') -> discord.Embed:
        """Create an embed listing all lobbies a user is part of."""
        embed = discord.Embed(
            title="📋 Your Lobbies",
            color=EmbedBuilder.COLOR_PRIMARY
        )

        if not lobbies:
            embed.description = "You are not in any lobbies."
        else:
            lines = []
            for lobby in lobbies:
                role = lobby.get_user_role(user)
                is_host = lobby.host == user
                role_str = "Host" if is_host else (role.title() if role else "—")
                lines.append(
                    f"**{lobby.name}** — {role_str} "
                    f"({lobby.debater_count()} debaters, {lobby.judge_count()} judges)"
                )
            embed.description = "\n".join(lines)

        embed.set_footer(text="Use /lobby <name> to see details • Use /leave <name> to exit")
        return embed

    @staticmethod
    def _get_threshold_info(debater_count: int, judge_count: int) -> str:
        """Get threshold information based on current queue composition."""
        thresholds = [
            (2, 1, "PM-LO Speech (1v1)"),
            (4, 1, "Double Iron Round (2v2)"),
            (5, 1, "Single Iron Round (3v2 or 2v3)"),
            (6, 1, "Standard Round (3v3)")
        ]

        lines = []
        for debaters_needed, judges_needed, desc in thresholds:
            if debater_count >= debaters_needed and judge_count >= judges_needed:
                status = "✅"
            else:
                status = "⬜"
            lines.append(f"{status} **{debaters_needed} Debaters + {judges_needed} Judge**: {desc}")

        return "\n".join(lines)

    @staticmethod
    def create_host_notification_embed(debater_count: int, judge_count: int, round_type: RoundType) -> discord.Embed:
        """Create notification embed for the host channel."""
        total = debater_count + judge_count
        embed = discord.Embed(
            title="🔔 Matchmaking Ready!",
            color=EmbedBuilder.COLOR_WARNING
        )

        if round_type == RoundType.PM_LO:
            embed.description = f"**{debater_count} debaters + {judge_count} judge(s)** ({total} total) ready for a **PM-LO Speech** (1v1)!"
            embed.add_field(
                name="Configuration",
                value=f"• Government: 1 Debater (PM)\n• Opposition: 1 Debater (LO)\n• Judges: {judge_count} (Chair" + (f" + {judge_count-1} Panelist(s)" if judge_count > 1 else "") + ")",
                inline=False
            )
        elif round_type == RoundType.DOUBLE_IRON:
            embed.description = f"**{debater_count} debaters + {judge_count} judge(s)** ({total} total) ready for a **Double Iron Round** (2v2)!"
            embed.add_field(
                name="Configuration",
                value=f"• Government: 2 Debaters (Iron)\n• Opposition: 2 Debaters (Iron)\n• Judges: {judge_count} (Chair" + (f" + {judge_count-1} Panelist(s)" if judge_count > 1 else "") + ")",
                inline=False
            )
        elif round_type == RoundType.SINGLE_IRON:
            embed.description = f"**{debater_count} debaters + {judge_count} judge(s)** ({total} total) ready for a **Single Iron Round**!"
            embed.add_field(
                name="Configuration",
                value=f"• One Full Team: 3 Debaters\n• One Iron Team: 2 Debaters\n• Judges: {judge_count} (Chair" + (f" + {judge_count-1} Panelist(s)" if judge_count > 1 else "") + ")",
                inline=False
            )
        elif round_type == RoundType.STANDARD:
            embed.description = f"**{debater_count} debaters + {judge_count} judge(s)** ({total} total) ready for a **Standard Round**!"
            config_text = f"• Government: 3 Debaters\n• Opposition: 3 Debaters\n• Judges: {judge_count} (Chair"
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
