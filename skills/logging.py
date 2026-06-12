import json
from datetime import datetime

import discord
from discord.ext import commands

import os

from core.config import DATA_DIR, LOG_CHANNEL_ID


CONFIG_FILE = DATA_DIR / "logging_config.json"


def load_config() -> dict:
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"log_channel_id": None}


def save_config(data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def format_dt(dt: datetime | None) -> str:
    if not dt:
        return "Unknown"
    return f"<t:{int(dt.timestamp())}:F>"


class Logging(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # Priority:
        # 1. Environment variable (LOG_CHANNEL_ID) — survives Railway restarts/deploys
        # 2. data/logging_config.json (local development or when using Railway Volume)
        if LOG_CHANNEL_ID:
            try:
                self.log_channel_id: int | None = int(LOG_CHANNEL_ID)
            except ValueError:
                self.log_channel_id = None
                print("[ERROR] Invalid LOG_CHANNEL_ID in environment variables.")
        else:
            cfg = load_config()
            self.log_channel_id: int | None = (
                int(cfg["log_channel_id"]) if cfg.get("log_channel_id") else None
            )

        # Attach helper so other cogs can call: await bot.send_log(embed)
        self.bot.send_log = self._send_log  # type: ignore[attr-defined]
        source = "env var" if LOG_CHANNEL_ID else "config file"
        print(f"[LOG] Logging cog initialized. Log channel configured: {bool(self.log_channel_id)} (source: {source})")

    async def _send_log(self, embed: discord.Embed) -> None:
        if not self.log_channel_id:
            # Silent for normal operation; the init print already shows the status
            return

        channel = self.bot.get_channel(self.log_channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(self.log_channel_id)
            except Exception:
                print(f"[LOG] Log channel {self.log_channel_id} not found (fetch failed).")
                return

        if not isinstance(channel, discord.TextChannel):
            print(f"[ERROR] Configured log channel {self.log_channel_id} is not a text channel.")
            return

        try:
            if embed.timestamp is None:
                embed.timestamp = discord.utils.utcnow()

            guild = channel.guild
            embed.set_footer(
                text=f"Server Logs • {guild.name}" if guild else "Server Logs",
                icon_url=guild.icon.url if guild and guild.icon else None,
            )
            await channel.send(embed=embed)
            print(f"[LOG] Log sent to channel {self.log_channel_id}")
        except discord.Forbidden:
            print("[ERROR] No permission to send to log channel. Check the channel permissions / role overwrites.")
        except Exception as e:
            print(f"[ERROR] Failed to send log: {e}")

    async def _get_log_channel(self) -> discord.TextChannel | None:
        if not self.log_channel_id:
            return None
        ch = self.bot.get_channel(self.log_channel_id)
        if isinstance(ch, discord.TextChannel):
            return ch
        return None

    # ==================== COMMANDS ====================

    def _is_admin(self, author: discord.Member) -> bool:
        return author.guild_permissions.administrator

    @commands.command(name="setlogs")
    async def set_logs(self, ctx: commands.Context, channel: discord.TextChannel = None):
        if not self._is_admin(ctx.author):
            embed = discord.Embed(
                description="❌ You don't have permission to use this command (Administrator required).",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=8)
            return

        if channel is None:
            channel = ctx.channel

        if not isinstance(channel, discord.TextChannel):
            embed = discord.Embed(
                description="❌ Please provide a valid text channel.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=8)
            return

        self.log_channel_id = channel.id
        save_config({"log_channel_id": str(channel.id)})

        try:
            await ctx.message.delete()
        except Exception:
            pass

        embed = discord.Embed(
            title="📋 Log Channel Set",
            description=f"Server logs will now be sent to {channel.mention}.",
            color=discord.Color.blurple(),
        )
        embed.set_footer(text=f"Configured by {ctx.author.display_name}")
        await ctx.send(embed=embed, delete_after=10)

        # Railway note for persistence
        if not LOG_CHANNEL_ID:
            note = discord.Embed(
                description=(
                    "⚠️ **Railway users**: This setting is stored in a file that resets on redeploy.\n"
                    f"To make it permanent, go to your Railway service → **Variables** and add:\n"
                    f"`LOG_CHANNEL_ID` = `{channel.id}`"
                ),
                color=discord.Color.orange(),
            )
            await ctx.send(embed=note, delete_after=20)

        # Send a test message to the log channel
        test = discord.Embed(
            title="✅ Logging Enabled",
            description="This channel is now receiving server activity logs.",
            color=discord.Color.green(),
        )
        await self._send_log(test)

    @commands.command(name="createlogs")
    async def create_logs(self, ctx: commands.Context):
        if not self._is_admin(ctx.author):
            embed = discord.Embed(
                description="❌ You don't have permission to use this command (Administrator required).",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=8)
            return

        guild = ctx.guild
        if guild is None:
            embed = discord.Embed(
                description="❌ This command can only be used in a server.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=8)
            return

        try:
            await ctx.message.delete()
        except Exception:
            pass

        # === Smart handling to avoid duplicate channels ===
        # 1. If we already have a valid configured log channel that still exists, just inform
        if self.log_channel_id:
            existing_configured = guild.get_channel(self.log_channel_id)
            if existing_configured and isinstance(existing_configured, discord.TextChannel):
                embed = discord.Embed(
                    title="📋 Log Channel Already Configured",
                    description=f"Server logging is already pointing to {existing_configured.mention}.\nNo new channel was created.",
                    color=discord.Color.blurple(),
                )
                await ctx.send(embed=embed, delete_after=10)

                if not LOG_CHANNEL_ID:
                    note = discord.Embed(
                        description=(
                            "💡 Tip for Railway: Set `LOG_CHANNEL_ID` = "
                            f"`{self.log_channel_id}` in your service Variables so it survives redeploys."
                        ),
                        color=discord.Color.orange(),
                    )
                    await ctx.send(embed=note, delete_after=15)
                return

        # 2. Look for any existing channel literally named "server-logs"
        existing = discord.utils.get(guild.text_channels, name="server-logs")
        if existing:
            self.log_channel_id = existing.id
            save_config({"log_channel_id": str(existing.id)})

            embed = discord.Embed(
                title="📋 Log Channel Found",
                description=(
                    f"Found existing **{existing.mention}**.\n"
                    "Updated the bot config to use it for server logs.\n\n"
                    "No duplicate channel was created."
                ),
                color=discord.Color.green(),
            )
            await ctx.send(embed=embed, delete_after=12)

            if not LOG_CHANNEL_ID:
                note = discord.Embed(
                    description=(
                        "⚠️ **Railway users**: Add this as a Variable in the Railway dashboard for persistence across redeploys:\n"
                        f"`LOG_CHANNEL_ID` = `{existing.id}`"
                    ),
                    color=discord.Color.orange(),
                )
                await ctx.send(embed=note, delete_after=20)

            # Send a confirmation/test inside the log channel
            test = discord.Embed(
                title="✅ Server Logs Active",
                description="This channel is now configured to receive server activity logs.",
                color=discord.Color.green(),
            )
            if hasattr(self.bot, "send_log"):
                await self.bot.send_log(test)
            else:
                await existing.send(embed=test)
            return

        # 3. No existing one found → create a fresh one
        try:
            log_channel = await guild.create_text_channel(
                "server-logs",
                topic="Server activity logs • Joins, leaves, message changes, moderation, custom VCs and more. Do not delete this channel.",
                reason="Log channel created via c!createlogs command",
            )
        except discord.Forbidden:
            embed = discord.Embed(
                description="❌ I don't have permission to create channels. Make sure the bot has 'Manage Channels'.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=8)
            return
        except Exception as e:
            embed = discord.Embed(
                description=f"❌ Failed to create log channel: {e}",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=8)
            return

        self.log_channel_id = log_channel.id
        save_config({"log_channel_id": str(log_channel.id)})

        success = discord.Embed(
            title="📋 Log Channel Created",
            description=(
                f"Created **{log_channel.mention}** and enabled server logging.\n\n"
                "All important events will be recorded here:\n"
                "• Member joins and leaves\n"
                "• Deleted and edited messages\n"
                "• Mutes, bans, and other moderation\n"
                "• Custom voice channel creation/deletion\n"
                "• Voice activity (joins/leaves)\n\n"
                "You can restrict who can read this channel in Discord settings."
            ),
            color=discord.Color.green(),
        )
        await ctx.send(embed=success, delete_after=12)

        if not LOG_CHANNEL_ID:
            note = discord.Embed(
                description=(
                    "⚠️ **Railway users**: To keep this setting after future redeploys, go to Railway → Variables and set:\n"
                    f"`LOG_CHANNEL_ID` = `{log_channel.id}`"
                ),
                color=discord.Color.orange(),
            )
            await ctx.send(embed=note, delete_after=20)

        # Welcome message inside the new log channel
        welcome = discord.Embed(
            title="✅ Server Logs Active",
            description="This channel will automatically record important server events.",
            color=discord.Color.green(),
        )
        await log_channel.send(embed=welcome)

    @commands.command(name="logs")
    async def show_logs(self, ctx: commands.Context):
        if not self._is_admin(ctx.author):
            embed = discord.Embed(
                description="❌ You don't have permission to use this command (Administrator required).",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=8)
            return

        if self.log_channel_id:
            ch = ctx.guild.get_channel(self.log_channel_id)
            if ch:
                desc = f"Current log channel: {ch.mention} (`{ch.id}`)"
            else:
                desc = f"Configured channel ID `{self.log_channel_id}` (channel not found in this server)."
            source = " (from LOG_CHANNEL_ID env var)" if LOG_CHANNEL_ID else " (from config file)"
            desc += source
        else:
            desc = "No log channel configured.\nUse `c!setlogs #channel` or `c!createlogs`."

        embed = discord.Embed(
            title="📋 Server Logs Status",
            description=desc,
            color=discord.Color.blurple(),
        )
        await ctx.send(embed=embed, delete_after=15)

    # ==================== EVENT LISTENERS ====================

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        embed = discord.Embed(
            title="📥 Member Joined",
            description=f"{member.mention} (`{member.id}`)",
            color=discord.Color.green(),
        )
        embed.add_field(
            name="Account Created",
            value=format_dt(member.created_at),
            inline=True,
        )
        embed.add_field(
            name="Member Count",
            value=str(member.guild.member_count),
            inline=True,
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        await self._send_log(embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        embed = discord.Embed(
            title="📤 Member Left",
            description=f"{member} (`{member.id}`)",
            color=discord.Color.red(),
        )
        embed.add_field(
            name="Account Created",
            value=format_dt(member.created_at),
            inline=True,
        )
        embed.add_field(
            name="Joined Server",
            value=format_dt(member.joined_at),
            inline=True,
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        await self._send_log(embed)

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):
        """Log message deletions server-wide (works even for uncached/old messages)."""
        if payload.guild_id is None:
            return

        # If we have a cached version and it was a bot message, skip
        if payload.cached_message and payload.cached_message.author.bot:
            return

        channel = self.bot.get_channel(payload.channel_id)
        channel_str = channel.mention if channel and hasattr(channel, "mention") else f"<#{payload.channel_id}>"

        embed = discord.Embed(
            title="🗑️ Message Deleted",
            color=discord.Color.from_rgb(255, 100, 100),
        )
        embed.add_field(name="Channel", value=channel_str, inline=True)

        if payload.cached_message:
            # We have full info because the message was still in cache
            msg = payload.cached_message
            embed.add_field(
                name="Author",
                value=f"{msg.author} (`{msg.author.id}`)",
                inline=True,
            )
            content = (msg.content or "").strip()
            if content:
                if len(content) > 1024:
                    content = content[:1021] + "..."
                embed.add_field(name="Content", value=content, inline=False)
            else:
                embed.add_field(name="Content", value="*No text content*", inline=False)

            if msg.attachments:
                att = ", ".join([a.filename for a in msg.attachments[:5]])
                embed.add_field(name="Attachments", value=att, inline=False)
        else:
            # Uncached delete (old message, bot restart, or very high volume)
            embed.add_field(name="Author", value="Unknown (message not cached)", inline=True)
            embed.add_field(name="Message ID", value=str(payload.message_id), inline=True)
            embed.add_field(
                name="Note",
                value="Full content/author not available (the message was sent before the bot saw it or cache was cleared).",
                inline=False,
            )

        await self._send_log(embed)

    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload: discord.RawMessageUpdateEvent):
        """Log message edits server-wide."""
        if payload.guild_id is None:
            return

        # Get before state if available
        before = payload.cached_message

        if before and before.author.bot:
            return

        # Try to extract the new content from the raw data
        data = payload.data or {}
        after_content = data.get("content")

        if before:
            if before.content == after_content:
                return  # no meaningful text change
            old = (before.content or "*empty*").strip()
            author = before.author
            channel = before.channel
        else:
            old = "*unknown (not cached)*"
            author = None
            channel = self.bot.get_channel(payload.channel_id)

        new = (after_content or "*empty*").strip() if after_content else "*unknown*"

        if old == new:
            return

        embed = discord.Embed(
            title="✏️ Message Edited",
            color=discord.Color.orange(),
        )

        if author:
            embed.add_field(
                name="Author",
                value=f"{author} (`{author.id}`)",
                inline=True,
            )
        else:
            embed.add_field(name="Author", value="Unknown (not cached)", inline=True)

        channel_str = channel.mention if channel and hasattr(channel, "mention") else f"<#{payload.channel_id}>"
        embed.add_field(name="Channel", value=channel_str, inline=True)

        if len(old) > 512:
            old = old[:509] + "..."
        if len(new) > 512:
            new = new[:509] + "..."

        embed.add_field(name="Before", value=old, inline=False)
        embed.add_field(name="After", value=new, inline=False)

        # Try to include jump link if we have message id
        if payload.message_id:
            try:
                guild = self.bot.get_guild(payload.guild_id)
                ch = guild.get_channel(payload.channel_id) if guild else None
                if ch:
                    # We can't easily build jump_url without the message object, but we can note the ID
                    embed.add_field(
                        name="Message ID",
                        value=str(payload.message_id),
                        inline=False,
                    )
            except Exception:
                pass

        await self._send_log(embed)

    @commands.Cog.listener()
    async def on_voice_state_update(
        self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
    ):
        if before.channel == after.channel:
            return  # ignore pure mute/deafen changes

        if before.channel is None and after.channel is not None:
            title = "🔊 Voice Channel Joined"
            color = discord.Color.green()
            desc = f"{member.mention} joined **{after.channel.name}**"
        elif before.channel is not None and after.channel is None:
            title = "🔇 Voice Channel Left"
            color = discord.Color.red()
            desc = f"{member.mention} left **{before.channel.name}**"
        else:
            title = "🔄 Voice Channel Switched"
            color = discord.Color.blurple()
            desc = f"{member.mention} moved from **{before.channel.name}** to **{after.channel.name}**"

        embed = discord.Embed(title=title, description=desc, color=color)
        embed.add_field(name="User", value=f"{member} (`{member.id}`)", inline=True)
        await self._send_log(embed)

    @commands.Cog.listener()
    async def on_audit_log_entry_create(self, entry: discord.AuditLogEntry):
        # Skip actions performed by the bot itself (we log those in the commands)
        if entry.user and entry.user.id == self.bot.user.id:
            return

        if entry.action == discord.AuditLogAction.ban:
            target = entry.target
            moderator = entry.user or "Unknown"
            reason = entry.reason or "No reason provided"

            embed = discord.Embed(
                title="🔨 Member Banned",
                color=discord.Color.red(),
            )
            embed.add_field(
                name="User",
                value=f"{target} (`{getattr(target, 'id', 'N/A')}`)",
                inline=True,
            )
            embed.add_field(name="Moderator", value=str(moderator), inline=True)
            embed.add_field(name="Reason", value=reason, inline=False)
            await self._send_log(embed)

        elif entry.action == discord.AuditLogAction.unban:
            target = entry.target
            moderator = entry.user or "Unknown"
            reason = entry.reason or "No reason provided"

            embed = discord.Embed(
                title="🔓 Member Unbanned",
                color=discord.Color.green(),
            )
            embed.add_field(
                name="User",
                value=f"{target} (`{getattr(target, 'id', 'N/A')}`)",
                inline=True,
            )
            embed.add_field(name="Moderator", value=str(moderator), inline=True)
            embed.add_field(name="Reason", value=reason, inline=False)
            await self._send_log(embed)

        elif entry.action == discord.AuditLogAction.kick:
            target = entry.target
            moderator = entry.user or "Unknown"
            reason = entry.reason or "No reason provided"

            embed = discord.Embed(
                title="👢 Member Kicked",
                color=discord.Color.orange(),
            )
            embed.add_field(
                name="User",
                value=f"{target} (`{getattr(target, 'id', 'N/A')}`)",
                inline=True,
            )
            embed.add_field(name="Moderator", value=str(moderator), inline=True)
            embed.add_field(name="Reason", value=reason, inline=False)
            await self._send_log(embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Logging(bot))
