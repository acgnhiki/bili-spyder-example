import asyncio
import re
import time
import random
from urllib.parse import urlencode
from typing import Dict

import aiohttp
from aiohttp import ClientSession
from tenacity import (
    retry,
    wait_random,
    stop_after_delay,
    retry_if_exception_type,
)

from bili_spyder import calc_sign_async as calc_sign

__all__ = 'WebApi', 'WebApiRequestError'

class WebApiRequestError(Exception):
    pass

class WebApi:
    @staticmethod
    def _check(res_json):
        if res_json['code'] != 0:
            raise WebApiRequestError(res_json['message'])
        
    @classmethod
    @retry(stop=stop_after_delay(5),
           wait=wait_random(0, 1),
           retry=retry_if_exception_type(aiohttp.ServerConnectionError))
    async def _get(cls, session: ClientSession, *args, **kwds):
        async with session.get(*args, **kwds) as res:
            res_json = await res.json()
            cls._check(res_json)
            return res_json['data']
           
    @classmethod
    @retry(stop=stop_after_delay(5),
           wait=wait_random(0, 1),
           retry=retry_if_exception_type(aiohttp.ServerConnectionError))
    async def _post(cls, session: ClientSession, *args, **kwds):
        async with session.post(*args, **kwds) as res:
            res_json = await res.json()
            cls._check(res_json)
            return res_json['data']

    @classmethod
    async def post_enter_room_heartbeat(cls,
            session: ClientSession, csrf: str, buvid: str, uuid: str,
            room_id: int, parent_area_id: int, area_id: int) -> Dict:
        url = 'https://live-trace.bilibili.com/xlive/data-interface/v1/x25Kn/E'

        headers = {
            'Referer': f'https://live.bilibili.com/{room_id}',
            'Content-Type': 'application/x-www-form-urlencoded',
        }

        data = {
            'id': f'[{parent_area_id}, {area_id}, 0, {room_id}]',
            # 'device': '["unknown", "23333333-3333-3333-3333-333333333333"]', # LIVE_BUVID, xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx
            'device': f'["{buvid}", "{uuid}"]',
            'ts': int(time.time()) * 1000,
            'is_patch': 0,
            'heart_beat': [],
            'ua': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.163 Safari/537.36',
            'csrf_token': csrf,
            'csrf': csrf,
            'visit_id': '',
        }

        return await cls._post(session, url, headers=headers, data=urlencode(data))

    @classmethod
    async def post_in_room_heartbeat(cls,
            session: ClientSession, csrf: str, buvid: str, uuid: str,
            room_id: int, parent_area_id: int, area_id: int,
            sequence: int, interval: int, ets: int,
            secret_key: str, secret_rule: list) -> Dict:
        url = 'https://live-trace.bilibili.com/xlive/data-interface/v1/x25Kn/X'

        headers = {
            'Referer': f'https://live.bilibili.com/{room_id}',
            'Content-Type': 'application/x-www-form-urlencoded',
        }

        data = {
            'id': f'[{parent_area_id}, {area_id}, {sequence}, {room_id}]',
            # 'device': '["unknown", "23333333-3333-3333-3333-333333333333"]', # LIVE_BUVID, xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx
            'device': f'["{buvid}", "{uuid}"]',
            'ets': ets,
            'benchmark': secret_key,
            'time': interval,
            'ts': int(time.time()) * 1000,
            'ua': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.163 Safari/537.36',
        }

        data.update({
            'csrf_token': csrf,
            'csrf': csrf,
            'visit_id': '',
            's': await calc_sign(data, secret_rule),
        })

        return await cls._post(session, url, headers=headers, data=urlencode(data))

    @classmethod
    async def get_medal(cls, session: ClientSession, page=1, page_size=10) -> Dict:
        url = 'https://api.live.bilibili.com/i/api/medal'

        params = {
            'page': page,
            'pageSize': page_size,
        }

        return await cls._get(session, url, params=params)

    @classmethod
    async def get_info(cls, session: ClientSession, room_id: int) -> Dict:
        url = 'https://api.live.bilibili.com/room/v1/Room/get_info'
        return await cls._get(session, url, params={'room_id': room_id})

    @classmethod
    async def get_info_by_room(cls, session: ClientSession, room_id: int) -> Dict:
        url = 'https://api.live.bilibili.com/xlive/web-room/v1/index/getInfoByRoom'
        return await cls._get(session, url, params={'room_id': room_id})
