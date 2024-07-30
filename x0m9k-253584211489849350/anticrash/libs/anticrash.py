import copy
import shutil
from typing import List
from libs.const_views import ACRestoreRolesView, BaseConstantView
from libs.ui import make_button
from libs.util import *
from libs.config import Config
from datetime import timedelta, datetime
import asyncio
import pytz

import logging
from io import BytesIO

from libs.x3m_api import X3m_API


log = logging.getLogger("log")

temp_audit_last = {}
temp_audit_restored_webhook = {}


def get_restricted_role_perms(r, only_check=False):
    p = r.permissions

    restricted_perms = (
        "administrator",
        "ban_members",
        "kick_members",
        "deafen_members",
        "manage_channels",
        "manage_emojis",
        "manage_emojis_and_stickers",
        "manage_guild",
        "manage_permissions",
        "manage_roles",
        "moderate_members",
        "move_members",
        "mute_members",
    )

    found = []

    for perm in restricted_perms:
        if hasattr(p, perm):
            if getattr(p, perm, None):
                if only_check:
                    return True
                found.append(perm)

    if only_check:
        return False

    return found


async def punish_violator(
    bot, guild: discord.Guild, user_id, only_check=False, log_type=None, **kwargs
):
    if user_id in Config.get("anticrash", {}).get("allowed_bot_ids", []):
        return False

    if user_id == bot.user.id:
        return False

    member: discord.Member = guild.get_member(user_id)
    if not member:
        member = await guild.fetch_member(user_id)

    settings = await bot.get_fetch_server_settings(member.guild.id)
    language = settings.get("language") or Config.get("default_language")

    # already violated, no need to punish them twice
    if get_utc_timestamp() - temp_audit_last.get(user_id, 0) < 2:
        return False

    loc = Locale(bot, language)

    if member.id in (walk_dict(settings, "anticrash.whitelist") or []):
        return False

    whitelist_roles = []

    for rid in whitelist_roles:
        if guild.get_role(rid) in member.roles:
            return False

    if only_check:
        return True

    temp_audit_last[user_id] = get_utc_timestamp()
    # bot.store_set(f"_internal.anticrash.{guild.id}.violated.{user_id}", True, expire=3)

    # try:
    log_channel_id = walk_dict(settings, "channels.logs_anticrash")
    if not log_channel_id:
        log_channel_id = walk_dict(settings, "anticrash.logs_channel", 0)
    log_channel = guild.get_channel(log_channel_id)

    embed = discord.Embed(color=Const.embed_color_error)
    embed.title = loc.locale("anticrash_title")
    embed.description = loc.locale(
        "anticrash_log_desc",
        violator=user_id,
        type=loc.locale("anticrash_log_type_" + (log_type or "unknown")),
    )

    server_tz = pytz.timezone(walk_dict(settings, "timezone", "Europe/Moscow"))
    now = datetime.now()
    server_now = now.astimezone(server_tz)

    embed.set_footer(text=str(member.id))  # needed to restore roles
    embed.timestamp = now

    send_kw = {"embed": embed}

    if log_type in (
        "channel_delete",
        "ban",
        "webhook_created",
        "webhook_deleted",
        "webhook_updated",
    ):
        content = " ".join(
            [f"<@&{rid}>" for rid in walk_dict(settings, "anticrash.notifroles", [])]
        )
        if content:
            send_kw["content"] = content

    # except:
    # pass

    to_remove = []

    api: X3m_API = bot.api

    # for role in member.roles.copy():
    #     if get_restricted_role_perms(role, only_check=True):
    #         to_remove.append(role)

    member_roles = list(member.roles)

    # if to_remove:
    try:
        await member.edit(roles=[], reason=loc.locale("audit_anticrash"))
    except Exception as err:
        print("CANT TAKE ALL ROLES:", err)

    send_kw["view"] = ACRestoreRolesView()

    if log_channel:
        await log_channel.send(**send_kw)

    if member.bot:
        await member.kick(reason="ANTICRASH PUNISHMENT: BOT KICKED")
    else:

        ban_role = member.guild.get_role(
            walk_dict(settings, "anticrash.anticrash_ban", 0)
        )
        if ban_role:
            await member.add_roles(ban_role, reason=loc.locale("audit_anticrash"))
        else:
            try:
                await member.timeout_for(
                    timedelta(seconds=Time.hour), reason=loc.locale("audit_anticrash")
                )
            except:
                pass

    # if to_remove:
    await api.update_user(
        user_id=member.id,
        guild_id=member.guild.id,
        fields_guild={
            "$set": {
                "anticrash.viol_saved": [
                    r.id for r in member_roles if r != guild.default_role
                ]
            }
        },
    )

    return True


async def process(name, *args):
    func = globals().get(name)

    if Config.get("debug") and Config.get("verbose_debug"):
        log.debug(f'Anticrash: processing "{name}" event.')

    if func:
        await func(*args)


async def member_ban(bot, guild, user):
    preferences = await bot.api.get_user(
        user_id=user.id, guild_id=guild.id, get_preferences=True, walk_to_guild=False
    )
    preferences = preferences.get("preferences", {})

    user_language = preferences.get("language")
    settings = await bot.get_fetch_server_settings(guild.id)
    server_language = settings.get("language") or Config.get("default_language")

    if not user_language:
        user_language = server_language

    # loc = Locale(bot, user_language)
    loc_server = Locale(bot, server_language)

    entry = None

    async for entry in guild.audit_logs(
        limit=100,
        action=discord.AuditLogAction.ban,
        oldest_first=False,
    ):
        if entry.created_at <= datetime.now().astimezone(pytz.utc) - timedelta(
            seconds=60
        ):
            entry = None
            continue

        if entry.target.id == user.id:
            break
        else:
            entry = None

    # if temp_audit_last.get(guild.id) is None:
    #     temp_audit_last[guild.id] = {}

    # if entry.user.id == temp_audit_last[guild.id].get("member_ban"):
    #     return

    # temp_audit_last[guild.id]["member_ban"] = entry.user.id

    if entry:
        if entry.user.id in walk_dict(settings, "anticrash.perms.ban", []):
            return

        if await punish_violator(bot, guild, entry.user.id, only_check=True):
            try:
                await guild.unban(
                    user,
                    reason=loc_server.locale(
                        "audit_anticrash_unban", author=entry.user.id
                    ),
                )
            except:
                pass
            else:
                await punish_violator(bot, guild, entry.user.id, log_type="ban")

            # bot can't send msg to a user who is not on the server yet

            # invite_link = await guild.channels[0].create_invite(
            #     max_uses=1, reason=loc_server.locale("audit_anticrash")
            # )

            # try:
            #     await user.send(
            #         content=loc.locale("anticrash_victim_ban", invite_link=invite_link)
            #     )
            # except:
            #     pass


