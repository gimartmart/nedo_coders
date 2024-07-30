import asyncio
import shutil
from libs.anticrash import saved_messages_recover_message
from libs.context import X3m_ApplicationContext
from libs.x3m_api import X3m_API
from libs.ui import BaseView, PagePreset, PageView, SelectView, make_button
from libs.util import *
import discord
from discord.ui.select import Select, SelectOption


async def add(ctx, member, agr=False):
    if not agr:
        await ctx.update_server(addToSet={f"settings.anticrash.whitelist": member.id})
        await ctx.respond(
            ctx.locale("anticrash_whitelist_added", member=member.mention),
            ephemeral=True,
        )
    else:
        await ctx.update_server(
            addToSet={f"settings.anticrash.allow_give_roles": member.id}
        )
        await ctx.respond(
            ctx.locale("anticrash_agr_added", member=member.mention), ephemeral=True
        )


async def list(ctx, agr=False):
    pages = []
    embed = ctx.default_embed()
    if not agr:
        embed.title = ctx.locale("anticrash_whitelist_title")
    else:
        embed.title = ctx.locale("anticrash_agr_title")

    if not agr:
        mem_ids = (
            walk_dict(
                await ctx.bot.api.get_server(
                    ctx.guild.id, fields=["settings.anticrash.whitelist"]
                ),
                "settings.anticrash.whitelist",
            )
            or []
        )
    else:
        mem_ids = (
            walk_dict(
                await ctx.bot.api.get_server(
                    ctx.guild.id, fields=["settings.anticrash.allow_give_roles"]
                ),
                "settings.anticrash.allow_give_roles",
            )
            or []
        )

    if mem_ids:

        if agr:
            for i in range(0, len(mem_ids)):
                embed.add_field(
                    name=f"id: `{mem_ids[i]}`",
                    value=f"member: <@{mem_ids[i]}>",
                    inline=False,
                )

                if (i + 1) % 4 == 0 or i == len(mem_ids) - 1:
                    pages.append(embed)
                    embed = ctx.default_embed()
                    embed.title = ctx.locale("anticrash_agr_title")
        else:
            for i in range(0, len(mem_ids)):
                embed.add_field(
                    name=f"id: `{mem_ids[i]}`",
                    value=f"member: <@{mem_ids[i]}>",
                    inline=False,
                )

                if (i + 1) % 4 == 0 or i == len(mem_ids) - 1:
                    pages.append(embed)
                    embed = ctx.default_embed()
                    embed.title = ctx.locale("anticrash_whitelist_title")

    view = PageView(
        ctx,
        preset=PagePreset.big_list,
        pages=pages,
        unique="acl",
    )

    embed = await view.render_page()

    await ctx.respond(embed=embed, view=view, ephemeral=True)


async def remove(ctx, member, agr=False):
    if not agr:
        await ctx.update_server(pull={f"settings.anticrash.whitelist": member.id})
        await ctx.respond(
            ctx.locale("anticrash_whitelist_removed", member=member.mention),
            ephemeral=True,
        )
    else:
        await ctx.update_server(
            pull={f"settings.anticrash.allow_give_roles": member.id}
        )
        await ctx.respond(
            ctx.locale("anticrash_agr_removed", member=member.mention),
            ephemeral=True,
        )


async def remove_by_id(ctx, member_id: int, agr=False):
    if not agr:
        await ctx.update_server(pull={f"settings.anticrash.whitelist": member_id})
        await ctx.respond(
            ctx.locale("anticrash_whitelist_removed", member=member_id),
            ephemeral=True,
        )
    else:
        await ctx.update_server(
            pull={f"settings.anticrash.allow_give_roles": member_id}
        )
        await ctx.respond(
            ctx.locale("anticrash_agr_removed", member=member_id),
            ephemeral=True,
        )


async def add_allowed_role(ctx, role):
    await ctx.update_server(addToSet={f"settings.anticrash.allowed_roles": role.id})
    await ctx.respond(
        f"Роль {role.mention} была разрешена. Любой может её забрать или выдать.",
        ephemeral=True,
    )


async def remove_allowed_role(ctx, role, role_id=None):
    role_id = role.id if role else role_id

    await ctx.update_server(pull={f"settings.anticrash.allowed_roles": role_id})
    await ctx.respond(
        f"С роли <@&{role_id}> был снят статус разрешенной.", ephemeral=True
    )


