import discord
from discord.ext import commands
import re
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="c!", intents=intents)

INVITE_PATTERN = re.compile(
    r"(discord\.gg|discord(?:app)?\.com\/invite)\/[a-zA-Z0-9\-]+",
    re.IGNORECASE
)

ALLOWED_ROLE_IDS = [
    # Example: 1234567890123456789
]

@bot.event
async def on_ready():
    print("─" * 40)
    print(f"  ✅ Bot online as: {bot.user}")
    print(f"  🤖 ID: {bot.user.id}")
    print(f"  📡 Connected to {len(bot.guilds)} server(s)")
    print("─" * 40)

    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="🔒 Protecting the server"
        )
    )


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    author = message.author
    has_permission = False

    if isinstance(author, discord.Member):
        author_roles = [role.id for role in author.roles]
        has_permission = any(role_id in author_roles for role_id in ALLOWED_ROLE_IDS)

    if isinstance(author, discord.Member) and author.guild_permissions.administrator:
        has_permission = True

    if INVITE_PATTERN.search(message.content) and not has_permission:
        try:
            await message.delete()
        except discord.Forbidden:
            print(f"[ERROR] No permission to delete message in #{message.channel.name}")
            return
        except Exception as e:
            print(f"[ERROR] {e}")
            return

        embed = discord.Embed(
            description=f"🚫 {author.mention}, **server advertising is not allowed** here.\nTo advertise, please request permission from the **staff**.",
            color=discord.Color.from_rgb(255, 59, 59)
        )
        embed.set_footer(
            text=f"Action logged • Server: {message.guild.name}",
            icon_url=message.guild.icon.url if message.guild.icon else None
        )

        try:
            warning = await message.channel.send(embed=embed)
            print(f"[LOG] Link blocked | User: {author} | Channel: #{message.channel.name}")
        except Exception as e:
            print(f"[ERROR] Failed to send embed: {e}")
            return

        await asyncio.sleep(10)
        try:
            await warning.delete()
        except Exception:
            pass

        return

    await bot.process_commands(message)


@bot.command(name="ping")
async def ping(ctx: commands.Context):
    latency = round(bot.latency * 1000)
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"Current bot latency: **{latency}ms**",
        color=discord.Color.green() if latency < 100 else discord.Color.orange()
    )
    embed.set_footer(text=f"Requested by {ctx.author.display_name}")
    await ctx.send(embed=embed)


@bot.command(name="info")
async def info(ctx: commands.Context):
    embed = discord.Embed(
        title="🤖 Bot Information",
        description="Moderation and protection bot.",
        color=discord.Color.blurple()
    )
    embed.add_field(name="👤 Server", value=ctx.guild.name, inline=True)
    embed.add_field(name="⚙️ Prefix", value="`c!`", inline=True)
    embed.set_footer(text="Made by @gbeditor")
    await ctx.send(embed=embed)


async def main():
    async with bot:
        await bot.load_extension("moderacao")
        await bot.load_extension("custom_vc")
        await bot.start(TOKEN)

if __name__ == "__main__":
    if not TOKEN:
        print("[FATAL ERROR] Token not found! Check your .env file")
    else:
        asyncio.run(main())