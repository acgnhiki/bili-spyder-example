#!/usr/bin/env python3
import re
import json
import time
import uuid
import logging
import argparse
import asyncio
from datetime import datetime
from collections import namedtuple
from asyncio import CancelledError
from concurrent.futures import ProcessPoolExecutor

import aiohttp
import toml
from colorama import init, deinit, Fore, Back, Style
from bili_spyder import set_executor

from api import WebApi

async def get_info(session, room_id):
    try:
        info = await WebApi.get_info(session, room_id)
    except CancelledError:
        raise
    except Exception as e:
        info = await WebApi.get_info_by_room(session, room_id)
        info = info['room_info']

    return info

async def medals(session):
    page = 1

    while True:
        data = await WebApi.get_medal(session, page=page)
        page_info = data['pageinfo']
        assert page == page_info['curPage']

        for medal in data['fansMedalList']:
            yield medal

        if page < page_info['totalpages']:
            page += 1
        else:
            break

def extract_csrf(cookie):
    try:
        return re.search(r'bili_jct=([^;]+);', cookie).group(1)
    except Exception:
        return None

def extract_buvid(cookie):
    try:
        return re.search(r'LIVE_BUVID=([^;]+);', cookie).group(1)
    except Exception:
        return None

async def obtain_buvid(cookie):
    async with aiohttp.request('GET', 'https://live.bilibili.com/3',
                               headers={'Cookie': cookie}) as res:
        return extract_buvid(str(res.cookies['LIVE_BUVID']))

class User:
    count = 1

    def __init__(self, name, cookie, csrf, buvid, uuid):
        cls = self.__class__
        self.name = name
        self.num = cls.count
        cls.count += 1
        self.cookie = cookie
        self.csrf = csrf
        self.uuid = uuid
        self.buvid = buvid

class DailyTask:
    async def run(self):
        deviation = 60 # tolerated deviation

        while True:
            try:
                seconds = self.seconds_to_tomorrow() - deviation
                await asyncio.wait_for(self.do_work(), timeout=seconds)
            except asyncio.TimeoutError:
                self.timeout_handler()

            seconds = self.seconds_to_tomorrow() + deviation
            await self.sleep(seconds)

    async def do_work(self):
        pass

    def timeout_handler(self):
        pass

    @staticmethod
    def seconds_to_tomorrow():
        now = datetime.now()
        delta = now.replace(hour=23, minute=59, second=59) - now
        return delta.total_seconds() + 1

    @staticmethod
    async def sleep(seconds):
        ts = datetime.now().timestamp() + seconds

        while datetime.now().timestamp() <= ts:
            await asyncio.sleep(300)

RoomInfo = namedtuple('RoomInfo', 'room_id, parent_area_id, area_id')