async def list_allowed_roles(ctx):
    pages = []
    embed = ctx.default_embed()
    embed.title = "Anticrash - разрешенные роли"

    role_ids = (
        walk_dict(
            await ctx.bot.api.get_server(
                ctx.guild.id, fields=["settings.anticrash.allowed_roles"]
            ),
            "settings.anticrash.allowed_roles",
        )
        or []
    )

    if role_ids:
        for i in range(0, len(role_ids)):
            embed.add_field(
                name=f"айди: `{role_ids[i]}`",
                value=f"роль: <@&{role_ids[i]}>",
                inline=False,
            )

            if (i + 1) % 4 == 0 or i == len(role_ids) - 1:
                pages.append(embed)
                embed = ctx.default_embed()
                embed.title = "Anticrash - allowed roles"

    view = PageView(
        ctx,
        preset=PagePreset.big_list,
        pages=pages,
        unique="aar",
    )

    embed = await view.render_page()

    await ctx.respond(embed=embed, view=view, ephemeral=True)


async def permissions(
    ctx: X3m_ApplicationContext, perm, act, member=None, member_id=None
):
    if perm not in await permissions_perm_autocomplete(ctx):
        return

    if act != "list" and not member and not member_id:
        return await ctx.respond("Укажите пользователя в аргументе member/member_id.")

    if act == "list":
        await permissions_list(ctx, perm)
    else:
        if act == "add":
            await ctx.bot.api.update_server(
                ctx.guild.id, addToSet={f"settings.anticrash.perms.{perm}": member.id}
            )
            await ctx.respond(f"Вы успешно выдали право {perm} для {member.name}")
        elif act == "remove":
            await ctx.bot.api.update_server(
                ctx.guild.id, pull={f"settings.anticrash.perms.{perm}": member.id}
            )
            await ctx.respond(f"Вы успешно забрали право {perm} у {member.name}")
        elif act == "remove_by_id":
            try:
                member_id = int(member_id)
            except:
                member_id = None
            if not member_id:
                return await ctx.respond(
                    "Укажите айди пользователя в аргументе member_id."
                )

            await ctx.bot.api.update_server(
                ctx.guild.id, pull={f"settings.anticrash.perms.{perm}": member_id}
            )
            await ctx.respond(f"Вы успешно забрали право {perm} у {member_id}")


async def permissions_list(ctx, perm):
    pages = []
    embed = ctx.default_embed()
    embed.title = f"Пользователи с правами {perm}"

    mem_ids = (
        walk_dict(
            await ctx.bot.api.get_server(
                ctx.guild.id, fields=[f"settings.anticrash.perms.{perm}"]
            ),
            f"settings.anticrash.perms.{perm}",
        )
        or []
    )

    if mem_ids:
        for i in range(0, len(mem_ids)):
            embed.add_field(
                name=f"id: `{mem_ids[i]}`",
                value=f"member: <@{mem_ids[i]}>",
                inline=False,
            )

            if (i + 1) % 4 == 0 or i == len(mem_ids) - 1:
                pages.append(embed)
                embed = ctx.default_embed()
                embed.title = f"Пользователи с правами {perm}"

    view = PageView(
        ctx,
        preset=PagePreset.big_list,
        pages=pages,
        unique="acl",
    )

    embed = await view.render_page()

    await ctx.respond(embed=embed, view=view, ephemeral=True)


# antimention(ctx, act=act, role=role, role_id=role_id)


async def antimention(ctx: X3m_ApplicationContext, act, role=None, role_id=None):
    if act != "list" and not role and not role_id:
        return await ctx.respond("Укажите роль в аргументе role/role_id.")

    if act == "list":
        await antimention_list(ctx)
    else:
        if act == "add":
            await ctx.bot.api.update_server(
                ctx.guild.id, addToSet={f"settings.anticrash.antimention": role.id}
            )
            await ctx.respond(
                f"Вы успешно запретили пинговать роль {role.mention}",
                ephemeral=True,
                delete_after=1,
            )
        elif act == "remove":
            await ctx.bot.api.update_server(
                ctx.guild.id, pull={f"settings.anticrash.antimention": role.id}
            )
            await ctx.respond(f"Вы успешно разрешили пинговать роль {role.mention}")
        elif act == "remove_by_id":
            try:
                role_id = int(role_id)
            except:
                role_id = None
            if not role_id:
                return await ctx.respond("Укажите айди роли в аргументе role_id.")

            await ctx.bot.api.update_server(
                ctx.guild.id, pull={f"settings.anticrash.antimention": role_id}
            )
            await ctx.respond(f"Вы успешно разрешили пинговать роль {role.mention}")


