import discord
from discord.ext import commands

from core.config import TIPS_CHANNEL_ID, TIPS_REVIEW_CHANNEL_ID

QUILL_COLOR = discord.Color.from_rgb(72, 140, 104)
BUSUU_URL = "https://www.busuu.com/"


def get_busuu_tip_embed(guild: discord.Guild) -> discord.Embed:
    """Professional Quill Tip embed — Busuu phrase-bank method."""
    icon_url = guild.icon.url if guild.icon else None

    embed = discord.Embed(
        title="🍃 Quill Tip — The Real Way to Use Busuu",
        description=(
            "Most people use language apps the wrong way — they complete lessons "
            "and forget everything.\n\n"
            "**Busuu is different.** It gives you ready-made, natural phrases "
            "across **14 languages**. The smart move is to treat it like a "
            "**phrase bank**, not a game."
        ),
        color=QUILL_COLOR,
    )

    embed.add_field(
        name="📌 What Actually Works",
        value=(
            "**1.** Pick **4–5 useful phrases** every day\n"
            "**2.** Learn them properly on Busuu\n"
            "**3.** Join voice chat and **use them in real conversation**"
        ),
        inline=False,
    )

    embed.add_field(
        name="🎯 Keep It Simple",
        value=(
            "No complicated method — just **consistent phrase collection** "
            "+ **immediate use**.\n\n"
            "Do this for **two weeks** and your speaking will feel much more natural."
        ),
        inline=False,
    )

    embed.add_field(
        name="💬 Your Turn",
        value=(
            "Which language are you learning? Tell us in chat — "
            "we'll help you pick **5 strong starter phrases** to begin with.\n\n"
            f"🔗 [**Open Busuu**]({BUSUU_URL})"
        ),
        inline=False,
    )

    if icon_url:
        embed.set_thumbnail(url=icon_url)

    embed.set_footer(text="Quill Tips • Language Crew")
    return embed


class SubmitTipModal(discord.ui.Modal, title="💡 Share Your Language Tip"):
    tip_title = discord.ui.TextInput(
        label="Tip Title",
        placeholder="e.g. Shadowing with podcasts",
        min_length=5,
        max_length=100,
        style=discord.TextStyle.short,
    )

    tip_body = discord.ui.TextInput(
        label="Your Tip",
        placeholder="Describe your method, tool, or habit in a few sentences...",
        min_length=20,
        max_length=1000,
        style=discord.TextStyle.paragraph,
    )

    language = discord.ui.TextInput(
        label="Language (optional)",
        placeholder="e.g. Spanish, Japanese...",
        required=False,
        max_length=50,
        style=discord.TextStyle.short,
    )

    async def on_submit(self, interaction: discord.Interaction):
        member = interaction.user
        guild = interaction.guild

        submission = discord.Embed(
            title="💡 New Community Tip Submission",
            description=self.tip_body.value,
            color=QUILL_COLOR,
            timestamp=discord.utils.utcnow(),
        )
        submission.set_author(
            name=str(member),
            icon_url=member.display_avatar.url,
        )
        submission.add_field(name="Title", value=f"**{self.tip_title.value}**", inline=False)
        if self.language.value:
            submission.add_field(name="Language", value=self.language.value, inline=True)
        submission.add_field(name="Submitted by", value=f"{member.mention} (`{member.id}`)", inline=True)
        submission.set_footer(text="Review this tip before posting to the tips channel")

        review_channel_id = TIPS_REVIEW_CHANNEL_ID
        if review_channel_id:
            review_channel = guild.get_channel(review_channel_id)
            if review_channel is None:
                review_channel = await interaction.client.fetch_channel(review_channel_id)
            await review_channel.send(embed=submission)
        else:
            bot = interaction.client
            if hasattr(bot, "send_log"):
                await bot.send_log(submission)
            else:
                await interaction.response.send_message(
                    "❌ Tip submissions are not configured yet. Ask an admin to set `TIPS_REVIEW_CHANNEL_ID`.",
                    ephemeral=True,
                )
                return

        confirm = discord.Embed(
            title="✅ Tip Submitted!",
            description=(
                "Thank you for sharing your tip with the community.\n\n"
                "Our team will review it — if approved, it may be featured in the tips channel."
            ),
            color=QUILL_COLOR,
        )
        confirm.set_footer(text="Language Crew • Quill Tips")
        await interaction.response.send_message(embed=confirm, ephemeral=True)
        print(f"[LOG] Tip submitted by {member} ({member.id}): {self.tip_title.value}")


class QuillTipsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(
            discord.ui.Button(
                label="Visit Busuu",
                style=discord.ButtonStyle.link,
                url=BUSUU_URL,
                emoji="🌐",
            )
        )

    @discord.ui.button(
        label="Share Your Tip",
        style=discord.ButtonStyle.primary,
        custom_id="persistent_share_tip",
        emoji="💡",
    )
    async def share_tip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SubmitTipModal())


class QuillTips(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.add_view(QuillTipsView())

    @commands.command(name="quilltip")
    @commands.has_permissions(administrator=True)
    async def quill_tip(self, ctx: commands.Context):
        """Posts the Busuu Quill Tip embed with the community tip button."""
        embed = get_busuu_tip_embed(ctx.guild)
        view = QuillTipsView()

        try:
            await ctx.message.delete()
        except Exception:
            pass

        await ctx.send(embed=embed, view=view)

        confirm = discord.Embed(
            description="✅ Quill Tip posted successfully.",
            color=QUILL_COLOR,
        )
        await ctx.send(embed=confirm, delete_after=8)
        print(f"[LOG] Quill Tip (Busuu) posted by {ctx.author} ({ctx.author.id}) in #{ctx.channel}")

    @commands.command(name="setuptips")
    @commands.has_permissions(administrator=True)
    async def setup_tips(self, ctx: commands.Context):
        """Posts the Busuu Quill Tip panel to the configured tips channel."""
        if not TIPS_CHANNEL_ID:
            embed = discord.Embed(
                description=(
                    "❌ `TIPS_CHANNEL_ID` is not configured.\n"
                    "Set it as a Railway Variable or use `c!quilltip` in the tips channel directly."
                ),
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=10)
            return

        channel = self.bot.get_channel(TIPS_CHANNEL_ID)
        if channel is None:
            channel = await self.bot.fetch_channel(TIPS_CHANNEL_ID)

        embed = get_busuu_tip_embed(ctx.guild)
        view = QuillTipsView()
        await channel.send(embed=embed, view=view)

        try:
            await ctx.message.delete()
        except Exception:
            pass

        confirm = discord.Embed(
            description=f"✅ Quill Tip panel posted to {channel.mention}.",
            color=QUILL_COLOR,
        )
        await ctx.send(embed=confirm, delete_after=8)
        print(f"[LOG] Quill Tips panel set up by {ctx.author} ({ctx.author.id})")


async def setup(bot: commands.Bot):
    await bot.add_cog(QuillTips(bot))