async def member_unban(bot, guild, user):
    settings = await bot.get_fetch_server_settings(guild.id)
    language = settings.get("language") or Config.get("default_language")
    loc = Locale(bot, language)

    entry = None

    async for entry in guild.audit_logs(
        limit=100,
        action=discord.AuditLogAction.unban,
        oldest_first=False,
    ):
        if entry.created_at <= datetime.now().astimezone(pytz.utc) - timedelta(
            seconds=60
        ):
            entry = None
            continue

        if entry.target.id == user.id:
            break
        else:
            entry = None

    # if temp_audit_last.get(guild.id) is None:
    #     temp_audit_last[guild.id] = {}

    # if entry.user.id == temp_audit_last[guild.id].get("member_unban"):
    #     return

    # temp_audit_last[guild.id]["member_unban"] = entry.user.id

    if entry:
        if await punish_violator(bot, guild, entry.user.id, only_check=True):
            try:
                await guild.ban(
                    user,
                    reason=loc.locale("audit_anticrash_reban", author=entry.user.id),
                )
            except:
                pass
            else:
                await punish_violator(bot, guild, entry.user.id, log_type="unban")


async def member_update(bot, before, after):
    """
    Block giving or taking away a role with restricted rights.
    """

    entry = None

    async for entry in after.guild.audit_logs(
        limit=100,
        action=discord.AuditLogAction.member_role_update,
        oldest_first=False,
    ):
        if entry.created_at <= datetime.now().astimezone(pytz.utc) - timedelta(
            seconds=60
        ):
            entry = None
            continue

        if entry.target.id == after.id:
            break
        else:
            entry = None

    if not entry:
        return

    # if temp_audit_last.get(after.guild.id) is None:
    #     temp_audit_last[after.guild.id] = {}

    # if entry.user.id == temp_audit_last[after.guild.id].get("member_update"):
    #     return

    # temp_audit_last[after.guild.id]["member_update"] = entry.user.id

    settings = await bot.get_fetch_server_settings(after.guild.id)
    language = settings.get("language") or Config.get("default_language")
    loc = Locale(bot, language)

    removed_roles = []
    removed_restricted = []
    added_roles = []
    added_restricted = []

    member: discord.Member = after.guild.get_member(entry.user.id)
    if not member:
        member = await after.guild.fetch_member(entry.user.id)

    # if user has any of these roles, he'll be allowed to proceed
    ignored_roles = [
        1185961444886458458,
        1231603597565890590,
        1231602629038047232,
        1185961446434152449,
    ]
    for r in ignored_roles:
        if after.guild.get_role(r) in member.roles:
            return False

    for role in before.roles:
        if role not in after.roles:
            if get_restricted_role_perms(role, only_check=True):
                removed_restricted.append(role)
            else:
                if role.id in walk_dict(settings, "anticrash.allowed_roles", []):
                    continue
                removed_roles.append(role)

    for role in list(after.roles):
        if role not in before.roles:

            if get_restricted_role_perms(role, only_check=True):
                added_restricted.append(role)
            else:
                if role.id in walk_dict(settings, "anticrash.allowed_roles", []):
                    continue
                added_roles.append(role)

    give_any_role_role_id = walk_dict(settings, "anticrash.give_any_role_role", 0)

    proceed = True
    if added_roles or removed_roles:
        # allow to give unrestricted roles
        # if entry.user.id in walk_dict(settings, "anticrash.allow_give_roles", []):
        #     proceed = False
        for r in before.roles:
            if r.id == give_any_role_role_id:
                proceed = False
                break

        # give_any_roles also functions as "remove_all_roles"
        if entry.user.id in walk_dict(settings, "anticrash.perms.give_any_roles", []):
            proceed = False

        if proceed and await punish_violator(
            bot, after.guild, entry.user.id, only_check=True
        ):
            if removed_roles:
                try:
                    await after.add_roles(
                        *removed_roles,
                        reason=loc.locale(
                            "audit_anticrash_removed_roles_soft", author=entry.user.id
                        ),
                    )
                except:
                    pass
                # else:
                #     await punish_violator(
                #         bot, after.guild, entry.user.id, log_type="removed_roles"
                #     )

            if added_roles:
                try:
                    await after.remove_roles(
                        *added_roles,
                        reason=loc.locale(
                            "audit_anticrash_added_roles_soft", author=entry.user.id
                        ),
                    )
                except:
                    pass
                # else:
                #     await punish_violator(
                #         bot, after.guild, entry.user.id, log_type="added_roles"
                #     )

            try:
                await after.guild.get_member(entry.user.id).timeout_for(
                    timedelta(seconds=5 * 60)
                )
            except:
                pass

    if removed_restricted or added_restricted:
        if await punish_violator(bot, after.guild, entry.user.id, only_check=True):
            if removed_restricted:
                try:
                    await after.add_roles(
                        *removed_restricted,
                        reason=loc.locale(
                            "audit_anticrash_removed_roles", author=entry.user.id
                        ),
                    )
                except:
                    pass
                else:
                    await punish_violator(
                        bot,
                        after.guild,
                        entry.user.id,
                        log_type="removed_restricted_roles",
                    )

            if added_restricted:
                try:
                    await after.remove_roles(
                        *added_restricted,
                        reason=loc.locale(
                            "audit_anticrash_added_roles", author=entry.user.id
                        ),
                    )
                except:
                    pass
                else:
                    await punish_violator(
                        bot,
                        after.guild,
                        entry.user.id,
                        log_type="added_restricted_roles",
                    )


async def member_join(bot, member):
    if not member.bot:
        return

    entry = None

    async for entry in member.guild.audit_logs(
        limit=100,
        action=discord.AuditLogAction.bot_add,
        oldest_first=False,
    ):
        if entry.created_at <= datetime.now().astimezone(pytz.utc) - timedelta(
            seconds=60
        ):
            entry = None
            continue

        if entry.target.id == member.id:
            break
        else:
            entry = None

    if not entry:
        return

    # if temp_audit_last.get(member.guild.id) is None:
    #     temp_audit_last[member.guild.id] = {}

    # if entry.user.id == temp_audit_last[member.guild.id].get("member_join"):
    #     return

    # temp_audit_last[member.guild.id]["member_join"] = entry.user.id

    settings = await bot.get_fetch_server_settings(member.guild.id)
    language = settings.get("language") or Config.get("default_language")
    loc = Locale(bot, language)

    if entry.user.id in walk_dict(settings, "anticrash.perms.add_bots", []):
        return

    if await punish_violator(bot, member.guild, entry.user.id, only_check=True):
        try:
            await member.kick(
                reason=loc.locale("audit_anticrash_bot", author=entry.user.id)
            )
        except:
            pass
        else:
            await punish_violator(
                bot, member.guild, entry.user.id, log_type="invited_bot"
            )


