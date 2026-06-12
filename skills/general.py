import discord
from discord.ext import commands


class General(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print("─" * 40)
        print(f"  ✅ Bot online as: {self.bot.user}")
        print(f"  🤖 ID: {self.bot.user.id}")
        print(f"  📡 Connected to {len(self.bot.guilds)} server(s)")
        print("─" * 40)

        await self.bot.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="🔒 Protecting the server",
            )
        )

    @commands.command(name="ping")
    async def ping(self, ctx: commands.Context):
        latency = round(self.bot.latency * 1000)
        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"Current bot latency: **{latency}ms**",
            color=discord.Color.green() if latency < 100 else discord.Color.orange(),
        )
        embed.set_footer(text=f"Requested by {ctx.author.display_name}")
        await ctx.send(embed=embed)

    @commands.command(name="info")
    async def info(self, ctx: commands.Context):
        embed = discord.Embed(
            title="🤖 Bot Information",
            description="Moderation and protection bot for Language Crew.",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="👤 Server", value=ctx.guild.name, inline=True)
        embed.add_field(name="⚙️ Prefix", value="`c!`", inline=True)
        embed.set_footer(text="Made by @gbeditor")
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(General(bot))