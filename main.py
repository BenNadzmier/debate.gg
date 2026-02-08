import discord
from discord.ext import commands
import sys
import traceback
import logging

from config import Config

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('DebateBot')


class DebateBot(discord.Bot):
    """Main bot class for AP Debate Matchmaking."""

    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True

        super().__init__(
            intents=intents,
            debug_guilds=[Config.GUILD_ID] if Config.GUILD_ID else None
        )

        self.initial_extensions = [
            'cogs.matchmaking',
            'cogs.adjustment'
        ]

        self.cogs_loaded = False

        logger.info("Bot __init__ complete. Loading cogs...")
        for extension in self.initial_extensions:
            try:
                logger.info(f"Loading extension: {extension}")
                self.load_extension(extension)
                logger.info(f"[OK] Loaded {extension}")
            except Exception as e:
                logger.error(f"[FAIL] Error loading {extension}: {e}")
                traceback.print_exception(type(e), e, e.__traceback())

    async def on_ready(self):
        """Called when the bot is ready."""
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"Connected to {len(self.guilds)} guild(s)")

        # List all guilds
        for guild in self.guilds:
            logger.info(f"  - {guild.name} (ID: {guild.id})")

        # Check if we're in the configured guild
        if Config.GUILD_ID:
            target_guild = self.get_guild(Config.GUILD_ID)
            if target_guild:
                logger.info(f"✓ Found configured guild: {target_guild.name}")
            else:
                logger.warning(f"✗ Configured GUILD_ID {Config.GUILD_ID} not found!")
                logger.warning("Bot might not be in that server, or ID is wrong")

        # List registered commands
        logger.info(f"Registered {len(self.pending_application_commands)} application commands:")
        for cmd in self.pending_application_commands:
            logger.info(f"  - /{cmd.name}: {cmd.description}")

        logger.info("------")
        logger.info("Bot is ready! Waiting for commands...")

        # Set bot status
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="debate rounds | /queue"
            )
        )

    async def on_application_command_error(self, ctx: discord.ApplicationContext, error: discord.DiscordException):
        """Handle application command errors."""
        if isinstance(error, commands.MissingPermissions):
            await ctx.respond(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.respond(
                f"⏰ This command is on cooldown. Try again in {error.retry_after:.2f}s",
                ephemeral=True
            )
        else:
            print(f"Error in command {ctx.command}:", file=sys.stderr)
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
            await ctx.respond(
                "❌ An error occurred while processing this command.",
                ephemeral=True
            )

    async def setup_hook(self):
        """Called before the bot connects to Discord."""
        logger.info("setup_hook called")
        logger.info("Syncing commands...")
        if Config.GUILD_ID:
            logger.info(f"Syncing to specific guild: {Config.GUILD_ID}")
        else:
            logger.info("Syncing globally (may take up to 1 hour)")

    async def on_connect(self):
        """Called when bot connects to Discord - clear old command registrations."""
        logger.info("on_connect called - clearing old command registrations...")

        # IMPORTANT: Clear existing guild commands to remove duplicates from Discord's cache
        if Config.GUILD_ID and self.user:
            logger.info(f"Clearing existing commands from guild {Config.GUILD_ID}...")
            try:
                # Send empty command list to clear all existing commands
                await self.http.bulk_upsert_guild_commands(
                    self.user.id,
                    Config.GUILD_ID,
                    []
                )
                logger.info("✓ Existing guild commands cleared from Discord")
                # Small delay to ensure Discord processes the clear
                import asyncio
                await asyncio.sleep(2)
                logger.info("✓ Ready for fresh command sync")
            except Exception as e:
                logger.warning(f"Error clearing commands: {e}")


def main():
    """Main entry point for the bot."""
    logger.info("Starting AP Debate Matchmaking Bot...")

    try:
        # Validate configuration
        logger.info("Validating configuration...")
        Config.validate()
        logger.info("✓ Configuration valid")
        logger.info(f"  - Guild ID: {Config.GUILD_ID}")
        logger.info(f"  - Lobby Channel: {Config.LOBBY_CHANNEL_ID}")
        logger.info(f"  - Host Channel: {Config.HOST_CHANNEL_ID}")
        logger.info(f"  - Host Role: {Config.HOST_ROLE_ID if Config.HOST_ROLE_ID else 'Not set (optional)'}")
    except ValueError as e:
        logger.error(f"Configuration Error: {e}")
        logger.error("Please check your .env file and ensure all required values are set.")
        sys.exit(1)

    # Create and run bot
    bot = DebateBot()

    try:
        logger.info("Connecting to Discord...")
        bot.run(Config.DISCORD_TOKEN)
    except discord.LoginFailure:
        logger.error("Error: Invalid bot token. Please check your DISCORD_TOKEN in .env")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("\nBot stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        traceback.print_exception(type(e), e, e.__traceback__)
        sys.exit(1)


if __name__ == "__main__":
    main()
