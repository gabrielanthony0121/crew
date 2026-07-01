import discord
from discord.ext import commands

from core.config import (
    CREW_BOOSTER_ROLE_ID,
    CREW_PERKS_BANNER_URL,
    CREW_PERKS_CHANNEL_ID,
    CREW_PERKS_THUMBNAIL_URL,
)

CREW_BOOSTER_COLOR = discord.Color.from_rgb(104, 45, 200)


def get_crew_booster_embed(guild: discord.Guild) -> discord.Embed:
    """Compact minimalist Crew Booster perks embed for #crew-perks."""
    role = guild.get_role(CREW_BOOSTER_ROLE_ID)
    role_mention = role.mention if role else f"<@&{CREW_BOOSTER_ROLE_ID}>"
    icon_url = guild.icon.url if guild.icon else None

    embed = discord.Embed(
        title="Crew Booster",
        description=(
            f"Unlock {role_mention} with a server boost.\n\n"
            "👑 Highlighted booster role\n"
            "🎙️ Priority voice events\n"
            "✨ Custom emojis & reactions\n"
            "🛟 Direct staff support\n"
            "🔊 Server soundboards"
        ),
        color=CREW_BOOSTER_COLOR,
    )

    thumb = CREW_PERKS_THUMBNAIL_URL or CREW_PERKS_BANNER_URL or icon_url
    if thumb:
        embed.set_thumbnail(url=thumb)

    embed.set_footer(text="Boost to unlock • Language Crew")
    return embed


class BoostServerView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        self.add_item(
            discord.ui.Button(
                label="Boost",
                style=discord.ButtonStyle.link,
                url=f"https://discord.com/channels/{guild_id}/premium-subscriptions",
                emoji="💎",
            )
        )


class CrewPerks(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="setupcrewperks")
    @commands.has_permissions(administrator=True)
    async def setup_crew_perks(self, ctx: commands.Context):
        """Posts (or re-posts) the permanent Crew Booster perks embed in #crew-perks."""
        embed = get_crew_booster_embed(ctx.guild)
        view = BoostServerView(ctx.guild.id)

        channel = self.bot.get_channel(CREW_PERKS_CHANNEL_ID)
        if channel is None:
            channel = await self.bot.fetch_channel(CREW_PERKS_CHANNEL_ID)

        await channel.send(embed=embed, view=view)

        try:
            await ctx.message.delete()
        except Exception:
            pass

        confirm = discord.Embed(
            description="✅ Crew Booster panel posted to **#crew-perks**.",
            color=CREW_BOOSTER_COLOR,
        )
        await ctx.send(embed=confirm, delete_after=8)
        print(f"[LOG] Crew perks embed posted by {ctx.author} ({ctx.author.id})")


async def setup(bot: commands.Bot):
    await bot.add_cog(CrewPerks(bot))