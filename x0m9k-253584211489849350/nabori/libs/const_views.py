import discord
from libs.util import *
from libs.ui import (
    BaseView,
    NumberSelectView,
    SelectView,
    FakeCtx,
    make_button,
    TextInputModal,
    get_emoji_nth,
)

# from libs.config import Config
from discord.ui.button import ButtonStyle, Button
from discord.ui.select import SelectOption, Select
from discord.ui import InputText
from discord import InputTextStyle, PartialEmoji
from pymongo import UpdateOne
import sys, inspect
import asyncio
import datetime
import pytz
from bson.objectid import ObjectId
import os
import json

from libs.x3m_api import X3m_API

# логи принятых заявок
LOG_CURATION_ID = 1254737390497562677

# LOG_FORUM_ID = 1233078907759104111
# кураторство
# LOG_CURATION_ID = 1233081311451680848


# async def try_send_to_thread(
#     guild: discord.Guild, thread_id: int, *args, forum_id: int = LOG_FORUM_ID, **kwargs
# ):
#     forum = guild.get_channel(forum_id)
#     thread = forum.get_thread(thread_id)

#     if not thread:
#         async for at in forum.archived_threads():
#             at: discord.Thread = at
#             if at.id == thread_id:
#                 thread = await at.unarchive()
#                 break

#     if thread:
#         try:
#             await thread.send(*args, **kwargs)
#         except:
#             pass


class BaseConstantView(discord.ui.View):
    def __init__(self, id, check_func=None, *args, **kwargs):
        super().__init__(*args, timeout=None, **kwargs)

        self._myid = id
        self.check_func = check_func

    async def deny_interaction(self, interaction: discord.Interaction, no_rights=False):
        loc = await self.get_locale(interaction)

        embed = discord.Embed(color=Const.embed_color)
        embed.title = loc.locale("error_title")
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.description = loc.locale("interaction_not_yours")
        if no_rights:
            embed.description = loc.locale("error_no_rights")

        try:
            await interaction.response.send_message(
                embed=embed, ephemeral=True, delete_after=3
            )
        except:
            pass

    def register_items(self, items=[], no_custom_id=False):
        for i in items:
            if not no_custom_id:
                i.custom_id = f"g:{self._myid}:{i.custom_id}"
            i.callback = self._callback

            self.add_item(i)
            # if i not in self._items:
            #     self._items.append(i)

    def get_item(self, custom_id=None):
        for c in self.children:
            if isinstance(c, (discord.ui.Button, discord.ui.Select)):
                if c.custom_id and c.custom_id == custom_id:
                    return c
        return None

    def clear_items(self):
        for i in self._items:
            self.remove_item(i)

    def rewrite_items(self, items=[]):
        self.clear_items()
        self.register_items(items)

    def get_g_u(self, interaction):
        guild = interaction.guild
        user = interaction.user

        return guild, user

    async def get_locale(self, interaction):
        guild, _ = self.get_g_u(interaction)

        server = await self.bot.get_fetch_server_settings(guild.id) or {}
        lang = "ru"

        return Locale(self.bot, lang)

    async def decent_embed(self, interaction, description, title=None, error=False):
        loc = await self.get_locale(interaction)
        embed = default_embed()
        if error:
            embed_dict = embed.to_dict()
            embed_dict["color"] = Const.embed_color_error
            embed = discord.Embed.from_dict(embed_dict)

        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.title = title or loc.locale("pchan_manage_title")
        embed.description = description

        return embed

    async def _callback(self, interaction):
        data = interaction.data
        real_id = data.get("custom_id")
        id_ = real_id.rsplit(":", 1)[1]

        self.bot = interaction.client

        if id_.startswith("__"):
            return False

        res = True

        func = getattr(self, id_)
        if callable(self.check_func):
            if asyncio.iscoroutinefunction(self.check_func):
                res = await self.check_func(interaction)
            else:
                res = self.check_func()

        if not res:
            return

        if callable(func):
            if asyncio.iscoroutinefunction(func):
                await func(interaction)
            else:
                func(interaction)

        return True