async def member_remove(bot, member):
    entry = None

    async for entry in member.guild.audit_logs(
        limit=100,
        action=discord.AuditLogAction.kick,
        oldest_first=False,
    ):
        if entry.created_at <= datetime.now().astimezone(pytz.utc) - timedelta(
            seconds=60
        ):
            entry = None
            continue

        if entry.target.id == member.id:
            break
        else:
            entry = None

    if not entry:
        return

    # if temp_audit_last.get(member.guild.id) is None:
    #     temp_audit_last[member.guild.id] = {}

    # if entry.user.id == temp_audit_last[member.guild.id].get("member_remove"):
    #     return

    # temp_audit_last[member.guild.id]["member_remove"] = entry.user.id

    settings = await bot.get_fetch_server_settings(member.guild.id)
    language = settings.get("language") or Config.get("default_language")
    loc = Locale(bot, language)

    if entry.user.id in walk_dict(settings, "anticrash.perms.kick", []):
        return

    if await punish_violator(bot, member.guild, entry.user.id):
        pass


async def guild_channel_update(bot, before, after):
    entry = None

    if before.overwrites != after.overwrites:
        if len(before.overwrites) != len(after.overwrites):
            if len(before.overwrites) > len(after.overwrites):
                async for entry in after.guild.audit_logs(
                    limit=100,
                    action=discord.AuditLogAction.overwrite_delete,
                    oldest_first=False,
                ):
                    if entry.created_at <= datetime.now().astimezone(
                        pytz.utc
                    ) - timedelta(seconds=60):
                        entry = None
                        continue

                    if entry.target.id == after.id:
                        break
                    else:
                        entry = None
            else:
                async for entry in after.guild.audit_logs(
                    limit=100,
                    action=discord.AuditLogAction.overwrite_create,
                    oldest_first=False,
                ):
                    if entry.created_at <= datetime.now().astimezone(
                        pytz.utc
                    ) - timedelta(seconds=60):
                        entry = None
                        continue

                    if entry.target.id == after.id:
                        break
                    else:
                        entry = None

        if not entry:
            async for entry in after.guild.audit_logs(
                limit=100,
                action=discord.AuditLogAction.overwrite_update,
                oldest_first=False,
            ):
                if entry.created_at <= datetime.now().astimezone(pytz.utc) - timedelta(
                    seconds=60
                ):
                    entry = None
                    continue

                if entry.target.id == after.id:
                    break
                else:
                    entry = None

    else:
        async for entry in after.guild.audit_logs(
            limit=100,
            action=discord.AuditLogAction.channel_update,
            oldest_first=False,
        ):
            if entry.created_at <= datetime.now().astimezone(pytz.utc) - timedelta(
                seconds=60
            ):
                entry = None
                continue

            if entry.target.id == after.id:
                break
            else:
                entry = None

    if not entry:
        return

    # if temp_audit_last.get(after.guild.id) is None:
    #     temp_audit_last[after.guild.id] = {}

    # if entry.user.id == temp_audit_last[after.guild.id].get("guild_channel_update"):
    #     return

    # temp_audit_last[after.guild.id]["guild_channel_update"] = entry.user.id

    settings = await bot.get_fetch_server_settings(after.guild.id)
    language = settings.get("language") or Config.get("default_language")
    loc = Locale(bot, language)

    if entry.user.id in walk_dict(settings, "anticrash.perms.edit_channels", []):
        return

    if await punish_violator(bot, after.guild, entry.user.id, only_check=True):
        restore_properties = (
            "name",
            "position",
            "overwrites",
            "bitrate",
            "topic",
            "rtc_region",
            "video_quality_mode",
            "nsfw",
            "sync_permissions",
            "category",
            "slowmode_delay",
            "default_auto_archive_duration",
            "default_thread_slowmode_delay",
        )

        to_restore = {}

        for prop in restore_properties:
            before_prop = getattr(before, prop, None)
            if before_prop != getattr(after, prop, None):
                to_restore[prop] = before_prop

        if to_restore:
            # try:
            coro = after.edit(
                **to_restore,
                reason=loc.locale("audit_anticrash_channel", author=entry.user.id),
            )

            try:
                await asyncio.wait_for(coro, timeout=5)
            except asyncio.TimeoutError:
                for rate_limited in ("name", "topic"):
                    try:
                        to_restore.pop(rate_limited)
                    except:
                        pass

                if to_restore:
                    try:
                        await after.edit(
                            **to_restore,
                            reason=loc.locale(
                                "audit_anticrash_channel", author=entry.user.id
                            ),
                        )
                    except:
                        pass
                    else:
                        await punish_violator(
                            bot, after.guild, entry.user.id, log_type="channel_update"
                        )

                return
            else:
                await punish_violator(
                    bot, after.guild, entry.user.id, log_type="channel_update"
                )


