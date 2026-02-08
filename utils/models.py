from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum
import discord


class TeamType(Enum):
    """Team composition types."""
    FULL = "full"  # 3 debaters
    IRON = "iron"  # 2 debaters


class RoundType(Enum):
    """Types of debate rounds based on participant count."""
    DOUBLE_IRON = "double_iron"  # 5 people: 2v2 + 1 judge
    SINGLE_IRON = "single_iron"  # 6 people: 3v2 or 2v3 + 1 judge
    STANDARD = "standard"  # 7+ people: 3v3 + judges


@dataclass
class DebateTeam:
    """Represents a debate team (Gov or Opp)."""
    team_name: str  # "Government" or "Opposition"
    team_type: TeamType
    members: List[discord.Member] = field(default_factory=list)

    def add_member(self, member: discord.Member):
        """Add a member to the team."""
        max_size = 3 if self.team_type == TeamType.FULL else 2
        if len(self.members) < max_size:
            self.members.append(member)
            return True
        return False

    def remove_member(self, member: discord.Member):
        """Remove a member from the team."""
        if member in self.members:
            self.members.remove(member)
            return True
        return False

    def is_full(self) -> bool:
        """Check if team is at capacity."""
        max_size = 3 if self.team_type == TeamType.FULL else 2
        return len(self.members) >= max_size

    def get_position_name(self, index: int) -> str:
        """Get position name for a team member by index."""
        from config import Config

        if self.team_type == TeamType.FULL:
            positions = Config.TEAM_POSITIONS["gov" if self.team_name == "Government" else "opp"]
        else:
            positions = Config.IRON_TEAM_POSITIONS["gov" if self.team_name == "Government" else "opp"]

        return positions[index] if index < len(positions) else f"Speaker {index + 1}"


@dataclass
class JudgePanel:
    """Represents the judging panel."""
    chair: Optional[discord.Member] = None
    panelists: List[discord.Member] = field(default_factory=list)

    def add_judge(self, member: discord.Member):
        """Add a judge to the panel."""
        if self.chair is None:
            self.chair = member
        else:
            if member not in self.panelists:
                self.panelists.append(member)

    def remove_judge(self, member: discord.Member):
        """Remove a judge from the panel."""
        if self.chair == member:
            # Promote a panelist to chair if available
            if self.panelists:
                self.chair = self.panelists.pop(0)
            else:
                self.chair = None
        elif member in self.panelists:
            self.panelists.remove(member)

    def get_all_judges(self) -> List[discord.Member]:
        """Get all judges including chair and panelists."""
        judges = []
        if self.chair:
            judges.append(self.chair)
        judges.extend(self.panelists)
        return judges

    def total_judges(self) -> int:
        """Get total number of judges."""
        return (1 if self.chair else 0) + len(self.panelists)


@dataclass
class DebateRound:
    """Represents a complete debate round."""
    round_id: int
    round_type: RoundType
    government: DebateTeam
    opposition: DebateTeam
    judges: JudgePanel
    motion: Optional[str] = None
    confirmed: bool = False

    def get_all_participants(self) -> List[discord.Member]:
        """Get all participants in the round."""
        participants = []
        participants.extend(self.government.members)
        participants.extend(self.opposition.members)
        participants.extend(self.judges.get_all_judges())
        return participants

    def swap_members(self, member1: discord.Member, member2: discord.Member) -> bool:
        """Swap positions of two members in the round."""
        # Find where each member is
        loc1 = self._find_member_location(member1)
        loc2 = self._find_member_location(member2)

        if not loc1 or not loc2:
            return False

        # Remove both members
        self._remove_member_from_location(member1, loc1)
        self._remove_member_from_location(member2, loc2)

        # Add them to swapped positions
        self._add_member_to_location(member1, loc2)
        self._add_member_to_location(member2, loc1)

        return True

    def _find_member_location(self, member: discord.Member) -> Optional[tuple]:
        """Find where a member is located in the round."""
        if member in self.government.members:
            return ("gov", self.government.members.index(member))
        elif member in self.opposition.members:
            return ("opp", self.opposition.members.index(member))
        elif self.judges.chair == member:
            return ("judge", "chair")
        elif member in self.judges.panelists:
            return ("judge", self.judges.panelists.index(member))
        return None

    def _remove_member_from_location(self, member: discord.Member, location: tuple):
        """Remove a member from a specific location."""
        team_type, position = location
        if team_type == "gov":
            self.government.members.remove(member)
        elif team_type == "opp":
            self.opposition.members.remove(member)
        elif team_type == "judge":
            self.judges.remove_judge(member)

    def _add_member_to_location(self, member: discord.Member, location: tuple):
        """Add a member to a specific location."""
        team_type, position = location
        if team_type == "gov":
            if isinstance(position, int):
                self.government.members.insert(position, member)
            else:
                self.government.members.append(member)
        elif team_type == "opp":
            if isinstance(position, int):
                self.opposition.members.insert(position, member)
            else:
                self.opposition.members.append(member)
        elif team_type == "judge":
            self.judges.add_judge(member)


@dataclass
class MatchmakingQueue:
    """Manages the matchmaking queue."""
    users: List[discord.Member] = field(default_factory=list)
    lobby_message: Optional[discord.Message] = None

    def add_user(self, user: discord.Member) -> bool:
        """Add a user to the queue."""
        if user not in self.users:
            self.users.append(user)
            return True
        return False

    def remove_user(self, user: discord.Member) -> bool:
        """Remove a user from the queue."""
        if user in self.users:
            self.users.remove(user)
            return True
        return False

    def clear(self):
        """Clear the queue."""
        self.users.clear()

    def size(self) -> int:
        """Get the current queue size."""
        return len(self.users)

    def get_threshold_type(self) -> Optional[RoundType]:
        """Determine the round type based on current queue size."""
        size = self.size()
        if size == 5:
            return RoundType.DOUBLE_IRON
        elif size == 6:
            return RoundType.SINGLE_IRON
        elif size >= 7:
            return RoundType.STANDARD
        return None