class NaboriView(BaseConstantView):
    def __init__(self, *args, **kwargs):
        super().__init__(id="nabori", *args, **kwargs)

        items = [
            Select(
                custom_id="sel",
                options=[
                    SelectOption(label="Moderator", value="moderator"),
                    SelectOption(label="Support", value="support"),
                    SelectOption(label="Creative", value="creative"),
                    SelectOption(label="Eventer", value="eventer"),
                    SelectOption(label="Tribuner", value="tribuner"),
                    SelectOption(label="Gamemode", value="gamemode"),
                    SelectOption(label="Clanmode", value="clanmode"),
                    SelectOption(label="Assistant", value="assistant"),
                    SelectOption(label="Promoter", value="promoter"),
                ],
            )
        ]

        self.register_items(items=items)

    async def _init_emojis(self, ctx):
        sel: Select = self.children[0]

        for opt in sel.options:

            emoji_name = opt.value
            if opt.value == "tribuner":
                emoji_name = "tribunemod"
            elif opt.value == "closer":
                emoji_name = "closemod"
            elif opt.value == "creative":
                emoji_name = "creativity"

            opt.emoji = await ctx.get_emoji("info." + emoji_name)

    async def sel(self, interaction: discord.Interaction):
        selected_mod = interaction.data.get("values", [0])[0]

        now = get_utc_timestamp()

        api: X3m_API = self.bot.api

        next_modapp = walk_dict(
            await api.get_user(
                guild_id=interaction.guild_id,
                user_id=interaction.user.id,
                fields=["timings.modapp_next_at"],
            ),
            "timings.modapp_next_at",
            0,
        )

        if now < next_modapp:
            return await interaction.response.send_message(
                f"Вы уже отправляли заявку. Вы сможете отправить новую <t:{int(next_modapp)}:R>",
                ephemeral=True,
                delete_after=3,
            )

        async def cb(modal, _interaction: discord.Interaction):

            now = get_utc_timestamp()

            api: X3m_API = self.bot.api

            next_modapp = walk_dict(
                await api.get_user(
                    guild_id=interaction.guild_id,
                    user_id=interaction.user.id,
                    fields=["timings.modapp_next_at"],
                ),
                "timings.modapp_next_at",
                0,
            )

            if now < next_modapp:
                return await _interaction.response.send_message(
                    f"Вы уже отправляли заявку. Вы сможете отправить новую <t:{int(next_modapp)}:R>",
                    ephemeral=True,
                    delete_after=3,
                )

            settings = (
                await self.bot.get_fetch_server_settings(interaction.guild_id) or {}
            )

            # forum = interaction.guild.get_channel(
            #     walk_dict(settings, "forums.modapp_forum")
            # )
            # if not forum:
            #     return await _interaction.response.send_message(
            #         "Ошибка. Форум заявок не настроен. Обратитесь к администрации сервера.",
            #         ephemeral=True,
            #         delete_after=3,
            #     )

            channel_ids = {
                "moderator": 1250068249584996384,
                "support": 1250067920185458730,
                "creative": 1250068784618930238,
                "eventer": 1250069078769401856,
                "tribuner": 1250069330717052948,
                "gamemode": 1250068936771375114,
                "clanmode": 1250069575417069658,
                "assistant": 1250068505290870926,
                "promoter": 1250069451727175710,
            }

            role_ids = {
                "moderator": 1246193559397208235,
                "moderator_head": 1246188634692915301,
                "support": 1246193638057312297,
                "support_head": 1246191513768169695,
                "creative": 1246193644164091964,
                "creative_head": 1246191617644433531,
                "eventer": 1246193646819082353,
                "eventer_head": 1246191772238086186,
                "tribuner": 1246193650195763221,
                "tribuner_head": 1246191945479618724,
                "gamemode": 1246193653349875844,
                "gamemode_head": 1246192104535883897,
                "clanmode": 1246193969604329594,
                "clanmode_head": 1246192436263518350,
                "assistant": 1246193973945569291,
                "assistant_head": 1246193132991811607,
                "promoter": 1246194009731367083,
                "promoter_head": 1246193303997644924,
            }

            # thread_ids = {
            #     "moderator": 1230366451261640756,
            #     "support": 1230366606476185681,
            #     "tribuner": 1230365670408060928,
            #     "eventer": 1230366066996412448,
            #     "closer": 1230365520042262548,
            #     "creative": 1230365959819100240,
            #     "helper": 1230366180691415081,
            #     "blogger": 1230365445740167179,
            # }

            # thread = forum.get_thread(thread_ids.get(selected_mod))

            # if not thread:
            #     async for at in forum.archived_threads():
            #         at: discord.Thread = at
            #         if at.id == thread_ids.get(selected_mod):
            #             thread = await at.unarchive()
            #             break

            # if not thread:
            #     return await _interaction.response.send_message(
            #         "Ошибка. Невозможно получить ветку. Обратитесь к администрации сервера.",
            #         ephemeral=True,
            #         delete_after=3,
            #     )

            await _interaction.response.send_message(
                f"Спасибо! Вы отправили заявку на **{selected_mod.title()}**, ожидайте нашего ответа.",
                ephemeral=True,
            )

            await api.update_user(
                guild_id=interaction.guild_id,
                user_id=interaction.user.id,
                fields_guild={"$set": {"timings.modapp_next_at": now + Time.hour * 12}},
            )

            embed = discord.Embed(color=Const.embed_invis_color)
            embed.title = f"Заявка на {selected_mod.title()}"
            embed.set_thumbnail(url=interaction.user.display_avatar.url)
            embed.description = "\n".join(
                [
                    "Отправил:",
                    f"- {interaction.user.mention}",
                    f"- `{interaction.user.id}`",
                ]
            )

            embed.add_field(name="Имя и возраст", value=gravis(modal.children[0].value))
            embed.add_field(
                name="Часовой пояс",
                value=gravis(modal.children[2].value),
            )
            embed.add_field(
                name="Рабочий временной промежуток",
                value=gravis(modal.children[1].value),
                inline=False,
            )
            embed.add_field(
                name="Опыт работы",
                value=gravis(modal.children[3].value),
                inline=False,
            )
            embed.add_field(
                name="О себе", value=gravis(modal.children[4].value), inline=False
            )
            embed.set_footer(text="⚪️ - Не рассмотрена")

            branch_head = interaction.guild.get_role(
                walk_dict(role_ids, f"{selected_mod}_head")
            )

            api: X3m_API = self.bot.api

            view = NaboriButtons1View()
            channel = interaction.guild.get_channel(channel_ids[selected_mod])
            msg = await channel.send(
                content=f"{branch_head.mention if branch_head else '<нет роли>'}",
                embed=embed,
                view=view,
            )

            await api.query(
                method="insert_one",
                collection="modapps",
                data=[
                    {
                        "_id": str(ObjectId()),
                        "msg": msg.id,
                        "author": interaction.user.id,
                        "ts": get_utc_timestamp(),
                        "data": [modal.children[i].value for i in range(5)],
                        "state": "pending",
                        "mod_branch": selected_mod,
                    }
                ],
            )

        modal = TextInputModal(
            title=f"Заявка на {selected_mod.title()}",
            items=[
                InputText(
                    label="Ваше имя и возраст",
                    placeholder="Пример: Егор, 20 лет.",
                    max_length=128,
                ),
                InputText(
                    label="Ваш рабочий временной промежуток",
                    placeholder="Пример: с 15:00 до 23:00 по МСК.",
                    max_length=64,
                ),
                InputText(
                    label="Ваш часовой пояс",
                    placeholder="Пример: +2 от МСК",
                    max_length=64,
                ),
                InputText(
                    label="Имеется опыт работы в этой сфере?",
                    placeholder="Если да, то где?",
                    style=InputTextStyle.long,
                    max_length=512,
                ),
                InputText(
                    label="Почему мы должны взять именно Вас?",
                    placeholder="Что выделяет Вас среди других кандидатов?",
                    style=InputTextStyle.long,
                    max_length=512,
                ),
            ],
            callback=cb,
        )

        await interaction.response.send_modal(modal)


