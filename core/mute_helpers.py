"""Shared mute logic: strip roles on mute, restore on unmute."""

import discord

from core.muted_roles_db import clear_muted_roles, get_muted_roles, save_muted_roles


class UnmanageableRolesError(Exception):
    """Raised when the bot cannot remove one or more member roles."""

    def __init__(self, role_names: str):
        self.role_names = role_names
        super().__init__(role_names)


class VoiceDisconnectError(Exception):
    """Raised when the bot cannot disconnect a member from voice."""

    def __init__(self):
        super().__init__("Missing Move Members permission or channel restriction.")


async def get_or_create_muted_role(guild: discord.Guild) -> discord.Role | None:
    muted_role = discord.utils.get(guild.roles, name="Muted")
    if muted_role is not None:
        return muted_role

    try:
        muted_role = await guild.create_role(
            name="Muted",
            color=discord.Color.from_rgb(128, 128, 128),
            reason="Auto-created by bot",
        )
        bot_member = guild.me
        if bot_member and muted_role < bot_member.top_role:
            try:
                await muted_role.edit(position=bot_member.top_role.position - 1)
            except discord.Forbidden:
                pass

        for channel in guild.channels:
            try:
                await channel.set_permissions(
                    muted_role,
                    send_messages=False,
                    speak=False,
                    stream=False,
                    add_reactions=False,
                )
            except (discord.Forbidden, discord.HTTPException):
                pass
        return muted_role
    except discord.Forbidden:
        return None


def _bot_member(guild: discord.Guild) -> discord.Member | None:
    return guild.me


def _roles_bot_can_manage(guild: discord.Guild, roles: list[discord.Role]) -> list[discord.Role]:
    bot_member = _bot_member(guild)
    if bot_member is None:
        return []
    bot_top = bot_member.top_role
    return [role for role in roles if role < bot_top]


async def _disconnect_from_voice(
    guild: discord.Guild,
    user_id: int,
    voice_channel_id: int | None,
    reason: str,
) -> None:
    """Disconnect member from voice. Uses cache first, then HTTP API fallback."""
    if voice_channel_id is None:
        return

    cached = guild.get_member(user_id)
    if cached and cached.voice and cached.voice.channel:
        try:
            await cached.move_to(None, reason=reason)
            print(f"[LOG] Voice disconnect via move_to | user={user_id}")
            return
        except discord.Forbidden as exc:
            raise VoiceDisconnectError() from exc

    try:
        await guild.http.edit_member(
            guild.id,
            user_id,
            reason=reason,
            channel_id=None,
        )
        print(f"[LOG] Voice disconnect via HTTP API | user={user_id}")
    except discord.Forbidden as exc:
        raise VoiceDisconnectError() from exc


async def apply_mute(member: discord.Member, muted_role: discord.Role, reason: str) -> None:
    """Save current roles, disconnect from voice, remove all roles, leave only Muted."""
    guild = member.guild
    bot_member = _bot_member(guild)
    if bot_member is None:
        raise RuntimeError("Bot member not available in guild cache.")

    user_id = member.id

    # fetch_member() returns a new object WITHOUT voice state — capture voice first.
    voice_channel_id = (
        member.voice.channel.id
        if member.voice and member.voice.channel
        else None
    )

    fresh = await guild.fetch_member(user_id)

    saved_role_ids = [
        role.id
        for role in fresh.roles
        if role != guild.default_role and role != muted_role
    ]
    save_muted_roles(guild.id, user_id, saved_role_ids)
    print(
        f"[LOG] Mute start | user={user_id} | roles_to_save={len(saved_role_ids)} "
        f"| in_voice={voice_channel_id is not None}"
    )

    await _disconnect_from_voice(guild, user_id, voice_channel_id, reason)

    roles_to_remove = [
        role for role in fresh.roles
        if role != guild.default_role and role != muted_role
    ]
    unmanageable = [
        role for role in roles_to_remove
        if role >= bot_member.top_role
    ]
    if unmanageable:
        names = ", ".join(role.name for role in unmanageable)
        raise UnmanageableRolesError(names)

    if muted_role >= bot_member.top_role:
        raise UnmanageableRolesError("Muted (move the bot role above the Muted role)")

    for role in roles_to_remove:
        try:
            await fresh.remove_roles(role, reason=reason)
        except discord.Forbidden:
            if role.managed:
                print(f"[WARN] Could not remove managed role '{role.name}' from user {user_id}")
                continue
            raise

    if muted_role not in fresh.roles:
        await fresh.add_roles(muted_role, reason=reason)

    final = await guild.fetch_member(user_id)
    leftover = [
        role for role in final.roles
        if role != guild.default_role and role != muted_role
    ]
    if leftover:
        names = ", ".join(role.name for role in leftover)
        raise UnmanageableRolesError(
            f"{names} — move the bot role above these roles"
        )

    print(f"[LOG] Mute complete | user={user_id} | only_muted=True")


async def remove_mute(member: discord.Member, muted_role: discord.Role, reason: str) -> None:
    """Remove Muted and restore previously saved roles."""
    guild = member.guild
    member = await guild.fetch_member(member.id)
    saved_role_ids = get_muted_roles(guild.id, member.id)

    if muted_role in member.roles:
        await member.remove_roles(muted_role, reason=reason)

    if not saved_role_ids:
        clear_muted_roles(guild.id, member.id)
        return

    roles_to_restore = []
    for role_id in saved_role_ids:
        role = guild.get_role(role_id)
        if role is not None and role != guild.default_role and role != muted_role:
            roles_to_restore.append(role)

    addable = _roles_bot_can_manage(guild, roles_to_restore)
    if addable:
        await member.add_roles(*addable, reason=f"{reason} — restoring roles")

    clear_muted_roles(guild.id, member.id)
    print(f"[LOG] Unmute complete | user={member.id} | restored={len(addable)} roles")