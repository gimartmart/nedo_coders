import discord


class BaseCheck:
    __error_msg__ = "error_unknown_error"


class Checker:
    def __init__(self, ctx):
        self.ctx = ctx

    async def check(
        self,
        *checks: list[BaseCheck],
        silent: bool = False,
        ephemeral_err_msg: bool = True
    ) -> bool:
        for check in checks:
            if not await check.check(self.ctx):
                if not silent:
                    msg = check.__class__.__error_msg__
                    try:
                        await self.ctx.rembed(
                            self.ctx.locale(msg),
                            error=True,
                            ephemeral=ephemeral_err_msg,
                        )
                    except:
                        pass
                return False
        return True


class IsNotSelfCheck:
    __error_msg__ = "error_cmd_choose_not_self"

    def __init__(self, user: discord.User):
        self.user = user

    async def check(self, ctx) -> bool:
        return ctx.author != self.user


class IsNotBotCheck:
    __error_msg__ = "error_cmd_choose_not_bot"

    def __init__(self, user: discord.User):
        self.user = user

    async def check(self, ctx) -> bool:
        return not self.user.bot
