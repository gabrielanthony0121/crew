import discord
from discord.ext import commands

from core.mute_helpers import (
    UnmanageableRolesError,
    VoiceDisconnectError,
    apply_mute,
    get_or_create_muted_role,
    remove_mute,
)
from core.muted_roles_db import init_muted_roles_db
from core.warnings_db import add_warning, clear_user_warnings, get_user_warnings, init_warnings_db


# ID do canal exclusivo de comandos de moderação (fornecido pelo usuário)
# Todos os comandos novos (warn, review, spam) só funcionam neste canal.
MOD_COMMANDS_CHANNEL_ID: int = 1508675820967690311


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        init_warnings_db()
        init_muted_roles_db()

    def has_permission(self, author: discord.Member) -> bool:
        return (
            author.guild_permissions.administrator
            or author.guild_permissions.manage_roles
            or author.guild_permissions.moderate_members
            or author.guild_permissions.ban_members
        )

    async def get_member(self, ctx: commands.Context, user_id: int):
        member = ctx.guild.get_member(user_id)
        if member is None:
            try:
                member = await ctx.guild.fetch_member(user_id)
            except Exception:
                embed = discord.Embed(
                    description="❌ Member not found. Check the ID.",
                    color=discord.Color.red(),
                )
                await ctx.send(embed=embed, delete_after=8)
                return None
        return member

    def _get_mod_channel_id(self, channel) -> int:
        """Resolve o ID 'efetivo' do canal para a restrição de moderação.
        Se o usuário estiver dentro de um Thread/Post (muito comum quando o canal é um Forum ou tem threads),
        usamos o ID do canal pai em vez do ID do thread.
        """
        if isinstance(channel, discord.Thread):
            return getattr(getattr(channel, "parent", None), "id", channel.id)
        return getattr(channel, "id", 0)

    @commands.command(name="mute")
    async def mute(
        self,
        ctx: commands.Context,
        user_id: int = None,
        *,
        reason: str = "No reason provided",
    ):
        if not self.has_permission(ctx.author):
            embed = discord.Embed(
                description="❌ You don't have permission to use this command.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=8)
            return

        if user_id is None:
            embed = discord.Embed(
                description="❌ Correct usage: `c!mute <id> [reason]`",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=8)
            return

        member = await self.get_member(ctx, user_id)
        if member is None:
            return

        if member == ctx.author:
            embed = discord.Embed(
                description="❌ You cannot mute yourself.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=8)
            return

        if member.top_role >= ctx.author.top_role and not ctx.author.guild_permissions.administrator:
            embed = discord.Embed(
                description="❌ You cannot mute someone with an equal or higher role.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=8)
            return

        muted_role = await get_or_create_muted_role(ctx.guild)
        if muted_role is None:
            embed = discord.Embed(
                description="❌ I don't have permission to create the `Muted` role.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=8)
            return

        extra_roles = [
            role
            for role in member.roles
            if role != ctx.guild.default_role and role != muted_role
        ]
        if muted_role in member.roles and not extra_roles:
            embed = discord.Embed(
                description=f"⚠️ {member.mention} is already muted.",
                color=discord.Color.orange(),
            )
            await ctx.send(embed=embed, delete_after=8)
            return

        try:
            await apply_mute(member, muted_role, reason)
        except VoiceDisconnectError:
            embed = discord.Embed(
                description=(
                    "❌ I could not disconnect this member from voice. "
                    "Give me **Move Members** in that voice channel."
                ),
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=10)
            return
        except UnmanageableRolesError as exc:
            embed = discord.Embed(
                description=(
                    "❌ I cannot remove this member's roles because some are above my role: "
                    f"**{exc.role_names}**. Move my bot role higher in the server settings."
                ),
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=10)
            return
        except discord.Forbidden:
            embed = discord.Embed(
                description=(
                    "❌ I don't have permission to mute this member. "
                    "Make sure my role is above theirs and I have **Manage Roles**."
                ),
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=8)
            return
        except Exception as exc:
            print(f"[ERROR] Mute failed for {user_id}: {exc}")
            embed = discord.Embed(
                description=f"❌ Mute failed: `{exc}`",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=10)
            return

        try:
            await ctx.message.delete()
        except Exception:
            pass

        member = await ctx.guild.fetch_member(user_id)
        embed = discord.Embed(title="🔇 Member Muted", color=discord.Color.from_rgb(255, 165, 0))
        embed.add_field(name="👤 User", value=f"{member.mention} (`{member.id}`)", inline=True)
        embed.add_field(name="🛡️ Moderator", value=ctx.author.mention, inline=True)
        embed.add_field(name="📋 Reason", value=reason, inline=False)
        current_roles = [
            role.name for role in member.roles
            if role != ctx.guild.default_role
        ]
        embed.add_field(
            name="Current Roles",
            value=", ".join(current_roles) if current_roles else "Muted only",
            inline=False,
        )
        embed.set_footer(
            text=f"Action logged • Server: {ctx.guild.name}",
            icon_url=ctx.guild.icon.url if ctx.guild.icon else None,
        )
        await ctx.send(embed=embed)
        print(f"[LOG] Mute | {member} ({member.id}) | Roles: {current_roles} | Reason: {reason} | By: {ctx.author}")

        # Also send to configured log channel
        log_embed = discord.Embed(title="🔇 Member Muted", color=discord.Color.from_rgb(255, 165, 0), timestamp=discord.utils.utcnow())
        log_embed.set_author(name=str(member), icon_url=member.display_avatar.url)
        log_embed.add_field(name="User", value=f"{member.mention} (`{member.id}`)", inline=True)
        log_embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
        log_embed.add_field(name="Reason", value=reason, inline=False)
        log_embed.add_field(name="User ID", value=str(member.id), inline=True)
        if hasattr(self.bot, "send_log"):
            await self.bot.send_log(log_embed)

    @commands.command(name="unmute")
    async def unmute(self, ctx: commands.Context, user_id: int = None):
        if not self.has_permission(ctx.author):
            embed = discord.Embed(
                description="❌ You don't have permission to use this command.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=8)
            return

        if user_id is None:
            embed = discord.Embed(
                description="❌ Correct usage: `c!unmute <id>`",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=8)
            return

        member = await self.get_member(ctx, user_id)
        if member is None:
            return

        muted_role = discord.utils.get(ctx.guild.roles, name="Muted")
        if muted_role is None or muted_role not in member.roles:
            embed = discord.Embed(
                description=f"⚠️ {member.mention} is not muted.",
                color=discord.Color.orange(),
            )
            await ctx.send(embed=embed, delete_after=8)
            return

        try:
            await remove_mute(member, muted_role, reason="Unmuted via c!unmute")
        except discord.Forbidden:
            embed = discord.Embed(
                description=(
                    "❌ I don't have permission to unmute this member. "
                    "Make sure my role is above theirs and I have **Manage Roles**."
                ),
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=8)
            return

        try:
            await ctx.message.delete()
        except Exception:
            pass

        embed = discord.Embed(title="🔊 Member Unmuted", color=discord.Color.green())
        embed.add_field(name="👤 User", value=f"{member.mention} (`{member.id}`)", inline=True)
        embed.add_field(name="🛡️ Moderator", value=ctx.author.mention, inline=True)
        embed.set_footer(
            text=f"Action logged • Server: {ctx.guild.name}",
            icon_url=ctx.guild.icon.url if ctx.guild.icon else None,
        )
        await ctx.send(embed=embed)
        print(f"[LOG] Unmute | {member} ({member.id}) | By: {ctx.author}")

        # Also send to configured log channel
        log_embed = discord.Embed(title="🔊 Member Unmuted", color=discord.Color.green(), timestamp=discord.utils.utcnow())
        log_embed.set_author(name=str(member), icon_url=member.display_avatar.url)
        log_embed.add_field(name="User", value=f"{member.mention} (`{member.id}`)", inline=True)
        log_embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
        log_embed.add_field(name="User ID", value=str(member.id), inline=True)
        if hasattr(self.bot, "send_log"):
            await self.bot.send_log(log_embed)

    @commands.command(name="ban")
    async def ban(
        self,
        ctx: commands.Context,
        user_id: int = None,
        *,
        reason: str = "No reason provided",
    ):
        if not self.has_permission(ctx.author):
            embed = discord.Embed(
                description="❌ You don't have permission to use this command.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=8)
            return

        if user_id is None:
            embed = discord.Embed(
                description="❌ Correct usage: `c!ban <id> [reason]`",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=8)
            return

        member = await self.get_member(ctx, user_id)
        if member is None:
            return

        if member == ctx.author:
            embed = discord.Embed(
                description="❌ You cannot ban yourself.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=8)
            return

        if member.top_role >= ctx.author.top_role and not ctx.author.guild_permissions.administrator:
            embed = discord.Embed(
                description="❌ You cannot ban someone with an equal or higher role.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=8)
            return

        try:
            await ctx.message.delete()
        except Exception:
            pass

        try:
            await member.ban(reason=reason, delete_message_days=0)
        except discord.Forbidden:
            embed = discord.Embed(
                description="❌ I don't have permission to ban this member.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=8)
            return
        except Exception as e:
            embed = discord.Embed(
                description=f"❌ Failed to ban member: {e}",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=8)
            return

        embed = discord.Embed(title="🔨 Member Banned", color=discord.Color.red())
        embed.add_field(name="👤 User", value=f"{member.mention} (`{member.id}`)", inline=True)
        embed.add_field(name="🛡️ Moderator", value=ctx.author.mention, inline=True)
        embed.add_field(name="📋 Reason", value=reason, inline=False)
        embed.set_footer(
            text=f"Action logged • Server: {ctx.guild.name}",
            icon_url=ctx.guild.icon.url if ctx.guild.icon else None,
        )
        await ctx.send(embed=embed)
        print(f"[LOG] Ban | {member} ({member.id}) | Reason: {reason} | By: {ctx.author}")

        # Log channel
        log_embed = discord.Embed(title="🔨 Member Banned", color=discord.Color.red(), timestamp=discord.utils.utcnow())
        log_embed.set_author(name=str(member), icon_url=member.display_avatar.url)
        log_embed.add_field(name="User", value=f"{member.mention} (`{member.id}`)", inline=True)
        log_embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
        log_embed.add_field(name="Reason", value=reason, inline=False)
        log_embed.add_field(name="User ID", value=str(member.id), inline=True)
        if hasattr(self.bot, "send_log"):
            await self.bot.send_log(log_embed)

    @commands.command(name="unban")
    async def unban(self, ctx: commands.Context, user_id: int = None, *, reason: str = "No reason provided"):
        if not self.has_permission(ctx.author):
            embed = discord.Embed(
                description="❌ You don't have permission to use this command.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=8)
            return

        if user_id is None:
            embed = discord.Embed(
                description="❌ Correct usage: `c!unban <id>`",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=8)
            return

        try:
            await ctx.message.delete()
        except Exception:
            pass

        try:
            user = await self.bot.fetch_user(user_id)
        except Exception:
            embed = discord.Embed(
                description="❌ User not found. Make sure the ID is correct.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=8)
            return

        try:
            await ctx.guild.unban(user, reason=reason)
        except discord.NotFound:
            embed = discord.Embed(
                description=f"⚠️ {user.mention} (`{user.id}`) is not banned.",
                color=discord.Color.orange(),
            )
            await ctx.send(embed=embed, delete_after=8)
            return
        except discord.Forbidden:
            embed = discord.Embed(
                description="❌ I don't have permission to unban this user.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=8)
            return
        except Exception as e:
            embed = discord.Embed(
                description=f"❌ Failed to unban: {e}",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=8)
            return

        embed = discord.Embed(title="🔓 Member Unbanned", color=discord.Color.green())
        embed.add_field(name="👤 User", value=f"{user.mention} (`{user.id}`)", inline=True)
        embed.add_field(name="🛡️ Moderator", value=ctx.author.mention, inline=True)
        embed.add_field(name="📋 Reason", value=reason, inline=False)
        embed.set_footer(
            text=f"Action logged • Server: {ctx.guild.name}",
            icon_url=ctx.guild.icon.url if ctx.guild.icon else None,
        )
        await ctx.send(embed=embed)
        print(f"[LOG] Unban | {user} ({user.id}) | Reason: {reason} | By: {ctx.author}")

        # Log channel
        log_embed = discord.Embed(title="🔓 Member Unbanned", color=discord.Color.green(), timestamp=discord.utils.utcnow())
        log_embed.set_author(name=str(user), icon_url=user.display_avatar.url)
        log_embed.add_field(name="User", value=f"{user.mention} (`{user.id}`)", inline=True)
        log_embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
        log_embed.add_field(name="Reason", value=reason, inline=False)
        log_embed.add_field(name="User ID", value=str(user.id), inline=True)
        if hasattr(self.bot, "send_log"):
            await self.bot.send_log(log_embed)

    # ==================== NOVOS COMANDOS DE MODERAÇÃO ====================

    @commands.command(name="warn")
    async def warn(
        self,
        ctx: commands.Context,
        user_id: int = None,
        *,
        reason: str = None,
    ):
        """
        Registra um warn persistente para um membro (PostgreSQL no Railway, SQLite local).
        - Aceita ID numérico
        - Valida que o motivo não está vazio e tem tamanho mínimo
        - Tenta avisar o usuário por DM (falha silenciosa se DMs bloqueadas)
        - Envia embed de confirmação + registra no canal de logs (se configurado)
        """
        if not self.has_permission(ctx.author):
            embed = discord.Embed(
                description="❌ You don't have permission to use this command.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=8)
            return

        # Restrição de canal (resolve corretamente threads/posts de forum)
        effective_id = self._get_mod_channel_id(ctx.channel)
        if effective_id != MOD_COMMANDS_CHANNEL_ID:
            print(f"[DEBUG] Mod command blocked - Effective ID: {effective_id} | Raw channel ID: {getattr(ctx.channel, 'id', None)} | Expected: {MOD_COMMANDS_CHANNEL_ID} | Command: {ctx.command}")
            embed = discord.Embed(
                description=(
                    "❌ This command can only be used in the `mod commands` channel.\n\n"
                    f"**Channel ID the bot sees (effective):** `{effective_id}`\n"
                    f"**Configured ID:** `{MOD_COMMANDS_CHANNEL_ID}`\n\n"
                    "If you are inside a thread or post inside the channel, the bot now correctly checks the parent channel."
                ),
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=15)
            return

        if user_id is None or reason is None or len(reason.strip()) < 4:
            embed = discord.Embed(
                description="❌ Correct usage: `c!warn <id> <reason>`\nReason must be at least 4 characters long.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=8)
            return

        member = await self.get_member(ctx, user_id)
        if member is None:
            return

        if member == ctx.author:
            embed = discord.Embed(
                description="❌ You cannot warn yourself.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=8)
            return

        # Respeita hierarquia (mesmo padrão dos outros comandos de moderação)
        if member.top_role >= ctx.author.top_role and not ctx.author.guild_permissions.administrator:
            embed = discord.Embed(
                description="❌ You cannot warn someone with an equal or higher role.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=8)
            return

        # Persiste no banco (apenas para staff/moderadores - sem aviso ao membro)
        clean_reason = reason.strip()
        warning_id = add_warning(ctx.guild.id, member.id, ctx.author.id, clean_reason)

        # Deleta a mensagem do comando (padrão dos comandos de moderação)
        try:
            await ctx.message.delete()
        except Exception:
            pass

        # Embed público de confirmação (apenas para moderação - sem notificação ao membro)
        embed = discord.Embed(title="⚠️ Member Warned", color=discord.Color.orange())
        embed.add_field(name="👤 User", value=f"{member.mention} (`{member.id}`)", inline=True)
        embed.add_field(name="🛡️ Moderator", value=ctx.author.mention, inline=True)
        embed.add_field(name="📋 Reason", value=clean_reason, inline=False)
        embed.set_footer(
            text=f"Action logged • Server: {ctx.guild.name}",
            icon_url=ctx.guild.icon.url if ctx.guild.icon else None,
        )
        await ctx.send(embed=embed)

        print(f"[LOG] Warn | {member} ({member.id}) | Reason: {clean_reason} | By: {ctx.author} | ID: {warning_id}")

        # Envia para o canal de logs configurado (integra com skills/logging.py)
        log_embed = discord.Embed(
            title="⚠️ Member Warned",
            color=discord.Color.orange(),
            timestamp=discord.utils.utcnow()
        )
        log_embed.set_author(name=str(member), icon_url=member.display_avatar.url)
        log_embed.add_field(name="User", value=f"{member.mention} (`{member.id}`)", inline=True)
        log_embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
        log_embed.add_field(name="Reason", value=clean_reason, inline=False)
        log_embed.add_field(name="User ID", value=str(member.id), inline=True)
        log_embed.add_field(name="Warning ID", value=str(warning_id), inline=True)
        if hasattr(self.bot, "send_log"):
            await self.bot.send_log(log_embed)

    @commands.command(name="review")
    async def review(self, ctx: commands.Context, user_id: int = None):
        """
        Review a member's warning history.
        Only c!review (no extra aliases).

        - Shows total warnings
        - Lists warnings (most recent first) with Brazilian date format
        - User's avatar thumbnail
        - If no warnings: "Clean Record" message
        """
        if not self.has_permission(ctx.author):
            embed = discord.Embed(
                description="❌ You don't have permission to use this command.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=8)
            return

        # Restrição de canal (resolve corretamente threads/posts de forum)
        effective_id = self._get_mod_channel_id(ctx.channel)
        if effective_id != MOD_COMMANDS_CHANNEL_ID:
            print(f"[DEBUG] Mod command blocked - Effective ID: {effective_id} | Raw channel ID: {getattr(ctx.channel, 'id', None)} | Expected: {MOD_COMMANDS_CHANNEL_ID} | Command: {ctx.command}")
            embed = discord.Embed(
                description=(
                    "❌ This command can only be used in the `mod commands` channel.\n\n"
                    f"**Channel ID the bot sees (effective):** `{effective_id}`\n"
                    f"**Configured ID:** `{MOD_COMMANDS_CHANNEL_ID}`\n\n"
                    "If you are inside a thread or post inside the channel, the bot now correctly checks the parent channel."
                ),
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=15)
            return

        if user_id is None:
            embed = discord.Embed(
                description="❌ Correct usage: `c!review <id>`",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=8)
            return

        member = await self.get_member(ctx, user_id)
        if member is None:
            return

        warns = get_user_warnings(ctx.guild.id, member.id)

        if not warns:
            embed = discord.Embed(
                title="✅ Clean Record",
                color=discord.Color.green(),
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.add_field(name="Total Warnings", value="0", inline=True)
            embed.add_field(name="User ID", value=str(member.id), inline=True)
            embed.add_field(
                name="Status",
                value=f"{member.mention} has no warnings on record.",
                inline=False,
            )
            embed.set_footer(text=f"Requested by {ctx.author.display_name}")
            await ctx.send(embed=embed)
            return

        # Tem warns — monta embed organizado
        embed = discord.Embed(
            title=f"📋 Warnings for {member.display_name}",
            color=discord.Color.orange(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Total Warnings", value=str(len(warns)), inline=True)
        embed.add_field(name="User ID", value=str(member.id), inline=True)

        # Monta a lista (mais recentes primeiro — já vem ordenado do DB)
        lines = []
        for i, w in enumerate(warns, 1):
            mod_str = f"<@{w['moderator_id']}>"
            line = f"**#{i}** • {w['timestamp']} • By: {mod_str}\n> {w['reason']}"
            lines.append(line)

        # Limita tamanho para não estourar o limite do embed (1024 chars por field)
        content = "\n\n".join(lines)
        if len(content) > 1000:
            content = content[:997] + "...\n*(older warnings truncated)*"

        embed.add_field(
            name="Recent Warnings (newest first)",
            value=content if content else "No details available.",
            inline=False,
        )

        embed.set_footer(
            text=f"Requested by {ctx.author.display_name} • Server: {ctx.guild.name}",
            icon_url=ctx.guild.icon.url if ctx.guild.icon else None,
        )
        await ctx.send(embed=embed)

    @commands.command(name="clearwarn")
    async def clearwarn(
        self,
        ctx: commands.Context,
        user_id: int = None,
        *,
        reason: str = "No reason provided",
    ):
        """Clear all warnings from a member's record."""
        if not self.has_permission(ctx.author):
            embed = discord.Embed(
                description="❌ You don't have permission to use this command.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=8)
            return

        effective_id = self._get_mod_channel_id(ctx.channel)
        if effective_id != MOD_COMMANDS_CHANNEL_ID:
            embed = discord.Embed(
                description=(
                    "❌ This command can only be used in the `mod commands` channel.\n\n"
                    f"**Channel ID the bot sees (effective):** `{effective_id}`\n"
                    f"**Configured ID:** `{MOD_COMMANDS_CHANNEL_ID}`"
                ),
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=15)
            return

        if user_id is None:
            embed = discord.Embed(
                description="❌ Correct usage: `c!clearwarn <id> [reason]`",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=8)
            return

        member = await self.get_member(ctx, user_id)
        if member is None:
            return

        if member.top_role >= ctx.author.top_role and not ctx.author.guild_permissions.administrator:
            embed = discord.Embed(
                description="❌ You cannot clear warnings for someone with an equal or higher role.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=8)
            return

        previous_count = len(get_user_warnings(ctx.guild.id, member.id))
        if previous_count == 0:
            embed = discord.Embed(
                title="✅ Clean Record",
                description=f"{member.mention} has no warnings to clear.",
                color=discord.Color.green(),
            )
            await ctx.send(embed=embed, delete_after=8)
            return

        removed = clear_user_warnings(ctx.guild.id, member.id)

        try:
            await ctx.message.delete()
        except Exception:
            pass

        embed = discord.Embed(title="🧹 Warnings Cleared", color=discord.Color.green())
        embed.add_field(name="👤 User", value=f"{member.mention} (`{member.id}`)", inline=True)
        embed.add_field(name="🛡️ Moderator", value=ctx.author.mention, inline=True)
        embed.add_field(name="📋 Warnings Removed", value=str(removed), inline=True)
        embed.add_field(name="📋 Reason", value=reason.strip(), inline=False)
        embed.set_footer(
            text=f"Action logged • Server: {ctx.guild.name}",
            icon_url=ctx.guild.icon.url if ctx.guild.icon else None,
        )
        await ctx.send(embed=embed)

        print(
            f"[LOG] Clearwarn | {member} ({member.id}) | Removed: {removed} "
            f"| Reason: {reason} | By: {ctx.author}"
        )

        log_embed = discord.Embed(
            title="🧹 Warnings Cleared",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow(),
        )
        log_embed.set_author(name=str(member), icon_url=member.display_avatar.url)
        log_embed.add_field(name="User", value=f"{member.mention} (`{member.id}`)", inline=True)
        log_embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
        log_embed.add_field(name="Warnings Removed", value=str(removed), inline=True)
        log_embed.add_field(name="Reason", value=reason.strip(), inline=False)
        log_embed.add_field(name="User ID", value=str(member.id), inline=True)
        if hasattr(self.bot, "send_log"):
            await self.bot.send_log(log_embed)

    @commands.command(name="sendmodguide")
    @commands.has_permissions(administrator=True)
    async def send_mod_guide(self, ctx):
        """Envia (ou reenvia) o guia permanente de moderação no canal de anúncios."""
        from skills.mod_guide import get_mod_guide_embed
        from core.config import MOD_ANNOUNCEMENTS_CHANNEL_ID

        embed = await get_mod_guide_embed()

        channel = self.bot.get_channel(MOD_ANNOUNCEMENTS_CHANNEL_ID)
        if channel is None:
            channel = await self.bot.fetch_channel(MOD_ANNOUNCEMENTS_CHANNEL_ID)

        await channel.send(embed=embed)
        await ctx.send("✅ Guia de moderação enviado para #mod-announcements!", delete_after=8)

async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))