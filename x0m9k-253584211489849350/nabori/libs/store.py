from typing import Any, Optional
import keyword
import re
import string


if __name__ == "__main__":
    import datetime

    def get_local_timestamp():
        return datetime.datetime.now().timestamp()

else:
    from libs.util import get_local_timestamp


class Empty:
    pass


class DottedDict(dict):
    # written by josh-paul
    # modified by x3m4k
    # source:
    # https://github.com/josh-paul/dotted_dict
    """
    Override for the dict object to allow referencing of keys as attributes, i.e. dict.key
    """

    def __init__(self, *args, **kwargs):
        for arg in args:
            if isinstance(arg, dict):
                self._parse_input_(arg)
            elif isinstance(arg, list):
                for k, v in arg:
                    self.__setitem__(k, v)
            elif hasattr(arg, "__iter__"):
                for k, v in list(arg):
                    self.__setitem__(k, v)

        if kwargs:
            self._parse_input_(kwargs)

    def __delattr__(self, item):
        self.__delitem__(item)

    def __delitem__(self, key):
        super(DottedDict, self).__delitem__(key)
        del self.__dict__[key]

    def __getattr__(self, attr):
        try:
            return self.__dict__[attr]
        # Do this to match python default behavior
        except KeyError:
            raise AttributeError(attr)

    def __getitem__(self, key):
        return self.__dict__[key]

    def __repr__(self):
        """
        Wrap the returned dict in DottedDict() on output.
        """
        return "{0}({1})".format(
            type(self).__name__, super(DottedDict, self).__repr__()
        )

    def __setattr__(self, key, value):
        # No need to run _is_valid_identifier since a syntax error is raised if invalid attr name
        self.__setitem__(key, value)

    def __setitem__(self, key, value):
        try:
            self._is_valid_identifier_(key)
        except ValueError:
            if not keyword.iskeyword(key):
                key = self._make_safe_(key)
            else:
                raise ValueError('Key "{0}" is a reserved keyword.'.format(key))
        super(DottedDict, self).__setitem__(key, value)
        self.__dict__.update({key: value})

    def _is_valid_identifier_(self, identifier):
        return True

    def _make_safe_(self, key):
        return key

    def _parse_input_(self, input_item):
        """
        Parse the input item if dict into the dotted_dict constructor.
        """
        for key, value in input_item.items():
            if isinstance(value, dict):
                value = DottedDict(
                    **{str(k): v for k, v in value.items()},
                )
            if isinstance(value, list):
                _list = []
                for item in value:
                    if isinstance(item, dict):
                        _list.append(DottedDict(item))
                    else:
                        _list.append(item)
                value = _list
            self.__setitem__(key, value)

    def copy(self):
        """
        Ensure copy object is DottedDict, not dict.
        """
        return type(self)(self)

    def update(self, *args, **kwargs):
        """
        Override dict standard update method.
        """
        for arg in args:
            if isinstance(arg, dict):
                self._parse_input_(arg)
            elif isinstance(arg, list):
                for k, v in arg:
                    self.__setitem__(k, v)
            elif hasattr(arg, "__iter__"):
                for k, v in list(arg):
                    self.__setitem__(k, v)

        if kwargs:
            self._parse_input_(kwargs)

    def to_dict(self):
        """
        Recursive conversion back to dict.
        """
        out = dict(self)
        for key, value in out.items():
            if value is self:
                out[key] = out
            elif hasattr(value, "to_dict"):
                out[key] = value.to_dict()
            elif isinstance(value, list):
                _list = []
                for item in value:
                    if hasattr(item, "to_dict"):
                        _list.append(item.to_dict())
                    else:
                        _list.append(item)
                out[key] = _list
        return out