async def guild_channel_delete(bot, channel):
    if not isinstance(
        channel, (discord.VoiceChannel, discord.TextChannel, discord.CategoryChannel)
    ):
        return

    entry = None

    settings = await bot.get_fetch_server_settings(channel.guild.id)

    async for entry in channel.guild.audit_logs(
        limit=100,
        action=discord.AuditLogAction.channel_delete,
        oldest_first=False,
    ):
        if entry.created_at <= datetime.now().astimezone(pytz.utc) - timedelta(
            seconds=60
        ):
            entry = None
            continue

        if entry.target.id == channel.id:
            break
        else:
            entry = None

    if not entry:
        return

    if entry.user.id in walk_dict(settings, "anticrash.perms.delete_channels", []):
        return
    # if temp_audit_last.get(channel.guild.id) is None:
    #     temp_audit_last[channel.guild.id] = {}

    # if entry.user.id == temp_audit_last[channel.guild.id].get("guild_channel_delete"):
    #     return

    # temp_audit_last[channel.guild.id]["guild_channel_delete"] = entry.user.id

    language = settings.get("language") or Config.get("default_language")
    loc = Locale(bot, language)

    if await punish_violator(bot, channel.guild, entry.user.id, only_check=True):
        default_props = ("name", "position", "overwrites", "category")

        text_props = ("topic", "slowmode_delay", "nsfw")

        voice_props = (
            "bitrate",
            "user_limit",
            "rtc_region",
            "video_quality_mode",
        )
        # voice_props not yet supports slowmode_delay and i wont bother to implement this.

        all_props = list(default_props)

        if isinstance(channel, discord.VoiceChannel):
            all_props.extend(voice_props)

        elif isinstance(channel, discord.TextChannel):
            all_props.extend(text_props)

        to_restore = {}

        for prop in all_props:
            chan_prop = getattr(channel, prop, None)

            if not (chan_prop is None):
                to_restore[prop] = chan_prop

        method = "create_text_channel"

        if isinstance(channel, discord.VoiceChannel):
            method = "create_voice_channel"

        elif isinstance(channel, discord.CategoryChannel):
            method = "create_category"

        new_channel = await getattr(channel.guild, method)(
            **to_restore,
            reason=loc.locale("audit_anticrash_channel_deleted", author=entry.user.id),
        )

        await punish_violator(
            bot, channel.guild, entry.user.id, log_type="channel_delete"
        )

        if isinstance(channel, discord.CategoryChannel):
            anticrash_data = (
                await bot.api.get_server(
                    channel.guild.id,
                    fields=[f"anticrash.meta.temp.categories.{channel.id}"],
                )
            ) or {}
            previous_channels_inside = walk_dict(
                anticrash_data, f"anticrash.meta.temp.categories.{channel.id}", []
            )

            if previous_channels_inside:
                await bot.api.update_server(
                    channel.guild.id,
                    set={
                        f"anticrash.meta.temp.categories.{new_channel.id}": previous_channels_inside
                    },
                    unset={f"anticrash.meta.temp.categories.{channel.id}": ""},
                )

            for chan in previous_channels_inside:
                chan_to_edit = channel.guild.get_channel(int(chan))
                if chan_to_edit:
                    await chan_to_edit.edit(category=new_channel)
                    await asyncio.sleep(1)

        elif isinstance(channel, discord.VoiceChannel):
            embed = discord.Embed(color=Const.embed_color)
            embed.title = "Ой!"
            embed.description = "\n".join(
                [
                    "Извините, канал был удалён.",
                    "Пожалуйста, войдите заново:",
                    f"<#{new_channel.id}>",
                ]
            )

            temp_voices = bot.store_get(
                f"_internal.anticrash.temp_voices.{channel.guild.id}.{channel.id}", []
            )

            for mem_id in temp_voices:
                mem = channel.guild.get_member(mem_id)
                if mem:
                    try:
                        await mem.send(embed=embed)
                    except:
                        pass
                    await asyncio.sleep(0.1)

        elif isinstance(channel, discord.TextChannel):
            selected_source_channel_id = channel.id
            selected_destination_channel_id = new_channel.id
            aggr = [
                {"$match": {"_id": channel.guild.id}},
                {
                    "$project": {
                        "msgs": f"$anticrash.saved_messages.{selected_source_channel_id}"
                    }
                },
                {"$unwind": "$msgs"},
                {
                    "$project": {
                        "id": "$msgs.message.id",
                        "ts": "$msgs.message.ts",
                    }
                },
                {
                    "$group": {
                        "_id": None,
                        "msgs": {"$push": {"ts": "$ts", "id": "$id"}},
                    }
                },
            ]

            db_data = (
                (
                    await bot.api.aggregate(
                        aggregate=aggr, collection="servers", list_length=1
                    )
                )["response"]
                or [{}]
            )[0]
            msgs = walk_dict(db_data, "msgs", [])

            try:
                selected_destination_channel = channel.guild.get_channel(
                    int(selected_destination_channel_id)
                )

                if selected_destination_channel:
                    await bot.api.update_server(
                        channel.guild.id,
                        set={
                            f"anticrash.meta.channel_names.{selected_destination_channel_id}": selected_destination_channel.name
                        },
                    )
            except:
                pass

            for msg in sorted(msgs, key=lambda x: x["ts"]):
                await saved_messages_recover_message(
                    bot=bot,
                    channel_id=selected_source_channel_id,
                    guild_id=channel.guild.id,
                    message_id=int(msg["id"]),
                    force_channel_id=selected_destination_channel_id,
                )
                await asyncio.sleep(1.1)


async def guild_channel_create(bot, channel):
    if not isinstance(
        channel, (discord.VoiceChannel, discord.TextChannel, discord.CategoryChannel)
    ):
        return

    entry = None

    async for entry in channel.guild.audit_logs(
        limit=100,
        action=discord.AuditLogAction.channel_create,
        oldest_first=False,
    ):
        if entry.created_at <= datetime.now().astimezone(pytz.utc) - timedelta(
            seconds=60
        ):
            entry = None
            continue

        if entry.target.id == channel.id:
            break
        else:
            entry = None

    if not entry:
        return

    settings = await bot.get_fetch_server_settings(channel.guild.id)

    if entry.user.id in walk_dict(settings, "anticrash.perms.create_channels", []):
        return

    # if temp_audit_last.get(channel.guild.id) is None:
    #     temp_audit_last[channel.guild.id] = {}

    # if entry.user.id == temp_audit_last[channel.guild.id].get("guild_channel_create"):
    #     return

    # temp_audit_last[channel.guild.id]["guild_channel_create"] = entry.user.id

    language = settings.get("language") or Config.get("default_language")
    loc = Locale(bot, language)

    if await punish_violator(bot, channel.guild, entry.user.id, only_check=True):
        try:
            await channel.delete(
                reason=loc.locale(
                    "audit_anticrash_channel_created", author=entry.user.id
                )
            )
        except:
            pass
        else:
            await punish_violator(
                bot, channel.guild, entry.user.id, log_type="channel_create"
            )


async def guild_role_create(bot, role):
    entry = None

    async for entry in role.guild.audit_logs(
        limit=100,
        action=discord.AuditLogAction.role_create,
        oldest_first=False,
    ):
        if entry.created_at <= datetime.now().astimezone(pytz.utc) - timedelta(
            seconds=60
        ):
            entry = None
            continue

        if entry.target.id == role.id:
            break
        else:
            entry = None

    if not entry:
        return

    # if temp_audit_last.get(role.guild.id) is None:
    #     temp_audit_last[role.guild.id] = {}

    # if entry.user.id == temp_audit_last[role.guild.id].get("guild_role_create"):
    #     return

    # temp_audit_last[role.guild.id]["guild_role_create"] = entry.user.id

    settings = await bot.get_fetch_server_settings(role.guild.id)
    language = settings.get("language") or Config.get("default_language")
    loc = Locale(bot, language)

    if entry.user.id in walk_dict(settings, "anticrash.perms.create_roles", []):
        return

    if await punish_violator(bot, role.guild, entry.user.id, only_check=True):
        try:
            await role.delete(
                reason=loc.locale("audit_anticrash_role_created", author=entry.user.id)
            )
        except:
            pass
        else:
            await punish_violator(
                bot, role.guild, entry.user.id, log_type="role_create"
            )


