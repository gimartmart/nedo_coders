import cmds
from libs.anticrash import process as anticrash_process
from libs.util import *
from libs.config import Config
from libs.awards import AwardType


async def process_event(bot, name, *args, **kwargs):
    if name == "voice_state_update":
        member = args[0]
        mbefore = args[1]
        mafter = args[2]

        voice_channel_before = mbefore.channel.id if mbefore.channel else None
        voice_channel_after = mafter.channel.id if mafter.channel else None

        if voice_channel_before and voice_channel_after:
            if not bot.store_exists(
                f"_internal.anticrash.temp_voices.{member.guild.id}.{voice_channel_before}"
            ):
                prev_list = []
                bot.store_set(
                    f"_internal.anticrash.temp_voices.{member.guild.id}.{voice_channel_before}",
                    prev_list,
                )
            else:
                prev_list = bot.store_get(
                    f"_internal.anticrash.temp_voices.{member.guild.id}.{voice_channel_before}"
                )

            try:
                prev_list.remove(member.id)
            except:
                pass

        if voice_channel_after:
            if not bot.store_exists(
                f"_internal.anticrash.temp_voices.{member.guild.id}.{voice_channel_after}"
            ):
                new_list = []
                bot.store_set(
                    f"_internal.anticrash.temp_voices.{member.guild.id}.{voice_channel_after}",
                    new_list,
                )
            else:
                new_list = bot.store_get(
                    f"_internal.anticrash.temp_voices.{member.guild.id}.{voice_channel_after}"
                )

            if member.id not in new_list:
                new_list.append(member.id)

    await anticrash_process(name, bot, *args, **kwargs)

    # if name == "voice_state_update":
    #     member = args[0]
    #     mbefore = args[1]
    #     mafter = args[2]

    #     spider = member.guild.get_member(
    #         Config.get("awards", {}).get("spider_id", 1029791933649932418)
    #     )

    #     if mafter.channel:
    #         for member in mafter.channel.members:
    #             if (
    #                 spider
    #                 and spider.voice
    #                 and not spider.voice.self_deaf
    #                 and spider in mafter.channel.members
    #             ):
    #                 if not bot.store_exists(
    #                     f"{member.guild.id}.spider_award.{member.id}"
    #                 ):
    #                     awards = (
    #                         walk_dict(
    #                             await bot.api.get_user(
    #                                 member.guild.id,
    #                                 member.id,
    #                                 fields=["profile.awards"],
    #                             ),
    #                             "profile.awards",
    #                         )
    #                         or []
    #                     )

    #                     has_spider_award = False
    #                     for award in awards:
    #                         if award.get("type") == AwardType.find_spider.value:
    #                             has_spider_award = True
    #                             break

    #                     if not has_spider_award:
    #                         await bot.api.update_user(
    #                             guild_id=member.guild.id,
    #                             user_id=member.id,
    #                             fields_guild={
    #                                 "push": {
    #                                     "profile.awards": {
    #                                         "type": AwardType.find_spider.value,
    #                                         "ts": get_utc_timestamp(),
    #                                     }
    #                                 }
    #                             },
    #                         )
    #                     else:
    #                         bot.store_set(
    #                             f"{member.guild.id}.spider_award.{member.id}",
    #                             True,
    #                             expire=3600,
    #                         )

    #     settings = await bot.get_fetch_server_settings(member.guild.id)

    #     # await cmds.private_channels.process_voice_state(
    #     #     bot, settings, member, mbefore, mafter
    #     # )

    #     # await cmds.private_channels.personal_channel_process_voice_state(
    #     #     bot, settings, member, mbefore, mafter
    #     # )

    #     await cmds.marry.process_voice_state(bot, settings, member, mbefore, mafter)
    #     # await cmds.clan.process_voice_state(bot, settings, member, mbefore, mafter)

    # elif name == "member_join":
    #     member = args[0]

    #     settings = await bot.get_fetch_server_settings(member.guild.id)
    #     loc = Locale(
    #         bot, settings.get("language", Config.get("default_language", "en-US"))
    #     )

    #     # is_verified = (
    #     #     await bot.api.count_documents(
    #     #         pattern={
    #     #             "_id": member.id,
    #     #             f"{member.guild.id}.verify.verified": {"$eq": True},
    #     #         },
    #     #         collection="users",
    #     #     )
    #     #     == 1
    #     # )

    #     # if is_verified:
    #     # previous_roles = (
    #     #     await bot.api.get_user(
    #     #         guild_id=member.guild.id, user_id=member.id, fields=["saved_roles"]
    #     #     )
    #     # ) or {}

    #     # previous_roles = walk_dict(previous_roles, "saved_roles")

    #     # restored_roles = []

    #     # for role_id in previous_roles:
    #     #     r = member.guild.get_role(role_id)
    #     #     if r and r not in restored_roles:
    #     #         restored_roles.append(r)

    #     # if restored_roles:
    #     #     try:
    #     #         await member.edit(
    #     #             roles=restored_roles, reason=loc.locale("audit_restored_roles")
    #     #         )
    #     #     except:
    #     #         pass
    #     # else:

    #     autoroles = []
    #     autoroles_ids = walk_dict(settings, "autoroles") or []

    #     for role_id in autoroles_ids:
    #         role = member.guild.get_role(role_id)
    #         if role and role not in autoroles:
    #             autoroles.append(role)

    #     try:
    #         await member.edit(roles=autoroles, reason=loc.locale("audit_autoroles"))
    #     except:
    #         pass

    #     await bot.api.update_user(
    #         guild_id=member.guild.id,
    #         user_id=member.id,
    #         fields_guild={"set": {"disabled": False}},
    #     )

    # elif name == "member_remove":
    #     member = args[0]
    #     roles = [r.id for r in member.roles if r.id != member.guild.default_role.id]

    #     await bot.api.update_user(
    #         guild_id=member.guild.id,
    #         user_id=member.id,
    #         fields_guild={"set": {"saved_roles": roles, "disabled": True}},
    #     )

    if name == "member_update":
        mbefore = args[0]
        mafter = args[1]

        settings = await bot.get_fetch_server_settings(mafter.guild.id)

        if mbefore.roles != mafter.roles:
            diff = list(set(mbefore.roles) ^ set(mafter.roles))

            for role in diff:
                if role.id in walk_dict(settings, "anticrash.cached_roles", []):
                    action = "push"
                    if role not in mafter.roles:
                        action = "pull"

                    kwargs = {action: {f"anticrash.cache.roles.{role.id}": mafter.id}}

                    await bot.api.update_server(guild_id=mafter.guild.id, **kwargs)