class LocalStore(DottedDict):
    def __init__(self, bot, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.bot = bot

    @classmethod
    def dict_to_dotted(cls, dict: DottedDict) -> DottedDict:
        d = DottedDict(dict)

        def iter_obj(obj):
            for element in obj:
                if type(element) == dict:
                    obj[element] = DottedDict(element)
                    iter_obj(element)

        iter_obj(d)

        return d

    @classmethod
    def _dotted_iter(
        cls, obj: DottedDict, name: str, create_new_fields: bool = True
    ) -> dict:
        last_obj = name.rsplit(".", 1)[0]
        for dot in last_obj.split("."):
            try:
                obj = getattr(obj, dot)
            # when getting first layer than doesn't exist
            # dict.first
            except AttributeError as err:
                if create_new_fields:
                    new_obj = DottedDict()
                    setattr(obj, dot, new_obj)
                    obj = new_obj
                else:
                    raise err

        return obj

    @classmethod
    def dotted_update(
        cls, obj: DottedDict, name: str, value: Any, create_new_fields: bool = True
    ) -> None:
        obj = cls._dotted_iter(obj, name, create_new_fields=create_new_fields)

        if isinstance(value, dict):
            value = cls.dict_to_dotted(value)

        setattr(obj, name.rsplit(".", 1)[1], value)

    @classmethod
    def dotted_delete(cls, obj: DottedDict, name: str, ignore_errors=True) -> None:
        obj = cls._dotted_iter(obj, name)

        try:
            delattr(obj, name.rsplit(".", 1)[1])
        except Exception as err:
            if not ignore_errors:
                raise

    @classmethod
    def dotted_get(
        cls,
        obj: DottedDict,
        name: str,
        default: Optional[Any] = None,
        create_new_fields: bool = True,
    ) -> Any:
        obj = cls._dotted_iter(obj, name, create_new_fields=create_new_fields)

        return getattr(obj, name.rsplit(".", 1)[1], default)

    @classmethod
    def dotted_exists(cls, obj: DottedDict, name: str) -> bool:
        obj = cls._dotted_iter(obj, name)

        return hasattr(obj, name.rsplit(".", 1)[1])

    @classmethod
    def dotted_inc(
        cls,
        obj: DottedDict,
        name: str,
        inc_value: Any,
        default_value: Any = None,
        create_new_fields: bool = True,
    ) -> None:
        prev_value = cls.dotted_get(
            obj, name, default=default_value, create_new_fields=create_new_fields
        )

        cls.dotted_update(
            obj, name, prev_value + inc_value, create_new_fields=create_new_fields
        )


class LocalStoreExpire:
    def __init__(self, bot):
        self.bot = bot
        self.expire = {}

    def add_expire(self, name: str, time_s: int) -> None:
        self.expire[name] = get_local_timestamp() + time_s

    def get_expire(self, name: str, delta: Optional[bool] = False) -> Optional[float]:
        if delta:
            return self.expire.get(name, 0) - get_local_timestamp()
        return self.expire.get(name)

    def check(self) -> None:
        ts = get_local_timestamp()
        for field in list(self.expire):
            if ts > self.expire[field]:
                if self.expire.get(field, Empty) != Empty:
                    del self.expire[field]

                if self.bot.store_exists(field):
                    self.bot.store_delete(field)

                continue


if __name__ == "__main__":
    d = {
        "name": 123,
        "mydict": {
            "myvalue": 1,
            "abc": 2,
            "dict2": {"dict1": {"real_value": [123, 321]}},
        },
    }

    converted = LocalStore.dict_to_dotted(d)

    print(converted.name)
    print(converted.mydict)
    print(converted.mydict.myvalue)
    print(converted.mydict.abc)
    print(converted.mydict.dict2)

    converted.mydict.dict2 = LocalStore.dict_to_dotted(
        {"dict_another": LocalStore.dict_to_dotted({"another_value": "hi"})}
    )

    print(converted)

    LocalStore.dotted_update(converted, "mydict.myvalue2", 4)
    LocalStore.dotted_update(converted, "mydict.myvalue", 8)

    print(converted)
    print(converted.mydict.myvalue2)

    LocalStore.dotted_delete(converted, "mydict.myvalue")

    print(converted)
    print(LocalStore.dotted_get(converted, "mydict.abc"))
    print(LocalStore.dotted_exists(converted, "mydict.myvalue"))
    print(LocalStore.dotted_exists(converted, "mydict.abc"))

    LocalStore.dotted_inc(converted, "mydict.abc", 500)
    print(converted.mydict.abc)
    print(converted)
    print(
        LocalStore.dotted_get(
            converted, "mydict.myvalue", "default value if not exists"
        )
    )

    LocalStore.dotted_inc(
        converted, "1323.abc2", 20, default_value=5, create_new_fields=True
    )

    LocalStore.dotted_inc(
        converted, "1323.abc2", 20, default_value=5, create_new_fields=True
    )
    LocalStore.dotted_inc(
        converted, "1323.abc1.12131242132", 20, default_value=5, create_new_fields=True
    )

    print(LocalStore.dotted_get(converted, "1323.abc1.12131242132"))

    print(converted)

    print("-- new field creation")

    _id = 123

    LocalStore.dotted_update(converted, f"{_id}.timings", {}, create_new_fields=True)
    LocalStore.dotted_update(
        converted, f"{_id}.timings.messages.2h", 7200, create_new_fields=True
    )

    print(LocalStore.dotted_get(converted, f"{_id}.timings"))
