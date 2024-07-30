import logging, os
import inspect
from .config import Config


class MyFilter(object):
    def __init__(self, level: int):
        self.__level = level

    def filter(self, logRecord) -> bool:
        return logRecord.levelno <= self.__level


def concat(*args) -> str:
    """
    inspect.stack()[2] because we lose 2 calls:
    lambda *a: concat(*a)
    +
    concat(*a)
    """
    try:
        fname = inspect.stack()[2].filename.rsplit("\\", 1)[1]
    except:
        fname = "<?>"

    return f"{fname} | " + " ".join(str(a) for a in args)


def logger_layer(logger: logging.Logger) -> None:
    """
    This function creates new layer (lambda functions), which
    just takes any amount of args to mimic behavior of 'print' function:

    print("value:", "test")
    logger.warn("value:", "test")

    when default logger.warn function accepts only one arg. Not handy.
    """

    def create_lambda(old):
        return lambda *a: old(concat(*a))

    for n in ("warn", "debug", "error", "critical", "info"):

        old = getattr(logger, n)

        setattr(logger, n, create_lambda(old))


def init_logger() -> logging.Logger:
    logging_level = logging.INFO
    if Config.get("debug"):
        logging_level = logging.DEBUG

    log = logging.getLogger("log")

    logging.basicConfig(format="%(levelname).1s | %(message)s")
    log.setLevel(logging_level)
    logging.getLogger("discord").setLevel(logging.CRITICAL)
    logging.getLogger("discord.http").setLevel(logging.CRITICAL)

    handler_format = logging.Formatter(
        fmt="%(asctime)s.%(msecs)03d %(levelname).1s %(name)s | %(message)s",
        datefmt="%d-%m-%y %H:%M:%S",
    )

    logger_layer(log)  # check doc.

    return log
