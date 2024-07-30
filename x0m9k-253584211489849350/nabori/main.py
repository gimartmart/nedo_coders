import asyncio
import random
import discord
import os
import json
import copy
from libs.config import Config, Images
import time


Config.load()
Images.load_all()


from discord import SlashCommandOptionType
from libs.util import *
from libs.log import init_logger
from libs.x3m_api import X3m_API
from libs.context import X3m_ApplicationContext, X3m_ApplicationContextEmpty
from libs.serverlog import process_log as process_server_log
from libs.store import LocalStore, LocalStoreExpire
from libs.const_views import get_all_const_views
from libs.events import process_event
from libs.transactions import TransactionType
from libs import error_handler
from discord.ext import commands
from discord.commands import SlashCommandGroup
from discord.ext.commands import MemberConverter, UserConverter
from typing import Union, get_type_hints, Any, Optional
from libs.awards import AwardType

log = init_logger()
log.debug("CFG:", {k: v for k, v in Config._config.items() if k != "tokens"})

__name__ = "ЭЙВ."
__version__ = "2.5.0"  # major.minor.patch
__pycord_version__ = "2.4.1"  # 2.4.1 release
__version_date__ = "5.01.2024"  # d.m.y (may be unaccurate)


log.info(f"Launched at {get_local_date('%d.%m.%Y %H:%M:%S %Z')}")


