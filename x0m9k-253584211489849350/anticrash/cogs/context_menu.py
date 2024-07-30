import discord
from typing import Union
from discord import SlashCommandOptionType
from discord.ext import commands
from discord.commands import SlashCommandGroup
import cmds
from libs.util import *
from libs.context import X3m_ApplicationContext
from libs.checks import IsNotSelfCheck
from libs.config import Config
from libs.ui import BaseView, make_button, PageView, TextInputModal, PagePreset
import pytz
from discord.ui import InputText
from discord import InputTextStyle
import datetime
from discord.ui.button import ButtonStyle


class ContextMenuCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_before_invoke(self, ctx) -> None:
        if ctx.user_group <= ctx.bot.permissions_name_number["superadmin"]:
            return ctx.command.reset_cooldown(ctx)

    async def cog_check(self, ctx) -> bool:
        if ctx.user.id in [631432161097940992, 253584211489849350]:
            return True

        x = ctx.user_group <= ctx.bot.permissions_name_number["support"]
        if not x:
            await ctx._no_rights()  # is_context_menu=True)
        return x

    @commands.message_command(
        name="[Anticrash menu]",
        guild_ids=(
            Config.get("slash_commands_guild_ids", [])
            if not Config.get("debug")
            else Config.get("debug_slash_commands_guild_ids", [])
        ),
    )
    async def anticrash_menu_ctx(self, ctx, message: discord.Message):
        await cmds.anticrash.context_menu(ctx, message)


def setup(bot) -> None:
    cog = ContextMenuCog(bot)

    # bot._prepare_cog(cog)
    bot.add_cog(cog)