class SmallHeartTask(DailyTask):
    def __init__(self, user: User):
        self.user = user
        self.MAX_HEARTS_PER_DAY = 24
        self.MAX_CONCURRENT_ROOMS = self.MAX_HEARTS_PER_DAY
        self.HEART_INTERVAL = 300

    def timeout_handler(self):
        logger.warning(f'今天小心心任务未能完成（用户{self.user.num}：{self.user.name}）')

    async def do_work(self):
        uname = self.user.name
        num = self.user.num
        MAX_HEARTS_PER_DAY = self.MAX_HEARTS_PER_DAY

        headers = {
            'Referer': 'https://live.bilibili.com',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.116 Safari/537.36',
            'Cookie': self.user.cookie,
        }

        try:
            logger.info(f'开始今天的小心心任务（用户{num}：{uname}）')
            self.session = session = aiohttp.ClientSession(headers=headers)
            # self.session = session = aiohttp.ClientSession(headers=headers, trust_env=True)

            room_infos = []
            count = 0

            async for m in medals(session):
                info = await get_info(session, m['roomid'])
                room_id = info['room_id'] # ensure not the short id
                area_id = info['area_id']
                parent_area_id = info['parent_area_id']
                room_info = RoomInfo(room_id, parent_area_id, area_id)

                if parent_area_id == 0 or area_id == 0:
                    logger.warning(f'Invalid room info（用户{num}：{uname}）: {room_info}')
                    continue

                room_infos.append(room_info)
                count += 1

                if count == self.MAX_CONCURRENT_ROOMS:
                    break

            if len(room_infos) == 0:
                logger.warning(f'一个勋章都没有~结束任务（用户{num}：{uname}）')
                return

            self.queue = queue = asyncio.Queue(MAX_HEARTS_PER_DAY)

            for i in range(1, MAX_HEARTS_PER_DAY + 1):
                queue.put_nowait(i)

            dispatcher = asyncio.create_task(self.dispatch(room_infos))

            await queue.join()
            logger.info(f'今天小心心任务已完成（用户{num}：{uname}）')
        except CancelledError:
            raise
        finally:
            try:
                dispatcher.cancel()
            except Exception:
                pass

            try:
                for task in self.tasks:
                    task.cancel()
            except Exception:
                pass

            await session.close()
            self.queue = None
            self.tasks = None
            self.session = None

    async def dispatch(self, room_infos):
        uname = self.user.name
        num = self.user.num
        self.tasks = tasks = []

        for room_info in room_infos:
            task = asyncio.create_task(self.post_heartbeats(*room_info))
            tasks.append(task)
            logger.debug(f'{room_info.room_id}号直播间心跳任务开始（用户{num}：{uname}）')

    async def post_heartbeats(self, room_id, parent_area_id, area_id):
        session = self.session
        csrf = self.user.csrf
        buvid = self.user.buvid
        uuid = self.user.uuid
        uname = self.user.name
        num = self.user.num
        queue = self.queue

        while True:
            sequence = 0

            try:
                result = await WebApi.post_enter_room_heartbeat(session, csrf, buvid, uuid, room_id, parent_area_id, area_id)
                logger.debug(f'进入{room_id}号直播间心跳已发送（用户{num}：{uname}）')
                logger.debug(f'进入{room_id}号直播间心跳发送结果（用户{num}：{uname}）: {result}')

                while True:
                    sequence += 1
                    interval = result['heartbeat_interval']
                    logger.debug(f'{interval}秒后发送第{sequence}个{room_id}号直播间内心跳（用户{num}：{uname}）')
                    await asyncio.sleep(interval)

                    result = await WebApi.post_in_room_heartbeat(
                        session, csrf, buvid, uuid,
                        room_id, parent_area_id, area_id,
                        sequence, interval,
                        result['timestamp'],
                        result['secret_key'],
                        result['secret_rule'],
                    )

                    logger.debug(f'第{sequence}个{room_id}号直播间内心跳已发送（用户{num}：{uname}）')
                    logger.debug(f'第{sequence}个{room_id}号直播间内心跳发送结果（用户{num}：{uname}）: {result}')

                    assert self.HEART_INTERVAL % interval == 0, interval
                    heartbeats_per_heart = self.HEART_INTERVAL // interval

                    if sequence % heartbeats_per_heart == 0:
                        n = queue.get_nowait()
                        logger.info(f'获得第{n}个小心心（用户{num}：{uname}）')
                        queue.task_done()
            except asyncio.QueueEmpty:
                logger.debug(f'小心心任务已完成, {room_id}号直播间心跳任务终止。（用户{num}：{uname}）')
                break
            except CancelledError:
                logger.debug(f'{room_id}号直播间心跳任务取消（用户{num}：{uname}）')
                raise
            except Exception as e:
                if sequence == 0:
                    logger.error(f'进入{room_id}号直播间心跳发送异常（用户{num}：{uname}）: {repr(e)}')
                else:
                    logger.error(f'第{sequence}个{room_id}号直播间内心跳发送异常（用户{num}：{uname}）: {repr(e)}')

                delay = 60
                logger.info(f'{delay}秒后重试{room_id}号直播间心跳任务（用户{num}：{uname}）')
                await asyncio.sleep(delay)

class ConsoleHandler(logging.StreamHandler):
    def __init__(self, stream=None):
        super().__init__(stream)

    def emit(self, record):
        level = record.levelno
        if level == logging.DEBUG:
            self.stream.write(Fore.GREEN)
        elif level == logging.WARNING:
            self.stream.write(Fore.YELLOW)
        elif level == logging.ERROR:
            self.stream.write(Fore.RED)
        elif level == logging.CRITICAL:
            self.stream.write(Fore.WHITE + Back.RED + Style.BRIGHT)

        super().emit(record)

        if level != logging.INFO:
            self.stream.write(Style.RESET_ALL)
            self.stream.flush()

def configure_logging(*, name='root', filename='logging.log', debug=False):
    global logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s')
    # logging to console
    console_handler = ConsoleHandler()
    console_handler.setLevel(logging.DEBUG if debug else logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    # logging to file
    # ...

def get_args():
    parser = argparse.ArgumentParser(description='')
    parser.add_argument('--debug', action='store_true',
        help='enable logging debug information')
    args = parser.parse_args()
    return args

async def main(args):
    init()
    configure_logging(debug=args.debug)
    user_config = toml.load('./conf/user.toml')
    tasks = []

    for u in user_config['users']:
        name = u['username']
        cookie = u['cookie']
        csrf = extract_csrf(cookie)
        buvid = extract_buvid(cookie) or await obtain_buvid(cookie)
        user = User(name, cookie, csrf, buvid, uuid.uuid4())
        task = asyncio.create_task(SmallHeartTask(user).run())
        tasks.append(task)

    try:
        e = ProcessPoolExecutor()
        set_executor(e)
        await asyncio.wait(tasks)
    finally:
        set_executor(None)
        e.shutdown(True)
        deinit()

if __name__ == '__main__':
    if hasattr(asyncio, 'run'):
        try:
            asyncio.run(main(get_args()))
        except KeyboardInterrupt:
            pass
    else:
        if not hasattr(asyncio, 'create_task'):
            asyncio.create_task = asyncio.ensure_future

        if not hasattr(asyncio, 'get_running_loop'):
            asyncio.get_running_loop = asyncio.get_event_loop

        try:
            loop = asyncio.get_event_loop()
            loop.run_until_complete(main(get_args()))
        except KeyboardInterrupt:
            pass
        finally:
            loop.close()
