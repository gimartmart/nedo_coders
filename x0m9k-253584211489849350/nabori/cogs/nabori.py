import asyncio
import discord
from typing import Union
from discord import SlashCommandOptionType
from discord.ext import commands
from discord.commands import SlashCommandGroup
from libs.const_views import NaboriView
from libs.ui import FakeCtx
from libs.util import *


class PamyatkaNaboriCommandsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx: discord.ApplicationContext) -> bool:
        x = ctx.user.guild_permissions.administrator
        if not x:
            await ctx.respond(
                "У Вас недостаточно прав.", ephemeral=True, delete_after=3
            )
        return x

    @commands.slash_command(name="создать_меню")
    async def create_menu(self, ctx: discord.ApplicationContext):
        view = NaboriView()
        # ctx = FakeCtx(bot=ctx.bot, guild=ctx.guild, user=ctx.user)

        embed = discord.Embed(color=0x2B2D31)
        embed.title = "Набор на стафф JAX."
        embed.add_field(
            name=">>> Требования:",
            value="\n".join(
                [
                    "<:1253206798098239589:1254789470838849617> Быть не младше 15 лет",
                    "<:1253206798098239589:1254789470838849617> Уделять серверу в день минимум 3-х часов.",
                    "<:1253206798098239589:1254789470838849617> Адекватность и стрессоустойчивость.",
                    "<:1253206798098239589:1254789470838849617> Хорошие знание правил сервера.",
                ]
            ),
            inline=False,
        )
        embed.add_field(
            name="Что вы получите:",
            value="\n".join(
                [
                    "<:1253206798098239589:1254789470838849617> Приятный коллектив",
                    "<:1253206798098239589:1254789470838849617> Зарплата в виде платной валюты и Nitro Full.",
                    "<:1253206798098239589:1254789470838849617> Весёлые и интересные события, чисто для стаффа.",
                ]
            ),
        )
        embed.set_footer(text="С нетерпением ждём вас в нашей семье!")
        embed.set_image(url="attachment://1.png")
        file = discord.File(os.getcwd() + "/img/nabor.png", filename="1.png")

        await ctx.respond("OK", ephemeral=True, delete_after=1)
        await ctx.channel.send(embed=embed, view=view, file=file)


def setup(bot) -> None:
    cog = PamyatkaNaboriCommandsCog(bot)

    bot._prepare_cog(cog)
    bot.add_cog(cog)