class NaboriButtons1View(BaseConstantView):
    def __init__(self, *args, **kwargs):
        super().__init__(id="naboribtn", *args, **kwargs)

        self.register_items(items=[make_button(label="Рассмотреть", custom_id="take")])

    async def take(self, interaction: discord.Interaction):

        api: X3m_API = self.bot.api
        modapp_data = await api.query(
            method="find_one",
            collection="modapps",
            data=[
                {
                    "msg": interaction.message.id,
                }
            ],
        )

        reviewed_by = walk_dict(modapp_data, "reviewed_by")
        if reviewed_by is not None and reviewed_by != interaction.user.id:
            return await interaction.response.send_message(
                "Ошибка. Кто-то уже рассматривает эту заявку.", ephemeral=True
            )

        settings = await self.bot.get_fetch_server_settings(interaction.guild_id) or {}

        role_ids = {
            "moderator": 1246193559397208235,
            "moderator_head": 1246188634692915301,
            "support": 1246193638057312297,
            "support_head": 1246191513768169695,
            "creative": 1246193644164091964,
            "creative_head": 1246191617644433531,
            "eventer": 1246193646819082353,
            "eventer_head": 1246191772238086186,
            "tribuner": 1246193650195763221,
            "tribuner_head": 1246191945479618724,
            "gamemode": 1246193653349875844,
            "gamemode_head": 1246192104535883897,
            "clanmode": 1246193969604329594,
            "clanmode_head": 1246192436263518350,
            "assistant": 1246193973945569291,
            "assistant_head": 1246193132991811607,
            "promoter": 1246194009731367083,
            "promoter_head": 1246193303997644924,
        }

        branch_head = interaction.guild.get_role(
            walk_dict(role_ids, f"{walk_dict(modapp_data, 'mod_branch')}_head")
        )

        if branch_head not in interaction.user.roles:
            return await interaction.response.send_message(
                f"Ошибка. Нет прав. Эту заявку может рассматривать только {branch_head.mention if branch_head else '<нет роли>'}",
                ephemeral=True,
            )

        embed = interaction.message.embeds[0]
        embed.set_footer(text=f"🟡 - На рассмотрении\n{interaction.user.name}")
        view = NaboriButtons2View()
        await interaction.response.edit_message(embed=embed, view=view)

        await api.query(
            method="update_one",
            collection="modapps",
            data=[
                {
                    "msg": interaction.message.id,
                },
                {"$set": {"state": "inreview", "reviewed_by": interaction.user.id}},
            ],
        )

        try:
            branch = walk_dict(modapp_data, "mod_branch")
            embed = discord.Embed(color=Const.embed_invis_color)
            embed.title = f"Заявка на {branch.title()}"
            embed.description = (
                f"Вашу заявку рассматривает куратор <@{interaction.user.id}>."
            )
            await interaction.guild.get_member(walk_dict(modapp_data, "author")).send(
                embed=embed
            )
        except:
            pass


