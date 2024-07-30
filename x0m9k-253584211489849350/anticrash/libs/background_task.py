from libs.x3m_api import X3m_API
from libs.util import *
import cmds
from pymongo import UpdateOne
from libs.config import Config, Images, Fonts
from libs.transactions import TransactionType
from libs.awards import AwardType
from PIL import Image, ImageDraw
from io import BytesIO
from cmds.top import get_or_fetch_avatar
import time
import logging
import asyncio
import os


log = logging.getLogger("log")


async def background_task(bot, tick):
    pass
