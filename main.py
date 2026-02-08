import discord
from discord.ext import commands
import sys
import traceback

from config import Config


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

    async def on_ready(self):
        """Called when the bot is ready."""
        print(f"Logged in as {self.user} (ID: {self.user.id})")
        print(f"Connected to {len(self.guilds)} guild(s)")
        print("------")

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
        print("Loading extensions...")
        for extension in self.initial_extensions:
            try:
                self.load_extension(extension)
                print(f"✓ Loaded {extension}")
            except Exception as e:
                print(f"✗ Failed to load {extension}")
                traceback.print_exception(type(e), e, e.__traceback__)


def main():
    """Main entry point for the bot."""
    try:
        # Validate configuration
        Config.validate()
    except ValueError as e:
        print(f"Configuration Error: {e}")
        print("Please check your .env file and ensure all required values are set.")
        sys.exit(1)

    # Create and run bot
    bot = DebateBot()

    try:
        bot.run(Config.DISCORD_TOKEN)
    except discord.LoginFailure:
        print("Error: Invalid bot token. Please check your DISCORD_TOKEN in .env")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nBot stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {e}")
        traceback.print_exception(type(e), e, e.__traceback__)
        sys.exit(1)


if __name__ == "__main__":
    main()