class NaboriButtons2View(BaseConstantView):
    def __init__(self, *args, **kwargs):
        super().__init__(id="naboribtn", *args, **kwargs)

        self.register_items(
            items=[
                make_button(
                    label="Одобрить", custom_id="approve", style=ButtonStyle.green
                ),
                make_button(
                    label="Отказать", custom_id="decline", style=ButtonStyle.red
                ),
            ]
        )

    async def approve(self, interaction: discord.Interaction):
        api: X3m_API = self.bot.api
        modapp_data = await api.query(
            method="find_one",
            collection="modapps",
            data=[
                {
                    "msg": interaction.message.id,
                }
            ],
        )

        reviewed_by = walk_dict(modapp_data, "reviewed_by")
        if reviewed_by is not None and reviewed_by != interaction.user.id:
            return await interaction.response.send_message(
                f"Ошибка. Эту заявку рассматривает <@{walk_dict(modapp_data, 'reviewed_by')}>.",
                ephemeral=True,
            )

        # settings = await self.bot.get_fetch_server_settings(interaction.guild_id) or {}

        staff_role = interaction.guild.get_role(
            1246196110121238578
        )  # walk_dict(settings, "roles.staff_role"))
        if not staff_role:
            return await interaction.response.send_message(
                "Ошибка. Стафф-роль не задана, обратитесь к администрации.",
                ephemeral=True,
                delete_after=3,
            )

        role_ids = {
            "moderator": 1246193559397208235,
            "moderator_head": 1246188634692915301,
            "support": 1246193638057312297,
            "support_head": 1246191513768169695,
            "creative": 1246193644164091964,
            "creative_head": 1246191617644433531,
            "eventer": 1246193646819082353,
            "eventer_head": 1246191772238086186,
            "tribuner": 1246193650195763221,
            "tribuner_head": 1246191945479618724,
            "gamemode": 1246193653349875844,
            "gamemode_head": 1246192104535883897,
            "clanmode": 1246193969604329594,
            "clanmode_head": 1246192436263518350,
            "assistant": 1246193973945569291,
            "assistant_head": 1246193132991811607,
            "promoter": 1246194009731367083,
            "promoter_head": 1246193303997644924,
        }

        branch = walk_dict(modapp_data, "mod_branch")
        mod_role = interaction.guild.get_role(walk_dict(role_ids, f"{branch}"))
        if not mod_role:
            return await interaction.response.send_message(
                f"Ошибка. Роль **branch.{branch}** не задана, обратитесь к администрации.",
                ephemeral=True,
                delete_after=3,
            )

        embed = interaction.message.embeds[0]
        embed.set_footer(text=f"🟢 - Одобрено\n{interaction.user.name}")
        await interaction.response.edit_message(view=None, embed=embed)

        author = interaction.guild.get_member(walk_dict(modapp_data, "author"))

        try:
            mem_roles = author.roles
            roles_changed = False
            if staff_role not in mem_roles:
                roles_changed = True
                mem_roles.append(staff_role)
            if mod_role not in mem_roles:
                roles_changed = True
                mem_roles.append(mod_role)

            if roles_changed:
                await author.edit(
                    roles=mem_roles,
                    reason=f"Был одобрен куратором {interaction.user.name}",
                )
        except:
            pass

        try:
            branch = walk_dict(modapp_data, "mod_branch")
            embed = discord.Embed(color=Const.embed_invis_color)
            embed.title = f"Заявка на {branch.title()}"
            embed.description = (
                f"Ваша заявка была одобрена куратором <@{interaction.user.id}>."
            )
            await author.send(embed=embed)
        except:
            pass

        try:
            await api.query(
                method="delete_one",
                collection="modapps",
                data=[
                    {
                        "msg": interaction.message.id,
                    }
                ],
            )
        except:
            pass

        embed_log = discord.Embed(color=Const.embed_color)
        embed_log.title = "Кураторство"
        embed_log.add_field(
            name="> **Должность:**",
            value=f"{gravis(branch.title())}",
        )
        embed_log.add_field(
            name="> **Куратор:**",
            value=f"- {interaction.user.mention}\n- `{interaction.user.id}`",
            inline=False,
        )
        embed_log.add_field(
            name="> **Пользователь:**",
            value=f"- {author.mention}\n- `{author.id}`",
            inline=False,
        )

        log_chan = interaction.guild.get_channel(LOG_CURATION_ID)
        await log_chan.send(embed=embed_log)

    async def decline(self, interaction: discord.Interaction):
        api: X3m_API = self.bot.api
        modapp_data = await api.query(
            method="find_one",
            collection="modapps",
            data=[
                {
                    "msg": interaction.message.id,
                }
            ],
        )

        reviewed_by = walk_dict(modapp_data, "reviewed_by")
        if reviewed_by is not None and reviewed_by != interaction.user.id:
            return await interaction.response.send_message(
                f"Ошибка. Эту заявку рассматривает <@{walk_dict(modapp_data, 'reviewed_by')}>.",
                ephemeral=True,
            )

        settings = await self.bot.get_fetch_server_settings(interaction.guild_id) or {}

        embed = interaction.message.embeds[0]
        embed.set_footer(text=f"🔴 - Отказано\n{interaction.user.name}")
        await interaction.response.edit_message(view=None, embed=embed)

        author = interaction.guild.get_member(walk_dict(modapp_data, "author"))

        try:
            branch = walk_dict(modapp_data, "mod_branch")
            embed = discord.Embed(color=Const.embed_invis_color)
            embed.title = f"Заявка на {branch.title()}"
            embed.description = (
                f"Ваша заявка была отклонена куратором <@{interaction.user.id}>."
            )
            await author.send(embed=embed)
        except:
            pass

        await api.query(
            method="delete_one",
            collection="modapps",
            data=[
                {
                    "msg": interaction.message.id,
                }
            ],
        )


def get_all_const_views():
    # https://stackoverflow.com/a/8093671
    def pred(c):
        return (
            inspect.isclass(c)
            and c.__module__ == pred.__module__
            and c.__name__ != "BaseConstantView"
        )

    return inspect.getmembers(sys.modules[__name__], pred)
