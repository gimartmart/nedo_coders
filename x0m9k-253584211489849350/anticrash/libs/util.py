import datetime
import pytz
import json
import os
import re
import discord
from libs.config import Config
from typing import Union, Any, Optional
from enum import Enum
from datetime import timedelta


class EmptyElement:
    pass


class DefaultDict(dict):
    def __init__(self, *args, hide_empty=False, **kwargs):
        self.hide_empty = hide_empty

        super().__init__(*args, **kwargs)

    def __missing__(self, key) -> str:
        if self.hide_empty:
            return ""
        return key.join("{}")


class Const:
    embed_color = 0x2F3136
    embed_color_error = 0x2F3136  # 0xFEB6B6
    maxint_ds = 9_007_199_254_740_991  # max value discord accepts
    minint_ds = -9_007_199_254_740_991  # min value discord accepts
    default_emoji = "🔳"
    response_ok_emoji = "🆗"

    dateformat = "%H:%M:%S %d.%m.%Y %Z"
    dateformat_no_s = "%H:%M %d.%m.%Y %Z"


class VoiceRegion(Enum):
    brazil = "brazil"
    hongkong = "hongkong"
    india = "india"
    japan = "japan"
    rotterdam = "rotterdam"
    russia = "russia"
    singapore = "singapore"
    southafrica = "southafrica"
    south_korea = "south-korea"
    sydney = "sydney"
    us_central = "us-central"
    us_east = "us-east"
    us_south = "us-south"
    us_west = "us-west"

    def __str__(self):
        return self.value


class Locale:
    def __init__(self, bot, lang):
        self.lang = lang
        self.bot = bot

    def locale(self, *args, **kwargs):
        return self.bot.locale(self.lang, *args, **kwargs)


class Time:
    minute = 60
    hour = 3600
    day = 86400
    week = 604800
    month = 2_592_000  # 30 days
    year = 31_536_000  # 365 days


class CachedLocales:
    _loaded = False
    translations = {}

    @classmethod
    def get(cls, _code) -> dict:
        if not cls._loaded:
            cls.load()

        return cls.translations.get(_code, {}) or {}

    @classmethod
    def load(cls):
        with open(os.getcwd() + "/cache/translations.json", encoding="utf-8") as jsf:
            cached_schemes = json.load(jsf)

        if cached_schemes.get("icecream_base"):
            translations = cached_schemes["icecream_base"]
            del cached_schemes["icecream_base"]

        else:
            translations = {}

        for scheme in cached_schemes:
            translations.update(cached_schemes[scheme])

        cls.translations = translations


def default_wait_for_msg(ctx, m, allow_no_content=False):
    return (
        m.author == ctx.author
        and m.channel == ctx.message.channel
        and (m.content or allow_no_content)
    )


def default_embed() -> discord.Embed:
    embed = discord.Embed(color=Const.embed_color)

    return embed


def gravis(x: Any) -> str:
    """
    Converts any value to a string and wraps it around three gravis (`) symbols
    """
    return f"```{x}```"


def nice_number(number: Union[float, int]) -> Union[float, int]:
    """
    Rounds the number to an integer if it is a whole number.
    """
    if number.is_integer() and str(number).endswith(".0"):
        return int(number)
    return number


def k_format(number: int, force_1k=False, allow_kk=True) -> str:
    def formatted(number: int):
        if allow_kk:
            if number >= 1_000_000:
                return f"{nice_number(round(number/1_000_000, 1))}kk"

        return f"{nice_number(round(number/1000, 1))}k"

    if number < 1000:
        if not force_1k:
            return str(number)
    return formatted(number)


def ellipsis(obj, max=-1, symbol="...", direction="right"):
    string = str(obj)

    if len(string) > max:
        if direction == "right":
            string = string[: max - len(symbol)]
            return string + symbol
        else:
            string = string[max - len(symbol) :]
            return symbol + string
    return string


def get_local_date(fmt: str = "%d.%m.%Y %H:%M:%S %Z") -> str:
    return datetime.datetime.now().strftime(fmt)


def get_local_timestamp() -> float:
    return datetime.datetime.now().timestamp()


def get_utc_timestamp() -> float:
    return datetime.datetime.now().astimezone(pytz.utc).timestamp()


def get_date(
    fmt: str = "%d.%m.%Y %H:%M:%S %Z", tz_name: str = "America/New_York"
) -> str:
    return datetime.datetime.now().astimezone(pytz.timezone(tz_name)).strftime(fmt)