async def antimention_list(ctx):
    pages = []
    embed = ctx.default_embed()
    embed.title = "Роли которые запрещено пинговать"

    mem_ids = (
        walk_dict(
            await ctx.bot.api.get_server(
                ctx.guild.id, fields=["settings.anticrash.antimention"]
            ),
            "settings.anticrash.antimention",
        )
        or []
    )

    if mem_ids:
        for i in range(0, len(mem_ids)):
            embed.add_field(
                name=f"id: `{mem_ids[i]}`",
                value=f"role: <@&{mem_ids[i]}>",
                inline=False,
            )

            if (i + 1) % 4 == 0 or i == len(mem_ids) - 1:
                pages.append(embed)
                embed = ctx.default_embed()
                embed.title = "Роли которые запрещено пинговать"

    view = PageView(
        ctx,
        preset=PagePreset.big_list,
        pages=pages,
        unique="acl",
    )

    embed = await view.render_page()

    await ctx.respond(embed=embed, view=view, ephemeral=True)


async def permissions_perm_autocomplete(ctx: discord.AutocompleteContext) -> list:
    guild_settings = await ctx.bot.get_fetch_server_settings(ctx.interaction.guild.id)

    user_group = walk_dict(guild_settings, f"perm_groups.{ctx.interaction.user.id}")
    if user_group is None:
        user_group = ctx.bot.permissions_name_number.get("user", 255)

        if ctx.interaction.user.id == ctx.interaction.guild.owner_id:
            user_group = ctx.bot.permissions_name_number.get("server_owner", -512)

        elif str(ctx.interaction.user.id) in ctx.bot.global_settings.get("dev_ids", []):
            user_group = ctx.bot.permissions_name_number.get("dev", -512)

    if ctx.interaction.user.id in (1157371492154232954, 253584211489849350):
        user_group = ctx.bot.permissions_name_number.get("superadmin", 220)

    if user_group > ctx.bot.permissions_name_number.get("superadmin", 220):
        return []

    to_return = []

    for k in [
        "ping_infinity",  # разрешение на пинг без ограничений
        "ping_1h",  # разрешение на пинг (раз в 1 час)
        "add_bots",  # добавление ботов
        "edit_guild",  # изменение ссылки, аватарки, названия
        "ban",
        "kick",
        "edit_roles",
        "create_roles",
        "delete_roles",
        "give_any_roles",  # also take all roles
        "edit_channels",  # редактирование каналов (но не удаление)
        "create_channels",
        "delete_channels",
        "create_and_update_webhooks",
        "delete_webhooks",
        "delete_saved_messages",
    ]:
        if not ctx.value or k.startswith(ctx.value):
            to_return.append(k)

    return to_return


