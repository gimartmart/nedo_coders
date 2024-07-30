import discord
import asyncio
from libs.util import *
from discord.ui.button import Button, ButtonStyle
from discord.ui.select import Select, SelectOption
from discord.ui import InputText, Modal
from enum import Enum
from bson.int64 import Int64
from libs.config import Config


def make_button(
    style=ButtonStyle.primary,
    label="",
    custom_id="-",
    emoji=None,
    disabled=False,
    row=None,
    *args,
    **kwargs,
):
    return Button(
        style=style,
        label=label,
        custom_id=custom_id if not kwargs.get("url") else None,
        emoji=emoji,
        disabled=disabled,
        row=row,
        *args,
        **kwargs,
    )


def get_emoji_nth(i, emojis=["🔸", "🔹"]):
    return emojis[i % len(emojis)]


def filter_not_safe_roles(roles=[]):
    result = []
    for r in roles:
        if not get_restricted_role_perms(r, only_check=True):
            result.append(r)

    return result


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
        "manage_messages",
        "manage_permissions",
        "manage_roles",
        "manage_threads",
        "manage_webhooks",
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

    return found


class PagePreset(Enum):
    list = 0
    big_list = 1


class ChannelType(Enum):
    text = 0
    voice = 1
    thread = 2
    category = 3


class FakeCtx:
    def __init__(self, bot, guild, user):
        self.bot = bot
        self.guild = guild
        self.author = user
        self.default_embed = default_embed

    def store_exists(self, *args, **kwargs):
        return self.store_check(*args, **kwargs)

    def store_check(self, *args, user=None, special=False, **kwargs):
        if special:
            f = args[0]
        else:
            if user:
                if isinstance(user, (discord.User, discord.Member)):
                    user = user.id
                f = f"{self.guild.id}.{user}.{args[0]}"
            else:
                f = f"{self.guild.id}.{self.author.id}.{args[0]}"

        return self.bot.store_exists(f, *args[1:], **kwargs)

    def store_get(self, *args, user=None, special=False, **kwargs):
        if special:
            f = args[0]
        else:
            if user:
                if isinstance(user, (discord.User, discord.Member)):
                    user = user.id
                f = f"{self.guild.id}.{user}.{args[0]}"
            else:
                f = f"{self.guild.id}.{self.author.id}.{args[0]}"

        return self.bot.store_get(f, *args[1:], **kwargs)

    def store_delete(self, *args, user=None, special=False, **kwargs):
        if special:
            f = args[0]
        else:
            if user:
                if isinstance(user, (discord.User, discord.Member)):
                    user = user.id
                f = f"{self.guild.id}.{user}.{args[0]}"
            else:
                f = f"{self.guild.id}.{self.author.id}.{args[0]}"

        return self.bot.store_delete(f, *args[1:], **kwargs)

    def store_set(self, *args, user=None, special=False, **kwargs):
        if special:
            f = args[0]
        else:
            if user:
                if isinstance(user, (discord.User, discord.Member)):
                    user = user.id
                f = f"{self.guild.id}.{user}.{args[0]}"
            else:
                f = f"{self.guild.id}.{self.author.id}.{args[0]}"

        return self.bot.store_set(f, *args[1:], **kwargs)

    async def init_locale(self, server=None):
        server = await self.bot.get_fetch_server_settings(self.guild.id) or {}
        self.locale = Locale(
            self.bot, server.get("language", Config.get("default_language", "en-US"))
        ).locale


class PagePresetButtons:
    @classmethod
    def list(cls, ctx=None):
        return [
            make_button(
                emoji="◀️" if not ctx else ctx.get_emoji("nav_left"), custom_id="1"
            ),
            make_button(
                style=ButtonStyle.secondary,
                disabled=True,
                custom_id="page",
                label=f"1/?",
            ),
            make_button(
                emoji="▶️" if not ctx else ctx.get_emoji("nav_right"), custom_id="2"
            ),
        ]

    @classmethod
    def big_list(cls, ctx=None):
        return [
            make_button(
                emoji="⏪" if not ctx else ctx.get_emoji("nav_left_max"),
                custom_id="0",
                disabled=True,
            ),
            make_button(
                emoji="◀️" if not ctx else ctx.get_emoji("nav_left"), custom_id="1"
            ),
            make_button(
                style=ButtonStyle.secondary,
                disabled=True,
                custom_id="page",
                label=f"1/?",
            ),
            make_button(
                emoji="▶️" if not ctx else ctx.get_emoji("nav_right"), custom_id="2"
            ),
            make_button(
                emoji="⏩" if not ctx else ctx.get_emoji("nav_right_max"), custom_id="3"
            ),
        ]


