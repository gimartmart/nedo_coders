from io import BytesIO
import discord
from discord.ext import tasks
from discord.ext.commands import slash_command
from PIL import Image, ImageDraw, ImageFont
import os
import datetime
import pytz


banner_bg = Image.open(os.getcwd() + "/img/banner/bg.gif")
banner_font = ImageFont.truetype(os.getcwd() + "/fonts/gilroy-bold.ttf", 39)

intents = discord.Intents.all()
client = discord.Client(intents=intents)

tick = 0


@client.event
async def on_ready():
    print(f"We have logged in as {client.user}")
    bg_task.start()


@tasks.loop(seconds=1)
async def bg_task():
    global tick
    tick += 1
    if tick > 60:
        tick = 1

    for guild in list(client.guilds):

        if tick % 30 == 0:
            await update_banner(guild)


async def update_banner(guild: discord.Guild, return_bytes=False):
    if not return_bytes and "BANNER" not in guild.features:
        print(f"!!! Сервер {guild.name} не имеет бустов для установки баннера")
        return

    count = sum([len(vc.members) for vc in guild.voice_channels])
    count += sum([len(sc.members) for sc in guild.stage_channels])

    bg = banner_bg

    amount_of_frames = bg.n_frames

    frames = []
    duration = []

    for i in range(amount_of_frames):
        bg.seek(i)

        duration.append(bg.info["duration"])
        frame = bg.copy().convert("RGBA")
        d = ImageDraw.Draw(frame)
        d.text(
            (368, 162), text=f"{count}", font=banner_font, fill="#FFFFFF", anchor="mm"
        )
        del d

        # frame.thumbnail((bg.size[0] // 1.5, bg.size[1] // 1.5))
        frames.append(frame.convert("RGB"))
        frame.close()

    b = BytesIO()

    frames[0].save(
        b,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        optimize=True,
        duration=duration,
        # lossless=True,
        loop=0,
    )

    # frames[0].show()
    # bg.close()
    frames[0].close()

    # b = BytesIO()

    # # bg.thumbnail((bg.size[0] // 2, bg.size[1] // 2))
    # bg.save(b, "PNG")

    if return_bytes:
        b.read()
        b.seek(0)
        return b

    await guild.edit(banner=b.getvalue())


with open(os.getcwd() + "/token.txt", encoding="utf-8") as f:
    token = f.read()

client.run(token)
