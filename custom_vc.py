import discord
from discord.ext import commands
import json
import os

CONFIG_FILE = "vc_config.json"

# ──────────────────────────────────────────
#  Config helpers
# ──────────────────────────────────────────
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {"category_id": None, "role_id": None}

def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ──────────────────────────────────────────
#  Modal — popup que pede o nome da call
# ──────────────────────────────────────────
class CreateVCModal(discord.ui.Modal, title="🎙️ Create Your Voice Channel"):
    channel_name = discord.ui.TextInput(
        label="Voice Channel Name",
        placeholder="e.g. My Gaming Room",
        min_length=2,
        max_length=32,
        style=discord.TextStyle.short
    )

    async def on_submit(self, interaction: discord.Interaction):
        cfg = load_config()
        guild = interaction.guild
        member = interaction.user

        # Verifica se tem o cargo necessário
        role_id = cfg.get("role_id")
        if role_id:
            allowed_role = guild.get_role(int(role_id))
            if allowed_role and allowed_role not in member.roles:
                await interaction.response.send_message(
                    "❌ You don't have the required role to create a voice channel.",
                    ephemeral=True
                )
                return

        # Verifica se já tem uma call criada
        category_id = cfg.get("category_id")
        category = guild.get_channel(int(category_id)) if category_id else None

        if category:
            for ch in category.voice_channels:
                if ch.overwrites_for(member).manage_channels is True:
                    await interaction.response.send_message(
                        f"❌ You already have a voice channel: **{ch.name}**\nDelete it first with `c!deletevc`",
                        ephemeral=True
                    )
                    return

        # Permissões da call
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(
                view_channel=True,
                connect=False
            ),
            member: discord.PermissionOverwrite(
                view_channel=True,
                connect=True,
                speak=True,
                stream=True,
                use_voice_activation=True,
                manage_channels=True,   # pode renomear
                move_members=True,       # pode mover membros
                mute_members=True,       # pode mutar
                deafen_members=True,     # pode ensurdecer
                priority_speaker=True
            )
        }

        try:
            channel = await guild.create_voice_channel(
                name=self.channel_name.value,
                category=category,
                overwrites=overwrites,
                reason=f"Custom VC created by {member}"
            )

            embed = discord.Embed(
                title="✅ Voice Channel Created!",
                description=(
                    f"Your room **{channel.name}** is ready!\n\n"
                    f"**Your permissions as owner:**\n"
                    f"🏷️ Rename the channel\n"
                    f"👢 Move & kick members\n"
                    f"🔇 Mute & deafen members\n\n"
                    f"To delete your room: `c!deletevc`"
                ),
                color=discord.Color.green()
            )
            embed.set_footer(text=f"Owner: {member.display_name}")

            await interaction.response.send_message(embed=embed, ephemeral=True)
            print(f"[LOG] Custom VC created: '{channel.name}' by {member} ({member.id})")

        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to create voice channels. Contact an admin.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Something went wrong: {e}",
                ephemeral=True
            )


# ──────────────────────────────────────────
#  Botão persistente
# ──────────────────────────────────────────
class CreateVCView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Create Voice Channel",
        style=discord.ButtonStyle.primary,
        custom_id="persistent_create_vc",
        emoji="🎙️"
    )
    async def create_vc_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CreateVCModal())


# ──────────────────────────────────────────
#  Cog principal
# ──────────────────────────────────────────
class CustomVC(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.add_view(CreateVCView())  # Registra o botão como persistente

    # ──────────────────────────────────────────
    #  c!setupvc @cargo
    #  Roda no canal onde quer que fique o painel
    #  A categoria será a mesma do canal onde o comando foi rodado
    # ──────────────────────────────────────────
    @commands.command(name="setupvc")
    @commands.has_permissions(administrator=True)
    async def setup_vc(self, ctx: commands.Context, role: discord.Role):

        # Pega a categoria do canal atual
        if ctx.channel.category is None:
            embed = discord.Embed(
                description="❌ This channel is not inside a category. Move it to a category first.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed, delete_after=10)
            return

        category = ctx.channel.category

        # Salva config
        cfg = {
            "category_id": str(category.id),
            "role_id": str(role.id)
        }
        save_config(cfg)

        # Deleta o comando
        try:
            await ctx.message.delete()
        except Exception:
            pass

        # Envia o painel
        embed = discord.Embed(
            title="🎙️ Custom Voice Channel",
            description=(
                "**Create your own permanent voice channel!**\n\n"
                "Click the button below to set up your personal room.\n"
                "You'll have full control — rename it, manage members, and more.\n\n"
                f"🔑 Required role: {role.mention}"
                "🗑️ To delete your room: `c!deletevc`"
            ),
            color=discord.Color.from_rgb(114, 137, 218)
        )
        embed.set_footer(text=f"Channels will be created in: {category.name}")

        await ctx.send(embed=embed, view=CreateVCView())
        print(f"[LOG] Custom VC panel set up | Category: {category.name} | Role: {role.name}")

    # ──────────────────────────────────────────
    #  c!deletevc — dono deleta a própria call
    # ──────────────────────────────────────────
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
            embed = discord.Embed(description="❌ No VC system configured.", color=discord.Color.red())
            await ctx.send(embed=embed, delete_after=8)
            return

        category = ctx.guild.get_channel(int(category_id))
        if not category:
            embed = discord.Embed(description="❌ Category not found.", color=discord.Color.red())
            await ctx.send(embed=embed, delete_after=8)
            return

        for ch in category.voice_channels:
            if ch.overwrites_for(member).manage_channels is True:
                channel_name = ch.name
                await ch.delete(reason=f"Deleted by owner {member}")
                embed = discord.Embed(
                    description=f"🗑️ Your voice channel **{channel_name}** has been deleted.",
                    color=discord.Color.red()
                )
                embed.set_footer(text=f"Action by: {member.display_name}")
                await ctx.send(embed=embed, delete_after=8)
                print(f"[LOG] Custom VC deleted: '{channel_name}' by {member} ({member.id})")
                return

        embed = discord.Embed(
            description="❌ You don't have a voice channel to delete.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed, delete_after=8)

    # ──────────────────────────────────────────
    #  c!admindeletevc @user — admin deleta call de outro
    # ──────────────────────────────────────────
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
                    description=f"🗑️ Voice channel **{channel_name}** (owned by {member.mention}) has been deleted.",
                    color=discord.Color.red()
                )
                embed.set_footer(text=f"Action by admin: {ctx.author.display_name}")
                await ctx.send(embed=embed, delete_after=10)
                return

        await ctx.send(f"❌ {member.mention} doesn't have a voice channel.", delete_after=8)


async def setup(bot):
    await bot.add_cog(CustomVC(bot))