class BaseView(discord.ui.View):
    def __init__(
        self,
        ctx,
        *args,
        allowed_users=[],
        callback=None,
        check=None,
        disable_on_timeout=True,
        disable_on_timeout_ds=False,
        disable_on_stop=False,
        delete_view_on_disable=True,
        custom_actions={},
        items=[],
        timeout=300,
        not_unique=False,
        unique: str = "",
        delete_on_stop=False,
        # rate_limit=1,
        **kwargs,
    ):
        unique = f"{ctx.author.id}x" + unique

        if "." in unique:
            raise Exception("dots can't be used in unique.")

        super().__init__(
            *args, timeout=timeout, disable_on_timeout=disable_on_timeout_ds, **kwargs
        )

        if allowed_users:
            if allowed_users == "all":
                self.allowed_users = "all"
            else:
                self.allowed_users = self._validate_users(allowed_users)
        else:
            self.allowed_users = (ctx.author.id,)
        self._check = check
        self._user_callback = callback
        self._callback = self._default_callback
        self.disable_on_timeout = disable_on_timeout
        self.disable_on_stop = disable_on_stop
        self.delete_view_on_disable = delete_view_on_disable
        self.last_message = None
        self._items = []
        self.last_interaction = None
        self.last_interaction_ts = 0
        self.custom_actions = custom_actions
        self.unique = unique
        self.not_unique = not_unique
        self.ctx = ctx
        self.force_stopped = False
        self.delete_on_stop = delete_on_stop
        # self.rate_limit = rate_limit

        self.__stop = self.stop

        def custom_stop():
            self.__stop()

            if self.delete_on_stop:
                asyncio.run_coroutine_threadsafe(
                    self.disable_all(message=self.last_message, delete_message=True),
                    ctx.bot.loop,
                )

            else:
                if self.disable_on_stop:
                    asyncio.run_coroutine_threadsafe(
                        self.disable_all(message=self.last_message), ctx.bot.loop
                    )

            if self.unique:
                self.ctx.store_delete(f"_views.{self.unique}")

        self.stop = custom_stop

        if items:
            self.register_items(items)

        # outdated, probably doesn't work
        if unique and not not_unique:
            if ctx.store_exists(f"_views.{unique}"):
                ctx.store_get(f"_views.{unique}")()  # calling stop func at view
            # do not set timeout(expire) here because user can shift timeout
            # with every button press or etc.
            ctx.store_set(f"_views.{unique}", self.force_stop)

    @property
    def check(self):
        return self._check

    @property
    def callback(self):
        return self._callback

    # called e.g. when view has unique id -> old one will delete and new one
    # will be created. Never use it outside unique logic.
    def force_stop(self):
        self.force_stopped = True
        self.stop()

    def set_msg(self, msg):
        self.last_message = msg

    async def _default_callback(self, interaction):
        data = interaction.data
        id = data.get("custom_id", "")

        custom = self.custom_actions.get(id)

        if callable(custom):
            if asyncio.iscoroutinefunction(custom):
                await custom(self, interaction)
            else:
                custom(self, interaction)

            return

        if callable(self._user_callback):
            if asyncio.iscoroutinefunction(self._user_callback):
                await self._user_callback(self, interaction)
            else:
                self._user_callback(self, interaction)
            return

        # when no custom_actions and no callback are set.

        try:
            await interaction.response.send_message(
                content="Unknown interaction. Please report to admins.", ephemeral=True
            )
        except:
            pass

    def set_callback(self, cb):
        self._user_callback = cb

    def _validate_users(self, users):
        new = []

        for u in users:
            if type(u) not in (int, Int64):
                new.append(u.id)
            else:
                new.append(u)

        return new

    def set_allowed_users(self, users):
        if users == "all":
            self.allowed_users = "all"
        else:
            self.allowed_users = self._validate_users(users)

    def register_items(self, items=[]):
        for i in items:
            i.callback = self._callback

            if i.custom_id != None:
                if i.custom_id.startswith(self.unique):
                    i.custom_id = self.unique + i.custom_id.split(self.unique)[1]
                else:
                    i.custom_id = self.unique + i.custom_id

                if len(i.custom_id) > 100:
                    log.debug(f"View item exceeded 100 chars limit: {i.custom_id}")
                    continue

            self.add_item(i)
            if i not in self._items:
                self._items.append(i)

    def get_item(self, custom_id=None):
        for c in self.children:
            if isinstance(c, (discord.ui.Button, discord.ui.Select)):
                if c.custom_id and c.custom_id.split(self.unique)[1] == custom_id:
                    return c
        return None

    def clear_items(self):
        for i in self._items:
            self.remove_item(i)

        self._items = []

    def rewrite_items(self, items=[]):
        self.clear_items()
        self.register_items(items)

    async def interaction_check(self, interaction):
        self.last_message = interaction.message

        now = get_utc_timestamp()

        # if self.rate_limit:
        #     if now - self.last_interaction_ts < self.rate_limit:
        #         await self._deny_interaction_rate_limited(
        #             interaction, now - self.last_interaction_ts
        #         )
        #         return False

        self.last_interaction_ts = now

        user_check_func = getattr(self, "_check", None)

        user_check = True

        cid = interaction.data.get("custom_id")

        if cid != None and cid.startswith(self.unique):
            interaction.data["custom_id"] = interaction.data["custom_id"].split(
                self.unique
            )[1]

        if callable(user_check_func):
            if asyncio.iscoroutinefunction(user_check_func):
                user_check = await user_check_func(self, interaction)
            else:
                user_check = user_check_func(self, interaction)

        if not user_check:
            await self._deny_interaction(interaction)
            return False

        if self.allowed_users and interaction.user:
            if (
                self.allowed_users != "all"
                and interaction.user.id not in self.allowed_users
            ):
                await self._deny_interaction(interaction)
                return False

        self.last_interaction = interaction

        return True

    async def disable_all(self, interaction=None, message=None, delete_message=False):
        for c in self.children:
            if isinstance(c, (discord.ui.Button, discord.ui.Select)):
                c.disabled = True

        interaction = interaction or self.last_interaction
        message = message or self.last_message

        view = self
        if self.delete_view_on_disable:
            view = None

        if interaction:
            try:
                await interaction.response.edit_message(
                    view=view, delete_after=0 if delete_message else None
                )
            except:
                try:
                    await interaction.edit_original_response(
                        view=view, delete_after=0 if delete_message else None
                    )
                except:
                    pass

        elif message:
            try:
                await message.edit(
                    view=view, delete_after=0 if delete_message else None
                )
            except:
                pass

    async def _deny_interaction(self, interaction):
        """When you are not allowed to interact"""

        lang = (
            await interaction.client.api.get_user(
                0,
                interaction.user.id,
                fields=["preferences"],
                get_preferences=True,
                walk_to_guild=False,
            )
            or {}
        )
        lang = walk_dict(lang, "preferences.language")

        if not lang:
            lang = (
                await interaction.client.get_fetch_server_settings(interaction.guild.id)
            ).get("language", Config.get("default_language", "en-US"))

        loc = Locale(interaction.client, lang)

        embed = discord.Embed(color=Const.embed_color)
        embed.title = loc.locale("error_title")
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.description = loc.locale("interaction_not_yours")

        await interaction.response.send_message(
            embed=embed,
            delete_after=2,
            ephemeral=True,
        )

    async def _deny_interaction_rate_limited(self, interaction, wait):
        """When you are too fast"""

        lang = (
            await interaction.client.api.get_user(
                0,
                interaction.user.id,
                fields=["preferences"],
                get_preferences=True,
                walk_to_guild=False,
            )
            or {}
        )
        lang = walk_dict(lang, "preferences.language")

        if not lang:
            lang = (
                await interaction.client.get_fetch_server_settings(interaction.guild.id)
            ).get("language", Config.get("default_language", "en-US"))

        loc = Locale(interaction.client, lang)

        await interaction.response.send_message(
            content=loc.locale("interaction_rate_limited", wait_s=round(wait, 1)),
            delete_after=4,
            ephemeral=True,
        )

    async def on_timeout(self, *args, **kwargs):
        if self.unique:
            self.ctx.store_delete(f"_views.{self.unique}")

        if self.disable_on_timeout:
            await self.disable_all(message=self.last_message)