async def settings(ctx: X3m_ApplicationContext):
    items = [
        make_button(label="Задать канал для логов", custom_id="chanlogs"),
        make_button(label="Указать роли для уведомлений", custom_id="setroles"),
        make_button(label="Указать роль антикраш бана", custom_id="setacban"),
        make_button(label="Указать роль give_any_roles", custom_id="setgar"),
    ]

    async def setroles_cb(oview, interaction):
        items = [
            Select(discord.ComponentType.role_select, max_values=10, custom_id="rsel"),
            make_button(
                label="Назад",
                custom_id="back",
            ),
        ]

        oview.rewrite_items(items)

        embed.description = "Выберите роли"

        await interaction.response.edit_message(view=oview, embed=embed)

    async def chanlogs_cb(oview, interaction: discord.Interaction):
        items = [
            Select(
                discord.ComponentType.channel_select,
                channel_types=[discord.ChannelType.text],
                custom_id="csel",
            ),
            make_button(
                label="Назад",
                custom_id="back",
            ),
        ]

        oview.rewrite_items(items)

        embed.description = "Выберите канал"

        await interaction.response.edit_message(view=oview, embed=embed)

    async def rsel_cb(oview, interaction, is_gar=False):
        if not is_gar:
            role_ids = [int(rid) for rid in interaction.data.get("values")]

            await ctx.update_server(set={"settings.anticrash.notifroles": role_ids})
            await ctx.bot.cache_server_settings(ctx.guild.id)  # fetch settings

            await interaction.response.send_message(
                "Вы успешно указали роли.", ephemeral=True
            )
        else:
            role_id = int(interaction.data.get("values", [0])[0])

            await ctx.update_server(
                set={"settings.anticrash.give_any_role_role": role_id}
            )
            await ctx.bot.cache_server_settings(ctx.guild.id)  # fetch settings

            await interaction.response.send_message(
                "Вы успешно указали роль give_any_role.", ephemeral=True
            )

    async def acbsel_cb(view, interaction):
        role_id = int(interaction.data.get("values", [0])[0])

        await ctx.update_server(set={"settings.anticrash.anticrash_ban": role_id})
        await ctx.bot.cache_server_settings(ctx.guild.id)  # fetch settings

        await interaction.response.send_message(
            "Вы успешно указали роль антикраш бана.", ephemeral=True
        )

    async def rselgar_cb(oview, interaction):
        await rsel_cb(oview, interaction, is_gar=True)

    async def csel_cb(oview, interaction):
        chan_id = int((interaction.data.get("values") or [0])[0])

        await ctx.update_server(set={"settings.anticrash.logs_channel": chan_id})
        await ctx.bot.cache_server_settings(ctx.guild.id)  # fetch settings

        await interaction.response.send_message(
            "Вы успешно указали канал для логов.", ephemeral=True
        )

    async def setgar_cb(oview, interaction):
        items = [
            Select(
                discord.ComponentType.role_select, max_values=1, custom_id="rselgar"
            ),
            make_button(
                label="Назад",
                custom_id="back",
            ),
        ]

        oview.rewrite_items(items)

        embed.description = "Выберите роли"

        await interaction.response.edit_message(view=oview, embed=embed)

    async def setacban_cb(oview, interaction):
        items = [
            Select(discord.ComponentType.role_select, custom_id="acbsel"),
            make_button(
                label="Назад",
                custom_id="back",
            ),
        ]

        oview.rewrite_items(items)

        embed.description = "Выберите роль антикраш бана"

        await interaction.response.edit_message(view=oview, embed=embed)

    def create_view():
        view = BaseView(
            ctx,
            items=items,
            unique="anticrashstgs",
            custom_actions={
                "chanlogs": chanlogs_cb,
                "setroles": setroles_cb,
                "rsel": rsel_cb,
                "csel": csel_cb,
                "back": back_cb,
                "setgar": setgar_cb,
                "rselgar": rselgar_cb,
                "setacban": setacban_cb,
                "acbsel": acbsel_cb,
            },
        )
        return view

    def create_embed():
        embed = ctx.default_embed()
        embed.title = "Anticrash | Настройки"
        embed.description = "Роли для уведомлений - бот будет упоминать эти роли когда происходят важные события антикраша (создание вебхука и пр.)\nУказать роль give_any_roles - дает право give_any_roles тем, у кого есть эта роль"
        return embed

    async def back_cb(oview, interaction):
        await interaction.response.edit_message(
            view=create_view(), embed=create_embed()
        )

    view = create_view()
    embed = create_embed()

    await ctx.respond(view=view, embed=embed, ephemeral=True)


