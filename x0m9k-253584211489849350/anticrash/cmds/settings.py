from libs.ui import (
    SelectView,
    BaseView,
    PageView,
    PagePresetButtons,
    PagePreset,
    ConfirmView,
    NumberSelectView,
    RoleSelectView,
    ChannelSelectView,
    ChannelType,
)
from discord.ui.select import Select, SelectOption
from discord.ui.button import ButtonStyle
from libs.util import *
import asyncio


async def process_commands(ctx, return_view=False):
    options = {
        "menu": [
            "roles",
            "channels",
            "prices",
            "lang_and_timezone",
        ],
        "number": {
            "report_max_active_reports": {"min": 1},
            "vc_online.balance_per_60minutes": {"min": 1},
            "max_personal_roles": {"min": 0, "max": 100},
            "tickets_max_simultaneous": {"min": 0},
            "tickets_max_channels": {"min": 0},
        },
    }

    def find_opt(opt):
        for k in options.keys():
            if opt in options[k]:
                return k

    list_options = []

    def opts_gen_func(option):
        return SelectOption(
            label=ctx.locale("settings_btn_" + option),
            value=str(option),
            emoji="🔸" if list_options.index(option) % 2 else "🔹",
        )

    for k in options.keys():
        list_options.extend(options[k])

    embed = ctx.default_embed()
    embed.title = ctx.locale("settings_title")

    async def cb(oview, interaction):
        selected = oview.get_selected()[0]

        type = find_opt(selected)

        if type == "menu":
            func = globals().get("process_menu_" + selected)
            if not func:
                return

            return await func(ctx, interaction)

        if type == "number":
            data = options[type].get(selected)
            min, max = data.get("min"), data.get("max")

            _view = NumberSelectView(
                ctx, min=min, max=max, unique="settings:numberselect"
            )

            _embed = _view.render()
            _embed.set_author(
                name=ctx.locale(
                    "numberselect_current_title",
                    current=ctx.walk_server(f"numbers.{selected}"),
                )
            )

            await interaction.response.send_message(
                view=_view,
                embed=_embed,
                ephemeral=True,
            )

            timedout = await _view.wait()

            if timedout:
                embed.set_footer(text=ctx.locale("footer_timeout"))

                await interaction.response.edit_original_response(embed=embed)

                return

            elif _view.force_stopped:
                return

            num = _view.get_number()

            await ctx.update_server(set={f"settings.numbers.{selected}": num})

    view = SelectView(
        ctx,
        options=list_options,
        callback=cb,
        opts_gen_func=opts_gen_func,
        unique="settings:superadminmenu",
    )

    msg = await ctx.respond(embed=embed, view=view, ephemeral=True)


