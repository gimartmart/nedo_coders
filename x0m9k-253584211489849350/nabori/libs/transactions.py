from enum import Enum


class TransactionType(Enum):
    timely = 0
    pay = 1
    pay_get = 2
    coinflip = 3
    coinflip_duel = 4
    admin_add = 5
    admin_set = 6
    marry = 7
    role_bought = 8
    role_bought_income = 9
    role_created = 10
    role_monthly_payment = 11
    role_extend_manual = 12
    role_renamed = 13
    role_color = 14
    role_give = 15
    minefield = 16
    inv_case_open = 17
    exchange = 18
    achievement = 19
    voice_activity_6h = 20
    agift = 21
    donate_shop = 22
    minecraft = 23  # yasno mc
    profile_image = 24
    reaction = 25
    close_game = 26
    quest_completed = 27  # quest achievement completion
    marry_loveroom = 28

    branch_salary = 100
