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
from libs.config import Config
from discord.ui.button import ButtonStyle, Button
from discord.ui.select import SelectOption, Select
from discord.ui import InputText
from discord import InputTextStyle
from pymongo import UpdateOne
import sys, inspect
import asyncio
import datetime
import pytz
from bson.objectid import ObjectId
import os
import json

from libs.x3m_api import X3m_API


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
        lang = server.get("language", Config.get("default_language"))

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


class ACRestoreRolesView(BaseConstantView):
    def __init__(self):
        super().__init__("acrestore")

        self.register_items(
            items=[
                make_button(
                    label="Посмотреть роли",
                    custom_id="roles",
                    style=ButtonStyle.secondary,
                ),
                make_button(
                    label="Отменить наказание",
                    custom_id="restore",
                    style=ButtonStyle.primary,
                ),
            ]
        )

    async def roles(self, interaction: discord.Interaction):

        await interaction.response.defer()
        user_id = int(interaction.message.embeds[0].footer.text)

        api: X3m_API = self.bot.api

        saved_roles = walk_dict(
            await api.get_user(
                user_id=user_id,
                guild_id=interaction.guild_id,
                fields=["anticrash.viol_saved"],
            ),
            "anticrash.viol_saved",
            [],
        )

        to_add = []
        for rid in saved_roles:
            role = interaction.guild.get_role(rid)
            if role and role not in to_add:
                to_add.append(role)

        if not to_add:
            return await interaction.followup.send(
                "Этому пользователю нечего восстанавливать.",
                ephemeral=True,
                delete_after=3,
            )

        embed = discord.Embed(color=Const.embed_color)
        embed.title = "Восстанавливаемые роли"
        embed.description = (
            f"Этому пользователю можно восстановить **{len(to_add)}** ролей:\n"
            + " ".join([f"<@&{r.id}>" for r in to_add])
        )[:4096]

        await interaction.followup.send(
            embed=embed,
            ephemeral=True,
        )

    async def restore(self, interaction: discord.Interaction):
        await interaction.response.defer()
        settings = await self.bot.get_fetch_server_settings(interaction.guild_id)

        access_roles = [1253146308248735825]
        has_access = False

        if interaction.user.id in []:
            has_access = True

        for rid in access_roles:
            if interaction.guild.get_role(rid) in interaction.user.roles:
                has_access = True
                break

        if not has_access:
            return await interaction.followup.send(
                "У Вас недостаточно прав.", ephemeral=True
            )

        user_id = int(interaction.message.embeds[0].footer.text)

        api: X3m_API = self.bot.api

        saved_roles = walk_dict(
            await api.get_user(
                user_id=user_id,
                guild_id=interaction.guild_id,
                fields=["anticrash.viol_saved"],
            ),
            "anticrash.viol_saved",
            [],
        )

        to_add = []
        for rid in saved_roles:
            role = interaction.guild.get_role(rid)
            if role and role not in to_add:
                to_add.append(role)

        if not to_add:
            return await interaction.followup.send(
                "Этому пользователю нечего восстанавливать.",
                ephemeral=True,
                delete_after=3,
            )

        mem = interaction.guild.get_member(user_id)
        if not mem:
            return await interaction.followup.send(
                "Пользователь вышел с сервера.",
                ephemeral=True,
                delete_after=3,
            )

        try:
            await mem.add_roles(
                *to_add, reason=f"Отмена наказания {interaction.user.name}"
            )
        except Exception as err:
            return await interaction.followup.send(
                f"Ошибка: {err}"[:2048],
                ephemeral=True,
                delete_after=3,
            )

        ban_role = interaction.guild.get_role(
            walk_dict(settings, "anticrash.anticrash_ban", 0)
        )
        if ban_role:
            try:
                await mem.remove_roles(
                    ban_role, reason=f"Отмена наказания {interaction.user.name}"
                )
            except:
                pass

        if mem.timed_out:
            try:
                await mem.remove_timeout(
                    reason=f"Отмена наказания {interaction.user.name}"
                )
            except:
                pass

        embed = discord.Embed(color=Const.embed_color)
        embed.title = "Отменить наказание"
        embed.description = (
            f"Вы восстановили **{len(to_add)}** ролей <@{user_id}>:\n"
            + (" ".join(f"<@&{r.id}>" for r in to_add))[:4000]
        )

        await interaction.edit_original_response(view=None)

        await interaction.followup.send(
            embed=embed,
            ephemeral=True,
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