async def process_menu_roles(ctx, interaction):
    data = {}

    available_roles = [
        "info_all",
        "premium_status",
        "booster_status",
        "marry",
        "personal_role_marker",
        "tickets_bot",
        "tickets_server",
        "tickets_report",
        "tickets_another",
    ]

    async def cb(oview, interaction):
        selected = oview.get_selected()[0]

        if selected == "info_all":
            await info(oview, interaction)
        else:
            await choose(oview, interaction, selected)

    def opt_gen(opt):
        return SelectOption(
            label=ctx.locale("settings_role_btn_" + opt), value=str(opt)
        )

    view = SelectView(
        ctx,
        unique="settings:selectrole",
        options=available_roles,
        single_choice=False,
        opts_gen_func=opt_gen,
        callback=cb,
    )

    embed = ctx.default_embed()
    embed.title = ctx.locale("settings_roleselect_title")

    msg = await interaction.response.send_message(
        embed=embed, view=view, ephemeral=True
    )

    async def info(oview, interaction):
        all_roles = available_roles[1:]

        pages = []

        def get_role_name(name):
            role_id = ctx.walk_server(f"roles.{name}", 0)
            if not role_id:
                return ctx.locale("nothing")

            if not ctx.guild.get_role(role_id):
                return f"<deleted: {role_id}>"

            return f"<@&{role_id}>"

        for r in range(len(all_roles) // 25 + 1):
            embed = ctx.default_embed()
            embed.title = ctx.locale("settings_role_info_title")

            embed.description = "\n".join(
                "`{0}` - {1}".format(
                    ctx.locale("settings_role_btn_" + rr), get_role_name(rr)
                )
                for rr in all_roles[r * 25 : r * 25 + 25]
            )

            pages.append(embed)

        preset = PagePreset.list if len(pages) < 5 else PagePreset.big_list

        view = PageView(ctx, preset=preset, pages=pages, timeout=90)

        embed = await view.render_page()

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def choose(_, interaction, name):
        async def cb(oview, interaction):
            role_id = int(oview.get_selected()[0])

            embed.description = ctx.locale(
                "settings_setrole_success_desc",
                name=ctx.locale("settings_role_btn_" + name),
                role=f"<@&{role_id}>",
            )

            await msg.edit_original_response(embed=embed, view=None)

            await ctx.update_server(set={f"settings.roles.{name}": role_id})

        view = RoleSelectView(ctx, select_cb=cb, unique="settings:setrole")

        await view.render()

        embed = ctx.default_embed()
        embed.title = ctx.locale("roleselect_title")
        embed.description = ctx.locale(
            "settings_setrole_desc", name=ctx.locale("settings_role_btn_" + name)
        )

        msg = await interaction.response.send_message(
            embed=embed, view=view, ephemeral=True
        )


async def process_menu_channels(ctx, interaction):
    data = {}
    types = {
        "report_channel": ChannelType.text,
        "tickets_category": ChannelType.category,
        "tickets_bot": ChannelType.text,
        "tickets_server": ChannelType.text,
        "tickets_report": ChannelType.text,
        "tickets_another": ChannelType.text,
        "logs_users": ChannelType.text,
        "logs_chat": ChannelType.text,
        "logs_ban": ChannelType.text,
        "logs_award": ChannelType.text,
        "logs_nickname": ChannelType.text,
        "logs_voices": ChannelType.text,
        "logs_anticrash": ChannelType.text,
        "closes.announcements": ChannelType.text,
    }

    available_channels = list(types)
    available_channels.insert(0, "info_all")

    async def cb(oview, interaction):
        selected = oview.get_selected()[0]

        if selected == "info_all":
            await info(oview, interaction)
        else:
            await choose(oview, interaction, selected)

    def opt_gen(opt):
        return SelectOption(
            label=ctx.locale("settings_channel_btn_" + opt), value=str(opt)
        )

    view = SelectView(
        ctx,
        unique="settings:selectchan",
        options=available_channels,
        single_choice=False,
        opts_gen_func=opt_gen,
        callback=cb,
    )

    embed = ctx.default_embed()
    embed.title = ctx.locale("settings_chanselect_title")

    msg = await interaction.response.send_message(
        embed=embed, view=view, ephemeral=True
    )

    async def info(oview, interaction):
        all_chans = available_channels[1:]

        pages = []

        def get_channel_name(name):
            chan_id = ctx.walk_server(f"channels.{name}", 0)
            if not chan_id:
                return ctx.locale("nothing")

            if not ctx.guild.get_channel(chan_id):
                return f"<deleted: {chan_id}>"

            return f"<#{chan_id}>"

        for r in range(len(all_chans) // 25 + 1):
            embed = ctx.default_embed()
            embed.title = ctx.locale("settings_channel_info_title")

            embed.description = "\n".join(
                "`{0}` - {1}".format(
                    ctx.locale("settings_channel_btn_" + rr), get_channel_name(rr)
                )
                for rr in all_chans[r * 25 : r * 25 + 25]
            )

            pages.append(embed)

        preset = PagePreset.list if len(pages) < 5 else PagePreset.big_list

        view = PageView(ctx, preset=preset, pages=pages, timeout=90)

        embed = await view.render_page()

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def choose(_, interaction, name):
        async def cb(oview, interaction):
            chan_id = int(oview.get_selected()[0])

            embed.description = ctx.locale(
                "settings_setchan_success_desc",
                name=ctx.locale("settings_channel_btn_" + name),
                channel=f"<#{chan_id}>",
            )

            oview.stop()

            await msg.edit_original_response(embed=embed, view=None)

            type = types.get(name)

            if type == ChannelType.category:
                chan_type = "categories"
            elif type == ChannelType.voice or type == ChannelType.text:
                chan_type = "channels"
            elif type == ChannelType.thread:
                chan_type = "threads"

            await ctx.update_server(set={f"settings.{chan_type}.{name}": chan_id})

        view = ChannelSelectView(
            ctx, type=types.get(name), select_cb=cb, unique="settings:setchan"
        )

        await view.render()

        embed = ctx.default_embed()
        embed.title = ctx.locale("chanselect_title")
        embed.description = ctx.locale(
            "settings_setchan_desc", name=ctx.locale("settings_channel_btn_" + name)
        )

        msg = await interaction.response.send_message(
            embed=embed, view=view, ephemeral=True
        )


async def process_menu_prices(ctx, interaction):
    data = {}

    available_prices = [
        "info_all",
        "marry",
        "marry_monthly",
        "roles.buy",
        "roles.give",
        "roles.edit",
        "roles.monthly",
    ]

    async def cb(oview, interaction):
        selected = oview.get_selected()[0]

        if selected == "info_all":
            await info(oview, interaction)
        else:
            await choose(oview, interaction, selected)

    def opt_gen(opt):
        return SelectOption(
            label=ctx.locale("settings_price_btn_" + opt), value=str(opt)
        )

    view = SelectView(
        ctx,
        unique="settings:selectprice",
        options=available_prices,
        single_choice=False,
        opts_gen_func=opt_gen,
        callback=cb,
    )

    embed = ctx.default_embed()
    embed.title = ctx.locale("settings_prices_title")

    msg = await interaction.response.send_message(
        embed=embed, view=view, ephemeral=True
    )

    async def info(oview, interaction):
        all_prices = available_prices[1:]

        pages = []

        for r in range(len(all_prices) // 25 + 1):
            embed = ctx.default_embed()
            embed.title = ctx.locale("settings_price_info_title")

            embed.description = "\n".join(
                "`{0}` - {1}".format(
                    ctx.locale("settings_price_btn_" + rr),
                    ctx.walk_server(f"prices.{rr}"),
                )
                for rr in all_prices[r * 25 : r * 25 + 25]
            )

            pages.append(embed)

        preset = PagePreset.list if len(pages) < 5 else PagePreset.big_list

        view = PageView(ctx, preset=preset, pages=pages, timeout=90)

        embed = await view.render_page()

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def choose(_, interaction, name):
        view = NumberSelectView(ctx, unique="settings:setprice")

        embed = view.render()
        embed.description = ctx.locale(
            "settings_setprice_desc", name=ctx.locale("settings_price_btn_" + name)
        )

        price_msg = await interaction.response.send_message(
            embed=embed, view=view, ephemeral=True
        )

        timedout = await view.wait()

        if timedout:
            embed.set_footer(text=ctx.locale("footer_timeout"))

            await price_msg.edit_original_response(embed=embed)

            return

        elif view.force_stopped:
            return

        price = view.get_number()

        await ctx.update_server(set={f"settings.prices.{name}": price})

        embed = ctx.default_embed()

        embed.description = ctx.locale(
            "settings_setprice_success_desc",
            name=ctx.locale("settings_price_btn_" + name),
            price=f"{price:,}".replace(",", "."),
        )

        await price_msg.edit_original_response(embed=embed, view=None)