async def guild_role_delete(bot, role):
    entry = None

    async for entry in role.guild.audit_logs(
        limit=100,
        action=discord.AuditLogAction.role_delete,
        oldest_first=False,
    ):
        if entry.created_at <= datetime.now().astimezone(pytz.utc) - timedelta(
            seconds=60
        ):
            entry = None
            continue

        if entry.target.id == role.id:
            break
        else:
            entry = None

    if not entry:
        return

    # if temp_audit_last.get(role.guild.id) is None:
    #     temp_audit_last[role.guild.id] = {}

    # if entry.user.id == temp_audit_last[role.guild.id].get("guild_role_delete"):
    #     return

    # temp_audit_last[role.guild.id]["guild_role_delete"] = entry.user.id

    settings = await bot.get_fetch_server_settings(role.guild.id)
    language = settings.get("language") or Config.get("default_language")
    loc = Locale(bot, language)

    if entry.user.id in walk_dict(settings, "anticrash.perms.delete_roles", []):
        return

    if await punish_violator(bot, role.guild, entry.user.id, only_check=True):
        to_restore = {}

        restore_properties = ("name", "permissions", "color", "hoist", "mentionable")

        for prop in restore_properties:
            role_prop = getattr(role, prop, None)

            if not (role_prop is None):
                to_restore[prop] = role_prop

        try:
            new_role = await role.guild.create_role(
                **to_restore,
                reason=loc.locale("audit_anticrash_role_deleted", author=entry.user.id),
            )
        except:
            pass
        else:
            await punish_violator(
                bot, role.guild, entry.user.id, log_type="role_delete"
            )
            if new_role:
                icon = None
                if role.icon:
                    try:
                        icon = await role.icon.read()
                    except:
                        pass

                try:
                    await new_role.edit(
                        position=role.position,
                        icon=icon,
                        unicode_emoji=role.unicode_emoji,
                        reason=loc.locale("audit_anticrash"),
                    )
                except:
                    pass

                db_data = (
                    await bot.api.get_server(
                        guild_id=role.guild.id,
                        fields=[f"anticrash.cache.roles.{role.id}"],
                    )
                ) or {}

                cached_users = (
                    walk_dict(db_data, f"anticrash.cache.roles.{role.id}") or []
                )

                await bot.api.update_server(
                    guild_id=role.guild.id,
                    unset={f"anticrash.cache.roles.{role.id}": ""},
                    set={f"anticrash.cache.roles.{new_role.id}": cached_users},
                    pull={f"settings.anticrash.cached_roles": role.id},
                    push={f"settings.anticrash.cached_roles": new_role.id},
                )

                for user_id in cached_users:
                    await asyncio.sleep(1)
                    member = role.guild.get_member(user_id)
                    if not member:
                        member = await role.guild.fetch_member(user_id)

                    if member:
                        try:
                            await member.add_roles(
                                new_role, reason=loc.locale("audit_anticrash")
                            )
                        except:
                            continue


async def guild_role_update(bot, before, after):
    entry = None

    async for entry in after.guild.audit_logs(
        limit=100,
        action=discord.AuditLogAction.role_update,
        oldest_first=False,
    ):
        if entry.created_at <= datetime.now().astimezone(pytz.utc) - timedelta(
            seconds=60
        ):
            entry = None
            continue

        if entry.target.id == after.id:
            break
        else:
            entry = None

    if not entry:
        return

    # if temp_audit_last.get(after.guild.id) is None:
    #     temp_audit_last[after.guild.id] = {}

    # if entry.user.id == temp_audit_last[after.guild.id].get("guild_role_update"):
    #     return

    # temp_audit_last[after.guild.id]["guild_role_update"] = entry.user.id

    settings = await bot.get_fetch_server_settings(after.guild.id)
    language = settings.get("language") or Config.get("default_language")
    loc = Locale(bot, language)

    if entry.user.id in walk_dict(settings, "anticrash.perms.edit_roles", []):
        return

    if await punish_violator(bot, after.guild, entry.user.id, only_check=True):
        restore_properties = ("name", "color", "hoist", "mentionable")

        to_restore = {}

        if before.icon != after.icon:
            try:
                to_restore["icon"] = await before.icon.read()
            except:
                pass

        if before.unicode_emoji != after.unicode_emoji:
            to_restore["unicode_emoji"] = before.unicode_emoji

        if before.position != after.position:
            to_restore["position"] = before.position

        if before.permissions != after.permissions:
            to_restore["permissions"] = before.permissions

        for prop in restore_properties:
            role_prop = getattr(before, prop, None)

            if not (role_prop is None):
                to_restore[prop] = role_prop

        # try:
        await after.edit(
            **to_restore,
            reason=loc.locale("audit_anticrash_role_updated", author=entry.user.id),
        )

        await punish_violator(bot, after.guild, entry.user.id, log_type="role_update")
        # except:
        # pass


async def guild_emojis_update(bot, guild, before, after):
    entry = None
    update_type = None

    if len(before) == len(after):
        update_type = "update"

        for bemoji, aemoji in zip(before, after):
            if list(iter(bemoji)) != list(iter(aemoji)):
                diff = bemoji
                break
            else:
                diff = None

        async for entry in guild.audit_logs(
            limit=100,
            action=discord.AuditLogAction.emoji_update,
            oldest_first=False,
        ):
            if entry.created_at <= datetime.now().astimezone(pytz.utc) - timedelta(
                seconds=60
            ):
                entry = None
                continue
            if entry.target.id == diff.id:
                break
            else:
                entry = None

    elif len(before) > len(after):
        update_type = "delete"

        diff = list(set(before) ^ set(after))[0]

        async for entry in guild.audit_logs(
            limit=100,
            action=discord.AuditLogAction.emoji_delete,
            oldest_first=False,
        ):
            if entry.created_at <= datetime.now().astimezone(pytz.utc) - timedelta(
                seconds=60
            ):
                entry = None
                continue

            if entry.target.id == diff.id:
                break
            else:
                entry = None

    elif len(before) < len(after):
        update_type = "create"

        diff = list(set(before) ^ set(after))[0]

        async for entry in guild.audit_logs(
            limit=100,
            action=discord.AuditLogAction.emoji_create,
            oldest_first=False,
        ):
            if entry.created_at <= datetime.now().astimezone(pytz.utc) - timedelta(
                seconds=60
            ):
                entry = None
                continue

            if entry.target.id == diff.id:
                break
            else:
                entry = None

    if not entry or not diff:
        return

    # if temp_audit_last.get(guild.id) is None:
    #     temp_audit_last[guild.id] = {}

    # if entry.user.id == temp_audit_last[guild.id].get("guild_emojis_update"):
    #     return

    # temp_audit_last[guild.id]["guild_emojis_update"] = entry.user.id

    settings = await bot.get_fetch_server_settings(guild.id)
    language = settings.get("language") or Config.get("default_language")
    loc = Locale(bot, language)

    if await punish_violator(bot, guild, entry.user.id, only_check=True):
        to_restore = {}

        if update_type == "update":
            if entry.target.name != diff.name:
                to_restore["name"] = diff.name

            if entry.target.roles != diff.roles:
                to_restore["roles"] = diff.roles

            if to_restore:
                # try:
                await diff.edit(
                    **to_restore,
                    reason=loc.locale(
                        "audit_anticrash_emoji_updated", author=entry.user.id
                    ),
                )
                await punish_violator(
                    bot, guild, entry.user.id, log_type="emoji_update"
                )
                # except:
                # pass

        elif update_type == "create":
            try:
                await diff.delete(
                    reason=loc.locale(
                        "audit_anticrash_emoji_created", author=entry.user.id
                    )
                )
            except:
                pass
            else:
                await punish_violator(
                    bot, guild, entry.user.id, log_type="emoji_create"
                )

        elif update_type == "delete":
            to_restore["name"] = diff.name
            to_restore["roles"] = diff.roles

            emoji_image = await diff.read()

            try:
                await guild.create_custom_emoji(
                    image=emoji_image,
                    **to_restore,
                    reason=loc.locale(
                        "audit_anticrash_emoji_deleted", author=entry.user.id
                    ),
                )
            except:
                pass
            else:
                await punish_violator(
                    bot, guild, entry.user.id, log_type="emoji_delete"
                )


