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
    HOST_CHANNEL_ID = int(os.getenv("HOST_CHANNEL_ID", 0))
    LOBBY_CHANNEL_ID = int(os.getenv("LOBBY_CHANNEL_ID", 0))

    # Role IDs (Optional)
    _host_role_env = os.getenv("HOST_ROLE_ID", "")
    HOST_ROLE_ID = int(_host_role_env) if _host_role_env and _host_role_env.strip() and _host_role_env.strip().isdigit() else None

    # Bot Settings
    BOT_PREFIX = "!"

    # Debate Settings
    TEAM_POSITIONS = {
        "gov": ["Prime Minister", "Deputy Prime Minister", "Government Whip"],
        "opp": ["Leader of Opposition", "Deputy Leader of Opposition", "Opposition Whip"]
    }

    IRON_TEAM_POSITIONS = {
        "gov": ["Prime Minister", "Government Whip"],
        "opp": ["Leader of Opposition", "Opposition Whip"]
    }

    JUDGE_ROLES = ["Chair", "Panelist"]

    @classmethod
    def validate(cls):
        """Validate required configuration."""
        if not cls.DISCORD_TOKEN:
            raise ValueError("DISCORD_TOKEN is required in .env file")
        if not cls.GUILD_ID:
            raise ValueError("GUILD_ID is required in .env file")
        if not cls.HOST_CHANNEL_ID:
            raise ValueError("HOST_CHANNEL_ID is required in .env file")
        if not cls.LOBBY_CHANNEL_ID:
            raise ValueError("LOBBY_CHANNEL_ID is required in .env file")
