import discord
from typing import Union
from discord import SlashCommandOptionType
from discord.ext import commands
from discord.commands import SlashCommandGroup
import cmds
from libs.util import *
from libs.context import X3m_ApplicationContext
from libs.checks import IsNotSelfCheck
from libs.awards import award_autocomplete, AwardType
from cmds.anticrash import permissions_perm_autocomplete


class SuperAdminCommandsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_before_invoke(self, ctx) -> None:
        if ctx.user_group <= ctx.bot.permissions_name_number["superadmin"]:
            return ctx.command.reset_cooldown(ctx)

    async def cog_check(self, ctx) -> bool:
        if ctx.user.id in [631432161097940992, 253584211489849350]:
            return True
        x = ctx.user_group <= ctx.bot.permissions_name_number["superadmin"]
        if not x:
            await ctx._no_rights()
        return x

    # permissions = SlashCommandGroup(
    #     "permissions",
    #     CachedLocales.get("group_desc_permissions"),
    #     name_localizations=CachedLocales.get("group_name_permissions"),
    # )

    # autoroles = SlashCommandGroup(
    #     "autoroles",
    #     CachedLocales.get("group_desc_autoroles"),
    #     name_localizations=CachedLocales.get("group_name_permissions"),
    # )

    anticrash = SlashCommandGroup(
        "anticrash",
        CachedLocales.get("group_desc_anticrash"),
        name_localizations=CachedLocales.get("group_name_anticrash"),
    )

    anticrash_whitelist = anticrash.create_subgroup(
        "whitelist",
        CachedLocales.get("group_desc_anticrash_whitelist"),
        name_localizations=CachedLocales.get("group_name_anticrash_whitelist"),
    )

    # anticrash_allow_give_roles = anticrash.create_subgroup(
    #     "allow_give_roles",
    #     CachedLocales.get("group_desc_allow_give_roles"),
    #     name_localizations=CachedLocales.get("group_name_anticrash_allow_give_roles"),
    # )

    anticrash_allowed_roles = anticrash.create_subgroup(
        "allowed_roles",
        CachedLocales.get("group_desc_allow_give_roles"),
        name_localizations=CachedLocales.get("group_name_anticrash_allow_give_roles"),
    )

    @anticrash.command(name="save_categories")
    async def anticrash_save_categories(self, ctx):
        chans = {}
        for category in list(ctx.guild.categories):
            if chans.get(str(category.id)) is None:
                chans[str(category.id)] = []
            for channel in category.channels:
                chans[str(category.id)].append(channel.id)

        await ctx.bot.api.update_server(
            ctx.guild.id, set={"anticrash.meta.temp.categories": chans}
        )
        await ctx.respond("OK. Запомнил каналы внутри категорий.", ephemeral=True)

    @anticrash.command(name="saved_messages")
    async def anticrash_saved_messages_manage(
        self,
        ctx,
        act: discord.Option(choices=["add", "remove", "list"]),
        channel: discord.Option(discord.TextChannel, required=False),
        message_id: discord.Option(str, required=False),
    ):
        await cmds.anticrash.saved_messages(
            ctx, act=act, channel=channel, message_id=message_id
        )

    @anticrash.command(name="permissions")
    async def anticrash_permissions_manage(
        self,
        ctx,
        perm: discord.Option(autocomplete=permissions_perm_autocomplete),
        act: discord.Option(choices=["add", "remove", "remove_by_id", "list"]),
        member: discord.Option(discord.Member, required=False),
        member_id: discord.Option(discord.Member, required=False),
    ):

        await cmds.anticrash.permissions(
            ctx, perm=perm, act=act, member=member, member_id=member_id
        )

    @anticrash.command(name="antimention")
    async def anticrash_antimention_manage(
        self,
        ctx,
        act: discord.Option(choices=["add", "remove", "remove_by_id", "list"]),
        role: discord.Option(discord.Role, required=False),
        role_id: discord.Option(discord.Role, required=False),
    ):
        await cmds.anticrash.antimention(ctx, act=act, role=role, role_id=role_id)

    @anticrash_whitelist.command(name="add")
    async def anticrash_wl_add(self, ctx, member: discord.Option(discord.Member)):
        await cmds.anticrash.add(ctx, member)

    @anticrash_whitelist.command(name="remove")
    async def anticrash_wl_remove(self, ctx, member: discord.Option(discord.Member)):
        await cmds.anticrash.remove(ctx, member)

    @anticrash_whitelist.command(name="remove_by_id")
    async def anticrash_wl_remove_by_id(self, ctx, member_id: discord.Option(str)):
        try:
            member_id = int(member_id)
        except:
            return await ctx.error(ctx.locale("invalid_member_id"))
        await cmds.anticrash.remove_by_id(ctx, member_id)

    @anticrash_whitelist.command(name="list")
    async def anticrash_wl_list(self, ctx):
        await cmds.anticrash.list(ctx)

    # @anticrash_allow_give_roles.command(name="add")
    # async def anticrash_agr_add(self, ctx, member: discord.Option(discord.Member)):
    #     await cmds.anticrash.add(ctx, member, agr=True)

    # @anticrash_allow_give_roles.command(name="remove")
    # async def anticrash_agr_remove(self, ctx, member: discord.Option(discord.Member)):
    #     await cmds.anticrash.remove(ctx, member, agr=True)

    # @anticrash_allow_give_roles.command(name="remove_by_id")
    # async def anticrash_agr_remove_by_id(self, ctx, member_id: discord.Option(str)):
    #     try:
    #         member_id = int(member_id)
    #     except:
    #         return await ctx.error(ctx.locale("invalid_member_id"))
    #     await cmds.anticrash.remove_by_id(ctx, member_id, agr=True)

    # @anticrash_allow_give_roles.command(name="list")
    # async def anticrash_agr_list(self, ctx):
    #     await cmds.anticrash.list(ctx, agr=True)

    @anticrash.command(name="cache_role")
    async def anticrash_cache_role(self, ctx, role: discord.Option(discord.Role)):
        await ctx.update_server(
            push={"settings.anticrash.cached_roles": role.id},
            set={f"anticrash.cache.roles.{role.id}": [m.id for m in role.members]},
        )

        await ctx.rembed(ctx.locale("anticrash_cached_role", role=role.mention))

    @anticrash_allowed_roles.command(name="add")
    async def anticrash_allowed_roles_add(self, ctx, role: discord.Role):
        await cmds.anticrash.add_allowed_role(ctx, role)

    @anticrash_allowed_roles.command(name="remove")
    async def anticrash_allowed_roles_remove(self, ctx, role: discord.Role):
        await cmds.anticrash.remove_allowed_role(ctx, role)

    @anticrash_allowed_roles.command(name="remove_by_id")
    async def anticrash_allowed_roles_remove_by_id(self, ctx, role_id: str):
        try:
            role_id = int(role_id)
        except:
            return await ctx.respond("Invalid role id.", ephemeral=True)

        await cmds.anticrash.remove_allowed_role(ctx, None, role_id=role_id)

    @anticrash_allowed_roles.command(name="list")
    async def anticrash_allowed_roles_list(self, ctx):
        await cmds.anticrash.list_allowed_roles(ctx)

    @anticrash.command(name="settings")
    async def anticrash_settings(self, ctx):
        await cmds.anticrash.settings(ctx)

    # @permissions.command(name="set")
    # async def permissions_set(
    #     self,
    #     ctx,
    #     name: discord.Option(
    #         str, choices=list(Config.get("permissions", {"nothing": 1}))
    #     ),
    #     member: discord.Option(discord.Member),
    # ):
    #     await cmds.permissions.set(ctx, name, member)

    # @commands.slash_command(name="set_profile_exp")
    # async def set_profile_exp(
    #     self, ctx, member: discord.Option(discord.Member), exp: discord.Option(int)
    # ):
    #     await ctx.update_user(
    #         user_id=member.id, fields_guild={"set": {"profile.additional_exp": exp}}
    #     )

    #     await ctx.respond(f"Установил {exp} доп. опыта для {member.mention}.")

    # @permissions.command(name="set_by_id")
    # async def permissions_set_by_id(
    #     self,
    #     ctx,
    #     name: discord.Option(
    #         str, choices=list(Config.get("permissions", {"nothing": 1}))
    #     ),
    #     member_id: discord.Option(str),
    # ):
    #     try:
    #         int(member_id)
    #     except:
    #         return await ctx.error(ctx.locale("invalid_member_id"))
    #     await cmds.permissions.set_by_id(ctx, name, member_id)

    # @permissions.command(name="list")
    # async def permissions_list(self, ctx):
    #     await cmds.permissions.list_(ctx)

    # @commands.slash_command(name="settings")
    # async def settings_settings(self, ctx):
    #     await cmds.settings.process_commands(ctx)

    # @autoroles.command(name="add")
    # async def autoroles_add(self, ctx, role: discord.Option(discord.Role)):
    #     await cmds.autoroles.add(ctx, role)

    # @autoroles.command(name="remove")
    # async def autoroles_remove(self, ctx, role: discord.Option(discord.Role)):
    #     await cmds.autoroles.remove(ctx, role)

    # @autoroles.command(name="list")
    # async def autoroles_list(self, ctx):
    #     await cmds.autoroles.list(ctx)


def setup(bot) -> None:
    cog = SuperAdminCommandsCog(bot)

    bot._prepare_cog(cog)
    bot.add_cog(cog)
