import logging
import discord
from discord.ext import commands
from libs.config import Config

log = logging.getLogger("log")


async def on_command_error(ctx, error: discord.errors.ApplicationCommandError) -> None:
    bot = ctx.bot

    # if isinstance(error, commands.CommandNotFound):
    #     return await bot.suggest_similar_command(ctx, ctx.invoked_with.lower())

    if isinstance(error, commands.CheckFailure) or isinstance(
        error, discord.errors.CheckFailure
    ):
        return

    if isinstance(error, commands.errors.CommandOnCooldown):

        return await ctx._cooldown(
            ctx.make_time(error.retry_after, ms_digits=1),
            message=ctx.locale("error_cmd_cooldown"),
        )

    if Config.get("debug"):
        raise error
    else:
        log.error(error)

    return
    # \/ \/ \/ \/ \/ below is not adapted for v3.

    if isinstance(error, commands.errors.MissingRequiredArgument):
        arg = error.param

        return await ctx.error(
            ctx.locale("error_command_missing_required_arg", name=arg.name)
        )

    if isinstance(error, commands.errors.BadArgument):

        if isinstance(error, commands.errors.MemberNotFound):
            return await ctx.error(
                ctx.locale(
                    "error_command_invalid_member", member=ellipsis(error.argument, 128)
                )
            )
        elif isinstance(error, commands.errors.UserNotFound):
            return await ctx.error(
                ctx.locale(
                    "error_command_invalid_user", user=ellipsis(error.argument, 128)
                )
            )
        else:

            try:
                _type, name = re.findall('"(\w+)"', str(error))
            except Exception as err:
                return await ctx.error(
                    ctx.locale(
                        "error_command_badarg_unknown_error",
                        err=ellipsis(str(err), 900),
                    )
                )

            return await ctx.error(
                ctx.locale("error_command_cant_cast", type=_type, name=name)
            )

    if getattr(error, "original", None) != None:
        if isinstance(error.original, pymongo_WriteError):
            text = ctx.locale("database_error", code=error.original.code)

        elif isinstance(error.original, discord.errors.Forbidden):
            text = ctx.locale("error_command_forbidden")

        elif isinstance(error.original, IndexError):
            text = ctx.locale("error_command_not_enough_args")

        else:
            text = ctx.locale(
                "error_unknown_error",
                exc="".join(traceback.format_tb(error.original.__traceback__)),
            )[:2048]

        await ctx.error(text)

    else:
        await ctx.error(
            ctx.locale(
                "error_unknown_error",
                exc="".join(traceback.format_tb(error.__traceback__)),
            )[:2048]
        )

    if Config.get("debug"):
        raise error
    else:
        log.error(error)