def get_timestamp(tz_name: str = "America/New_York") -> float:
    return datetime.datetime.now().astimezone(pytz.timezone(tz_name)).timestamp()


def make_time(
    bot,
    lang: str,
    time: int,
    max: str = "d",
    ms_digits: int = 0,
    no_weeks: bool = False,
    default: Any = "",
    hours_as_decimal: bool = False,
    no_s=False,
) -> str:
    time = float(time)

    y = bot.locale(lang, "time_y")
    mo = bot.locale(lang, "time_mo")
    w = bot.locale(lang, "time_w")
    d = bot.locale(lang, "time_d")
    h = bot.locale(lang, "time_h")
    m = bot.locale(lang, "time_m")
    s = bot.locale(lang, "time_s")

    if ms_digits:
        seconds = round(time % 60, ms_digits)
    else:
        seconds = int(time) % 60

    time = int(time)

    minutes = time // 60 % 60
    hours = time // 3600 % 24
    days = time // 86400 % 28
    weeks = time // 604800 % 52
    months = time // 2628000 % 12
    years = time // 31536000

    if no_weeks:
        weeks = 0

    if max == "mo":
        years = 0
        months = time // 2628000

    elif max == "w":
        months = years = 0
        weeks = time // 604800

    elif max == "d":
        weeks = months = years = 0
        days = time // 86400

    elif max == "h":
        days = weeks = months = years = 0
        hours = time // 3600

    elif max == "m":
        days = 0
        weeks = 0
        hours = 0
        minutes = time // 60

    text = ""

    if years:
        text += f"{years}{y} "
    if months:
        text += f"{months}{mo} "
    if weeks:
        text += f"{weeks}{w} "
    if days:
        text += f"{days}{d} "
    if hours or hours_as_decimal:
        if hours_as_decimal:
            m_decimal = int(round(minutes / 60, 1) * 10)
            if m_decimal or hours:
                text += f"{hours}.{m_decimal}{h} "
        else:
            text += f"{hours}{h} "
    if minutes and not hours_as_decimal:
        text += f"{minutes}{m} "
    if not no_s and seconds:
        text += f"{seconds}{s} "

    return text[:-1] or default or f"0{s}"


def parse_time(
    bot,
    lang: str,
    time: str,
    to_string: bool = False,
    as_timedelta: bool = False,
    max_days: int = 60,
) -> int:
    total_locales = {}

    for l in Config.get("all_languages", []):
        for t in ("d", "h", "m", "s"):
            locale = bot.locale(l, "time_" + t)
            if total_locales.get(t) == None:
                total_locales[t] = [locale]
            else:
                total_locales[t].append(locale)

    total_time = {"d": 0, "h": 0, "m": 0, "s": 0}

    for real, types in total_locales.items():
        result = None
        for type in types:
            result = re.search(f"(\d+){type}", time)
            if not result:
                continue
            total_time[real] += int(result.group(1))

    total_seconds = 0
    total_seconds += total_time["d"] * 86400
    total_seconds += total_time["h"] * 3600
    total_seconds += total_time["m"] * 60
    total_seconds += total_time["s"]

    if as_timedelta:
        return timedelta(seconds=total_seconds)

    if to_string:
        return make_time(bot, lang, total_seconds)

    return total_seconds


def walk_dict(d, fields: str, default: Optional[Any] = None) -> Any:
    if isinstance(fields, str):
        fields = iter(f for f in fields.split(".") if f)

    try:
        f = next(fields)
    except StopIteration:
        if isinstance(d, type(EmptyElement)):
            return default
        return d

    try:
        obj = d.get(f, EmptyElement)
    except AttributeError:
        if isinstance(d, type(EmptyElement)):
            return default
        if isinstance(d, (tuple, list)):
            return walk_dict(d[int(f)], fields, default=default)
        return d

    return walk_dict(obj, fields, default=default)


def mfloor(x):
    if x % 1:
        return int(x) + 1
    return int(x)


def merge_dicts(a: dict, b: dict) -> None:
    for k in b.keys():
        item = a.get(k, EmptyElement)

        if not item is EmptyElement:
            if isinstance(item, dict):
                merge_dicts(item, b[k])
            else:
                a[k] = b[k]

        else:
            a[k] = b[k]