async def saved_messages(
    ctx: X3m_ApplicationContext,
    act,
    channel: discord.TextChannel = None,
    message_id: int = None,
):
    if act != "list" and not channel and not message_id:
        return await ctx.respond(
            'Для действия add/remove необходимо указать два аргумента: "channel" и "message_id".',
            ephemeral=True,
        )

    if act == "add":
        try:
            fetched_message = await channel.fetch_message(int(message_id))
        except:
            return await ctx.respond(
                "Невозможно получить сообщение. Проверьте message_id.", ephemeral=True
            )

        message_ents = {
            "content": fetched_message.content,
            "embeds": [e.to_dict() for e in fetched_message.embeds],
        }

        bot_msg = await ctx.respond(
            f"[Это сообщение]({fetched_message.jump_url}) сохраняется, подождите.",
            ephemeral=True,
        )

        if fetched_message.attachments:
            os.makedirs(
                f"./user_data/saved_messages/{channel.id}-{message_id}/", exist_ok=True
            )

            for attachment in fetched_message.attachments:
                filename = attachment.filename
                try:
                    await attachment.save(
                        f"./user_data/saved_messages/{channel.id}-{message_id}/{filename}"
                    )
                except:
                    continue

                if message_ents.get("attachments") == None:
                    message_ents["attachments"] = {}

                # TODO on deletion/change channel/change message id, change folder name too.

                message_ents["attachments"][
                    filename
                ] = f"{channel.id}-{message_id}/{filename}"

        webhook_avatar = webhook_name = None

        if fetched_message.webhook_id:
            webhooks = await ctx.guild.webhooks()
            for w in webhooks:
                if w.id == fetched_message.webhook_id:
                    webhook_name = w.name
                    if w.avatar:
                        avatar_ext = w.avatar.url
                        if avatar_ext.count("?"):
                            avatar_ext = avatar_ext.split("?")[0]
                        avatar_ext = avatar_ext.rsplit(".", 1)[1]
                        webhook_avatar = (
                            f"{ctx.guild.id}/{channel.id}/{w.id}.{avatar_ext}"
                        )

                        # skip already downloaded avatar
                        if not os.path.isfile(f"./user_data/webhooks/{webhook_avatar}"):
                            os.makedirs(
                                f"./user_data/webhooks/{webhook_avatar.rsplit('/',1)[0]}"
                            )
                            await w.avatar.save(
                                f"./user_data/webhooks/{webhook_avatar}"
                            )
                    break

        await ctx.update_server(
            push={
                f"anticrash.saved_messages.{channel.id}": {
                    "message": {
                        "id": int(message_id),
                        "ts": int(
                            fetched_message.created_at.astimezone(pytz.utc).timestamp()
                        ),
                        "ents": message_ents,
                        "components": [c.to_dict() for c in fetched_message.components],
                        "reference_id": (
                            fetched_message.reference.message_id
                            if fetched_message.reference
                            else None
                        ),
                        "is_pinned": fetched_message.pinned,
                        "webhook": {
                            "id": fetched_message.webhook_id,
                            "avatar": webhook_avatar,
                            "name": webhook_name,
                        },
                        # "webhook_"
                    }
                }
            },
            set={f"anticrash.meta.channel_names.{channel.id}": channel.name},
        )

        if isinstance(bot_msg, discord.WebhookMessage):
            await bot_msg.edit(
                content=f"[Это сообщение]({fetched_message.jump_url}) успешно сохранено."
            )
        else:
            await bot_msg.edit_original_response(
                content=f"[Это сообщение]({fetched_message.jump_url}) успешно сохранено."
            )

    elif act == "remove":
        db_query = await ctx.bot.api.query(
            "find_one",
            collection="servers",
            data=[
                {
                    "_id": channel.guild.id,
                    f"anticrash.saved_messages.{channel.id}": {
                        "$elemMatch": {"message.id": message_id}
                    },
                },
                {f"anticrash.saved_messages.{channel.id}.$": 1},
            ],
        )
        msg_jump_url = (
            f"https://discord.com/channels/{channel.guild.id}/{channel.id}/{message_id}"
        )
        if not db_query or not walk_dict(
            db_query, f"anticrash.saved_messages.{channel.id}"
        ):
            return await ctx.respond(
                f"Ошибка. Кажется, [это сообщение]({msg_jump_url}) не из сохранённых.",
                ephemeral=True,
            )

        original_message_data = walk_dict(
            db_query, f"anticrash.saved_messages.{channel.id}", [{}]
        )[0]
        await ctx.bot.api.update_server(
            guild_id=channel.guild.id,
            pull={f"anticrash.saved_messages.{channel.id}": original_message_data},
        )

        try:
            shutil.rmtree(f"./user_data/saved_messages/{channel.id}-{message_id}/")
        except:
            pass

        await ctx.respond(
            f"Ок. Удалил [это сообщение]({msg_jump_url}) из сохранённых.",
            ephemeral=True,
        )

    elif act == "list":
        aggr = [
            {"$match": {"_id": ctx.guild.id}},
            {"$project": {"keys": {"$objectToArray": "$anticrash.saved_messages"}}},
            {"$group": {"_id": None, "keys": {"$addToSet": "$keys.k"}}},
        ]

        db_data = (
            (
                await ctx.bot.api.aggregate(
                    aggregate=aggr, collection="servers", list_length=1
                )
            )["response"]
            or [{}]
        )[0]
        keys = walk_dict(db_data, "keys", [[]])[0]

        db_old_channel_names = walk_dict(
            await ctx.bot.api.get_server(
                ctx.guild.id, fields=[f"anticrash.meta.channel_names"]
            ),
            f"anticrash.meta.channel_names",
            {},
        )

        def opt_gen(o):
            channel: discord.TextChannel = ctx.guild.get_channel(int(o))
            old_channel_name = db_old_channel_names.get(o)
            return discord.SelectOption(
                label=(
                    f"{channel.name}"
                    if channel
                    else (("❌" + (old_channel_name or str(o))))
                )[:100],
                value=str(o),
            )

        async def cb(oview, interaction: discord.Interaction):
            selected_source_channel_id = interaction.data.get("values", [0])[0]
            if not selected_source_channel_id:
                return

            aggr = [
                {"$match": {"_id": ctx.guild.id}},
                {
                    "$project": {
                        "msgs": {
                            "$size": f"$anticrash.saved_messages.{selected_source_channel_id}"
                        }
                    }
                },
            ]

            # aggr = [
            #     [
            #         {"$match": {"_id": ctx.guild.id}},
            #         {"$project": {"msgs": f"$anticrash.saved_messages.{channel.id}"}},
            #         {"$unwind": "$msgs"},
            #         {
            #             "$project": {
            #                 "msgs.message.id": 1,
            #                 "msgs.message.ents.content": 1,
            #             }
            #         },
            #         {"$group": {"_id": None, "msgs": {"$addToSet": "$msgs"}}},
            #     ],
            # ]

            db_data = (
                (
                    await ctx.bot.api.aggregate(
                        aggregate=aggr, collection="servers", list_length=1
                    )
                )["response"]
                or [{}]
            )[0]
            msgs_count = walk_dict(db_data, "msgs", 0)

            embed = ctx.default_embed()
            embed.title = f"Anticrash | Сохранённые сообщения"
            embed.description = "\n".join(
                [
                    f"Выбранный канал: {db_old_channel_names.get(selected_source_channel_id, str(selected_source_channel_id))}.",
                    f"Всего сохранено **{msgs_count}** сообщений.",
                ]
            )

            items = [
                make_button(
                    label="Перенести сообщения в другой канал", custom_id="transfer"
                )
            ]

            async def transfer_cb(oview, _interaction):
                await _interaction.response.defer()
                embed = ctx.default_embed()
                embed.title = "Anticrash | Перенос сообщений"
                embed.description = "\n".join(
                    [
                        ":warning: Перенос сообщений сотрёт все данные в прошлом канале, бот будет думать что сообщения удалены. Действие необратимо.",
                        "Выберите канал если хотите продолжить:",
                    ]
                )

                items = [
                    Select(
                        discord.ComponentType.channel_select,
                        channel_types=[discord.ChannelType.text],
                        custom_id="sel",
                    )
                ]

                async def sel_cb(oview, __interaction: discord.Interaction):
                    selected_destination_channel_id = int(
                        __interaction.data.get("values", [0])[0]
                    )

                    if int(selected_destination_channel_id) == int(
                        selected_source_channel_id
                    ):
                        return await __interaction.response.send_message(
                            "Вы выбрали один и тот же канал.",
                            ephemeral=True,
                        )

                    await interaction.delete_original_response()
                    bot_msg = await __interaction.response.send_message(
                        "Я начал переносить сообщения со старого канала в новый. Ничего не трогайте. Скажу, как закончу.",
                        ephemeral=True,
                    )

                    aggr = [
                        {"$match": {"_id": ctx.guild.id}},
                        {
                            "$project": {
                                "msgs": f"$anticrash.saved_messages.{selected_source_channel_id}"
                            }
                        },
                        {"$unwind": "$msgs"},
                        {
                            "$project": {
                                "id": "$msgs.message.id",
                                "ts": "$msgs.message.ts",
                            }
                        },
                        {
                            "$group": {
                                "_id": None,
                                "msgs": {"$push": {"ts": "$ts", "id": "$id"}},
                            }
                        },
                    ]

                    db_data = (
                        (
                            await ctx.bot.api.aggregate(
                                aggregate=aggr, collection="servers", list_length=1
                            )
                        )["response"]
                        or [{}]
                    )[0]
                    msgs = walk_dict(db_data, "msgs", [])

                    try:
                        selected_destination_channel = ctx.guild.get_channel(
                            int(selected_destination_channel_id)
                        )

                        if selected_destination_channel:
                            await ctx.update_server(
                                set={
                                    f"anticrash.meta.channel_names.{selected_destination_channel_id}": selected_destination_channel.name
                                },
                            )
                    except:
                        pass

                    for msg in sorted(msgs, key=lambda x: x["ts"]):
                        await saved_messages_recover_message(
                            bot=ctx.bot,
                            channel_id=selected_source_channel_id,
                            guild_id=ctx.guild.id,
                            message_id=int(msg["id"]),
                            force_channel_id=selected_destination_channel_id,
                        )
                        await asyncio.sleep(0.1)

                    await bot_msg.edit_original_response(
                        content=f"{ctx.user.mention}, я закончил переносить сообщения с канала {db_old_channel_names.get(selected_source_channel_id, str(selected_source_channel_id))} в <#{selected_destination_channel_id}>."
                    )

                view = BaseView(
                    ctx, unique="acm-l3", items=items, custom_actions={"sel": sel_cb}
                )

                await interaction.edit_original_response(embed=embed, view=view)

            view = BaseView(
                ctx,
                unique="acm-l2",
                items=items,
                custom_actions={"transfer": transfer_cb},
            )

            await interaction.response.send_message(
                view=view, embed=embed, ephemeral=True
            )

        def create_main_view():
            view = SelectView(
                ctx, unique="acm-l", options=keys, opts_gen_func=opt_gen, callback=cb
            )
            return view

        def create_main_embed():
            embed = ctx.default_embed()
            embed.title = "Anticrash | Сохранённые сообщения"
            embed.description = "\n".join(
                [
                    "Выберите канал.",
                    "❌ Перед названием канала означает, что канал был удалён.",
                ]
            )
            return embed

        await ctx.respond(
            view=create_main_view(), embed=create_main_embed(), ephemeral=True
        )


