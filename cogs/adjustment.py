import discord
from discord.ext import commands
from typing import Optional

from utils.models import DebateRound, TeamType
from utils.embeds import EmbedBuilder


class AllocationAdjustmentView(discord.ui.View):
    """View for adjusting round allocations before confirmation."""

    def __init__(self, matchmaking_cog, debate_round: DebateRound):
        super().__init__(timeout=600)  # 10 minute timeout
        self.matchmaking_cog = matchmaking_cog
        self.debate_round = debate_round
        self.message: Optional[discord.Message] = None

    async def on_timeout(self):
        """Handle view timeout."""
        if self.message:
            for item in self.children:
                item.disabled = True
            try:
                await self.message.edit(view=self)
            except:
                pass

    @discord.ui.button(label="Swap Members", style=discord.ButtonStyle.primary, row=0)
    async def swap_members_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Open modal to swap two members."""
        modal = SwapMembersModal(self, self.debate_round)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Toggle Team Type", style=discord.ButtonStyle.secondary, row=0)
    async def toggle_team_type_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Toggle between Full and Iron team types."""
        view = ToggleTeamTypeView(self, self.debate_round)
        await interaction.response.send_message(
            "Select which team to toggle between Full (3 debaters) and Iron (2 debaters):",
            view=view,
            ephemeral=False
        )

    @discord.ui.button(label="Move to Judge", style=discord.ButtonStyle.secondary, row=1)
    async def move_to_judge_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Move a debater to judge role."""
        view = MoveToJudgeView(self, self.debate_round)
        await interaction.response.send_message(
            "Select a debater to move to the judging panel:",
            view=view,
            ephemeral=False
        )

    @discord.ui.button(label="Move to Debater", style=discord.ButtonStyle.secondary, row=1)
    async def move_to_debater_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Move a judge to debater role."""
        view = MoveToDebaterView(self, self.debate_round)
        await interaction.response.send_message(
            "Select a judge to move to a debate team:",
            view=view,
            ephemeral=False
        )

    @discord.ui.button(label="✅ Confirm & Start Round", style=discord.ButtonStyle.success, row=2)
    async def confirm_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Confirm allocations and start the round."""
        modal = MotionInputModal(self, self.debate_round)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.danger, row=2)
    async def cancel_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Cancel the round."""
        self.matchmaking_cog.current_round = None
        await interaction.response.send_message("❌ Round cancelled.", ephemeral=True)
        self.stop()
        for item in self.children:
            item.disabled = True
        await self.message.edit(view=self)

    async def refresh_embed(self, interaction: discord.Interaction):
        """Refresh the allocation embed."""
        embed = EmbedBuilder.create_allocation_embed(self.debate_round)
        try:
            await self.message.edit(embed=embed, view=self)
        except:
            pass


class SwapMembersModal(discord.ui.Modal):
    """Modal for swapping two members."""

    def __init__(self, parent_view: AllocationAdjustmentView, debate_round: DebateRound):
        super().__init__(title="Swap Members")
        self.parent_view = parent_view
        self.debate_round = debate_round

        self.member1_input = discord.ui.InputText(
            label="First Member (User ID or @mention)",
            placeholder="Enter user ID or mention",
            required=True
        )
        self.member2_input = discord.ui.InputText(
            label="Second Member (User ID or @mention)",
            placeholder="Enter user ID or mention",
            required=True
        )

        self.add_item(self.member1_input)
        self.add_item(self.member2_input)

    async def callback(self, interaction: discord.Interaction):
        # Parse member IDs
        member1_id = self._parse_member_id(self.member1_input.value)
        member2_id = self._parse_member_id(self.member2_input.value)

        if not member1_id or not member2_id:
            await interaction.response.send_message(
                "❌ Invalid user ID or mention format.",
                ephemeral=False
            )
            return

        # Get member objects
        member1 = interaction.guild.get_member(member1_id)
        member2 = interaction.guild.get_member(member2_id)

        if not member1 or not member2:
            await interaction.response.send_message(
                "❌ Could not find one or both members.",
                ephemeral=False
            )
            return

        # Perform swap
        if self.debate_round.swap_members(member1, member2):
            await interaction.response.send_message(
                f"✅ Swapped {member1.mention} and {member2.mention}",
                ephemeral=False
            )
            await self.parent_view.refresh_embed(interaction)
        else:
            await interaction.response.send_message(
                "❌ Could not swap members. Make sure both are in the round.",
                ephemeral=False
            )

    def _parse_member_id(self, text: str) -> Optional[int]:
        """Parse a member ID from text (handles mentions and raw IDs)."""
        # Remove <@ and > if present (mention format)
        text = text.strip().replace('<@', '').replace('>', '').replace('!', '')
        try:
            return int(text)
        except ValueError:
            return None


