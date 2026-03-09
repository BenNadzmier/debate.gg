import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Bot configuration loaded from environment variables."""

    # Discord Bot Token
    DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

    # Server Configuration
    GUILD_ID = int(os.getenv("GUILD_ID", 0))

    # Channel IDs
    LOBBY_CHANNEL_ID = int(os.getenv("LOBBY_CHANNEL_ID", 0))

    # Bot Settings
    BOT_PREFIX = "!"

    # Prep Time (seconds)
    PREP_TIME_1V1 = 15 * 60   # 15 minutes
    PREP_TIME_AP = 30 * 60    # 30 minutes
    PREP_TIME_BP = 15 * 60    # 15 minutes

    # Debate Settings
    TEAM_POSITIONS = {
        "gov": ["Prime Minister", "Deputy Prime Minister", "Government Whip"],
        "opp": ["Leader of Opposition", "Deputy Leader of Opposition", "Opposition Whip"]
    }

    IRON_TEAM_POSITIONS = {
        "gov": ["Prime Minister", "Government Whip"],
        "opp": ["Leader of Opposition", "Opposition Whip"]
    }

    PM_LO_POSITIONS = {
        "gov": ["Prime Minister"],
        "opp": ["Leader of Opposition"]
    }

    # BP position names per team (index 0 = first speaker, index 1 = second speaker)
    BP_OG_POSITIONS = ["Prime Minister", "Deputy Prime Minister"]
    BP_OO_POSITIONS = ["Leader of Opposition", "Deputy Leader of Opposition"]
    BP_CG_POSITIONS = ["Member of Government", "Government Whip"]
    BP_CO_POSITIONS = ["Member of Opposition", "Opposition Whip"]

    JUDGE_ROLES = ["Chair", "Panelist"]

    @classmethod
    def validate(cls):
        """Validate required configuration."""
        if not cls.DISCORD_TOKEN:
            raise ValueError("DISCORD_TOKEN is required in .env file")
        if not cls.GUILD_ID:
            raise ValueError("GUILD_ID is required in .env file")
        if not cls.LOBBY_CHANNEL_ID:
            raise ValueError("LOBBY_CHANNEL_ID is required in .env file")
