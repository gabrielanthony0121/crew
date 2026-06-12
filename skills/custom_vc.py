import json
import os

import discord
from discord.ext import commands

from core.config import DATA_DIR

CONFIG_FILE = DATA_DIR / "vc_config.json"


def load_config() -> dict:
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"category_id": None, "role_id": None}


def save_config(data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


class CreateVCModal(discord.ui.Modal, title="🎙️ Create Your Voice Channel"):
    channel_name = discord.ui.TextInput(
        label="Voice Channel Name",
        placeholder="e.g. My Gaming Room",
        min_length=2,
        max_length=32,
        style=discord.TextStyle.short,
    )

    async def on_submit(self, interaction: discord.Interaction):
        cfg = load_config()
        guild = interaction.guild
        member = interaction.user

        role_id = cfg.get("role_id")
        if role_id:
            allowed_role = guild.get_role(int(role_id))
            if allowed_role and allowed_role not in member.roles:
                await interaction.response.send_message(
                    "❌ You don't have the required role to create a voice channel.",
                    ephemeral=True,
                )
                return

        category_id = cfg.get("category_id")
        category = guild.get_channel(int(category_id)) if category_id else None

        if category:
            for ch in category.voice_channels:
                if ch.overwrites_for(member).manage_channels is True:
                    await interaction.response.send_message(
                        f"❌ You already have a voice channel: **{ch.name}**\n"
                        "Delete it first with `c!deletevc`",
                        ephemeral=True,
                    )
                    return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(
                view_channel=True,
                connect=False,
            ),
            member: discord.PermissionOverwrite(
                view_channel=True,
                connect=True,
                speak=True,
                stream=True,
                use_voice_activation=True,
                manage_channels=True,
                move_members=True,
                mute_members=True,
                deafen_members=True,
                priority_speaker=True,
            ),
        }

        try:
            channel = await guild.create_voice_channel(
                name=self.channel_name.value,
                category=category,
                overwrites=overwrites,
                reason=f"Custom VC created by {member}",
            )

            embed = discord.Embed(
                title="✅ Voice Channel Created!",
                description=(
                    f"Your room **{channel.name}** is ready!\n\n"
                    "**Your permissions as owner:**\n"
                    "🏷️ Rename the channel\n"
                    "👢 Move & kick members\n"
                    "🔇 Mute & deafen members\n\n"
                    "To delete your room: `c!deletevc`"
                ),
                color=discord.Color.green(),
            )
            embed.set_footer(text=f"Owner: {member.display_name}")

            await interaction.response.send_message(embed=embed, ephemeral=True)
            print(f"[LOG] Custom VC created: '{channel.name}' by {member} ({member.id})")

            # Log to server logs channel
            log_embed = discord.Embed(
                title="🎙️ Custom Voice Channel Created",
                color=discord.Color.from_rgb(67, 181, 129),
                timestamp=discord.utils.utcnow()
            )
            log_embed.set_author(name=str(member), icon_url=member.display_avatar.url)
            log_embed.add_field(name="Channel", value=f"**{channel.name}** (`{channel.id}`)", inline=True)
            log_embed.add_field(name="Owner", value=f"{member.mention} (`{member.id}`)", inline=True)
            log_embed.add_field(name="Category", value=category.name if category else "None", inline=True)
            bot = interaction.client
            if hasattr(bot, "send_log"):
                await bot.send_log(log_embed)

        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to create voice channels. Contact an admin.",
                ephemeral=True,
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Something went wrong: {e}",
                ephemeral=True,
            )


class CreateVCView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Create Voice Channel",
        style=discord.ButtonStyle.primary,
        custom_id="persistent_create_vc",
        emoji="🎙️",
    )
    async def create_vc_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CreateVCModal())