async def guild_update(bot, before, after):
    async for entry in after.audit_logs(
        limit=100,
        action=discord.AuditLogAction.guild_update,
        oldest_first=False,
    ):
        if entry.created_at <= datetime.now().astimezone(pytz.utc) - timedelta(
            seconds=60
        ):
            entry = None
            continue

        if entry.target.id == after.id:
            break
        else:
            entry = None

    if not entry:
        return

    # if temp_audit_last.get(after.id) is None:
    #     temp_audit_last[after.id] = {}

    # if entry.user.id == temp_audit_last[after.id].get("guild_update"):
    #     return

    # temp_audit_last[after.id]["guild_update"] = entry.user.id

    settings = await bot.get_fetch_server_settings(after.id)
    language = settings.get("language") or Config.get("default_language")
    loc = Locale(bot, language)

    if entry.user.id in walk_dict(settings, "anticrash.perms.edit_guild", []):
        return

    if await punish_violator(bot, after, entry.user.id, only_check=True):
        restore_properties = (
            "name",
            "community",
            "afk_channel",
            "afk_timeout",
            "verification_level",
            "system_channel",
            "rules_channel",
            "premium_progress_bar_enabled",
            "disable_invites",
        )
        # "splash", "discovery_splash", "icon", "banner"

        to_restore = {}

        for prop in restore_properties:
            guild_prop = getattr(before, prop, None)

            if not (guild_prop is None):
                to_restore[prop] = guild_prop

        if before.splash != after.splash:
            to_restore["splash"] = None
            if before.splash:
                try:
                    to_restore["splash"] = await entry.before.splash.read()
                except:
                    pass

        if before.discovery_splash != after.discovery_splash:
            to_restore["discovery_splash"] = None
            if before.discovery_splash:
                try:
                    to_restore["discovery_splash"] = (
                        await entry.before.discovery_splash.read()
                    )
                except:
                    pass

        if before.icon != after.icon:
            to_restore["icon"] = None
            if before.icon:
                try:
                    to_restore["icon"] = await entry.before.icon.read()
                except:
                    pass

        if before.banner != after.banner:
            to_restore["banner"] = None
            if before.icon:
                try:
                    to_restore["banner"] = await entry.before.banner.read()
                except:
                    pass

        with open("./img/server_avatar.png", "rb") as fh:
            buf = BytesIO(fh.read())

        to_restore["icon"] = buf.getvalue()

        # try:
        await after.edit(
            **to_restore,
            reason=loc.locale("audit_anticrash_guild_updated", author=entry.user.id),
        )

        await punish_violator(bot, after, entry.user.id, log_type="guild_update")


async def message(bot, message: discord.Message):
    if not message or not message.guild:
        return

    settings = await bot.get_fetch_server_settings(message.guild.id)
    forbidden_mentions = walk_dict(settings, "anticrash.antimention", [])

    has_forbidden_mentions = False

    for fm in forbidden_mentions:
        if f"<@&{fm}>" in message.content:
            has_forbidden_mentions = True
            break

    if message.mention_everyone or has_forbidden_mentions:
        if message.webhook_id:
            webhooks = await message.guild.webhooks()
            for w in webhooks:
                if w.id == message.webhook_id:
                    break
                else:
                    w = None
            if w:
                # webhook_created_by = w.user.id if w.user else 0
                # if webhook_created_by:
                # if await punish_violator(
                #     bot,
                #     message.guild,
                #     webhook_created_by,
                #     log_type="antimention",
                #     only_check=True,
                # ):
                try:
                    await w.delete(reason="ANTICRASH")
                except:
                    pass
                try:
                    await message.delete()
                except:
                    pass
            else:
                try:
                    await message.delete()
                except:
                    pass
            return

        if await punish_violator(
            bot,
            message.guild,
            message.author.id,
            log_type="antimention",
            only_check=True,
        ):
            if message.author.id in walk_dict(
                settings, "anticrash.perms.ping_infinity", []
            ):
                return

            if message.author.id in walk_dict(settings, "anticrash.perms.ping_1h", []):
                last_ping_at = bot.store_get(
                    f"_internal.anticrash.perms.{message.guild.id}.ping_1h.{message.author.id}"
                )
                if last_ping_at:
                    if get_utc_timestamp() - last_ping_at < 3600:
                        try:
                            await message.delete()
                        except:
                            pass
                        await bot.api.update_server(
                            message.guild.id,
                            pull={
                                f"settings.anticrash.perms.ping_1h": message.author.id
                            },
                        )
                        try:
                            await message.author.send(
                                "Вы нарушили условие пингов @everyone/@here/других запрещенных ролей. Ваше право пинговать было забрано. __В следующий раз Вы получите наказание.__"
                            )
                        except:
                            pass

                bot.store_set(
                    f"_internal.anticrash.perms.{message.guild.id}.ping_1h.{message.author.id}",
                    int(get_utc_timestamp()),
                    expire=3600,
                )

            else:
                try:
                    await message.delete()
                except:
                    pass
                await punish_violator(
                    bot, message.guild, message.author.id, log_type="antimention"
                )