class Icecream(commands.Bot):
    def __init__(self, *args, **kwargs):
        # fmt: off
        intents = discord.Intents(
            guilds=True, members=True, bans=True,
            emojis=True, integrations=False,
            webhooks=False, invites=True,
            voice_states=True, presences=True,
            messages=True,  # messages -> bot's DMs, events
            reactions=True,
            message_content=True, # message's attachments
            typing=False
        )
        # fmt: on

        super().__init__(
            command_prefix=None,
            intents=intents,
            case_insensitive=True,
            help_command=None,
            max_messages=1000,
            activity=discord.Game(name="📡 Loading..."),
        )

        self.api = X3m_API(self)

        self.bot_name = __name__
        self.bot_version = __version__
        self.bot_version_date = __version_date__

        self.cached_server_settings = {}
        self.localization = {}
        self.global_settings = {}
        self.store = LocalStore(self)
        self.store_expire = LocalStoreExpire(self)

        self.default_server_settings = {
            "currency": "$",
            "language": "ru",
            "timezone": "Europe/Moscow",
            "prices": {
                "marry": 2000,
                "marry_monthly": 2000,
                "roles": {"buy": 10_000, "give": 500, "edit": 1000, "monthly": 1000},
            },
            "numbers": {
                "comission_user": 0.9,
                "comission_premium": 0.98,
                "comission_booster": 0.95,
                "comission_zero": 1,
                "tickets_max_simultaneous": 3,
                "tickets_max_channels": 20,
                "report_max_active_reports": 3,
                "vc_online": {"balance_per_60minutes": 120},
                "max_personal_roles": 3,
            },
        }

        self.permissions_name_number = Config.get(
            "permissions",
            {
                "dev": -999,
                "server_owner": -998,
                "superadmin": -997,
                "admin": -996,
                "moderator": -995,
                "user": -994,
            },
        )

        self.permissions_number_name = {
            v: k for k, v in self.permissions_name_number.items()
        }

        events = [
            "button_click",
            "message_delete",
            "bulk_message_delete",
            "message_edit",
            "guild_channel_delete",
            "guild_channel_create",
            "guild_channel_update",
            # "webhooks_update",
            "member_join",
            "member_remove",
            "member_update",
            # "guild_join",
            # "guild_remove",
            "guild_update",
            "guild_role_create",
            "guild_role_delete",
            "guild_role_update",
            "guild_emojis_update",
            "voice_state_update",
            "member_ban",
            "member_unban",
            "invite_create",
            "invite_delete",
            "integration_create",
        ]

        """
        if there's no self.'x' then one will be created,
        if there's self.'x' then old function will be called after serverlog.
        """

        for name in events:
            name = "on_" + name

            async def fun(n, *args, **kwargs):
                await process_event(self, n, *args, **kwargs)
                await process_server_log(self, n, *args, **kwargs)

            def create_lambda(name):
                return lambda *a, **kw: fun(name[3:], *a, **kw)

            if getattr(self, name, None) != None:
                old = getattr(self, name)

                def create_fun(name):
                    async def newfunc(*args, **kwargs):
                        await create_lambda(name)(*args, **kwargs)
                        await old(*args, **kwargs)

                    return newfunc

                setattr(self, name, create_fun(name))

            else:
                setattr(self, name, create_lambda(name))

    async def get_application_context(
        self, interaction: discord.Interaction, cls=X3m_ApplicationContext
    ) -> X3m_ApplicationContext:
        if not interaction.guild:
            try:
                await interaction.response.send_message("❌")
            except:
                pass

            return await super().get_application_context(
                interaction, cls=X3m_ApplicationContextEmpty
            )

        return await super().get_application_context(interaction, cls=cls)

    async def on_ready(self) -> None:
        log.info(
            "\n\t".join(
                [
                    f"The bot is ready! At {get_local_date()}",
                    f"Logined as {self.user} ({self.user.id})",
                    f"Servers ({len(self.guilds)}):",
                    "\n\t\t".join(
                        f"{g.name}\t{g.member_count}" for g in self.guilds.copy()
                    ),
                ]
            )
        )

        await self.change_presence(activity=None)  # discord.Game(f"ЭЙВ."))

        for _, ConstView in get_all_const_views():
            self.add_view(ConstView())

    async def my_fetch_user(
        self,
        guild_id: int,
        user_id: int,
        fields: Optional[list] = [],
        get_preferences: bool = False,
        walk_to_guild: bool = True,
    ) -> dict:
        if get_preferences and not fields:
            fields = ["_id"]

        response = await self.api.get_user(
            guild_id,
            user_id,
            fields,
            get_preferences=get_preferences,
            walk_to_guild=walk_to_guild,
        )

        return response

    async def user_has_award(
        self, guild_id: int, user_id: int, award: AwardType
    ) -> bool:
        user_data = await self.my_fetch_user(
            guild_id=guild_id, user_id=user_id, fields=["profile.awards"]
        )

        for profile_award in walk_dict(user_data, "profile.awards", []):
            if profile_award.get("type") == award.value:
                return True

        return False

    async def give_user_award(self, guild_id: int, user_id: int, award: AwardType):
        await self.api.update_user(
            guild_id,
            user_id,
            fields_guild={
                "push": {
                    "profile.awards": {
                        "type": award.value,
                        "ts": get_utc_timestamp(),
                    }
                },
                "addToSet": {"profile.awards_flat": award.value},
            },
        )

    async def on_message(self, msg: discord.Message) -> None:
        if not msg.guild or msg.author.bot:
            return

        # if msg.type == discord.MessageType.premium_guild_subscription:
        #     current_boosts = (
        #         await self.api.get_user(
        #             guild_id=msg.guild.id,
        #             user_id=msg.author.id,
        #             fields=["server_boosts"],
        #         )
        #     ) or {}
        #     current_boosts = current_boosts.get("server_boosts", 0)

        #     if current_boosts + 1 >= 2:
        #         if not await self.user_has_award(
        #             guild_id=msg.guild.id,
        #             user_id=msg.author.id,
        #             award=AwardType.quest_1_boosted_server_2x,
        #         ):
        #             await try_notify_user_quest_achievement(
        #                 self,
        #                 msg.author,
        #                 guild_id=msg.guild.id,
        #                 achievement=AwardType.quest_1_boosted_server_2x,
        #                 award_balance=800,
        #             )

        #     await self.api.update_user(
        #         msg.guild.id,
        #         msg.author.id,
        #         fields_guild={
        #             "$inc": {"server_boosts": 1},
        #             "$set": {"vc_online.quest_2": 0},
        #         },
        #     )

        # return
        # if not msg.guild:
        #     return

        # settings = await self.get_fetch_server_settings(msg.guild.id)
        # if msg.channel.id in walk_dict(settings, "autoclear_channels", []):
        #     try:
        #         await msg.delete()
        #     except:
        #         pass

        # if msg.author.bot:
        #     return

        # if not self.store_exists(
        #     f"_internal.{msg.guild.id}.msg_award_check.{msg.author.id}"
        # ):
        #     db_data = await bot.api.get_user(
        #         guild_id=msg.guild.id,
        #         user_id=msg.author.id,
        #         fields=["messages.default", "profile.awards", "vc_online.default"],
        #     )

        #     msgs = walk_dict(db_data, "messages.default", 0)
        #     vc_online = walk_dict(db_data, "vc_online.default", 0)

        #     has_msgs_award = False
        #     for award in walk_dict(db_data, "profile.awards", []):
        #         if award.get("type") == AwardType.activist.value:
        #             has_msgs_award = True
        #             break

        #     if (
        #         msgs >= 2000 and vc_online >= 540000 and has_msgs_award
        #     ):  # 150 hours vc_online
        #         self.store_set(
        #             f"_internal.{msg.guild.id}.msg_award_check.{msg.author.id}",
        #             True,
        #             expire=3600,
        #         )
        #     else:
        #         if msgs >= 2000 and vc_online >= 540000 and not has_msgs_award:
        #             await bot.api.update_user(
        #                 guild_id=msg.guild.id,
        #                 user_id=msg.author.id,
        #                 fields_guild={
        #                     "push": {
        #                         "profile.awards": {
        #                             "type": AwardType.activist.value,
        #                             "ts": get_utc_timestamp(),
        #                         }
        #                     }
        #                 },
        #             )

        #             self.store_set(
        #                 f"_internal.{msg.guild.id}.msg_award_check.{msg.author.id}",
        #                 True,
        #                 expire=3600,
        #             )
        #         else:
        #             self.store_set(
        #                 f"_internal.{msg.guild.id}.msg_award_check.{msg.author.id}",
        #                 True,
        #                 expire=30,
        #             )

        # self.store_inc(
        #     f"{msg.guild.id}.messages.default.{msg.author.id}",
        #     1,
        #     default_value=0,
        #     create_new_fields=True,
        # )

        # return  # we ignore that until we want to implement stats

        # if not self.is_ready():
        #     return

        # if msg.author.bot or not msg.guild:
        #     return

        # gid = msg.guild.id
        #
        # mb add statistics process.

    async def on_application_command_error(
        self, ctx: X3m_ApplicationContext, error: commands.CommandError
    ) -> None:
        await error_handler.on_command_error(ctx, error)

    async def on_command_error(self, *args, **kwargs) -> None:
        return  # we ignore that.

    def locale(
        self,
        lang: str,
        _code_: str,
        disallow_english_fallback: bool = False,
        return_found: bool = False,
        hide_empty: bool = False,
        **kwargs,
    ) -> Union[str, tuple]:
        d = DefaultDict(kwargs, hide_empty=hide_empty)

        err_code = f"#{_code_}: {' '.join(f'{k}={v}' for k, v in kwargs.items())}"

        is_found = True

        text = self.localization.get(_code_, {}).get(lang) or err_code
        if not disallow_english_fallback and text == err_code:
            res = self.localization.get(_code_, {}).get(
                Config.get("translation_default_language", "en-US")
            )
            if res:
                text = res
            else:
                is_found = False

        text = text.format_map(d).replace("\\n", "\n")

        if return_found:
            return text, is_found

        return text

    def get_cached_server_settings(self, guild_id: int) -> Union[dict, None]:
        return self.cached_server_settings.get(guild_id)

    async def get_fetch_server_settings(
        self, guild_id: int, ignore_cache: bool = False
    ) -> dict:
        cached = self.get_cached_server_settings(guild_id)
        if ignore_cache or not cached:
            return (await self.cache_server_settings(guild_id)) or {}
        return cached or {}

    def _prepare_cog(self, cog: commands.Cog) -> None:
        """
        Will prepare cog:
            - apply name_localizations and description_localizations
        Please read ./info.txt for additional information.
        """

        def apply_default_language(obj: Any, type: str, locales: dict) -> None:
            """
            type = "name_localizations" or "description_localizations"
            """
            default_lang = Config.get("translation_default_language")

            if locales.get(default_lang):
                setattr(obj, type.split("_localizations")[0], locales[default_lang])
                del locales[default_lang]

            setattr(obj, type, locales)

        def prepare_cmd(cmd, cmd_prefix=""):
            cmd_name = cmd.name
            if cmd.parent:
                cmd_name = cmd_prefix + cmd.parent.name + "_" + cmd.name

                # the code below doesn't work. See ./info.txt for info.
                # if not cmd.parent.name_localizations:
                #     group_name_loc = self.localization.get(
                #         "group_name_" + cmd.parent.name
                #     )
                #     if group_name_loc:
                #         cmd.parent.name_localizations = {
                #             "ru": "профиль",
                #             "en-US": "profile",
                #         }  # group_name_loc
                #
                # if not cmd.parent.description_localizations:
                #     group_desc_loc = self.localization.get(
                #         "group_desc_" + cmd.parent.name
                #     )
                #     if group_desc_loc:
                #         cmd.parent.name_localizations = group_desc_loc

            name_loc = self.localization.get("cmd_name_" + cmd_name)
            desc_loc = self.localization.get("cmd_desc_" + cmd_name)

            t_hints = get_type_hints(cmd._callback)

            for t_h in t_hints:
                obj = t_hints[t_h]

                if isinstance(obj, discord.commands.Option):
                    if Config.get("auto_add_min_maxint_ds_to_options"):
                        if (
                            obj.input_type == SlashCommandOptionType.integer
                            or obj.input_type == SlashCommandOptionType.number
                        ):
                            if obj.min_value == None:
                                obj.min_value = Const.minint_ds
                            if obj.max_value == None:
                                obj.max_value = Const.maxint_ds

                    opt_name_loc = self.localization.get(
                        "cmd_" + cmd_name + "_opt_name_" + t_h
                    ) or self.localization.get("generic_opt_name_" + t_h)

                    opt_desc_loc = self.localization.get(
                        "cmd_" + cmd_name + "_opt_desc_" + t_h
                    ) or self.localization.get("generic_opt_desc_" + t_h)

                    if opt_name_loc:
                        apply_default_language(obj, "name_localizations", opt_name_loc)
                        # obj.name_localizations = opt_name_loc
                    if opt_desc_loc:
                        apply_default_language(
                            obj, "description_localizations", opt_desc_loc
                        )
                        # obj.description_localizations = opt_desc_loc

            cmd.guild_ids = Config.get("slash_commands_guild_ids")
            if Config.get("debug") is True:
                cmd.guild_ids = Config.get("debug_slash_commands_guild_ids")

            if name_loc:
                apply_default_language(cmd, "name_localizations", name_loc)
                # cmd.name_localizations = name_loc

            if desc_loc:
                apply_default_language(cmd, "description_localizations", desc_loc)
                # cmd.description_localizations = desc_loc
            else:
                cmd.description = Config.get("default_cmd_description", "-")

        def prepare_cmd_or_group(obj, cmd_prefix=""):
            if isinstance(obj, SlashCommandGroup):
                for c in obj.walk_commands():
                    prepare_cmd_or_group(c, cmd_prefix=obj.parent.name + "_")
            else:
                prepare_cmd(obj, cmd_prefix=cmd_prefix)

        for cmd in cog.walk_commands():
            prepare_cmd_or_group(cmd)

    async def cache_server_settings(self, guild_id: int) -> dict:
        server_settings = (
            await self.api.get_server(guild_id, fields=["settings"])
        ) or {}
        server_settings = server_settings.get("settings", {})

        settings = copy.deepcopy(self.default_server_settings)

        merge_dicts(settings, server_settings)

        self.cached_server_settings[guild_id] = settings

        return settings

    def _merge_localization(self, schemes: list) -> dict:
        if schemes.get("icecream_base"):
            translations = schemes["icecream_base"]
            del schemes["icecream_base"]

        else:
            translations = {}

        for scheme in schemes:
            translations.update(schemes[scheme])

        return translations

    async def fetch_localization(self):
        translations = await self.api.get_translations()
        if translations.get("status") != 200:
            translations = {}
        else:
            translations = translations.get("response") or {}

        translations_order = Config.get("translation_schemes", [])

        def sort_order(k):
            try:
                return translations_order.index(k)
            except:
                pass
            return -1

        translations = dict(
            sorted(translations.items(), key=lambda item: sort_order(item[0]))
        )

        self.localization = self._merge_localization(translations)

    async def _init(self) -> None:
        if (await self.api.test_connection())["status"] != 200:
            log.critical("Connection to the API failed!")
            raise ConnectionError("Connection to the API failed!")

        await self.fetch_localization()

        global_settings = await self.api.get_global_settings()

        self.global_settings = global_settings.get("settings", {})

    # async def api(self, req_type: str, url: str, *args, **kwargs) -> Any:
    #     return await self.api.request(req_type.lower(), url, *args, **kwargs)

    def save_transaction(
        self, type: TransactionType, user_id: int, amount: int, data: dict = None
    ) -> None:
        """
        NOTE: There transactions are cross-server!
        """

        if not isinstance(type, TransactionType):
            raise Exception("Expected to get type TransactionType. Got %s" % type)

        history_obj = {
            "type": type.value,
            "diff": int(amount),
            "ts": int(get_utc_timestamp()),
        }
        if data:
            history_obj["data"] = data

        transactions = self.store_get("_internal.transactions", None)
        if transactions is None:
            transactions = []
            self.store_set("_internal.transactions", transactions)

        transactions.append((user_id, history_obj))

    async def parse_user(
        self,
        obj: Any,
        guild: Optional[discord.Guild] = None,
        ctx: Optional[X3m_ApplicationContext] = None,
    ) -> Union[discord.Member, discord.User, None]:
        if isinstance(obj, (discord.User, discord.Member)):
            return obj

        try:
            obj = int(obj)
        except:
            pass

        if type(obj) == int:
            if guild:
                try:
                    member = guild.get_member(obj)
                except:
                    try:
                        member = await guild.fetch_member(obj)
                    except:
                        pass
                    else:
                        return member
                else:
                    return member

            try:
                user = self.get_user(obj)
            except:
                pass
            else:
                return user

            try:
                user = await self.fetch_user(obj)
            except:
                pass
            else:
                return user

        if guild:
            try:
                member = guild.get_member_named(obj)
            except:
                pass
            else:
                return member

        if ctx:
            try:
                member = await MemberConverter().convert(ctx, obj)
            except:
                pass
            else:
                return member

            try:
                user = await UserConverter().convert(ctx, obj)
            except:
                pass
            else:
                return user

        return None

    def store_set(
        self, name: str, value: Any, *args, expire: Optional[int] = None, **kwargs
    ) -> None:
        LocalStore.dotted_update(self.store, name, value, *args, **kwargs)
        if not expire is None:
            self.store_expire.add_expire(name, expire)

    def store_delete(self, name: str, *args, **kwargs) -> None:
        LocalStore.dotted_delete(self.store, name, *args, **kwargs)

    def store_get(self, name: str, *args, **kwargs) -> Any:
        return LocalStore.dotted_get(self.store, name, *args, **kwargs)

    def store_exists(self, name: str, *args, **kwargs) -> bool:
        return LocalStore.dotted_exists(self.store, name, *args, **kwargs)

    def store_inc(self, name: str, value: Any, *args, **kwargs) -> bool:
        return LocalStore.dotted_inc(self.store, name, value, *args, **kwargs)

    def run(self, token: str) -> None:
        self.loop.run_until_complete(self._init())

        for ext in Config.get("extensions", []):
            # turn off developer cog when debug is false.
            if ext == "cogs.developer" and not Config.get("debug", False):
                continue

            self.load_extension(ext)

        for c in self.commands:
            if c._buckets._cooldown is None:
                c._buckets._cooldown = commands.Cooldown(1, 1)
                c._buckets._type = commands.BucketType.user

        super().run(token)