class SelectView(BaseView):
    def __init__(
        self,
        ctx,
        *args,
        select=None,
        can_select_page=True,
        options=None,
        custom_items=[],
        opts_per_page=25,
        opts_gen_func=None,
        add_deselect=True,
        single_choice=False,
        set_default_emojis=True,
        **kwargs,
    ):
        callback = None
        if kwargs.get("callback", EmptyElement) != EmptyElement:
            callback = kwargs.pop("callback")

        super().__init__(ctx, *args, callback=self._default_callback, **kwargs)

        self.options = options
        self.opts_per_page = opts_per_page
        self.scroll = 0
        self.opts_gen_func = opts_gen_func
        self.single_choice = single_choice
        self.can_select_page = can_select_page
        self.add_deselect = add_deselect
        self.custom_items = custom_items
        self.set_default_emojis = set_default_emojis
        if not self.single_choice:
            self.add_deselect = add_deselect
        self.last_select = None

        if self.options:
            self.max_scrolls = mfloor(len(self.options) / opts_per_page)
            self._generate_options()
        else:
            if select:
                select.custom_id = "select"  # will be updated in .register_items
                select.add_option(
                    emoji="〰️", value="deselect", label=ctx.locale("select_deselect")
                )
                self.register_items((select,))

        self.last_interaction = None
        self.cb = callback

    def set_options(self, options):
        self.options = options
        self.max_scrolls = mfloor(len(options) / self.opts_per_page)
        self._generate_options()

    def _generate_options(self, scroll=0):
        opp = self.opts_per_page
        s = scroll

        if callable(self.opts_gen_func):
            options = []

            for i, opt in enumerate(self.options[s * opp : s * opp + opp]):
                gen = self.opts_gen_func(opt)

                if self.set_default_emojis and not gen.emoji:
                    gen.emoji = discord.PartialEmoji.from_str(get_emoji_nth(i))

                options.append(gen)

        else:
            options = [opt for opt in self.options[s * opp : s * opp + opp]]

        up_btn = make_button(emoji="⬆️", custom_id="up")

        down_btn = make_button(emoji="⬇️", custom_id="down")

        page_disabled = not (self.can_select_page and self.max_scrolls > 1)

        page = make_button(
            label=f"{scroll+1}/{max(self.max_scrolls, 1)}",
            disabled=page_disabled,
            style=ButtonStyle.gray,
            custom_id=f"page",
        )

        if scroll == 0:
            up_btn.disabled = True
        elif scroll == (self.max_scrolls - 1):
            down_btn.disabled = True

        if self.max_scrolls == 1:
            up_btn.disabled = True
            down_btn.disabled = True

        if not options:
            options = [
                SelectOption(
                    emoji="〰️", label=self.ctx.locale("select_empty"), value="_$empty"
                )
            ]

        items = [
            Select(
                custom_id="select",
                options=options,
            ),
            up_btn,
            page,
            down_btn,
        ]

        if self.add_deselect:
            items.append(
                make_button(
                    label=self.ctx.locale("select_deselect"),
                    emoji="〰️",
                    custom_id="deselect",
                )
            )

        items.extend(self.custom_items)

        self.rewrite_items(items)

    async def _page_select_cb(self, oview, interaction):
        interaction.data["custom_id"] = "select_scroll"
        # HACK:
        interaction.data["selected"] = oview.get_selected()[0]

        await self._default_callback(interaction)

    async def _default_callback(self, interaction):
        data = interaction.data
        id = data.get("custom_id", "")
        scroll = self.scroll

        if id == "select":
            self.last_interaction = interaction

            selected = interaction.data.get("values", [])
            if selected:
                if selected[0] == "_$empty":
                    return

            # calling user-defined callback
            if callable(self.cb):
                if asyncio.iscoroutinefunction(self.cb):
                    await self.cb(self, interaction)
                else:
                    self.cb(self, interaction)

            if self.single_choice:
                self.stop()
            return

        elif id == "deselect":
            pass  # will update items anyway

        elif id == "select_scroll":
            scroll = int(interaction.data["selected"]) - 1

        elif id == "page":
            options = [
                SelectOption(
                    label=self.ctx.locale("page_num", num=str(i + 1)), value=str(i + 1)
                )
                for i in range(self.max_scrolls)
            ]

            choose_page_embed = self.ctx.default_embed()
            choose_page_embed.title = self.ctx.locale("select_page_title")
            choose_page_view = SelectView(
                self.ctx,
                options=options,
                callback=self._page_select_cb,
                unique="selectview:selectpage",
                add_deselect=False,
                single_choice=True,
            )

            await interaction.response.edit_message(
                embed=choose_page_embed, view=choose_page_view
            )

            return

        elif id == "up":
            scroll -= 1
            if scroll < 0:
                return

        elif id == "down":
            scroll += 1
            if scroll > (self.max_scrolls - 1):
                return
        else:
            custom = self.custom_actions.get(id)

            if callable(custom):
                if asyncio.iscoroutinefunction(custom):
                    await custom(self, interaction)
                else:
                    custom(self, interaction)

            return

        self.scroll = scroll

        self._generate_options(scroll)

        await interaction.response.edit_message(view=self)

    def get_selected(self):
        return self.last_interaction.data.get("values", [])


