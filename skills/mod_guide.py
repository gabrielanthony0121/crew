import discord

from core.config import MOD_ANNOUNCEMENTS_CHANNEL_ID


async def get_mod_guide_embed() -> discord.Embed:
    """
    Creates a professional, permanent moderation guide embed.
    This embed is meant to be sent in #mod-announcements as a reference for all moderators.
    All text is in English as requested.
    """

    # Professional blurple color (Discord's brand color, clean and serious)
    embed = discord.Embed(
        title="🛡️ Moderation Commands & Channels Guide",
        description=(
            "This is the **official moderation guide** for Language Crew.\n\n"
            "All moderation commands **must be used exclusively in #mod-commands**.\n"
            "This channel (#mod-announcements) is read-only and contains important information."
        ),
        color=discord.Color.from_rgb(88, 101, 242),  # Blurple
    )

    # =====================
    # MODERATION CHANNELS
    # =====================
    embed.add_field(
        name="📋 Moderation Channels",
        value=(
            "• **#mod-commands** — Exclusive channel for executing moderation commands. "
            "**No conversation** or casual talk is allowed here.\n\n"
            "• **#evidence-logs** — Dedicated channel for submitting evidence and screenshots "
            "(prints of rule violations, spam, toxic behavior, etc.). **Images only**.\n\n"
            "• **#mod-general** — Private channel where moderators can talk to each other, "
            "ask questions, discuss cases, and coordinate actions.\n\n"
            "• **#mod-announcements** — Read-only channel. Contains important updates and this permanent guide."
        ),
        inline=False,
    )

    # =====================
    # MODERATION COMMANDS
    # =====================
    embed.add_field(
        name="⚠️ c!warn",
        value=(
            "**Usage:** `c!warn <user_id> <reason>`\n"
            "**Description:** Records a permanent warning in the user's history.\n"
            "**Example:** `c!warn 123456789012345678 Being toxic in voice chat`"
        ),
        inline=False,
    )

    embed.add_field(
        name="🔍 c!review",
        value=(
            "**Usage:** `c!review <user_id>`\n"
            "**Aliases:** `c!warnings`, `c!warns`, `c!check`\n"
            "**Description:** Shows the complete warning history of a member. "
            "If the member has no warnings, it displays a 'Clean Record' message."
        ),
        inline=False,
    )

    embed.add_field(
        name="🧹 c!clearwarn",
        value=(
            "**Usage:** `c!clearwarn <user_id> [reason]`\n"
            "**Description:** Clears all warnings from a member's record.\n"
            "**Example:** `c!clearwarn 123456789012345678 Improved behavior`"
        ),
        inline=False,
    )

    embed.add_field(
        name="🚫 c!spam",
        value=(
            "**Usage:** `c!spam <user_id>`\n"
            "**Description:** Automatically deletes the user's recent messages in the current channel "
            "and applies the Muted role. Use this for spam or mass messaging cases."
        ),
        inline=False,
    )

    embed.add_field(
        name="🔇 c!mute",
        value=(
            "**Usage:** `c!mute <user_id> <reason>`\n"
            "**Description:** Mutes the member by applying the Muted role.\n"
            "**Example:** `c!mute 123456789012345678 Spamming links`"
        ),
        inline=False,
    )

    embed.add_field(
        name="🔊 c!unmute",
        value=(
            "**Usage:** `c!unmute <user_id>`\n"
            "**Description:** Removes the Muted role from the member, restoring their ability to speak."
        ),
        inline=False,
    )

    # =====================
    # FOOTER
    # =====================
    embed.set_footer(
        text="Use all moderation commands only in #mod-commands • Language Crew Moderation"
    )

    return embed


# =====================
# EXAMPLE USAGE
# =====================
#
# Option 1: Send it once manually.
#
# Option 2 (Recommended): Add this command inside your Moderation class
# (in skills/moderation.py). See instructions below.