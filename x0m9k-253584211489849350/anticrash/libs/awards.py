from enum import Enum


class AwardType(Enum):
    marry_24h = 1  # 24 hours in marry room
    find_spider = 2
    most_active_2h = 3
    top_1_voice = 4
    businessman = 5  # 2 personal roles
    activist = 6  # vc:150h msg:2k


async def award_autocomplete(ctx):
    return [
        a.name
        for a in AwardType
        if a.name.startswith(ctx.value.lower() if ctx.value else "")
    ]
