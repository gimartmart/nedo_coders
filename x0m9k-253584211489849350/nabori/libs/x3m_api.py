import aiohttp
from aiohttp.web import Response
import os
import json
from libs.config import Config
from libs.util import walk_dict
from typing import Union, List, Any, Optional
import logging
import bson


verbose = Config.get("verbose_debug")


log = logging.getLogger("log")


class X3m_API:
    def __init__(self, bot, **kwargs):
        self.session = aiohttp.ClientSession()
        self.url = Config.get("api_base_url")  # e.g. http://127.0.0.1:8000/v1
        self.bot = bot
        self.db_name = Config.get("db_name")

    # low-level
    async def request(self, req_type: str, url: str, *args, **kwargs) -> Any:
        # try:

        if verbose:
            log.debug(f"API request {req_type} {url} #a:{len(args)} #kw:{len(kwargs)}")

        return await getattr(self, req_type)(url, *args, **kwargs)
        # except:
        #     return {"message": "API FAILURE"}

    async def get(self, url: str, *args, **kwargs) -> Any:
        return await self.session.get(url, *args, **kwargs)

    async def post(self, url: str, *args, **kwargs) -> Any:
        return await self.session.post(url, *args, **kwargs)

    async def put(self, url: str, *args, **kwargs) -> None:
        raise NotImplementedError

    async def patch(self, url: str, *args, **kwargs) -> None:
        raise NotImplementedError

    async def delete(self, url: str, *args, **kwargs) -> None:
        raise NotImplementedError

    # high-level

    async def test_connection(self) -> dict:
        try:
            return await self._prepare_response(
                await self.request("get", self.url + "/")
            )
        except:
            return {"message": "API CONNECTION FAILED", "response": None, "status": 500}

    async def _prepare_response(
        self,
        req: Response,
        walk_fields: Optional[str] = None,
        only_response=False,
        return_safe_response=True,
    ) -> dict:
        res_json = {}

        try:
            res_json = await req.json()
        except:
            pass

        if req.status != 200:
            log.warning(f"API {req.url} returned {req.status} status.")

        response = res_json.get("response", None)

        if not walk_fields is None:
            response = walk_dict(response, walk_fields)

        if only_response:
            if not response and return_safe_response:
                return {}
            return response

        return {
            "message": res_json.get("message", None),
            "response": response,
            "status": req.status,
        }

    async def get_user(
        self,
        guild_id: int,
        user_id: int,
        fields: Optional[list] = [],
        get_preferences: bool = True,
        walk_to_guild: bool = True,
        only_response: bool = True,
    ) -> dict:
        json_ = {
            "db": self.db_name,
            "guild_id": guild_id,
            "user_id": bson.int64.Int64(user_id),
            "fields": fields,
            "get_preferences": get_preferences,
        }

        if verbose:
            log.debug(f"API fetched user. json: \n\t{json_}\n")

        req = await self.request(
            "get",
            self.url + "/get_user/",
            json=json_,
        )

        return await self._prepare_response(
            req,
            walk_fields=(None) if not walk_to_guild else f"{guild_id}",
            only_response=only_response,
        )

    async def get_server(
        self, guild_id: int, fields: Union[None, list] = [], only_response: bool = True
    ) -> dict:
        json_ = {
            "db": self.db_name,
            "guild_id": bson.int64.Int64(guild_id),
            "fields": fields,
        }

        if verbose:
            log.debug(f"API fetched server. json: \n\t{json_}\n")

        req = await self.request("get", self.url + "/get_server/", json=json_)

        return await self._prepare_response(req, only_response=only_response)

    async def get_translations(self, _force_no_cache: bool = False) -> dict:
        schemes = Config.get("translation_schemes", ["icecream_base"])

        json_ = {
            "db": Config.get("translation_db_name", "x3m4k_translation"),
            "schemes": schemes,
        }

        if not _force_no_cache and Config.get("cache_translations"):
            ts_json = {**json_, "only_timestamps": True}

            req_ts = await self.request(
                "get", self.url + "/get_translations/", json=ts_json
            )

            if req_ts.status != 200:
                return await self.get_translations(_force_no_cache=True)

            timestamps = (await self._prepare_response(req_ts)).get("response", {})

            to_fetch = []

            if os.path.isfile(os.getcwd() + "/cache/translations.json"):
                with open(
                    os.getcwd() + "/cache/translations.json", encoding="utf-8"
                ) as jsf:
                    try:
                        json_data = json.load(jsf)
                    except:
                        return await self.get_translations(_force_no_cache=True)

                for scheme in timestamps:
                    if (
                        json_data.get(scheme, {}).get("_meta", {}).get("last_update")
                        != timestamps[scheme]
                    ):
                        to_fetch.append(scheme)

            else:
                to_fetch = schemes

            response_result = {"message": "ok", "response": {}, "status": 200}

            if len(to_fetch) > 0:
                json_["schemes"] = to_fetch

                req = await self.request(
                    "get", self.url + "/get_translations/", json=json_
                )

                response_result = await self._prepare_response(req)

            cached = {}

            if os.path.isfile(os.getcwd() + "/cache/translations.json"):
                with open(
                    os.getcwd() + "/cache/translations.json", encoding="utf-8"
                ) as jsf:
                    cached = json.load(jsf)

            cached.update(response_result["response"])

            if Config.get("cache_translations"):
                log.debug(
                    f"Downloaded and cached {len(to_fetch)} localization(s): {', '.join(to_fetch)}\n"
                    + f'\t{len(Config.get("translation_schemes")) - len(to_fetch)} localization(s) had confirmed timestamps and were loaded locally'
                )
                os.makedirs(os.getcwd() + "/cache/", exist_ok=True)
                with open(
                    os.getcwd() + "/cache/translations.json", "w", encoding="utf-8"
                ) as jsf:
                    jsf.write(json.dumps(cached, indent=2, ensure_ascii=False))

            response_result["response"] = cached

            return response_result

        else:
            req = await self.request("get", self.url + "/get_translations/", json=json_)

            return await self._prepare_response(req)

    async def get_global_settings(self, fields: Optional[List[str]] = None) -> dict:
        if verbose:
            log.debug(f"API fetched global settings. Fields: {fields}")

        json_ = {"db": self.db_name, "fields": fields}

        req = await self.request("get", self.url + "/get_global_settings/", json=json_)

        return await self._prepare_response(req, only_response=True)

    async def add_translation(
        self, scheme_name: str, language: str, code: str, translation: str
    ) -> int:
        json_ = {
            "db": Config.get("translation_db_name"),
            "scheme_name": scheme_name,
            "language": language,
            "code": code,
            "translation": translation,
        }

        req = await self.request("post", self.url + "/add_translation/", json=json_)

        return req.status

    async def update_server(
        self,
        guild_id: int,
        upsert: bool = True,
        **fields,
    ) -> dict:
        json_ = {
            "db": self.db_name,
            "guild_id": bson.int64.Int64(guild_id),
            "update": {
                "fields": fields,
                "upsert": upsert,
            },
        }

        if verbose:
            log.debug(f"API update_server, update:\n\t{json_}\n")

        req = await self.request("post", self.url + "/update_server/", json=json_)

        updated_settings = False
        for f in fields:
            for key in fields[f]:
                if key.startswith("settings."):
                    updated_settings = True
                    break

        if updated_settings:
            # unvalidate settings, because we changed them.
            if verbose:
                log.debug(f"API update_server unvalidate settings for gid {guild_id}")
            await self.bot.cache_server_settings(guild_id)

        return await self._prepare_response(req)

    async def update_user(
        self,
        guild_id: int,
        user_id: int,
        fields: Union[dict, None] = None,
        fields_guild: Union[dict, None] = None,
        upsert: bool = True,
    ) -> int:
        json_ = {
            "db": self.db_name,
            "guild_id": guild_id,
            "user_id": bson.int64.Int64(user_id),
            "update": {
                "fields": fields,
                "fields_guild": fields_guild,
                "upsert": upsert,
            },
        }

        if verbose:
            log.debug(f"API update_user, update:\n\t{json_}\n")

        req = await self.request("post", self.url + "/update_user/", json=json_)

        return req.status

    async def aggregate(
        self,
        aggregate: Union[list, tuple],
        collection: str,
        list_length: Optional[int] = None,
        to_int64_fields: Optional[List[str]] = None,
    ) -> dict:
        json_ = {
            "db": self.db_name,
            "aggregate": aggregate,
            "length": list_length,
            "collection": collection,
            "to_int64_fields": to_int64_fields,
        }

        if verbose:
            log.debug(f"API aggregate, aggregate:\n\t{json_}\n")

        req = await self.request("post", self.url + "/aggregate/", json=json_)

        return await self._prepare_response(req)

    async def count_documents(
        self,
        pattern: dict,
        collection: str,
    ) -> int:
        json_ = {
            "db": self.db_name,
            "pattern": pattern,
            "collection": collection,
        }

        if verbose:
            log.debug(f"API count_documents, data:\n\t{json_}\n")

        req = await self.request("post", self.url + "/count_documents/", json=json_)

        return (await self._prepare_response(req)).get("response") or 0

    async def query(
        self,
        method: str,
        collection: str,
        data: list,
        to_int64_fields: Optional[List[str]] = None,
    ) -> Any:
        """
        Example:
            method = "find_one"
            data = [{"_id": 123}]
        """
        json_ = {
            "method": method,
            "db": self.db_name,
            "collection": collection,
            "data": data,
            "to_int64_fields": to_int64_fields,
        }

        if verbose:
            log.debug(f"API query, data:\n\t{json_}\n")

        req = await self.request("post", self.url + "/query/", json=json_)

        return (await self._prepare_response(req)).get("response")
