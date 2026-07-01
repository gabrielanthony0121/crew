import discord
from discord.ext import commands

from core.config import (
    CREW_BOOSTER_ROLE_ID,
    CREW_PERKS_BANNER_URL,
    CREW_PERKS_CHANNEL_ID,
    CREW_PERKS_THUMBNAIL_URL,
)

# Purple accent pulled from the Language Crew Booster brand art
CREW_BOOSTER_COLOR = discord.Color.from_rgb(104, 45, 200)


def get_crew_booster_embed(guild: discord.Guild) -> discord.Embed:
    """Permanent Crew Booster perks embed for #crew-perks (CDW-style layout)."""
    role = guild.get_role(CREW_BOOSTER_ROLE_ID)
    role_mention = role.mention if role else f"<@&{CREW_BOOSTER_ROLE_ID}>"
    icon_url = guild.icon.url if guild.icon else None

    embed = discord.Embed(
        title="Become a Crew Booster",
        description=(
            "**Perks:**\n\n"
            f"**01** Exclusive {role_mention} role highlighted across the server;\n"
            "**02** Priority access to voice events and community sessions;\n"
            "**03** More custom emojis and reactions throughout the server;\n"
            "**04** Direct staff support whenever you need assistance;\n"
            "**05** Full access to server soundboards in voice channels;"
        ),
        color=CREW_BOOSTER_COLOR,
    )

    embed.set_author(
        name="Language Crew",
        icon_url=icon_url,
    )

    thumb = CREW_PERKS_THUMBNAIL_URL or icon_url
    if thumb:
        embed.set_thumbnail(url=thumb)

    if CREW_PERKS_BANNER_URL:
        embed.set_image(url=CREW_PERKS_BANNER_URL)

    embed.set_footer(
        text="Add your boost and claim your perks. • Language Crew",
        icon_url=icon_url,
    )
    return embed


class BoostServerView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        self.add_item(
            discord.ui.Button(
                label="Boost Now",
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
        if not CREW_PERKS_BANNER_URL:
            warn = discord.Embed(
                description=(
                    "⚠️ **CREW_PERKS_BANNER_URL** is not set — the embed will post without the banner image.\n"
                    "Upload your **Language Crew Booster** art to Discord, copy the link, "
                    "then set it in Railway env vars or `core/config.py`."
                ),
                color=discord.Color.orange(),
            )
            await ctx.send(embed=warn, delete_after=20)

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
            description="✅ **Crew Booster** perks panel posted to **#crew-perks**!",
            color=CREW_BOOSTER_COLOR,
        )
        await ctx.send(embed=confirm, delete_after=8)
        print(f"[LOG] Crew perks embed posted by {ctx.author} ({ctx.author.id})")


async def setup(bot: commands.Bot):
    await bot.add_cog(CrewPerks(bot))