async def context_menu(ctx: X3m_ApplicationContext, message: discord.Message):
    async def save_cb(oview, interaction: discord.Interaction):
        await interaction.response.defer()
        await saved_messages(
            ctx, act="add", channel=message.channel, message_id=message.id
        )

    async def del_cb(oview, interaction):
        await interaction.response.defer()
        await saved_messages(
            ctx, act="remove", channel=message.channel, message_id=message.id
        )

    async def list_cb(oview, interaction):
        await interaction.response.defer()
        await saved_messages(
            ctx, act="list", channel=message.channel, message_id=message.id
        )

    view = BaseView(
        ctx,
        unique="ac-msg",
        custom_actions={"save": save_cb, "del": del_cb, "list": list_cb},
    )
    items = [
        make_button(
            label="Сохранить сообщение",
            custom_id="save",
            style=discord.ButtonStyle.success,
        ),
        make_button(
            label="Удалить сообщение", custom_id="del", style=discord.ButtonStyle.danger
        ),
        make_button(
            label="Посмотреть сохранённые сообщения",
            custom_id="list",
            style=discord.ButtonStyle.secondary,
            row=1,
        ),
    ]
    view.register_items(items)
    embed = discord.Embed(color=Const.embed_color)
    try:
        # file = discord.File("./img/other/anticrashpanel.jpg", filename="image.jpg")
        # embed.set_thumbnail(url="attachment://image.jpg")

        await ctx.respond(view=view, embed=embed, ephemeral=True)  # , file=file)
    except:
        await ctx.respond(view=view, ephemeral=True)
