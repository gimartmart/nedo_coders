import logging

import pytz
import discord
from libs.util import *
from libs.config import Config
from datetime import datetime

log = logging.getLogger("log")


async def get_settings(bot, gid):
    server = await bot.get_fetch_server_settings(gid)
    return server or {}


class EventColors:
    _default_color = 0xA3ACB5
    message_delete = 0xFF7176
    message_edit = 0xFFF171
    member_join = 0xAAFF71
    member_remove = 0xFF7171
    member_ban = 0xFF7171
    member_unban = 0xFFAC71
    member_update = 0xFFF100
    voice_state_update = 0x71F6FF
    invite_create = 0xB371FF
    invite_delete = 0xD659FF
    balance_edit = 0xFFAC71


# class EventLogChannel:
#     _default = "logs_chat"
#     message_delete = "logs_chat"
#     message_edit = "logs_chat"
#     member_ban = "logs_ban"
#     member_unban = "logs_ban"
#     member_update = "logs_nickname" + "logs_voices"


def get_guild(name, *args, **kwargs):

    if name in (
        "message_delete",
        "message_edit",
        "member_join",
        "member_remove",
        "member_update",
        "voice_state_update",
        "invite_create",
        "invite_delete",
        "balance_edit",  # internal
    ):
        guild = args[0].guild

    elif name == "bulk_message_delete":
        guild = args[0][0].guild

    # mute, gag - are internal
    elif name in ("member_ban", "member_unban", "mute", "gag"):
        guild = args[0]

    else:
        return None

    return guild


