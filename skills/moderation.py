import sqlite3
from datetime import datetime

import discord
from discord.ext import commands

from core.config import DATA_DIR


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
    return warnings_list


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        init_warnings_db()  # Inicializa o banco de warnings na carga do cog (cria tabela se necessário)

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

        # Restrição: comando só pode ser usado no canal de moderação "mod commands"
        if getattr(ctx.channel, "name", "") != "mod commands":
            embed = discord.Embed(
                description="❌ This command can only be used in the `mod commands` channel.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=8)
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

        # Persiste no banco
        clean_reason = reason.strip()
        warning_id = add_warning(ctx.guild.id, member.id, ctx.author.id, clean_reason)

        # Tenta notificar por DM (opção solicitada)
        dm_sent = False
        try:
            dm_embed = discord.Embed(
                title="⚠️ You received a warning",
                description=(
                    f"**Server:** {ctx.guild.name}\n"
                    f"**Reason:** {clean_reason}\n"
                    f"**Moderator:** {ctx.author.mention}\n\n"
                    "Please follow the server rules to avoid further action."
                ),
                color=discord.Color.orange(),
            )
            dm_embed.set_footer(text=f"Warning ID: {warning_id}")
            await member.send(embed=dm_embed)
            dm_sent = True
        except Exception:
            # Usuário pode ter DMs fechadas ou bloqueado o bot
            pass

        # Deleta a mensagem do comando (padrão dos comandos de moderação)
        try:
            await ctx.message.delete()
        except Exception:
            pass

        # Embed público de confirmação (estilo consistente com mute/ban)
        embed = discord.Embed(title="⚠️ Member Warned", color=discord.Color.orange())
        embed.add_field(name="👤 User", value=f"{member.mention} (`{member.id}`)", inline=True)
        embed.add_field(name="🛡️ Moderator", value=ctx.author.mention, inline=True)
        embed.add_field(name="📋 Reason", value=clean_reason, inline=False)
        if dm_sent:
            embed.add_field(name="📨 Notification", value="User was notified via DM.", inline=False)
        else:
            embed.add_field(name="📨 Notification", value="Could not send DM (user may have DMs disabled).", inline=False)
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

    @commands.command(name="review", aliases=["warnings", "warns", "check", "infractions"])
    async def review(self, ctx: commands.Context, user_id: int = None):
        """
        Comando de revisão/histórico de warns.
        Nome principal: c!review
        Aliases: c!warnings, c!warns, c!check, c!infractions

        - Mostra total de warns
        - Lista organizada (mais recentes primeiro) com data no formato brasileiro
        - Thumbnail do avatar do usuário
        - Se zero warns: mensagem de "clean record"
        """
        if not self.has_permission(ctx.author):
            embed = discord.Embed(
                description="❌ You don't have permission to use this command.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=8)
            return

        # Restrição: comando só pode ser usado no canal de moderação "mod commands"
        if getattr(ctx.channel, "name", "") != "mod commands":
            embed = discord.Embed(
                description="❌ This command can only be used in the `mod commands` channel.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=8)
            return

        if user_id is None:
            embed = discord.Embed(
                description="❌ Correct usage: `c!review <id>` (aliases: c!warnings, c!warns, c!check)",
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
                description=f"{member.mention} (`{member.id}`) has no warnings on record.",
                color=discord.Color.green(),
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(
                text=f"Requested by {ctx.author.display_name} • Server: {ctx.guild.name}",
                icon_url=ctx.guild.icon.url if ctx.guild.icon else None,
            )
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

    @commands.command(name="spam")
    async def spam(self, ctx: commands.Context, user_id: int = None):
        """
        Comando anti-spam rápido.
        - Deleta mensagens recentes do usuário **apenas no canal atual**
        - Aplica mute automaticamente usando o mesmo sistema de cargo "Muted" do c!mute
        - Mostra resumo claro (quantas msgs deletadas + status do mute)
        - Não pede motivo (é spam por definição)
        """
        if not self.has_permission(ctx.author):
            embed = discord.Embed(
                description="❌ You don't have permission to use this command.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=8)
            return

        # Restrição: comando só pode ser usado no canal de moderação "mod commands"
        if getattr(ctx.channel, "name", "") != "mod commands":
            embed = discord.Embed(
                description="❌ This command can only be used in the `mod commands` channel.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=8)
            return

        if user_id is None:
            embed = discord.Embed(
                description="❌ Correct usage: `c!spam <id>`",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=8)
            return

        member = await self.get_member(ctx, user_id)
        if member is None:
            return

        if member == ctx.author:
            embed = discord.Embed(
                description="❌ You cannot use this command on yourself.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=8)
            return

        if member.top_role >= ctx.author.top_role and not ctx.author.guild_permissions.administrator:
            embed = discord.Embed(
                description="❌ You cannot moderate someone with an equal or higher role.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=8)
            return

        # 1. Deletar mensagens recentes do membro neste canal (usando purge com check)
        deleted_count = 0
        try:
            def check_author(m: discord.Message) -> bool:
                return m.author.id == member.id

            # Limite 50 é razoável e seguro. Purge só funciona em mensagens < 14 dias.
            deleted_messages = await ctx.channel.purge(
                limit=50,
                check=check_author,
                before=ctx.message,  # não tenta apagar o próprio comando
            )
            deleted_count = len(deleted_messages)
        except discord.Forbidden:
            # Bot sem permissão de gerenciar mensagens no canal
            embed = discord.Embed(
                description="❌ I don't have permission to delete messages in this channel.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=8)
            # Continua para aplicar o mute mesmo assim (melhor punir de alguma forma)
        except Exception as e:
            print(f"[ERROR] Spam purge failed: {e}")

        # 2. Aplicar mute reutilizando a mesma lógica do c!mute original (duplicação intencional
        #    para não alterar o código do mute e não criar helpers, conforme solicitado).
        #    Isso garante que c!unmute continue funcionando para mutes de spam.
        mute_reason = "Spam / mass messaging (via c!spam command)"
        mute_success = False

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
                muted_role = None

        if muted_role is not None:
            if muted_role in member.roles:
                mute_success = True  # já estava mutado
            else:
                try:
                    await member.add_roles(muted_role, reason=mute_reason)
                    mute_success = True
                except discord.Forbidden:
                    mute_success = False
                except Exception:
                    mute_success = False

        # Deleta a mensagem do comando
        try:
            await ctx.message.delete()
        except Exception:
            pass

        # Embed de resumo da ação
        embed = discord.Embed(title="🚫 Spam Action Taken", color=discord.Color.red())
        embed.add_field(name="👤 User", value=f"{member.mention} (`{member.id}`)", inline=True)
        embed.add_field(name="🛡️ Moderator", value=ctx.author.mention, inline=True)
        embed.add_field(
            name="🗑️ Messages Deleted",
            value=f"{deleted_count} recent message(s) deleted in this channel.",
            inline=False,
        )

        if mute_success:
            embed.add_field(
                name="🔇 Mute Applied",
                value="Member was muted using the server's `Muted` role system.\nUse `c!unmute` to remove when appropriate.",
                inline=False,
            )
        else:
            embed.add_field(
                name="🔇 Mute Failed",
                value="Could not apply the Muted role (check bot permissions and role hierarchy).",
                inline=False,
            )

        embed.set_footer(
            text=f"Action logged • Server: {ctx.guild.name}",
            icon_url=ctx.guild.icon.url if ctx.guild.icon else None,
        )
        await ctx.send(embed=embed)

        print(f"[LOG] Spam | {member} ({member.id}) | Deleted: {deleted_count} | Mute: {mute_success} | By: {ctx.author}")

        # Log detalhado no canal de logs
        log_embed = discord.Embed(
            title="🚫 Spam Action Taken",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        log_embed.set_author(name=str(member), icon_url=member.display_avatar.url)
        log_embed.add_field(name="User", value=f"{member.mention} (`{member.id}`)", inline=True)
        log_embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
        log_embed.add_field(name="Messages Deleted (channel)", value=str(deleted_count), inline=True)
        log_embed.add_field(name="Mute Applied", value="Yes" if mute_success else "No", inline=True)
        log_embed.add_field(name="User ID", value=str(member.id), inline=True)
        if hasattr(self.bot, "send_log"):
            await self.bot.send_log(log_embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))