class CustomVC(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.add_view(CreateVCView())

    @commands.command(name="setupvc")
    @commands.has_permissions(administrator=True)
    async def setup_vc(self, ctx: commands.Context, role: discord.Role):
        if ctx.channel.category is None:
            embed = discord.Embed(
                description="❌ This channel is not inside a category. Move it to a category first.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=10)
            return

        category = ctx.channel.category

        save_config({
            "category_id": str(category.id),
            "role_id": str(role.id),
        })

        try:
            await ctx.message.delete()
        except Exception:
            pass

        embed = discord.Embed(
            title="🎙️ Custom Voice Channel",
            description=(
                "**Create your own permanent voice channel!**\n\n"
                "Click the button below to set up your personal room.\n"
                "You'll have full control — rename it, manage members, and more.\n\n"
                f"🔑 Required role: {role.mention}\n\n"
                "🗑️ To delete your room: `c!deletevc`"
            ),
            color=discord.Color.from_rgb(114, 137, 218),
        )
        embed.set_footer(text=f"Channels will be created in: {category.name}")

        await ctx.send(embed=embed, view=CreateVCView())
        print(f"[LOG] Custom VC panel set up | Category: {category.name} | Role: {role.name}")

        # Log setup action
        log_embed = discord.Embed(
            title="⚙️ Custom VC Panel Configured",
            color=discord.Color.blurple(),
        )
        log_embed.add_field(name="Category", value=category.name, inline=True)
        log_embed.add_field(name="Required Role", value=role.mention, inline=True)
        log_embed.add_field(name="Set up by", value=ctx.author.mention, inline=True)
        if hasattr(self.bot, "send_log"):
            await self.bot.send_log(log_embed)

    @commands.command(name="deletevc")
    async def delete_vc(self, ctx: commands.Context):
        cfg = load_config()
        category_id = cfg.get("category_id")
        member = ctx.author

        try:
            await ctx.message.delete()
        except Exception:
            pass

        if not category_id:
            embed = discord.Embed(
                description="❌ No VC system configured.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=8)
            return

        category = ctx.guild.get_channel(int(category_id))
        if not category:
            embed = discord.Embed(
                description="❌ Category not found.",
                color=discord.Color.red(),
            )
            await ctx.send(embed=embed, delete_after=8)
            return

        for ch in category.voice_channels:
            if ch.overwrites_for(member).manage_channels is True:
                channel_name = ch.name
                await ch.delete(reason=f"Deleted by owner {member}")
                embed = discord.Embed(
                    description=f"🗑️ Your voice channel **{channel_name}** has been deleted.",
                    color=discord.Color.red(),
                )
                embed.set_footer(text=f"Action by: {member.display_name}")
                await ctx.send(embed=embed, delete_after=8)
                print(f"[LOG] Custom VC deleted: '{channel_name}' by {member} ({member.id})")

                # Log to server logs
                log_embed = discord.Embed(
                    title="🗑️ Custom Voice Channel Deleted",
                    color=discord.Color.from_rgb(240, 71, 71),
                    timestamp=discord.utils.utcnow()
                )
                log_embed.set_author(name=str(member), icon_url=member.display_avatar.url)
                log_embed.add_field(name="Channel", value=f"**{channel_name}**", inline=True)
                log_embed.add_field(name="Owner", value=f"{member.mention} (`{member.id}`)", inline=True)
                log_embed.add_field(name="Deleted by", value="Owner (self)", inline=True)
                if hasattr(self.bot, "send_log"):
                    await self.bot.send_log(log_embed)
                return

        embed = discord.Embed(
            description="❌ You don't have a voice channel to delete.",
            color=discord.Color.red(),
        )
        await ctx.send(embed=embed, delete_after=8)

    @commands.command(name="admindeletevc")
    @commands.has_permissions(administrator=True)
    async def admin_delete_vc(self, ctx: commands.Context, member: discord.Member):
        cfg = load_config()
        category_id = cfg.get("category_id")

        try:
            await ctx.message.delete()
        except Exception:
            pass

        if not category_id:
            await ctx.send("❌ No VC system configured.", delete_after=8)
            return

        category = ctx.guild.get_channel(int(category_id))
        if not category:
            await ctx.send("❌ Category not found.", delete_after=8)
            return

        for ch in category.voice_channels:
            if ch.overwrites_for(member).manage_channels is True:
                channel_name = ch.name
                await ch.delete(reason=f"Admin delete by {ctx.author}")
                embed = discord.Embed(
                    description=(
                        f"🗑️ Voice channel **{channel_name}** "
                        f"(owned by {member.mention}) has been deleted."
                    ),
                    color=discord.Color.red(),
                )
                embed.set_footer(text=f"Action by admin: {ctx.author.display_name}")
                await ctx.send(embed=embed, delete_after=10)
                print(f"[LOG] Custom VC admin-deleted: '{channel_name}' (owner {member}) by {ctx.author}")

                # Log to server logs
                log_embed = discord.Embed(
                    title="🗑️ Custom Voice Channel Deleted",
                    color=discord.Color.from_rgb(240, 71, 71),
                    timestamp=discord.utils.utcnow()
                )
                log_embed.set_author(name=str(member), icon_url=member.display_avatar.url)
                log_embed.add_field(name="Channel", value=f"**{channel_name}**", inline=True)
                log_embed.add_field(name="Owner", value=f"{member.mention} (`{member.id}`)", inline=True)
                log_embed.add_field(name="Deleted by", value=f"Admin {ctx.author.mention}", inline=True)
                if hasattr(self.bot, "send_log"):
                    await self.bot.send_log(log_embed)
                return

        await ctx.send(f"❌ {member.mention} doesn't have a voice channel.", delete_after=8)


async def setup(bot: commands.Bot):
    await bot.add_cog(CustomVC(bot))