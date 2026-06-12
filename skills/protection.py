import asyncio
import re

import discord
from discord.ext import commands

from core.config import ALLOWED_ROLE_IDS

INVITE_PATTERN = re.compile(
    r"(discord\.gg|discord(?:app)?\.com\/invite)\/[a-zA-Z0-9\-]+",
    re.IGNORECASE,
)


class Protection(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
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
                description=(
                    f"🚫 {author.mention}, **server advertising is not allowed** here.\n"
                    "To advertise, please request permission from the **staff**."
                ),
                color=discord.Color.from_rgb(255, 59, 59),
            )
            embed.set_footer(
                text=f"Action logged • Server: {message.guild.name}",
                icon_url=message.guild.icon.url if message.guild.icon else None,
            )

            try:
                warning = await message.channel.send(embed=embed)
                print(f"[LOG] Link blocked | User: {author} | Channel: #{message.channel.name}")
            except Exception as e:
                print(f"[ERROR] Failed to send embed: {e}")
                return

            # Log blocked invite to server logs channel
            log_embed = discord.Embed(
                title="🚫 Invite Link Blocked",
                color=discord.Color.from_rgb(255, 59, 59),
            )
            log_embed.add_field(name="User", value=f"{author.mention} (`{author.id}`)", inline=True)
            log_embed.add_field(name="Channel", value=message.channel.mention, inline=True)
            log_embed.add_field(
                name="Content",
                value=message.content[:500] if message.content else "*no content*",
                inline=False,
            )
            if hasattr(self.bot, "send_log"):
                await self.bot.send_log(log_embed)

            await asyncio.sleep(10)
            try:
                await warning.delete()
            except Exception:
                pass

            return

        # Do not call process_commands here.
        # The commands.Bot framework handles command processing for all messages automatically.
        # Calling it here would cause every command to execute twice.


async def setup(bot: commands.Bot):
    await bot.add_cog(Protection(bot))