class TextInputModal(Modal):
    def __init__(
        self,
        title="Title",
        items=[],
        callback=None,
        custom_id=None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, title=title, custom_id=custom_id, **kwargs)

        self._user_callback = callback

        if items:
            self.add_items(items)

    def add_items(self, items):
        for i in items:
            self.add_item(i)

    def clear_items(self):
        for i in self.children[:]:
            self.remove_item(i)

    def rewrite_items(self, items):
        self.clear_items()
        self.set_items(items)

    async def callback(self, interaction):
        if callable(self._user_callback):
            if asyncio.iscoroutinefunction(self._user_callback):
                await self._user_callback(self, interaction)
            else:
                self._user_callback(self, interaction)


class EmojiSelectView(BaseView):
    def __init__(
        self,
        ctx,
        *args,
        title=None,
        description=None,
        select_cb=None,
        emojis=[],
        emoji_check=None,
        items_per_page=25,
        can_select_page=True,
        add_remove_opt=False,
        add_deselect=False,
        **kwargs,
    ):
        super().__init__(ctx, *args, callback=self._page_callback, **kwargs)

        assert self.ctx.guild, "No guild present."

        self.select_cb = select_cb
        self.title = title
        self.description = description
        self.last_interaction = None
        self.type = type
        self.emoji_check = emoji_check
        self.items_per_page = items_per_page
        self.add_remove_opt = add_remove_opt
        self.add_deselect = add_deselect
        self.can_select_page = can_select_page

        if not emojis:
            emojis = ctx.bot.emojis

        self.emojis = emojis
        if not emojis:
            emojis = [discord.PartialEmoji.from_str(Const.default_emoji)]
        self._check_emojis()

        self.scroll = 0
        self.max_scrolls = mfloor(len(self.emojis) / self.items_per_page)

    def _check_emojis(self):
        if not callable(self.emoji_check):
            return

        self.emojis = [c for c in self.emojis if self.emoji_check(c)]

    async def _page_select_cb(self, oview, interaction):
        interaction.data["custom_id"] = "select_scroll"
        # HACK:
        interaction.data["selected"] = oview.get_selected()[0]

        await self._page_callback(None, interaction)

    async def _page_callback(self, _, interaction):
        data = interaction.data
        id = data.get("custom_id", "")

        scroll = self.scroll

        if id == "up":
            scroll -= 1
            if scroll < 0:
                return

        elif id == "down":
            scroll += 1
            if scroll > (self.max_scrolls - 1):
                return

        elif id == "deselect":
            pass

        elif id == "page":
            options = [
                SelectOption(
                    label=self.ctx.locale("page_num", num=str(i + 1)), value=str(i + 1)
                )
                for i in range(self.max_scrolls)
            ]

            choose_page_embed = self.ctx.default_embed()
            choose_page_embed.title = self.ctx.locale("select_page_title")
            choose_page_view = SelectView(
                self.ctx,
                options=options,
                callback=self._page_select_cb,
                unique="emojiview:selectpage",
                add_deselect=False,
                single_choice=True,
            )

            await interaction.response.edit_message(
                embed=choose_page_embed, view=choose_page_view
            )

            return

        elif id == "select_scroll":
            scroll = int(interaction.data["selected"]) - 1

        elif id == "select":
            self.last_interaction = interaction

            if callable(self.select_cb):
                if asyncio.iscoroutinefunction(self.select_cb):
                    await self.select_cb(self, interaction)
                else:
                    self.select_cb(self, interaction)
            else:
                e = self.ctx.default_embed()
                if self.title:
                    e.title = self.title
                else:
                    e.title = self.ctx.locale("emojiselect_title")

                emoji_id = data.get("values", (0,))[0]

                emoji = self.ctx.get_guild_emoji(int(emoji_id))

                if self.description:
                    e.description = self.description
                else:
                    e.description = self.ctx.locale("emojiselect_success", emoji=emoji)

                await interaction.response.edit_message(embed=e, view=None)

                self.stop()

            return

        else:
            return

        e = await self.render(scroll)

        await interaction.response.edit_message(embed=e, view=self)

    async def render(self, scroll=0):
        i = self.items_per_page
        emojis = self.emojis[scroll * i : scroll * i + i]

        if len(self.emojis) == 0:
            embed = self.ctx.default_embed()
            embed.description = self.ctx.locale("emojiselect_no_emojis")
            return embed

        if scroll > (self.max_scrolls - 1):
            return

        self.scroll = scroll

        up = make_button(emoji="⬆️", custom_id="up")

        page_disabled = not (self.can_select_page and self.max_scrolls > 1)

        page = make_button(
            label=f"{scroll+1}/{self.max_scrolls}",
            style=ButtonStyle.secondary,
            disabled=page_disabled,
            custom_id="page",
        )

        down = make_button(emoji="⬇️", custom_id="down")

        options = [
            SelectOption(label=e.name, value=str(e.id), emoji=e)
            for i, e in enumerate(emojis, start=1)
        ]

        if self.add_remove_opt:
            options.insert_at(
                0,
                SelectOption(
                    label=self.ctx.locale("btn_remove"), emoji="❌", value="remove"
                ),
            )

        select = Select(
            options=options,
            custom_id="select",
        )

        if scroll == 0:
            up.disabled = True
        elif scroll == (self.max_scrolls - 1):
            down.disabled = True

        if self.max_scrolls == 1:
            up.disabled = True
            down.disabled = True

        items = [select, up, page, down]

        if self.add_deselect:
            items.append(
                make_button(
                    label=self.ctx.locale("select_deselect"),
                    emoji="〰️",
                    custom_id="deselect",
                )
            )

        self.rewrite_items(items)

        embed = self.ctx.default_embed()

        embed.title = self.title or self.ctx.locale("emojiselect_title")
        embed.description = self.description or self.ctx.locale("emojis_default_desc")

        return embed

    def get_selected(self):
        return self.last_interaction.data.get("values", [])


