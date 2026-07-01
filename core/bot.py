import discord
from discord.ext import commands

from core.config import COMMAND_PREFIX

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)

SKILLS = [
    "skills.logging",
    "skills.protection",
    "skills.general",
    "skills.moderation",
    "skills.custom_vc",
    "skills.video_crew",
    "skills.spam_clear",
    "skills.crew_perks",
    "skills.quill_tips",
]


async def load_skills() -> None:
    for skill in SKILLS:
        try:
            await bot.load_extension(skill)
            print(f"[LOG] Loaded skill: {skill}")
        except Exception as e:
            print(f"[FATAL ERROR] Failed to load skill {skill}: {e}")
            raise  # Stop startup so the problem is visible


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.MissingPermissions):
        embed = discord.Embed(
            description="❌ You don't have permission to use this command (requires Administrator).",
            color=discord.Color.red(),
        )
        await ctx.send(embed=embed, delete_after=8)
        return

    if isinstance(error, commands.MissingRequiredArgument):
        # Let the command itself handle usage messages (like the existing ones do)
        return

    if isinstance(error, commands.CommandNotFound):
        # Ignore unknown commands (don't spam logs or user)
        return

    if isinstance(error, commands.BadArgument):
        cmd = ctx.command.name if ctx.command else "command"
        embed = discord.Embed(
            description=(
                f"❌ Invalid argument for `c!{cmd}`.\n"
                "Please use the correct format (e.g. numeric user ID like `c!review 123456789012345678`)."
            ),
            color=discord.Color.red(),
        )
        await ctx.send(embed=embed, delete_after=8)
        return

    # For other errors, log to console and optionally tell user
    print(f"[ERROR] Command error in {ctx.command}: {error}")
    # Optional: send a generic message for unexpected errors
    # embed = discord.Embed(description="❌ Something went wrong with that command.", color=discord.Color.red())
    # await ctx.send(embed=embed, delete_after=6)