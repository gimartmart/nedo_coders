import os
import json
from typing import Any, Optional
from PIL import Image, ImageFont


class Config:
    _config = {}

    @classmethod
    def load(cls) -> None:
        if not os.path.isfile(os.getcwd() + "/config.json"):
            return

        with open(os.getcwd() + "/config.json") as f:
            cls._config = json.load(f)

        with open(os.getcwd() + "/bot_tokens.json") as f:
            cls._config["tokens"] = json.load(f)

    # k: str because json can only store strings as keys.
    @classmethod
    def get(cls, k: str, d: Optional[Any] = None) -> Any:
        return cls._config.get(k, d)


class Images:

    _images = {}

    @classmethod
    def load_all(cls):
        with open(os.getcwd() + "/images.json", "r", encoding="utf-8") as jsf:
            data = json.load(jsf)

        for img in data:
            try:
                cls.load(img, "./img/" + data[img])
            except:  # we don't have set the logger yet
                print("ERROR: Could not load image:", data[img])
                cls.load(img, "./img/missing.png")

    @classmethod
    def load(cls, name, pt):
        cls._images[name] = Image.open(pt)

    @classmethod
    def get(cls, k, d=None, allow_fallback=True):
        img = cls._images.get(k)
        if not img:
            if allow_fallback:
                cls.load(k, "./img/missing.png")
                img = cls._images[k]
        return img or d

    @classmethod
    def get_by_path(cls, path, allow_fallback=True, relative=True):
        if relative:
            path = "./img/" + path
        cls.load(path, path)
        return cls.get(path, allow_fallback=allow_fallback)


class Fonts:

    _fonts = {}

    @classmethod
    def get_font(cls, name, size):

        res = cls._fonts.get(name + str(size))
        if not res:
            return cls._create_font(name, size)
        return res

    @classmethod
    def _create_font(cls, name, size):

        font = None

        if name.endswith(".ttf") or name.endswith(".otf"):
            font = ImageFont.truetype(font=f"./fonts/{name}", size=size)
            cls._fonts[name + str(size)] = font
        else:
            raise Exception(f'Invalid font "{name}"')

        return font
