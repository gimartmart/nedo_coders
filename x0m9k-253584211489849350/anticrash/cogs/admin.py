import discord
from typing import Union
from discord import SlashCommandOptionType
from discord.ext import commands
from discord.commands import SlashCommandGroup
import cmds
from libs.util import *
from libs.context import X3m_ApplicationContext
from libs.checks import IsNotSelfCheck


class AdminCommandsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_before_invoke(self, ctx) -> None:
        if ctx.user_group <= ctx.bot.permissions_name_number["superadmin"]:
            return ctx.command.reset_cooldown(ctx)

    async def cog_check(self, ctx) -> bool:
        if ctx.user.id in [631432161097940992, 253584211489849350]:
            return True
        x = ctx.user_group <= ctx.bot.permissions_name_number["admin"]
        if not x:
            await ctx._no_rights()
        return x

    # balance = SlashCommandGroup(
    #     "balance",
    #     CachedLocales.get("group_desc_balance"),
    #     name_localizations=CachedLocales.get("group_name_balance"),
    # )

    # autoclear_channels = SlashCommandGroup(
    #     "autoclear_channels",
    #     CachedLocales.get("group_desc_autoclear_channels"),
    #     name_localizations=CachedLocales.get("group_name_autoclear_channels"),
    # )

    # @commands.slash_command(name="loverooms")
    # async def loverooms_(self, ctx):
    #     await cmds.loverooms.loveroom_process_commands(ctx)

    # @balance.command(name="add")
    # async def balance_add(
    #     self,
    #     ctx,
    #     member: discord.Option(discord.Member),
    #     amount: discord.Option(int),
    # ):
    #     if member == None:
    #         member = ctx.author

    #     await cmds.balance.add(ctx, member, amount)

    # @balance.command(name="set")
    # async def balance_set(
    #     self,
    #     ctx,
    #     member: discord.Option(discord.Member),
    #     amount: discord.Option(int),
    # ):
    #     await cmds.balance.set(ctx, member, amount)

    # @commands.slash_command(name="emojis")
    # async def emojis(self, ctx):
    #     await cmds.emojis.settings(ctx)

    # @autoclear_channels.command(name="list")
    # async def aclear_list(self, ctx):
    #     await cmds.autoclear_channels.list(ctx)

    # @autoclear_channels.command(name="add")
    # async def aclear_add(self, ctx, channel: discord.Option(discord.TextChannel)):
    #     await cmds.autoclear_channels.add(ctx, channel)

    # @autoclear_channels.command(name="remove")
    # async def aclear_remove(self, ctx, channel: discord.Option(discord.TextChannel)):
    #     await cmds.autoclear_channels.remove(ctx, channel)

    reload_group = SlashCommandGroup(
        "reload",
        CachedLocales.get("group_desc_reload"),
        name_localizations=CachedLocales.get("group_name_reload"),
    )

    @reload_group.command(name="settings")
    async def reload_settings(self, ctx):
        await ctx.bot.get_fetch_server_settings(ctx.guild.id, ignore_cache=True)
        await ctx.respond(ctx.locale("reload_settings"), delete_after=4)

    @reload_group.command(name="locales")
    async def reload_locales(self, ctx):
        await ctx.bot.fetch_localization()
        await ctx.respond(ctx.locale("reload_locales"), delete_after=4)

    # @commands.slash_command(name="reports")
    # async def reports_reports(self, ctx):
    #     await cmds.reports.menu(ctx)


def setup(bot) -> None:
    cog = AdminCommandsCog(bot)

    bot._prepare_cog(cog)
    bot.add_cog(cog)
