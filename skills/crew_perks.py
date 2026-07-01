import discord
from discord.ext import commands

from core.config import (
    CREW_BOOSTER_ROLE_ID,
    CREW_PERKS_BANNER_URL,
    CREW_PERKS_CHANNEL_ID,
    CREW_PERKS_THUMBNAIL_URL,
)

CREW_BOOSTER_COLOR = discord.Color.from_rgb(104, 45, 200)


def _emoji(guild: discord.Guild, name: str, fallback: str = "") -> str:
    """Resolve a custom server emoji by name; fall back to unicode if missing."""
    found = discord.utils.get(guild.emojis, name=name)
    return str(found) if found else fallback


def get_crew_booster_embed(guild: discord.Guild) -> discord.Embed:
    """Compact minimalist Crew Booster perks embed for #crew-perks."""
    role = guild.get_role(CREW_BOOSTER_ROLE_ID)
    role_mention = role.mention if role else f"<@&{CREW_BOOSTER_ROLE_ID}>"
    icon_url = guild.icon.url if guild.icon else None

    e_crown = _emoji(guild, "pp_coroa_cdw", "👑")
    e_boost = _emoji(guild, "p_boost_cdw", "🎙️")
    e_custom = _emoji(guild, "useta40", "✨")
    e_diamond = _emoji(guild, "p_diamante_cdw", "💎")

    embed = discord.Embed(
        title="Crew Booster",
        description=(
            f"Unlock {role_mention} with a server boost.\n\n"
            f"{e_crown} Highlighted booster role\n"
            f"{e_boost} Priority voice events\n"
            f"{e_custom} Custom emojis & reactions\n"
            f"{e_diamond} Direct staff support\n"
            f"{e_boost} Server soundboards"
        ),
        color=CREW_BOOSTER_COLOR,
    )

    if icon_url:
        embed.set_thumbnail(url=icon_url)

    banner = CREW_PERKS_BANNER_URL or CREW_PERKS_THUMBNAIL_URL
    if banner:
        embed.set_image(url=banner)

    embed.set_footer(text="Boost to unlock • Language Crew")
    return embed


class BoostServerView(discord.ui.View):
    def __init__(self, guild: discord.Guild):
        super().__init__(timeout=None)
        diamond = discord.utils.get(guild.emojis, name="p_diamante_cdw")
        self.add_item(
            discord.ui.Button(
                label="Boost",
                style=discord.ButtonStyle.link,
                url=f"https://discord.com/channels/{guild.id}/premium-subscriptions",
                emoji=diamond if diamond else "💎",
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
        view = BoostServerView(ctx.guild)

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