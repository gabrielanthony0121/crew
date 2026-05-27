import discord
from discord.ext import commands
import asyncio


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def has_permission(self, author: discord.Member) -> bool:
        return (
            author.guild_permissions.administrator or
            author.guild_permissions.manage_roles or
            author.guild_permissions.moderate_members
        )

    async def get_member(self, ctx, user_id):
        member = ctx.guild.get_member(user_id)
        if member is None:
            try:
                member = await ctx.guild.fetch_member(user_id)
            except Exception:
                embed = discord.Embed(description="❌ Member not found. Check the ID.", color=discord.Color.red())
                await ctx.send(embed=embed, delete_after=8)
                return None
        return member

    # ──────────────────────────────────────────
    #  c!mute <id> [reason]
    # ──────────────────────────────────────────
    @commands.command(name="mute")
    async def mute(self, ctx: commands.Context, user_id: int = None, *, reason: str = "No reason provided"):

        if not self.has_permission(ctx.author):
            embed = discord.Embed(description="❌ You don't have permission to use this command.", color=discord.Color.red())
            await ctx.send(embed=embed, delete_after=8)
            return

        if user_id is None:
            embed = discord.Embed(description="❌ Correct usage: `c!mute <id> [reason]`", color=discord.Color.red())
            await ctx.send(embed=embed, delete_after=8)
            return

        member = await self.get_member(ctx, user_id)
        if member is None:
            return

        if member == ctx.author:
            embed = discord.Embed(description="❌ You cannot mute yourself.", color=discord.Color.red())
            await ctx.send(embed=embed, delete_after=8)
            return

        if member.top_role >= ctx.author.top_role and not ctx.author.guild_permissions.administrator:
            embed = discord.Embed(description="❌ You cannot mute someone with an equal or higher role.", color=discord.Color.red())
            await ctx.send(embed=embed, delete_after=8)
            return

        muted_role = discord.utils.get(ctx.guild.roles, name="Muted")
        if muted_role is None:
            try:
                muted_role = await ctx.guild.create_role(name="Muted", color=discord.Color.from_rgb(128, 128, 128), reason="Auto-created by bot")
                for channel in ctx.guild.channels:
                    await channel.set_permissions(muted_role, send_messages=False, speak=False, add_reactions=False)
            except discord.Forbidden:
                embed = discord.Embed(description="❌ I don't have permission to create the `Muted` role.", color=discord.Color.red())
                await ctx.send(embed=embed, delete_after=8)
                return

        if muted_role in member.roles:
            embed = discord.Embed(description=f"⚠️ {member.mention} is already muted.", color=discord.Color.orange())
            await ctx.send(embed=embed, delete_after=8)
            return

        try:
            await member.add_roles(muted_role, reason=reason)
        except discord.Forbidden:
            embed = discord.Embed(description="❌ I don't have permission to mute this member.", color=discord.Color.red())
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
        embed.set_footer(text=f"Action logged • Server: {ctx.guild.name}", icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
        await ctx.send(embed=embed)
        print(f"[LOG] Mute | {member} ({member.id}) | Reason: {reason} | By: {ctx.author}")

    # ──────────────────────────────────────────
    #  c!unmute <id>
    # ──────────────────────────────────────────
    @commands.command(name="unmute")
    async def unmute(self, ctx: commands.Context, user_id: int = None):

        if not self.has_permission(ctx.author):
            embed = discord.Embed(description="❌ You don't have permission to use this command.", color=discord.Color.red())
            await ctx.send(embed=embed, delete_after=8)
            return

        if user_id is None:
            embed = discord.Embed(description="❌ Correct usage: `c!unmute <id>`", color=discord.Color.red())
            await ctx.send(embed=embed, delete_after=8)
            return

        member = await self.get_member(ctx, user_id)
        if member is None:
            return

        muted_role = discord.utils.get(ctx.guild.roles, name="Muted")
        if muted_role is None or muted_role not in member.roles:
            embed = discord.Embed(description=f"⚠️ {member.mention} is not muted.", color=discord.Color.orange())
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
        embed.set_footer(text=f"Action logged • Server: {ctx.guild.name}", icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
        await ctx.send(embed=embed)
        print(f"[LOG] Unmute | {member} ({member.id}) | By: {ctx.author}")


async def setup(bot):
    await bot.add_cog(Moderation(bot))