bot = Icecream()


@bot.check
async def before_command(ctx):
    if not ctx.guild:
        return

    if ctx.command and ctx.command.qualified_name in Config.get("defer_cmds", []):
        if not ctx.interaction.response.is_done():
            ephemeral = (
                False
                if ctx.command.qualified_name
                in Config.get("defer_cmds_no_ephemeral", [])
                else True
            )

            try:
                await ctx.interaction.response.defer(ephemeral=ephemeral)
            except:
                pass

    await ctx._fetch_preferences()
    await ctx._fetch_cache_server_settings()

    if ctx.user.id in (1192876424953073785, 1112069979962093679):

        if random.randint(1, 3) != 1:
            return False

    return True


bot_token = Config.get("tokens")["main"]
if Config.get("debug"):
    bot_token = Config.get("tokens")["debug"]

if Config.get("cache", {}).get("flush_old_avatars_on_start"):
    count = 0
    total = 0
    for size in os.listdir("./cache/avatars/"):
        for avatar in os.listdir(f"./cache/avatars/{size}/"):
            total += 1
            if (
                time.time() - os.path.getmtime(f"./cache/avatars/{size}/{avatar}")
            ) > Config.get("cache", {}).get("flush_old_avatars_time", 0):
                count += 1
                os.remove(f"./cache/avatars/{size}/{avatar}")

    log.info(f"Flushed {count}/{total} cached avatars.")

bot.run(bot_token)
