import discord
from discord.ext import commands
from datetime import timedelta


class SpamClear(commands.Cog):
    """Dedicated cog for server-wide spam message clearing (last 2 hours)."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="spam")
    async def spam(self, ctx: commands.Context, user_id: int = None):
        """
        c!spam <user_id>
        Deletes all messages from the specified user in the last 2 hours across the server.
        Only users with Administrator or Manage Messages can use this.
        """

        # Permission check: administrator or manage_messages (as specified)
        if not (
            ctx.author.guild_permissions.administrator
            or ctx.author.guild_permissions.manage_messages
        ):
            embed = discord.Embed(
                description="❌ You need Administrator or Manage Messages permission to use this command.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=8)
            return

        if user_id is None:
            embed = discord.Embed(
                description="❌ Correct usage: `c!spam <user_id>`",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=8)
            return

        # Fetch the target user (works even if not in guild)
        target = None
        try:
            target = await ctx.guild.fetch_member(user_id)
        except discord.NotFound:
            try:
                target = await self.bot.fetch_user(user_id)
            except discord.NotFound:
                embed = discord.Embed(
                    description="❌ User not found. Make sure the ID is correct.",
                    color=discord.Color.red(),
                )
                await ctx.send(embed=embed, delete_after=8)
                return
        except Exception:
            embed = discord.Embed(
                description="❌ Could not fetch the user.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=8)
            return

        # Delete the command message
        try:
            await ctx.message.delete()
        except Exception:
            pass

        # Calculate cutoff time (last 2 hours)
        cutoff = discord.utils.utcnow() - timedelta(hours=2)

        total_deleted = 0
        channels_affected = 0

        for channel in ctx.guild.text_channels:
            channel_deleted = 0
            try:
                # Preferred: efficient bulk purge (works for messages < 14 days)
                deleted = await channel.purge(
                    limit=500,
                    check=lambda m: m.author.id == user_id,
                    after=cutoff,
                )
                channel_deleted = len(deleted)
            except discord.Forbidden:
                # Bot cannot manage messages in this channel
                pass
            except Exception:
                # Fallback: individual deletes (for any edge cases)
                try:
                    async for message in channel.history(limit=200, after=cutoff):
                        if message.author.id == user_id:
                            await message.delete()
                            channel_deleted += 1
                except Exception:
                    pass

            if channel_deleted > 0:
                channels_affected += 1
                total_deleted += channel_deleted

        # Send confirmation embed (compact & professional, stays in chat)
        embed = discord.Embed(
            title="🧹 Messages Cleared",
            description=f"**{getattr(target, 'mention', f'<@{user_id}>')}** (`{user_id}`)",
            color=discord.Color.green() if total_deleted > 0 else discord.Color.orange(),
        )
        embed.add_field(name="Deleted", value=f"{total_deleted} messages", inline=True)
        embed.add_field(name="Channels", value=str(channels_affected), inline=True)
        embed.add_field(name="Period", value="Last 2 hours", inline=True)
        embed.set_footer(text=f"Action by {ctx.author.display_name} • {ctx.guild.name}")

        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(SpamClear(bot))
