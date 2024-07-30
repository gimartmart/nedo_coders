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
