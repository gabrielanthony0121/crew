import asyncio

import discord
from discord.ext import commands

from core.config import VIDEO_CREW_CHAT_ID, CAMERA_GRACE_SECONDS


class VideoCrew(commands.Cog):
    """Enforces camera requirement in the Video Crew Chat voice channel.

    - Users must have their camera (self_video) turned on to remain in the channel.
    - On joining without camera: 20-second grace period.
    - If camera is turned off while inside: another grace period starts.
    - Turning the camera on cancels any pending removal.
    - On timer expiry (still no camera + still in channel): user is moved out + receives professional DM.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._kick_tasks: dict[int, asyncio.Task] = {}

    async def cog_unload(self):
        # Cancel any pending kick timers on unload/reload
        for task in list(self._kick_tasks.values()):
            if not task.done():
                task.cancel()
        self._kick_tasks.clear()

    def _cancel_pending_kick(self, member_id: int) -> None:
        task = self._kick_tasks.pop(member_id, None)
        if task and not task.done():
            task.cancel()

    async def _enforce_camera_kick(self, member: discord.Member, channel_id: int) -> None:
        """Waits the grace period then removes the member if they still lack camera."""
        try:
            await asyncio.sleep(CAMERA_GRACE_SECONDS)

            # Re-fetch current voice state (member object may be stale)
            guild = member.guild
            current_member = guild.get_member(member.id) if guild else None
            if not current_member or not current_member.voice:
                return

            current_channel = current_member.voice.channel
            if not current_channel or current_channel.id != channel_id:
                return  # Left or switched away

            if current_member.voice.self_video:
                return  # Camera was turned on in time

            # Still in the channel and still no camera → enforce
            channel_name = current_channel.name

            # Send DM first (while the user is still in the channel) — more reliable
            dm_sent = False
            try:
                embed = discord.Embed(
                    title="📹 Camera Required — Video Crew Chat",
                    description=(
                        f"Hello {current_member.display_name},\n\n"
                        f"You were removed from the **{channel_name}** voice channel because your camera was not enabled.\n\n"
                        "This channel is reserved for active video participation. "
                        "All members are required to have their **camera turned on** while connected. "
                        "This policy ensures a high-quality, face-to-face conversation experience for everyone practicing languages together.\n\n"
                        "To rejoin, please turn your camera on before connecting to the channel.\n\n"
                        "Thank you for your understanding and cooperation!"
                    ),
                    color=discord.Color.orange(),
                )
                embed.set_footer(text="Language Crew • Video Crew Chat")
                await current_member.send(embed=embed)
                dm_sent = True
                print(f"[LOG] DM sent successfully to {current_member} ({current_member.id})")
            except discord.Forbidden:
                print(f"[LOG] Could not send DM to {current_member} ({current_member.id}) — user has 'Allow direct messages from server members' turned OFF in their Discord privacy settings.")
            except Exception as dm_err:
                print(f"[ERROR] Unexpected error while sending DM to {current_member}: {dm_err}")

            # Now disconnect the user from the voice channel
            try:
                await current_member.move_to(None)
                print(f"[LOG] Removed {current_member} ({current_member.id}) from '{channel_name}' (no camera after {CAMERA_GRACE_SECONDS}s)")

                # Record in server logs (if logging cog is loaded)
                if hasattr(self.bot, "send_log"):
                    try:
                        log_embed = discord.Embed(
                            title="📹 Member Removed from Video Crew Chat",
                            color=discord.Color.orange(),
                            timestamp=discord.utils.utcnow(),
                        )
                        log_embed.set_author(name=str(current_member), icon_url=current_member.display_avatar.url)
                        log_embed.add_field(name="User", value=f"{current_member.mention} (`{current_member.id}`)", inline=True)
                        log_embed.add_field(name="Channel", value=f"**{channel_name}** (`{channel_id}`)", inline=True)
                        log_embed.add_field(
                            name="Reason",
                            value=f"Camera not turned on within the {CAMERA_GRACE_SECONDS}-second grace period.",
                            inline=False,
                        )
                        if not dm_sent:
                            log_embed.add_field(
                                name="DM Status",
                                value="❌ Failed to send private message (user has DMs from server members disabled in privacy settings)",
                                inline=False,
                            )
                        await self.bot.send_log(log_embed)
                    except Exception as log_err:
                        print(f"[ERROR] Failed to send enforcement log: {log_err}")

            except discord.Forbidden:
                print(f"[ERROR] Missing 'Move Members' permission to remove {current_member} from voice channel.")
            except Exception as move_err:
                print(f"[ERROR] Failed to remove {current_member} from voice: {move_err}")

        except asyncio.CancelledError:
            # Timer was cancelled (user turned camera on or left)
            pass
        finally:
            self._kick_tasks.pop(member.id, None)

    @commands.Cog.listener()
    async def on_voice_state_update(
        self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
    ):
        target_id = VIDEO_CREW_CHAT_ID
        if not target_id:
            return

        was_in_target = before.channel is not None and before.channel.id == target_id
        is_in_target = after.channel is not None and after.channel.id == target_id

        # Case 1: User just joined (or switched into) the target channel
        if is_in_target and not was_in_target:
            self._cancel_pending_kick(member.id)

            if not after.self_video:
                # Start grace period
                task = asyncio.create_task(self._enforce_camera_kick(member, target_id))
                self._kick_tasks[member.id] = task
                print(
                    f"[LOG] {member} ({member.id}) joined '{after.channel.name}' without camera — "
                    f"{CAMERA_GRACE_SECONDS}s grace period started"
                )
            # If they joined WITH camera on, nothing to do
            return

        # Case 2: User left (or switched out of) the target channel
        if was_in_target and not is_in_target:
            self._cancel_pending_kick(member.id)
            return

        # Case 3: Still inside the target channel — camera state may have changed
        if is_in_target:
            was_video = getattr(before, "self_video", False)
            is_video = getattr(after, "self_video", False)

            if is_video and not was_video:
                # Turned camera ON → cancel any pending removal
                self._cancel_pending_kick(member.id)
                print(f"[LOG] {member} ({member.id}) turned camera ON in '{after.channel.name}' — grace cancelled")
            elif not is_video and was_video:
                # Turned camera OFF while inside → start fresh grace period
                self._cancel_pending_kick(member.id)
                task = asyncio.create_task(self._enforce_camera_kick(member, target_id))
                self._kick_tasks[member.id] = task
                print(
                    f"[LOG] {member} ({member.id}) turned camera OFF in '{after.channel.name}' — "
                    f"{CAMERA_GRACE_SECONDS}s grace period started"
                )


async def setup(bot: commands.Bot):
    await bot.add_cog(VideoCrew(bot))