class ChannelSelectView(BaseView):
    def __init__(
        self,
        ctx,
        type,
        *args,
        title=None,
        description=None,
        select_cb=None,
        channels=[],
        channel_check=None,
        add_deselect=True,
        items_per_page=25,
        single_choice=True,
        **kwargs,
    ):
        super().__init__(ctx, *args, callback=self._page_callback, **kwargs)

        assert self.ctx.guild, "No guild present."

        self.select_cb = select_cb
        self.title = title
        self.description = description
        self.last_interaction = None
        self.type = type
        self.channel_check = channel_check
        self.items_per_page = items_per_page
        self.single_choice = single_choice
        self.add_deselect = add_deselect

        if not channels:
            if type == ChannelType.text:
                channels = self.ctx.guild.text_channels
            elif type == ChannelType.voice:
                channels = self.ctx.guild.voice_channels
            elif type == ChannelType.thread:
                channels = self.ctx.guild.threads
            elif type == ChannelType.category:
                channels = self.ctx.guild.categories

        self.channels = channels
        self._check_channels()

        self.scroll = 0
        self.max_scrolls = mfloor(len(self.channels) / self.items_per_page)

    def _check_channels(self):
        if not callable(self.channel_check):
            return

        self.channels = [c for c in self.channels if self.channel_check(c)]

    async def _page_callback(self, _, interaction):
        data = interaction.data
        id = data.get("custom_id", "")

        scroll = self.scroll

        if id == "up":
            scroll -= 1
            if scroll < 0:
                return

        elif id == "down":
            scroll += 1
            if scroll > (self.max_scrolls - 1):
                return

        elif id == "deselect":
            pass

        elif id == "select":
            self.last_interaction = interaction

            if callable(self.select_cb):
                if asyncio.iscoroutinefunction(self.select_cb):
                    await self.select_cb(self, interaction)
                else:
                    self.select_cb(self, interaction)
            else:
                e = self.ctx.default_embed()
                if self.title:
                    e.title = self.title
                else:
                    e.title = self.ctx.locale("chanselect_title")

                chan_id = data.get("values", (0,))[0]

                if self.description:
                    e.description = self.description
                else:
                    e.description = self.ctx.locale(
                        "chanselect_success", chan_id=chan_id
                    )

                await interaction.response.edit_message(embed=e, view=None)

            if self.single_choice:
                self.stop()

            return

        else:
            return

        e = await self.render(scroll)

        await interaction.response.edit_message(embed=e, view=self)

    async def render(self, scroll=0):
        i = self.items_per_page
        channels = self.channels[scroll * i : scroll * i + i]

        if len(self.channels) == 0:
            embed = self.ctx.default_embed()
            embed.description = self.ctx.locale("chanselect_no_channels")
            return embed

        if scroll > (self.max_scrolls - 1):
            return

        self.scroll = scroll

        up = make_button(emoji="⬆️", custom_id="up")

        page = make_button(
            label=f"{scroll+1}/{self.max_scrolls}",
            style=ButtonStyle.secondary,
            disabled=True,
        )

        down = make_button(emoji="⬇️", custom_id="down")

        select = Select(
            options=[
                SelectOption(label=r.name, value=str(r.id), emoji=get_emoji_nth(i))
                for i, r in enumerate(channels, start=1)
            ],
            custom_id="select",
        )

        if scroll == 0:
            up.disabled = True
        elif scroll == (self.max_scrolls - 1):
            down.disabled = True

        if self.max_scrolls == 1:
            up.disabled = True
            down.disabled = True

        items = [select, up, page, down]

        if self.add_deselect:
            items.append(
                make_button(
                    label=self.ctx.locale("select_deselect"),
                    emoji="〰️",
                    custom_id="deselect",
                )
            )

        self.rewrite_items(items)

        embed = self.ctx.default_embed()
        embed.title = self.title or self.ctx.locale("chanselect_title")
        embed.description = self.description

        return embed

    def get_selected(self):
        return self.last_interaction.data.get("values", [])


