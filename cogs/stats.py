import discord
from discord.ext import commands
import logging

from config import Config
from utils.database import get_participant_stats
from utils.embeds import EmbedBuilder

logger = logging.getLogger('DebateBot.Stats')


class Stats(commands.Cog):
    """Cog for viewing participant statistics."""

    def __init__(self, bot):
        self.bot = bot

    @discord.slash_command(
        name="stats",
        description="View debate stats for a participant",
        guild_ids=[Config.GUILD_ID] if Config.GUILD_ID else None
    )
    async def stats(
        self,
        ctx: discord.ApplicationContext,
        member: discord.Option(
            discord.Member,
            description="The member to view stats for (defaults to yourself)",
            required=False
        ) = None
    ):
        member = member or ctx.author
        stats = await get_participant_stats(member.id)

        if not stats:
            await ctx.respond(
                f"No stats found for {member.display_name}.",
                ephemeral=True
            )
            return

        embed = EmbedBuilder.create_stats_embed(member, stats)
        await ctx.respond(embed=embed, ephemeral=True)


def setup(bot):
    bot.add_cog(Stats(bot))