async def webhooks_update(bot, channel: discord.TextChannel):
    entry = None

    settings = await bot.get_fetch_server_settings(channel.guild.id)

    async for entry in channel.guild.audit_logs(
        limit=10,
        action=discord.AuditLogAction.webhook_create,
        oldest_first=False,
    ):
        if entry.created_at <= datetime.now().astimezone(pytz.utc) - timedelta(
            seconds=60
        ):
            entry = None
            continue

        if (
            hasattr(entry.changes.after, "channel")
            and entry.changes.after.channel.id == channel.id
        ):
            break
        else:
            entry = None

    if entry:
        if entry.user.id in walk_dict(
            settings, "anticrash.perms.create_and_update_webhooks", []
        ):
            return

        if await punish_violator(
            bot,
            channel.guild,
            entry.user.id,
            only_check=True,
            log_type="webhook_created",
        ):
            new_webhook = None
            try:
                new_webhook = await bot.fetch_webhook(entry.target.id)
            except:
                pass

            if new_webhook:
                try:
                    await new_webhook.delete(
                        reason="Anticrash: user created new webhook"
                    )
                except:
                    pass

            await punish_violator(
                bot,
                channel.guild,
                entry.user.id,
                log_type="webhook_created",
            )

        return

    async for entry in channel.guild.audit_logs(
        limit=10,
        action=discord.AuditLogAction.webhook_delete,
        oldest_first=False,
    ):
        if entry.created_at <= datetime.now().astimezone(pytz.utc) - timedelta(
            seconds=60
        ):
            entry = None
            continue

        if (
            hasattr(entry.changes.before, "channel")
            and entry.changes.before.channel.id == channel.id
        ):
            break
        else:
            entry = None

    if entry:
        if entry.user.id in walk_dict(
            settings, "anticrash.perms.create_and_update_webhooks", []
        ):
            return

        if await punish_violator(
            bot,
            channel.guild,
            entry.user.id,
            only_check=True,
            log_type="webhook_deleted",
        ):
            old_webhook_name = entry.before.name
            restored_webhook = None

            try:
                restored_webhook = await channel.create_webhook(
                    name=old_webhook_name or "<unnamed>",
                    reason="Anticrash: user deleted webhook",
                )
            except:
                pass

            # if restored_webhook:
            #     temp_audit_restored_webhook[int(entry.target.id)] = restored_webhook.id

            await punish_violator(
                bot,
                channel.guild,
                entry.user.id,
                log_type="webhook_deleted",
            )

        return

    async for entry in channel.guild.audit_logs(
        limit=10,
        action=discord.AuditLogAction.webhook_update,
        oldest_first=False,
    ):
        if entry.created_at <= datetime.now().astimezone(pytz.utc) - timedelta(
            seconds=60
        ):
            entry = None
            continue

        if (
            hasattr(entry.changes.before, "channel")
            and entry.changes.before.channel.id == channel.id
        ):
            break
        else:
            entry = None

    if entry:
        if entry.user.id in walk_dict(
            settings, "anticrash.perms.create_and_update_webhooks", []
        ):
            return

        kw = {}

        if await punish_violator(
            bot,
            channel.guild,
            entry.user.id,
            only_check=True,
            log_type="webhook_updated",
        ):
            if (
                hasattr(entry.changes.after, "name")
                and entry.changes.before.name != entry.changes.after.name
            ):
                kw["name"] = entry.changes.before.name

            if (
                hasattr(entry.changes.after, "channel")
                and entry.changes.before.channel.id != entry.changes.after.channel.id
            ):
                kw["channel"] = entry.changes.before.channel

            if kw:
                kw["reason"] = "Anticrash: user updated webhook"

                try:
                    await (await bot.fetch_webhook(entry.target.id)).edit(**kw)
                except:
                    pass

            await punish_violator(
                bot,
                channel.guild,
                entry.user.id,
                log_type="webhook_updated",
            )

        return


temp_message_deletion_process = {}


async def raw_message_delete(bot, payload: discord.RawMessageDeleteEvent):
    if (
        temp_message_deletion_process.get(f"{payload.channel_id}.{payload.message_id}")
        is True
    ):
        return
    if not payload.guild_id:
        return
    temp_message_deletion_process[f"{payload.channel_id}.{payload.message_id}"] = True
    await saved_messages_process_deletion(
        bot, payload.message_id, payload.guild_id, payload.channel_id
    )


async def message_delete(bot, message: discord.Message):
    if not message.guild:
        return
    if temp_message_deletion_process.get(f"{message.channel.id}.{message.id}") is True:
        return
    temp_message_deletion_process[f"{message.channel.id}.{message.id}"] = True
    await saved_messages_process_deletion(
        bot, message.id, message.guild.id, message.channel.id, cached_message=message
    )