class NumberSelectView(BaseView):
    def __init__(
        self, ctx, *args, items=None, callback=None, min=None, max=None, **kwargs
    ):
        self._cb = None

        if kwargs.get("callback", EmptyElement) != EmptyElement:
            self._cb = kwargs.pop("callback")

        if min == None:
            min = Const.minint_ds

        self.min = min

        if max == None:
            max = Const.maxint_ds

        self.max = max

        if not items:
            items = [
                make_button(emoji=e, custom_id=str(i), row=(i - 1) // 3)
                for i, e in enumerate(
                    ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"],
                    start=1,
                )
            ]

            items.extend(
                [
                    make_button(
                        emoji="⬅️", custom_id="back", row=3, style=ButtonStyle.gray
                    ),
                    make_button(emoji="0️⃣", custom_id="0", row=3),
                    make_button(
                        emoji="🆗", custom_id="confirm", row=3, style=ButtonStyle.green
                    ),
                ]
            )

        super().__init__(
            ctx, *args, items=items, callback=self._select_callback, **kwargs
        )

        self.text = ""

    def render(self):
        embed = self.ctx.default_embed()
        embed.title = self.ctx.locale("numberselect_title")
        embed.description = f"`{self.text}`" if self.text else "`<>`"

        min, max = self.min, self.max

        if max == Const.maxint_ds and min != Const.minint_ds:
            embed.set_footer(text=self.ctx.locale("numberselect_footer_min", min=min))

        elif min == Const.minint_ds and max != Const.maxint_ds:
            embed.set_footer(text=self.ctx.locale("numberselect_footer_max", max=max))
        else:
            embed.set_footer(
                text=self.ctx.locale("numberselect_footer", min=min, max=max)
            )

        return embed

    def get_number(self):
        if not self.text:
            return

        return int(self.text)

    async def _select_callback(self, _, interaction):
        data = interaction.data

        id = data.get("custom_id", "")

        if id == "back":
            if not self.text:
                try:
                    await interaction.response.defer()
                except:
                    pass
                return

            self.text = self.text[:-1]

        elif id == "confirm":
            if not self.text:
                return

            if int(self.text) < self.min:
                await interaction.response.edit_message(
                    content=gravis(
                        self.ctx.locale("numberselect_footer_min", min=self.min)
                    )
                )
                return

            elif int(self.text) > self.max:
                await interaction.response.edit_message(
                    content=gravis(
                        self.ctx.locale("numberselect_footer_max", max=self.max)
                    )
                )
                return

            self.stop()

            if callable(self._cb):
                if asyncio.iscoroutinefunction(self._cb):
                    await self._cb(self, interaction)
                else:
                    self._cb(self, interaction)

            else:
                await self.disable_all(interaction=interaction)

            if not interaction.response.is_done():
                try:
                    await interaction.response.defer()
                except:
                    pass

            return

        else:
            self.text += id

            if self.text.startswith("0") and len(self.text) > 1:
                self.text = self.text[1:]

        await interaction.response.edit_message(embed=self.render(), content=None)


class ConfirmView(BaseView):
    def __init__(
        self,
        ctx,
        *args,
        confirm_style=discord.ButtonStyle.primary,
        cancel_style=discord.ButtonStyle.secondary,
        cancel_emoji=None,
        confirm_emoji=None,
        confirm_label=None,
        cancel_label=None,
        disable_on_callback=True,
        defer_interaction=False,
        **kwargs,
    ):
        cb = self.callback_

        if kwargs.get("callback", EmptyElement) != EmptyElement:
            cb = kwargs.pop("callback")

        super().__init__(
            ctx,
            *args,
            callback=cb,
            **kwargs,
        )
        self.value = None
        self.disable_on_callback = disable_on_callback
        self.defer_interaction = defer_interaction

        if confirm_label is None:
            confirm_label = ctx.locale("btn_confirm")
        if cancel_label is None:
            cancel_label = ctx.locale("btn_cancel")

        btn_confirm = make_button(
            style=confirm_style, label=confirm_label, custom_id="0", emoji=confirm_emoji
        )

        btn_cancel = make_button(
            style=cancel_style, label=cancel_label, custom_id="1", emoji=cancel_emoji
        )

        self.register_items((btn_confirm, btn_cancel))

    async def callback_(self, _, interaction):
        data = interaction.data
        id = data["custom_id"]

        if self.defer_interaction:
            await interaction.response.defer()

        # if id == "1":
        #     await interaction.response.send_message("Cancelling", ephemeral=True)

        if self.disable_on_callback:
            await self.disable_all(interaction)
        self.stop()


class DynamicPage:
    def __init__(self, render_func):
        self.render_func = render_func

    async def render(self, ctx):
        return await self.render_func(ctx)


class PageView(BaseView):
    def __init__(
        self,
        ctx,
        *args,
        preset=None,
        loop=True,
        pages=[],
        custom_items=[],
        custom_pages={},
        can_select_page=True,
        allow_custom_actions=False,
        **kwargs,
    ):
        callback = None
        if kwargs.get("callback", EmptyElement) != EmptyElement:
            callback = kwargs.pop("callback")

        self.cb = callback
        self.pages = pages
        self.custom_pages = custom_pages
        self.custom_page = None
        self.custom_items = custom_items
        self.can_select_page = can_select_page
        self.page = 0
        self.pages_temp = {}
        self.preset = preset
        self.loop = loop
        self.ctx = ctx
        self.allow_custom_actions = allow_custom_actions

        super().__init__(ctx, *args, callback=self._page_callback, **kwargs)
        self._init_buttons()

    async def _page_callback(self, inst, interaction):
        if len(self.pages) == 0:
            try:
                await interaction.response.defer()
            except:
                pass
            return

        item = interaction.data
        id = item.get("custom_id", "")

        if self.allow_custom_actions:
            if self.custom_actions.get(id):
                cb = self.custom_actions[id]

                if callable(cb):
                    if asyncio.iscoroutinefunction(cb):
                        await cb(self, interaction)
                    else:
                        cb(self, interaction)

                return

        page = self.page

        if id == "0":
            page = 0

        elif id == "1":
            page = self.page - 1
            if page < 0:
                if self.loop:
                    page = len(self.pages) - 1
                else:
                    return

        elif id == "2":
            page = self.page + 1
            if page >= len(self.pages):
                if self.loop:
                    page = 0
                else:
                    return

        elif id == "3":
            page = len(self.pages) - 1

        elif id == "select" and self.can_select_page:
            page = int(inst.get_selected()[0]) - 1

        elif id == "page":
            options = [SelectOption(label=str(i + 1)) for i in range(len(self.pages))]

            choose_page_embed = self.ctx.default_embed()
            choose_page_embed.title = self.ctx.locale("select_page_title")
            choose_page_view = SelectView(
                self.ctx,
                options=options,
                callback=self._page_callback,
                unique="pageview:selectpage",
            )

            await interaction.response.edit_message(
                embed=choose_page_embed, view=choose_page_view
            )

            return

        else:
            if self.custom_page == id:
                self.custom_page = None

                # return back to normal pages
            else:
                if self.custom_pages.get(id):
                    new_emb = await self.render_page(id, custom=True)
                    await interaction.response.edit_message(embed=new_emb, view=self)

                    if callable(self.cb):
                        if asyncio.iscoroutinefunction(self.cb):
                            await self.cb(self, interaction)
                        else:
                            self.cb(self, interaction)
                    return

        new_emb = await self.render_page(page)
        self._update_btns(page)

        await interaction.response.edit_message(embed=new_emb, view=self)

        # calling user-defined callback
        if callable(self.cb):
            if asyncio.iscoroutinefunction(self.cb):
                await self.cb(self, interaction)
            else:
                self.cb(self, interaction)

    def _update_btns(self, page):
        p = self.get_item("page")
        if p:
            p.label = f"{page+1}/{max(len(self.pages), 1)}"

        fast_back = self.get_item("0")
        fast_forward = self.get_item("3")

        back = self.get_item("1")
        forward = self.get_item("2")

        page_btn = self.get_item("page")

        if page_btn and self.can_select_page:
            page_btn.disabled = False
            if len(self.pages) == 1:
                page_btn.disabled = True

        for e in (fast_back, fast_forward, back, forward):
            if e is not None:
                e.disabled = False

        if page == 0:
            if fast_back:
                fast_back.disabled = True
            if self.loop == False or len(self.pages) <= 1:
                if back:
                    back.disabled = True

        if page == len(self.pages) - 1 or len(self.pages) == 0:
            if fast_forward:
                fast_forward.disabled = True
            if self.loop == False or len(self.pages) <= 1:
                if forward:
                    forward.disabled = True

    def _init_buttons(self):
        if self.preset is None:
            items = self.custom_items

        if self.preset is PagePreset.list:
            items = (
                make_button(emoji=self.ctx.get_emoji("nav_left", "◀️"), custom_id="1"),
                make_button(
                    style=ButtonStyle.secondary, disabled=True, custom_id="page"
                ),
                make_button(emoji=self.ctx.get_emoji("nav_right", "▶️"), custom_id="2"),
            )

        elif self.preset is PagePreset.big_list:
            items = (
                # This is disabled because we start on the first page anyway.
                make_button(
                    emoji=self.ctx.get_emoji("nav_left_max", "⏪"),
                    custom_id="0",
                    disabled=True,
                ),  # <-
                make_button(emoji=self.ctx.get_emoji("nav_left", "◀️"), custom_id="1"),
                make_button(
                    style=ButtonStyle.secondary, disabled=True, custom_id="page"
                ),
                make_button(emoji=self.ctx.get_emoji("nav_right", "▶️"), custom_id="2"),
                make_button(
                    emoji=self.ctx.get_emoji("nav_right_max", "⏩"), custom_id="3"
                ),
            )

        self.register_items(items)
        self._update_btns(0)

    def set_pages(self, pages):
        self.pages = pages
        self.page = 0

        self._update_btns(0)

    async def render_page(self, page=0, custom=False):
        if len(self.pages) == 0:
            embed = default_embed()
            embed.description = self.ctx.locale("empty_page")

            return embed

        if not custom:
            self.page = page
            embed = self.pages[page]  # static page

            if isinstance(embed, DynamicPage):
                embed = await self.pages[page].render(self.ctx)
        else:
            self.custom_page = page
            embed = self.custom_pages[page]

            if isinstance(embed, DynamicPage):
                embed = await self.custom_pages[page].render(self.ctx)

        # page_btn = self.get_item(custom_id="page")
        # if page_btn and not custom:
        #     page_btn.label = f"{page+1}/{len(self.pages)}"

        return embed


class RoleSelectView(BaseView):
    class FakeRole:
        def __init__(self, id):
            self.id = id
            self.name = f"<deleted:{id}>"
            self.permissions = discord.Permissions()

    def __init__(
        self,
        *args,
        role_check=None,
        title=None,
        description=None,
        select_cb=None,
        roles=[],
        single_choice=True,
        **kwargs,
    ):
        super().__init__(*args, callback=self._page_callback, **kwargs)

        assert self.ctx.guild, "No guild present."

        self.select_cb = select_cb
        self.title = title
        self.description = description
        self.last_interaction = None
        self.role_check = role_check
        self.single_choice = single_choice

        if not roles:
            # skip 'everyone' role and reverse the role list
            roles = self.ctx.guild.roles[1:][::-1]
        else:
            checked_roles = []
            for r in roles:
                role = self.ctx.guild.get_role(r)
                if not role:
                    checked_roles.append(self.FakeRole(r))
                else:
                    checked_roles.append(role)

            roles = checked_roles

        self.roles = filter_not_safe_roles(roles)
        self._check_roles()

        self.scroll = 0
        self.max_scrolls = mfloor(len(self.roles) / 25)

    async def _page_callback(self, _, interaction):
        data = interaction.data
        id = data.get("custom_id", "")

        scroll = self.scroll

        if id == "up":
            scroll -= 1
            if scroll < 0:
                return

        elif id == "down":
            scroll += 1
            if scroll > (self.max_scrolls - 1):
                return

        elif id == "select":
            self.last_interaction = interaction

            if callable(self.select_cb):
                if asyncio.iscoroutinefunction(self.select_cb):
                    await self.select_cb(self, interaction)
                else:
                    self.select_cb(self, interaction)
            else:
                e = default_embed()
                if self.title:
                    e.title = self.title
                else:
                    e.title = self.ctx.locale("roleselect_title")

                role_id = data.get("values", (0,))[0]

                if self.description:
                    e.description = self.description
                else:
                    e.description = self.ctx.locale(
                        "roleselect_success", role_id=role_id
                    )

                await interaction.response.edit_message(embed=e, view=None)

            if self.single_choice:
                self.stop()

            return

        else:
            return

        e = await self.render(scroll)

        await interaction.response.edit_message(embed=e, view=self)

    async def render(self, scroll=0):
        roles = self.roles[scroll * 25 : scroll * 25 + 25]

        if scroll > (self.max_scrolls - 1):
            return

        self.scroll = scroll

        up = make_button(emoji="⬆️", custom_id="up")

        page = make_button(
            label=f"{scroll+1}/{self.max_scrolls}",
            style=ButtonStyle.secondary,
            disabled=True,
        )

        down = make_button(emoji="⬇️", custom_id="down")

        select = Select(
            options=[
                SelectOption(label=r.name, value=str(r.id), emoji=get_emoji_nth(i))
                for i, r in enumerate(roles, start=1)
            ],
            custom_id="select",
        )

        if scroll == 0:
            up.disabled = True
        elif scroll == (self.max_scrolls - 1):
            down.disabled = True

        if self.max_scrolls == 1:
            up.disabled = True
            down.disabled = True

        items = [select, up, page, down]

        self.rewrite_items(items)

        embed = self.ctx.default_embed()
        embed.title = "⚙️"

        return embed

    def _check_roles(self):
        if not callable(self.role_check):
            return

        self.roles = [r for r in self.roles if self.role_check(r)]

    def get_selected(self):
        return self.last_interaction.data.get("values", [])
