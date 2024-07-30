import discord
import copy
from typing import Optional, Any, Union
from libs.util import *
from libs.checks import BaseCheck, Checker
from libs.store import LocalStore
from discord.ext.commands import (
    EmojiConverter,
    MemberConverter,
    UserConverter,
    RoleConverter,
)
from libs.ui import ConfirmView, BaseView
from datetime import datetime
import pytz
from libs.transactions import TransactionType
from libs.awards import AwardType


class X3m_ApplicationContext(discord.ApplicationContext):
    """
    Helpful methods here, locale and etc.
    There will be helpful methods such as bot.locale, which automatically
    will receive self.guild(language) and thus will simplify usage:
    ctx.locale(code) instead of bot.locale(code, language)
    """

    def __init__(self, bot, interaction):
        super().__init__(bot, interaction)

        # will be set at bot.check, see main.py at the end.
        # @bot.check
        # async def before_command(...)...
        self.server_settings = {}
        self.user_preferences = {}

        self._fetched_user_preferences = False

        self.bot = bot
        self.udata = {}
        self.interaction = interaction
        self.guild = self.interaction.guild
        self.guild_id = self.guild.id

        # hack
        self._ctx_respond = super().respond
        # self.respond = self._respond

    async def _fetch_preferences(self):
        if self._fetched_user_preferences:
            return

        self._fetched_user_preferences = True

        db_preferences = (
            await self.bot.api.get_user(
                0,
                self.user.id,
                fields=["preferences"],
                get_preferences=True,
                walk_to_guild=False,
            )
        ) or {}

        self.user_preferences = db_preferences.get("preferences", {})

    def _prepare_settings(self, fetched_settings: dict) -> None:
        settings = copy.deepcopy(self.bot.default_server_settings)

        merge_dicts(settings, fetched_settings)

        self.server_settings = settings

        # quick acess
        # there will be always language, currency and other default settings
        # specified at main.py: Icecream().default_server_settings
        self.server_language = settings["language"]
        self.server_currency = self.get_emoji("currency")
        self.server_timezone = settings["timezone"]

        self.user_language = self.user_preferences.get("language")
        self.user_timezone = self.user_preferences.get("timezone")

        self.language = self.user_language or self.server_language
        self.timezone = self.user_timezone or self.server_timezone

    async def fetch_user(
        self,
        fields: Optional[list] = [],
        user_id: Optional[int] = None,
        get_preferences: bool = False,
        walk_to_guild: bool = True,
    ) -> dict:
        if get_preferences and not fields:
            fields = ["_id"]

        response = await self.bot.api.get_user(
            self.guild_id,
            user_id or self.author.id,
            fields,
            get_preferences=get_preferences,
            walk_to_guild=walk_to_guild,
        )

        if user_id is None:
            response_safe = response or {}
            merge_dicts(self.udata, response_safe)

        return response

    async def user_has_award(self, award: AwardType, user_id: int = None) -> bool:
        user_data = await self.fetch_user(user_id=user_id, fields=["profile.awards"])

        for profile_award in walk_dict(user_data, "profile.awards", []):
            if profile_award.get("type") == award.value:
                return True

        return False

    async def update_server(self, **kwargs) -> None:
        await self.bot.api.update_server(self.guild_id, **kwargs)

        updated_settings = False
        for kw in kwargs:
            for k in kwargs[kw]:
                if k.startswith("settings."):
                    updated_settings = True
                    break

        if updated_settings:
            # we get updated settings from line above self.bot.api.update_server,
            # that method unvalidates settings.
            # unvalidate settings, because we changed them.
            settings = self.bot.get_cached_server_settings(self.guild_id)
            self._prepare_settings(settings)
        return

    def make_date_from_utc(self, timestamp: Union[float, int]) -> str:
        return (
            datetime.fromtimestamp(timestamp)
            .astimezone(pytz.timezone(self.timezone))
            .strftime(Const.dateformat_no_s)
        )

    def locale(self, _code_, *args, **kwargs) -> str:
        return self.bot.locale(self.language, _code_, *args, **kwargs)

    def make_time(self, time: int, *args, **kwargs) -> str:
        return make_time(self.bot, self.language, time, *args, **kwargs)

    def parse_time(self, time: str, *args, **kwargs) -> int:
        return parse_time(self.bot, self.language, time, *args, **kwargs)

    def get_price(self, name: str, default: Optional[Any] = 99999) -> Optional[int]:
        return self.walk_server(f"prices.{name}", default=default)

    def get_comission_perc(self, member: discord.Member) -> Union[int, float]:
        comission_group = "user"
        premium_role_id = walk_dict(self.server_settings, "roles.premium_status", 0)
        booster_role_id = walk_dict(self.server_settings, "roles.booster_status", 0)

        if booster_role_id:
            booster_role = self.guild.get_role(booster_role_id)
            if booster_role in member.roles:
                comission_group = "booster"

        if premium_role_id:
            premium_role = self.guild.get_role(premium_role_id)
            if premium_role in member.roles:
                comission_group = "premium"

        comission_perc = walk_dict(
            self.server_settings, "numbers.comission_" + comission_group, 1
        )

        return comission_perc

    async def _post_init(self) -> None:
        """
        This method creates additional useful information such as self.user_group.
        """

        comission_group = "user"
        premium_role_id = walk_dict(self.server_settings, "roles.premium_status", 0)
        booster_role_id = walk_dict(self.server_settings, "roles.booster_status", 0)

        if booster_role_id:
            booster_role = self.guild.get_role(booster_role_id)
            if booster_role in self.author.roles:
                comission_group = "booster"

        if premium_role_id:
            premium_role = self.guild.get_role(premium_role_id)
            if premium_role in self.author.roles:
                comission_group = "premium"

        # -- \
        self.comission_group = comission_group

        # comission_perc - is a comission, e.g. number * 0.95 means 5% comission.
        self.comission_perc = walk_dict(
            self.server_settings, "numbers.comission_" + comission_group, 1
        )
        # -- /

        if str(self.author.id) in self.bot.global_settings.get("dev_ids", []):
            user_group = self.bot.permissions_name_number["dev"]
        else:
            user_group = self.server_settings.get("perm_groups", {}).get(
                str(self.author.id), None
            )

        if user_group == None:
            support_role = self.guild.get_role(
                walk_dict(self.server_settings, "roles.permissions_support", 0)
            )
            moderator_role = self.guild.get_role(
                walk_dict(self.server_settings, "roles.permissions_moderator", 0)
            )

            if isinstance(self.author, discord.Member):
                if support_role in self.author.roles:
                    user_group = self.bot.permissions_name_number.get("support")
                if moderator_role in self.author.roles:
                    user_group = self.bot.permissions_name_number.get("moderator")

        if user_group == None:
            user_group = self.bot.permissions_name_number["user"]

        if (
            self.author.id == self.guild.owner_id
            # this will ensure that we don't rewrite superior rights with server_owner
            # e.g. when server_owner is a developer.
            and user_group > self.bot.permissions_name_number["server_owner"]
        ):
            self.user_group = self.bot.permissions_name_number["server_owner"]
        else:
            self.user_group = user_group

    async def _fetch_cache_server_settings(self) -> None:
        """
        This method ensures that we have cached server settings and will
        fetch them if we don't.
        Also this method calls self._post_init()!
        """

        settings = self.bot.get_cached_server_settings(self.guild_id)
        if not settings:
            settings = await self.bot.cache_server_settings(self.guild_id)

        self._prepare_settings(settings)

        await self._post_init()

    def save_transaction(
        self,
        type: TransactionType,
        amount: int,
        data: dict = None,
        user_id: int = None,
        **kwargs,
    ) -> None:
        """
        NOTE: There transactions are cross-server!
        """

        self.bot.save_transaction(
            type, user_id or self.user.id, amount, data=data, **kwargs
        )

    async def _respond(
        self,
        *args,
        leave_prev_message=False,
        prev_delete_view=False,
        prev_force_leave_embed=False,
        **kwargs,
    ):
        cmd_name = None

        for arg in args:
            if isinstance(arg, BaseView):
                cmd_name = arg.unique or f"{self.interaction.user.id}xview"
                break

        for kw in kwargs:
            if isinstance(kwargs[kw], BaseView):
                cmd_name = kwargs[kw].unique or f"{self.interaction.user.id}xview"
                break

        interacts = self.bot.store_get(f"_internal.vinteracts.{cmd_name}")
        is_interacts_none = False
        if interacts is None:
            is_interacts_none = True
            interacts = []
            self.bot.store_set(f"_internal.vinteracts.{cmd_name}", interacts)

        if (not leave_prev_message or prev_delete_view) and cmd_name:
            if not is_interacts_none:
                for interact in list(interacts):
                    if not leave_prev_message:
                        try:
                            await interact.delete_original_response()
                        except:
                            # delete regular messages (sent with ephemeral=False)
                            try:
                                await interact.delete()
                            except:
                                pass
                    if prev_delete_view:
                        to_edit = {"view": None}
                        if prev_force_leave_embed:
                            e = self.default_embed()
                            e.title = self.locale("menu_not_active_title")
                            e.description = self.locale(
                                "menu_not_active_desc", author=self.user.mention
                            )
                            to_edit["embed"] = e

                        try:
                            await interact.edit_original_response(**to_edit)
                        except:
                            try:
                                await interact.edit(**to_edit)
                            except:
                                pass
                    interacts.remove(interact)

        interaction = await self._ctx_respond(*args, **kwargs)
        if cmd_name:
            interacts.append(interaction)

        return interaction

    def default_embed(self) -> discord.Embed:
        embed = discord.Embed(color=Const.embed_color)
        embed.set_thumbnail(url=self.author.display_avatar.url)

        # embed.set_footer(text=f"/{self.command}")

        return embed

    def error_embed(self) -> None:
        embed = discord.Embed(color=Const.embed_color_error)
        embed.title = self.locale("error_title")
        embed.set_thumbnail(url=self.author.display_avatar.url)

        return embed

    async def error(self, description, ephemeral=True) -> discord.Embed:
        embed = self.error_embed()
        embed.description = description

        await self.respond(embed=embed, ephemeral=ephemeral)

    def get_guild_emoji(
        self, id, default=Const.default_emoji
    ) -> Union[discord.Emoji, discord.PartialEmoji, Any]:
        return self.bot.get_emoji(int(id)) or default

    async def rembed(
        self, description: str, error: bool = False, ephemeral: bool = True
    ) -> None:
        e = self.default_embed()
        if error:
            e = self.error_embed()
        e.description = description

        await self.respond(embed=e, ephemeral=ephemeral)

    def walk_server(self, x, default=None):
        return walk_dict(self.server_settings, x, default=default)

    async def _cooldown(
        self,
        seconds_left: int,
        message: str = "You're on cooldown! {cooldown_s}s left.",
    ) -> None:
        try:
            await self.respond(
                content=message.format(cd_s=seconds_left), ephemeral=True
            )
        except discord.HTTPException:
            pass

    async def _no_rights(self) -> None:
        embed = self.error_embed()
        embed.description = self.locale("error_cmd_no_rights")

        await self.respond(embed=embed, ephemeral=True)

    async def update_user(
        self,
        user_id: Optional[int] = None,
        fields: Optional[dict] = {},
        fields_guild: Optional[dict] = {},
        upsert: bool = True,
    ) -> int:
        return await self.bot.api.update_user(
            self.guild_id,
            user_id or self.author.id,
            fields,
            fields_guild,
            upsert=upsert,
        )

    async def checker(self, *checks: list[BaseCheck]) -> bool:
        return await Checker(self).check(*checks)

    async def user_has_enough_balance(
        self, amount: int, user_id: int = None, auto_respond: bool = True
    ) -> bool:
        user_id = user_id or self.author.id

        res = (
            await self.fetch_user(
                fields=["balance"], user_id=user_id, get_preferences=False
            )
        ) or {}

        balance = res.get("balance", 0)

        x = balance >= amount

        if auto_respond:
            if not x:
                await self.error(
                    self.locale(
                        "error_you_have_no_enough_balance",
                        delta=mfloor((amount - balance) / 1),
                        currency=self.get_emoji("currency"),
                    ),
                    ephemeral=True,
                )

                return False
            return True

        return x

    def get_emoji(
        self,
        emoji_fields: str,
        default: Optional[Any] = Const.default_emoji,
        return_id=False,
    ) -> Optional[Any]:
        emoji_id = self.walk_server(f"emojis.{emoji_fields}", default=False)
        if return_id:
            return emoji_id
        if emoji_id is False:
            return Const.default_emoji
        return self.get_guild_emoji(emoji_id, default=default)

    async def user_add_balance(
        self, amount: int, user_id: int = None, balance_field: str = "balance"
    ) -> int:
        return await self.bot.api.update_user(
            self.guild_id,
            user_id or self.author.id,
            None,  # fields
            {"inc": {balance_field: int(amount)}},  # fields_guild
        )

    async def send_confirm_and_wait(
        self,
        description: Optional[str],
        title: Optional[str] = None,
        timeout: Optional[int] = 30,
        style=None,
        confirm_style=discord.ButtonStyle.primary,
        cancel_style=discord.ButtonStyle.secondary,
        confirm_emoji=None,
        cancel_emoji=None,
        confirm_label=None,
        cancel_label=None,
        default_response=False,
        ephemeral=False,
        return_msg=False,
        disable_on_callback=True,
        defer_interaction=False,
        leave_prev_message=False,
    ) -> Union[bool, tuple]:
        description = description or self.locale("confirm_title")

        embed = self.default_embed()
        embed.title = title or self.locale("confirm_title")
        embed.description = description

        view = ConfirmView(
            self,
            cancel_style=cancel_style,
            confirm_style=confirm_style,
            confirm_emoji=confirm_emoji,
            confirm_label=confirm_label,
            cancel_label=cancel_label,
            cancel_emoji=cancel_emoji,
            timeout=timeout,
            disable_on_callback=disable_on_callback,
            defer_interaction=defer_interaction,
        )

        msg = await self.respond(
            embed=embed,
            view=view,
            ephemeral=ephemeral,
            leave_prev_message=leave_prev_message,
        )

        timedout = await view.wait()

        if timedout:
            if default_response:
                embed.set_footer(text=self.locale("confirm_footer_timeout"))
                await msg.edit_original_response(embed=embed, view=None)

            if return_msg:
                return None, msg
            return None

        interaction = view.last_interaction
        if not interaction:
            if return_msg:
                return None, msg
            return None

        btn = interaction.data

        confirm = True

        if btn["custom_id"] == "1":
            confirm = False

        if default_response:
            embed.set_footer(
                text=self.locale(
                    "confirm_footer_" + ("accept" if confirm else "decline")
                )
            )

            await msg.edit_original_response(embed=embed, delete_after=5)

        if return_msg:
            return confirm, msg

        return confirm

    async def to_user(self, obj: Any) -> Union[None, discord.Member, discord.User]:
        return await self.bot.parse_user(obj, guild=self.guild, ctx=self)

    def store_set(
        self,
        name: str,
        value: Any,
        guild_id: Optional[int] = None,
        expire: Optional[int] = None,
    ) -> None:
        guild_id = guild_id or self.guild_id

        self.bot.store_set(f"{guild_id}.{name}", value)
        if not expire is None:
            self.bot.store_expire.add_expire(f"{guild_id}.{name}", expire)

    def store_delete(self, name: str, guild_id: Optional[int] = None) -> None:
        guild_id = guild_id or self.guild_id

        self.bot.store_delete(f"{guild_id}.{name}")

    def store_get(self, name: str, guild_id: Optional[int] = None) -> Any:
        guild_id = guild_id or self.guild_id

        return self.bot.store_get(f"{guild_id}.{name}")

    def store_exists(self, name: str, guild_id: Optional[int] = None) -> bool:
        guild_id = guild_id or self.guild_id

        return self.bot.store_exists(f"{guild_id}.{name}")

    def store_inc(self, name: str, value: Any, guild_id: Optional[int] = None) -> None:
        guild_id = guild_id or self.guild_id

        return self.bot.store_inc(f"{guild_id}.{name}", value)


class X3m_ApplicationContextEmpty(discord.ApplicationContext):
    """
    Used when a user executes command in DMs (no guild)
    """

    pass
