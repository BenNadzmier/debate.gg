import discord
from discord.ext import commands
import logging

from utils.embeds import EmbedBuilder

logger = logging.getLogger('DebateBot')


class Welcome(commands.Cog):
    """Handles welcome DMs for new server members."""

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Send a welcome DM when a new member joins the server."""
        if member.bot:
            return

        try:
            embed = EmbedBuilder.create_welcome_dm_embed(member.guild.name)
            await member.send(embed=embed)
        except discord.Forbidden:
            logger.info(f"Could not DM {member} (DMs disabled)")


def setup(bot):
    bot.add_cog(Welcome(bot))