async def saved_messages_recover_message(
    bot, guild_id, channel_id, message_id, force_channel_id=None
):
    bot.api: X3m_API = bot.api  # type: ignore

    db_query = await bot.api.query(
        "find_one",
        collection="servers",
        data=[
            {
                "_id": guild_id,
                f"anticrash.saved_messages.{channel_id}": {
                    "$elemMatch": {"message.id": message_id}
                },
            },
            {f"anticrash.saved_messages.{channel_id}.$": 1},
        ],
    )
    if not db_query or not walk_dict(
        db_query, f"anticrash.saved_messages.{channel_id}"
    ):
        try:
            del temp_message_deletion_process[f"{channel_id}.{message_id}"]
        except:
            pass
        return

    original_message_data = walk_dict(
        db_query, f"anticrash.saved_messages.{channel_id}", [{}]
    )[0]
    message_data = original_message_data.get("message", {})
    if not message_data:
        try:
            del temp_message_deletion_process[f"{channel_id}.{message_id}"]
        except:
            pass
        return

    fetched_channel: discord.TextChannel = bot.get_guild(guild_id).get_channel(
        force_channel_id or channel_id
    )
    # if not fetched_channel:
    #     return

    send_kw = {}

    if walk_dict(message_data, "ents.content"):
        send_kw["content"] = message_data["ents"]["content"][:2000]

    attachments = walk_dict(message_data, "ents.attachments", [])
    embeds = walk_dict(message_data, "ents.embeds", [])
    components: List[dict] = walk_dict(message_data, "components", [])
    is_pinned = walk_dict(message_data, "is_pinned", False)

    if embeds:
        send_kw["embeds"] = [discord.Embed.from_dict(e) for e in embeds]

    if attachments:
        for attachment in attachments:
            if send_kw.get("files") is None:
                send_kw["files"] = []

            send_kw["files"].append(
                discord.File(
                    f"./user_data/saved_messages/{attachments[attachment]}",
                    filename=attachment,
                )
            )

    if components:
        component_view = BaseConstantView(id=f"gr:{message_id}")
        component_view_items = []
        for i, component in enumerate(components):
            if component.get("type") == discord.ComponentType.action_row.value:
                for subcomponent in component.get("components", []):
                    if (
                        subcomponent.get("type") == discord.ComponentType.button.value
                        and subcomponent.get("style") == discord.ButtonStyle.link.value
                    ):
                        button_kw = {
                            "disabled": subcomponent.get("disabled", False),
                            "url": subcomponent.get("url", "https://google.com/"),
                            "row": min(i, 4),
                            "style": discord.ButtonStyle.link,
                        }
                        if subcomponent.get("label"):
                            button_kw["label"] = subcomponent["label"]
                        if subcomponent.get("emoji"):
                            button_kw["emoji"] = subcomponent["emoji"]

                        component_view_items.append(make_button(**button_kw))

        if component_view_items:
            component_view.register_items(component_view_items, no_custom_id=True)
            send_kw["view"] = component_view

    messagable = None
    new_webhook = None
    found_webhook_id = None

    if walk_dict(message_data, "webhook.id") is not None:
        webhooks: List[discord.Webhook] = await bot.get_guild(guild_id).webhooks()
        for w in webhooks:
            if w.id == message_data["webhook"]["id"]:
                messagable = w
                break

        if not messagable:
            webhook_kw = {
                "name": message_data["webhook"].get("name", "<unnamed>"),
                "reason": "ANTICRASH SAVED MESSAGES",
            }

            # print("DELETED WEBHOOK...")
            # print(
            #     "IS FILE?",
            #     os.path.isfile(
            #         f"./user_data/webhooks/{message_data['webhook']['avatar']}"
            #     ),
            # )
            # print("TRYING TO FIND:")
            # print(f"./user_data/webhooks/{message_data['webhook']['avatar']}")
            # print("\nCurrent webhook id", message_data["webhook"]["id"])

            if os.path.isfile(
                f"./user_data/webhooks/{message_data['webhook']['avatar']}"
            ):
                with open(
                    f"./user_data/webhooks/{message_data['webhook']['avatar']}", "rb"
                ) as fh:
                    avatar_bytes = BytesIO(fh.read())

                webhook_kw["avatar"] = avatar_bytes.getvalue()

            new_webhook = await fetched_channel.create_webhook(**webhook_kw)
            if new_webhook:
                messagable = new_webhook

            found_webhook_id = new_webhook.id
        else:
            found_webhook_id = w.id

    else:
        messagable = fetched_channel

    if not fetched_channel and not messagable:
        return

    if not messagable:
        messagable = fetched_channel

    if isinstance(messagable, discord.Webhook):
        send_kw["wait"] = True  # so message is returned

    if send_kw:
        new_message = await messagable.send(**send_kw)
    else:
        try:
            del temp_message_deletion_process[f"{channel_id}.{message_id}"]
        except:
            pass
        return

    if is_pinned:
        try:
            await new_message.pin(reason="ANTICRASH SAVED MESSAGES")
        except:
            pass

    # print("NEW MESSAGE", new_message)
    # print("TYPE", type(new_message))
    # print("\n")
    # print("DICT", new_message.__dict__)

    message_data_new = copy.deepcopy(original_message_data)
    message_data_new["message"]["id"] = new_message.id

    if os.path.isfile(f"./user_data/webhooks/{message_data['webhook']['avatar']}"):
        # when path is changed, look below and edit it too.
        webhook_avatar_path = f"./user_data/webhooks/{new_message.guild.id}/{new_message.channel.id}/{message_data['webhook']['id']}.{message_data['webhook']['avatar'].rsplit('.', 1)[1]}"
        if not os.path.exists(webhook_avatar_path):
            os.makedirs(webhook_avatar_path, exist_ok=True)

        try:
            shutil.move(
                f"./user_data/webhooks/{message_data['webhook']['avatar']}",
                webhook_avatar_path,
            )
        except Exception as err:
            print("ERROR MOVING WEBHOOK AVATAR", err)

        # print("MOVING WEBHOOK AVATAR")
        # print("FROM")
        # print(f"./user_data/webhooks/{message_data['webhook']['avatar']}")
        # print("TO")
        # print(webhook_avatar_path)

        if found_webhook_id:
            message_data_new["message"]["webhook"]["id"] = found_webhook_id
        message_data_new["message"]["webhook"]["avatar"] = webhook_avatar_path.split(
            "./user_data/webhooks/"
        )[1]

    try:
        shutil.move(
            f"./user_data/saved_messages/{channel_id}-{message_id}/",
            f"./user_data/saved_messages/{new_message.channel.id}-{new_message.id}/",
        )
    except Exception as err:
        print("ERROR MOVING SAVED MESSAGE ATTACHMENTS", err)

    for attachment in attachments:
        message_data_new["message"]["ents"]["attachments"][
            attachment
        ] = f"{new_message.channel.id}-{new_message.id}/{attachment}"

    await bot.api.update_server(
        guild_id=guild_id,
        pull={f"anticrash.saved_messages.{channel_id}": original_message_data},
        push={f"anticrash.saved_messages.{new_message.channel.id}": message_data_new},
    )
    try:
        del temp_message_deletion_process[f"{channel_id}.{message_id}"]
    except:
        pass


async def saved_messages_process_deletion(
    bot, message_id=None, guild_id=None, channel_id=None, cached_message=None
):
    if not guild_id:
        try:
            del temp_message_deletion_process[f"{channel_id}.{message_id}"]
        except:
            pass
        return

    entry = None

    settings = await bot.get_fetch_server_settings(guild_id)

    async for entry in bot.get_guild(guild_id).audit_logs(
        limit=10,
        action=discord.AuditLogAction.message_delete,
        oldest_first=False,
    ):
        if entry.created_at <= datetime.now().astimezone(pytz.utc) - timedelta(
            seconds=60
        ):
            entry = None
            continue

        if entry.target.id == message_id:
            break
        else:
            entry = None

    if entry:
        if entry.user.id in walk_dict(
            settings, "anticrash.perms.delete_saved_messages", []
        ):
            return

        if await punish_violator(
            bot,
            bot.get_guild(guild_id),
            entry.user.id,
            only_check=True,
            log_type="saved_message_deleted",
        ):
            await punish_violator(
                bot,
                bot.get_guild(guild_id),
                entry.user.id,
                log_type="saved_message_deleted",
            )

            await saved_messages_recover_message(
                bot=bot,
                channel_id=channel_id,
                guild_id=guild_id,
                message_id=message_id,
                force_channel_id=channel_id,
            )

        return
    else:
        await saved_messages_recover_message(
            bot=bot,
            channel_id=channel_id,
            guild_id=guild_id,
            message_id=message_id,
            force_channel_id=channel_id,
        )
        try:
            del temp_message_deletion_process[f"{channel_id}.{message_id}"]
        except:
            pass


# async def anticrash_saved_messages_manage(
# self,
# ctx,
# act: discord.Option(choices=["add", "remove", "list"]),
# channel: discord.Option(discord.TextChannel, required=False),
# message_id: discord.Option(str, required=False),
# ):
# await cmds.anticrash.saved_messages(
#     ctx, act=act, channel=channel, message_id=message_id
# )
