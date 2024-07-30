from enum import Enum


class AwardType(Enum):
    marry_24h = 1  # [no display] 24 hours in marry room
    # old_find_spider = 2  # [deleted]
    most_active_2h = 3  # [no display]
    # top_1_voice = 4  # [deleted]
    businessman = 5  # 2 personal roles
    activist = 6  # [no display] vc:150h msg:2k
    thx_4_supporting = 7  # for donating

    # new
    quest_1_boosted_server_2x = 50  # boosted server 2x
    quest_2_4h_activity = 51  # activity for four hours.
    quest_3_businessman = 52  # 2 personal roles in auction
    quest_4_most_active_2h = 53  # most active 2h
    quest_5_donated = 54  # donated (will be given thru /give_achievement cmd)
    quest_6_investments = 55  # buy 3 roles in /shop
    quest_7_generous = 56  # transfer 5k balance to user
    quest_8_pirate = 57  # open 5 cases simultaneously


async def award_autocomplete(ctx):
    return [
        a.name
        for a in AwardType
        if a.name.startswith(ctx.value.lower() if ctx.value else "") and a.value >= 50
    ]