class ToggleTeamTypeView(discord.ui.View):
    """View for selecting which team to toggle."""

    def __init__(self, parent_view: AllocationAdjustmentView, debate_round: DebateRound):
        super().__init__(timeout=60)
        self.parent_view = parent_view
        self.debate_round = debate_round

    @discord.ui.button(label="Toggle Government", style=discord.ButtonStyle.primary)
    async def toggle_gov_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Toggle Government team type."""
        await self._toggle_team(interaction, self.debate_round.government)

    @discord.ui.button(label="Toggle Opposition", style=discord.ButtonStyle.primary)
    async def toggle_opp_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Toggle Opposition team type."""
        await self._toggle_team(interaction, self.debate_round.opposition)

    async def _toggle_team(self, interaction: discord.Interaction, team):
        """Toggle a team between Full and Iron."""
        if team.team_type == TeamType.FULL:
            # Check if we can reduce to Iron (need to remove 1 member)
            if len(team.members) > 2:
                removed_member = team.members.pop()
                # Add to judges
                self.debate_round.judges.add_judge(removed_member)
            team.team_type = TeamType.IRON
            await interaction.response.send_message(
                f"✅ {team.team_name} is now an Iron team (2 debaters)",
                ephemeral=False
            )
        else:
            team.team_type = TeamType.FULL
            await interaction.response.send_message(
                f"✅ {team.team_name} is now a Full team (3 debaters)",
                ephemeral=False
            )

        await self.parent_view.refresh_embed(interaction)
        self.stop()


class MoveToJudgeView(discord.ui.View):
    """View for moving a debater to judge."""

    def __init__(self, parent_view: AllocationAdjustmentView, debate_round: DebateRound):
        super().__init__(timeout=60)
        self.parent_view = parent_view
        self.debate_round = debate_round

        # Create select menu with all debaters
        options = []
        for member in debate_round.government.members:
            options.append(discord.SelectOption(
                label=f"Gov: {member.display_name}",
                value=f"gov_{member.id}"
            ))
        for member in debate_round.opposition.members:
            options.append(discord.SelectOption(
                label=f"Opp: {member.display_name}",
                value=f"opp_{member.id}"
            ))

        if options:
            select = discord.ui.Select(
                placeholder="Select a debater to move to judge",
                options=options
            )
            select.callback = self.select_callback
            self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        """Handle debater selection."""
        value = interaction.data["values"][0]
        team_type, member_id = value.split("_")
        member_id = int(member_id)

        member = interaction.guild.get_member(member_id)
        if not member:
            await interaction.response.send_message("❌ Member not found.", ephemeral=True)
            return

        # Remove from team
        if team_type == "gov":
            self.debate_round.government.remove_member(member)
        else:
            self.debate_round.opposition.remove_member(member)

        # Add to judges
        self.debate_round.judges.add_judge(member)

        await interaction.response.send_message(
            f"✅ Moved {member.mention} to judging panel",
            ephemeral=False
        )
        await self.parent_view.refresh_embed(interaction)
        self.stop()


