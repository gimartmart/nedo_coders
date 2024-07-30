from libs.const_views import NaboriView
from libs.ui import FakeCtx
from libs.util import *
import cmds
from pymongo import UpdateOne
from libs.config import Config, Images, Fonts
from libs.transactions import TransactionType
from libs.awards import AwardType
from PIL import Image, ImageDraw, ImageChops, ImageFont
from io import BytesIO

# from cmds.top import get_or_fetch_avatar
import time
import logging
import asyncio
import os

from libs.x3m_api import X3m_API


def get_next_12oclock(days=0) -> int:
    next_12_oclock = datetime.datetime.now().astimezone(pytz.timezone("Europe/Moscow"))
    next_12_oclock += datetime.timedelta(
        days=days,
        hours=-next_12_oclock.hour,
        minutes=-next_12_oclock.minute,
        seconds=-next_12_oclock.second,
    )
    return int(next_12_oclock.astimezone(pytz.utc).timestamp())


log = logging.getLogger("log")


async def background_task(bot, tick):
    return