async def process_log(bot, name, *args, **kwargs):
    if not bot.is_ready():
        return

    name = name.lower()
    guild = get_guild(name, *args, **kwargs)
    if not guild:
        return  # dm messages

    settings = await get_settings(bot, guild.id)

    server_tz = pytz.timezone(settings.get("timezone", "Europe/Moscow"))

    log_channel_id = None
    if name in ("message_delete", "message_edit"):
        log_channel_id = walk_dict(settings, "channels.logs_chat")
    elif name in ("member_ban", "member_unban"):
        log_channel_id = walk_dict(settings, "channels.logs_ban")

    elif name in ("member_join", "member_remove"):
        log_channel_id = walk_dict(settings, "channels.logs_users")

    elif name == "member_update":
        if args[0].nick != args[1].nick:
            log_channel_id = walk_dict(settings, "channels.logs_nickname")

    elif name == "balance_edit":
        log_channel_id = walk_dict(settings, "channels.logs_award")

    elif name == "voice_state_update":
        log_channel_id = walk_dict(settings, "channels.logs_voices")

    elif name in ("mute", "gag"):
        log_channel_id = walk_dict(settings, "channels.logs_mutes")

    if not log_channel_id:
        return
    
    if name not in ("balance_edit",): ######################################################## TURNED OFF FOR ECONOMY
        return

    log_channel = guild.get_channel(log_channel_id)

    if not log_channel or not settings.get("states", {}).get("logs", True):
        return

    lang = settings.get("language", Config.get("default_language", "en-US"))
    loc = Locale(bot, lang)

    ignored_channels = settings.get("logs", {}).get("ignored_channels", [])
    ignored_categories = settings.get("logs", {}).get("ignored_categories", [])

    server_now = datetime.now(server_tz)

    embed = discord.Embed(color=Const.embed_color)
    embed.color = getattr(EventColors, name, EventColors._default_color)
    embed.timestamp = datetime.now()
    embed.set_footer(
        text=server_now.strftime("%H:%M:%S.%f")[:-5] + server_now.strftime(" %Z")
    )

    file = None
    files = []

    if name == "message_delete":
        msg = args[0]
        if msg.author.bot:
            return

        if msg.author == bot.user or not msg.content:
            return

        if msg.channel.id in ignored_channels:
            return

        if msg.channel.category and msg.channel.category.id in ignored_categories:
            return

        embed.set_author(name=loc.locale("log_msg_delete_title"))
        embed.title = loc.locale("log_msg_delete_content")
        embed.description = ellipsis(msg.content, max=2048)
        embed.set_thumbnail(url=msg.author.display_avatar.url)

        embed.add_field(
            name=loc.locale("log_msg_author"),
            value=f"{msg.author.mention}/{msg.author.id}",
        )

        channel_value = f"{msg.channel.mention}"

        if isinstance(msg.channel, discord.TextChannel):
            channel_value = f"`{msg.channel.category}`/{msg.channel.mention}"

        embed.add_field(
            name=loc.locale("log_msg_channel"), value=channel_value, inline=False
        )

        for attachment in msg.attachments:
            try:
                files.append(await attachment.to_file())
            except:
                try:
                    files.append(await attachment.to_file(use_cached=True))
                except:
                    pass

    elif name == "message_edit":
        msg = mbefore = args[0]
        if msg.author.bot:
            return
        mafter = args[1]

        if msg.channel.id in ignored_channels:
            return
        if msg.channel.category and msg.channel.category.id in ignored_categories:
            return

        if mbefore.content == mafter.content or msg.author == bot.user:
            return

        embed.set_author(name=loc.locale("log_msg_edit_title"))
        embed.set_thumbnail(url=msg.author.display_avatar.url)
        embed.description = loc.locale("log_msg_jump_to", url=msg.jump_url)

        embed.add_field(
            name=loc.locale("log_msg_edit_before"),
            value=ellipsis(mbefore.content, max=1024),
        )
        embed.add_field(
            name=loc.locale("log_msg_edit_after"),
            value=ellipsis(mafter.content, max=1024),
            inline=False,
        )

        embed.add_field(
            name=loc.locale("log_msg_author"),
            value=f"{msg.author.mention}/{msg.author.id}",
            inline=False,
        )

        channel_value = f"{msg.channel.mention}"

        if isinstance(msg.channel, discord.TextChannel):
            channel_value = f"`{msg.channel.category}`/{msg.channel.mention}"

        embed.add_field(
            name=loc.locale("log_msg_channel"), value=channel_value, inline=False
        )

    elif name == "balance_edit":
        member = args[0]
        editor = args[1]
        bal_before = args[2]
        bal_after = args[3]

        bal_before = f"{int(bal_before):,}".replace(",", ".")
        bal_after = f"{int(bal_after):,}".replace(",", ".")

        embed.add_field(
            name=loc.locale("log_mem_vcstate_user_title"),
            value=f"{member.mention}/{member.id}",
            inline=False,
        )
        embed.set_thumbnail(url=member.display_avatar.url)

        embed.add_field(
            name=loc.locale("log_balance_edit_before"),
            value=ellipsis(bal_before, max=1024),
        )
        embed.add_field(
            name=loc.locale("log_balance_edit_after"),
            value=ellipsis(bal_after, max=1024),
            inline=False,
        )

        embed.add_field(
            name=loc.locale("log_balance_edit_author"),
            value=f"{editor.mention}/`{editor.id}`",
            inline=False,
        )

    elif name in ("mute", "gag"):
        embed = args[1]

    elif name == "member_join":
        member = args[0]
        if member == bot.user:
            return

        embed.set_author(name=loc.locale("log_mem_join_title"))
        embed.set_thumbnail(url=member.display_avatar.url)

        created_at = member.created_at.astimezone(server_tz)

        age = make_time(
            bot, lang, (datetime.now(server_tz) - created_at).total_seconds()
        )

        embed.add_field(
            name=loc.locale("log_mem_data_title"),
            value=loc.locale(
                "log_mem_join_data_value",
                created_at=created_at.strftime("%d.%m.%Y %H:%M %Z"),
                age=age,
                tag=member.mention,
                id=member.id,
            ),
        )

    elif name == "member_remove":
        member = args[0]
        if member == bot.user:
            return

        embed.set_author(name=loc.locale("log_mem_remove_title"))
        embed.set_thumbnail(url=member.display_avatar.url)

        created_at = member.created_at.astimezone(server_tz)
        joined_at = member.joined_at.astimezone(server_tz)

        now = datetime.now(server_tz)

        age = make_time(bot, lang, (now - created_at).total_seconds())
        been_on_server_time = make_time(bot, lang, (now - joined_at).total_seconds())

        embed.add_field(
            name=loc.locale("log_mem_data_title"),
            value=loc.locale(
                "log_mem_remove_data_value",
                created_at=created_at.strftime("%d.%m.%Y %H:%M %Z"),
                joined_at=joined_at.strftime("%d.%m.%Y %H:%M %Z"),
                server_time=been_on_server_time,
                age=age,
                id=member.id,
                tag=str(member),
            ),
        )

    elif name == "member_unban":
        member = args[1]
        if member == bot.user:
            return

        embed.set_author(name=loc.locale("log_mem_unban_title"))
        embed.set_thumbnail(url=member.display_avatar.url)

        created_at = member.created_at.astimezone(server_tz)

        now = datetime.now(server_tz)

        age = make_time(bot, lang, (now - created_at).total_seconds())

        entry = None

        async for entry in guild.audit_logs(
            limit=100,
            action=discord.AuditLogAction.unban,
            oldest_first=False,
        ):
            if entry.target.id == member.id:
                break
            else:
                entry = None

        embed.add_field(
            name=loc.locale("log_mem_data_title"),
            value=loc.locale(
                "log_mem_ban_value",
                created_at=created_at.strftime("%d.%m.%Y %H:%M %Z"),
                age=age,
                id=member.id,
                tag=str(member),
            )
            + (
                ("\n\n" + loc.locale("log_mem_unban_data", author=entry.user.id))
                if entry
                else ""
            ),
        )

        if entry.reason:
            embed.add_field(
                name=loc.locale("log_reason_title"),
                value=entry.reason[:1024],
                inline=False,
            )

    elif name == "member_ban":
        member = args[1]
        if member == bot.user:
            return

        embed.set_author(name=loc.locale("log_mem_ban_title"))
        embed.set_thumbnail(url=member.display_avatar.url)

        created_at = member.created_at.astimezone(server_tz)

        now = datetime.now(server_tz)

        age = make_time(bot, lang, (now - created_at).total_seconds())

        entry = None

        async for entry in guild.audit_logs(
            limit=100,
            action=discord.AuditLogAction.ban,
            oldest_first=False,
        ):
            if entry.target.id == member.id:
                break
            else:
                entry = None

        embed.add_field(
            name=loc.locale("log_mem_data_title"),
            value=loc.locale(
                "log_mem_ban_value",
                created_at=created_at.strftime("%d.%m.%Y %H:%M %Z"),
                age=age,
                id=member.id,
                tag=str(member),
            )
            + (
                ("\n\n" + loc.locale("log_mem_ban_data", author=entry.user.id))
                if entry
                else ""
            ),
        )

        if entry.reason:
            embed.add_field(
                name=loc.locale("log_reason_title"),
                value=entry.reason[:1024],
                inline=False,
            )

    elif name == "member_update":
        mbefore = args[0]
        mafter = args[1]

        embed.set_author(name=loc.locale("log_mem_update_title"))

        embed.add_field(
            name=loc.locale("log_mem_update_user_title"),
            value=f"{mafter.mention}/{mafter.id}",
        )
        embed.set_thumbnail(url=mafter.display_avatar.url)

        if mbefore.nick == mafter.nick and mbefore.roles == mafter.roles:
            return

        if mbefore.nick != mafter.nick:
            embed.add_field(
                name=loc.locale("log_mem_old_nick"),
                value=mbefore.nick or loc.locale("nothing"),
                inline=False,
            )
            embed.add_field(
                name=loc.locale("log_mem_new_nick"),
                value=mafter.nick or loc.locale("nothing"),
                inline=False,
            )

        if mbefore.roles != mafter.roles:
            diff = set(mbefore.roles) ^ set(mafter.roles)

            added = []
            removed = []

            for r in diff:
                if r in mbefore.roles:
                    removed.append(r)
                elif r in mafter.roles:
                    added.append(r)

            if added:
                embed.add_field(
                    name=loc.locale("log_mem_roles_added_title", count=len(added)),
                    value=ellipsis("/".join(f"<@&{r.id}>" for r in added), max=1024),
                    inline=False,
                )
            if removed:
                embed.add_field(
                    name=loc.locale("log_mem_roles_removed_title", count=len(removed)),
                    value=ellipsis("/".join(f"<@&{r.id}>" for r in removed), max=1024),
                    inline=False,
                )

    elif name == "voice_state_update":
        member = args[0]
        mbefore = args[1]
        mafter = args[2]

        if mbefore.channel == mafter.channel:
            return

        if (
            mafter.channel
            and mafter.channel.category
            and mafter.channel.category.id in ignored_categories
        ):
            return

        if (
            mbefore.channel
            and mbefore.channel.category
            and mbefore.channel.category.id in ignored_categories
        ):
            return

        embed.set_author(name=loc.locale("log_mem_vcstate_title"))
        embed.add_field(
            name=loc.locale("log_mem_vcstate_user_title"),
            value=f"{member.mention}/{member.id}",
            inline=False,
        )

        def format_chan(chan):
            if not chan:
                return loc.locale("nothing")

            text = chan.mention

            if chan.category:
                text = f"`{chan.category}`/" + text

            return text

        embed.add_field(
            name=loc.locale("log_mem_vcstate_before_channel"),
            value=format_chan(mbefore.channel),
        )
        embed.add_field(
            name=loc.locale("log_mem_vcstate_after_channel"),
            value=format_chan(mafter.channel),
        )
        embed.set_thumbnail(url=member.display_avatar.url)

    elif name == "invite_create":
        invite = args[0]
        member = invite.inviter or bot.user

        embed.set_author(name=loc.locale("log_invite_create_title"))
        embed.set_thumbnail(url=member.display_avatar.url)

        embed.add_field(
            name=loc.locale("log_invite_user_title"),
            value=f"{member.mention}/{member.id}",
        )

        max_age = make_time(bot, lang, invite.max_age or 0)
        if invite.expires_at:
            expires_at = invite.expires_at.astimezone(server_tz).strftime(
                "%H:%M %d.%m.%Y %Z"
            )
        else:
            expires_at = loc.locale("never")

        max_uses = (
            invite.max_uses
            if invite.max_uses != 0
            else loc.locale("invite_uses_unlimited")
        )

        if not isinstance(invite.channel, discord.Object):
            channel = invite.channel.mention
        else:
            channel = "<?>"

        embed.add_field(
            name=loc.locale("log_invite_data_title"),
            value=loc.locale(
                "log_invite_data_desc",
                inviter=member,
                channel=channel,
                code=invite.code,
                max_uses=max_uses,
                max_age=max_age,
                expires_at=expires_at,
            ),
            inline=False,
        )

    elif name == "invite_delete":
        invite = args[0]

        embed.set_author(name=loc.locale("log_invite_delete_title"))

        if not isinstance(invite.channel, discord.Object):
            channel = invite.channel.mention
        else:
            channel = "<?>"

        embed.add_field(
            name=loc.locale("log_invite_data_title"),
            value=loc.locale(
                "log_invite_delete_data_desc", channel=channel, code=invite.code
            ),
            inline=False,
        )

    else:
        return log.debug(f"Server unknown log: {name} ({len(args) + len(kwargs)})")

    log_kw = {"embed": embed}

    if file and not files:
        log_kw["file"] = file

    elif files:
        log_kw["files"] = files

    await log_channel.send(**log_kw)

    log.debug(f"Server log: {name} ({len(args) + len(kwargs)})")