class MoveToDebaterView(discord.ui.View):
    """View for moving a judge to debater."""

    def __init__(self, parent_view: AllocationAdjustmentView, debate_round: DebateRound):
        super().__init__(timeout=60)
        self.parent_view = parent_view
        self.debate_round = debate_round

        # Create select menu with all judges
        options = []
        all_judges = debate_round.judges.get_all_judges()
        for judge in all_judges:
            role = "Chair" if judge == debate_round.judges.chair else "Panelist"
            options.append(discord.SelectOption(
                label=f"{role}: {judge.display_name}",
                value=str(judge.id)
            ))

        if options:
            select = discord.ui.Select(
                placeholder="Select a judge to move to debater",
                options=options
            )
            select.callback = self.select_callback
            self.add_item(select)

        # Add team selection buttons
        self.selected_judge_id = None

    async def select_callback(self, interaction: discord.Interaction):
        """Handle judge selection."""
        member_id = int(interaction.data["values"][0])
        self.selected_judge_id = member_id

        # Now show team selection
        await interaction.response.send_message(
            "Select which team to join:",
            view=TeamSelectionView(self.parent_view, self.debate_round, member_id),
            ephemeral=False
        )
        self.stop()


class TeamSelectionView(discord.ui.View):
    """View for selecting which team to join."""

    def __init__(self, parent_view: AllocationAdjustmentView, debate_round: DebateRound, member_id: int):
        super().__init__(timeout=60)
        self.parent_view = parent_view
        self.debate_round = debate_round
        self.member_id = member_id

    @discord.ui.button(label="Join Government", style=discord.ButtonStyle.primary)
    async def join_gov_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Join Government team."""
        await self._move_to_team(interaction, self.debate_round.government)

    @discord.ui.button(label="Join Opposition", style=discord.ButtonStyle.primary)
    async def join_opp_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Join Opposition team."""
        await self._move_to_team(interaction, self.debate_round.opposition)

    async def _move_to_team(self, interaction: discord.Interaction, team):
        """Move judge to a team."""
        member = interaction.guild.get_member(self.member_id)
        if not member:
            await interaction.response.send_message("❌ Member not found.", ephemeral=True)
            return

        # Remove from judges
        self.debate_round.judges.remove_judge(member)

        # Add to team
        if team.add_member(member):
            await interaction.response.send_message(
                f"✅ Moved {member.mention} to {team.team_name}",
                ephemeral=False
            )
            await self.parent_view.refresh_embed(interaction)
        else:
            # Team is full, add back to judges
            self.debate_round.judges.add_judge(member)
            await interaction.response.send_message(
                f"❌ {team.team_name} is full. Cannot add more members.",
                ephemeral=False
            )

        self.stop()


class MotionInputModal(discord.ui.Modal):
    """Modal for entering the debate motion."""

    def __init__(self, parent_view: AllocationAdjustmentView, debate_round: DebateRound):
        super().__init__(title="Enter Debate Motion")
        self.parent_view = parent_view
        self.debate_round = debate_round

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
                "❌ Motion cannot be empty.",
                ephemeral=False
            )
            return

        # Set motion and confirm round
        self.debate_round.motion = motion
        self.debate_round.confirmed = True

        # Create confirmed round embed
        embed = EmbedBuilder.create_confirmed_round_embed(self.debate_round, motion)

        # Send to channel
        await interaction.response.send_message(embed=embed)

        # Disable adjustment view
        self.parent_view.stop()
        for item in self.parent_view.children:
            item.disabled = True
        try:
            await self.parent_view.message.edit(view=self.parent_view)
        except:
            pass

        # Clear current round
        self.parent_view.matchmaking_cog.current_round = None


class Adjustment(commands.Cog):
    """Cog for handling allocation adjustments."""

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        """Called when the cog is loaded."""
        print("Adjustment cog loaded")


def setup(bot):
    bot.add_cog(Adjustment(bot))
