import sqlite3
from datetime import datetime

import discord
from discord.ext import commands

from core.config import DATA_DIR


# ID do canal exclusivo de comandos de moderação (fornecido pelo usuário)
# Todos os comandos novos (warn, review, spam) só funcionam neste canal.
MOD_COMMANDS_CHANNEL_ID: int = 1508675820967690311


# ==================== SISTEMA DE WARNINGS (SQLite) ====================
# Banco de dados persistente para registrar warns de forma duradoura.
# Arquivo: data/warnings.db (dentro da pasta data/ do projeto)
# Tabela contém guild_id para facilitar expansão futura para multi-guild.

WARNINGS_DB = DATA_DIR / "warnings.db"


def init_warnings_db() -> None:
    """Cria o diretório de dados (se necessário) e a tabela de warnings."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(WARNINGS_DB)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS warnings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            moderator_id INTEGER NOT NULL,
            reason TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def add_warning(guild_id: int, user_id: int, moderator_id: int, reason: str) -> int:
    """
    Adiciona um novo warn no banco de dados.
    Retorna o ID (auto-increment) do warn recém-criado.
    """
    conn = sqlite3.connect(WARNINGS_DB)
    c = conn.cursor()
    ts = datetime.utcnow().isoformat()
    c.execute("""
        INSERT INTO warnings (guild_id, user_id, moderator_id, reason, timestamp)
        VALUES (?, ?, ?, ?, ?)
    """, (guild_id, user_id, moderator_id, reason, ts))
    warning_id = c.lastrowid
    conn.commit()
    conn.close()
    print(f"[DEBUG] Warning saved | ID={warning_id} | Guild={guild_id} | User={user_id} | Mod={moderator_id} | Reason={reason[:50]}")
    return warning_id


def get_user_warnings(guild_id: int, user_id: int) -> list[dict]:
    """
    Busca todos os warns de um usuário no servidor.
    Retorna lista de dicionários ordenada do mais recente para o mais antigo.
    Cada item: {id, moderator_id, reason, timestamp (formatado DD/MM/YYYY às HH:MM)}
    """
    conn = sqlite3.connect(WARNINGS_DB)
    c = conn.cursor()
    c.execute("""
        SELECT id, moderator_id, reason, timestamp
        FROM warnings
        WHERE guild_id = ? AND user_id = ?
        ORDER BY timestamp DESC
    """, (guild_id, user_id))
    rows = c.fetchall()
    conn.close()

    warnings_list = []
    for row in rows:
        try:
            dt = datetime.fromisoformat(row[3])
            formatted = dt.strftime("%d/%m/%Y às %H:%M")
        except Exception:
            formatted = row[3] or "Data desconhecida"

        warnings_list.append({
            "id": row[0],
            "moderator_id": row[1],
            "reason": row[2],
            "timestamp": formatted
        })
    print(f"[DEBUG] Review query | Guild={guild_id} | User={user_id} | Found={len(warnings_list)} warns")
    return warnings_list


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        init_warnings_db()  # Inicializa o banco de warnings na carga do cog (cria tabela se necessário)
        print(f"[LOG] Warnings database loaded from: {WARNINGS_DB} (persistence depends on Railway Volume for data/ folder)")

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

        muted_role = discord.utils.get(ctx.guild.roles, name="Muted")
        if muted_role is None:
            try:
                muted_role = await ctx.guild.create_role(
                    name="Muted",
                    color=discord.Color.from_rgb(128, 128, 128),
                    reason="Auto-created by bot",
                )
                for channel in ctx.guild.channels:
                    await channel.set_permissions(
                        muted_role,
                        send_messages=False,
                        speak=False,
                        add_reactions=False,
                    )
            except discord.Forbidden:
                embed = discord.Embed(
                    description="❌ I don't have permission to create the `Muted` role.",
                    color=discord.Color.red(),
                )
                await ctx.send(embed=embed, delete_after=8)
                return

        if muted_role in member.roles:
            embed = discord.Embed(
                description=f"⚠️ {member.mention} is already muted.",
                color=discord.Color.orange(),
            )
            await ctx.send(embed=embed, delete_after=8)
            return

        try:
            await member.add_roles(muted_role, reason=reason)
        except discord.Forbidden:
            embed = discord.Embed(
                description="❌ I don't have permission to mute this member.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=8)
            return

        try:
            await ctx.message.delete()
        except Exception:
            pass

        embed = discord.Embed(title="🔇 Member Muted", color=discord.Color.from_rgb(255, 165, 0))
        embed.add_field(name="👤 User", value=f"{member.mention} (`{member.id}`)", inline=True)
        embed.add_field(name="🛡️ Moderator", value=ctx.author.mention, inline=True)
        embed.add_field(name="📋 Reason", value=reason, inline=False)
        embed.set_footer(
            text=f"Action logged • Server: {ctx.guild.name}",
            icon_url=ctx.guild.icon.url if ctx.guild.icon else None,
        )
        await ctx.send(embed=embed)
        print(f"[LOG] Mute | {member} ({member.id}) | Reason: {reason} | By: {ctx.author}")

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

        await member.remove_roles(muted_role)

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
        Registra um warn persistente para um membro (armazenado em SQLite).
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