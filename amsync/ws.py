from __future__ import annotations

from re import search
from enum import Enum
from typing import Any, Callable, AsyncIterator, Coroutine
from asyncio import TimeoutError
from contextlib import suppress

from ujson import dumps, loads
from aiohttp import ClientSession
from pybase64 import urlsafe_b64decode

from . import obj  # type: ignore
from .db import DB  # type: ignore
from .obj import Message, req  # type: ignore


Coro_return_None = Callable[[], Coroutine[None, None, None]]
Coro_return_Message = Callable[[], Coroutine[Message, None, None]]
Coro_return_Any = Callable[[], Coroutine[Any, None, None]]

class State(Enum):
    connection_closed = None
    stop_ws = None

class Ws:
    def __init__(
        self, email: str, password: str, loop, only_chats={}, ignore_chats={}
    ):
        self._deviceid = obj.headers['NDCDEVICEID']
        self._email = email
        self._password = password
        self._account = DB()
        self._loop = loop
        self._only_chats = only_chats
        self._ignore_chats = ignore_chats
        self._need_close = False
        self._msg = Message()
        self.futures = []

    async def _get_sid(self) -> str:
        data = {
            'email': self._email,
            'secret': f'0 {self._password}',
            'deviceID': self._deviceid,
        }

        return (await req('post', 'g/s/auth/login', data=data))['sid']

    async def _connect(self) -> AsyncIterator[Message]:
        async with ClientSession(json_serialize=dumps) as session:
            ws = await session.ws_connect(
                f'wss://ws1.narvii.com/?signbody={self._deviceid}',
                headers=obj.headers,
            )
            for i in self._events['ready']:
                self._loop.create_task(i())

            while True:
                if self._need_close:
                    break
                if ws.closed:
                    for i in self._events['close']:
                        self._loop.create_task(i())
                    yield State.connection_closed
                with suppress(TypeError, TimeoutError):
                    res = await ws.receive_json(loads=loads, timeout=.01)
                    if res['t'] == 1000:
                        yield self._msg.from_ws(res['o'])
        yield State.stop_ws

    def _can_call(self, msg: Message):
        if not self._only_chats and not self._ignore_chats:
            return True
            
        for community in self._only_chats:
            if (
                msg.chat in self._only_chats[community]
                or not self._only_chats[community]
                and msg.com == community
            ):
                return True

        for community in self._ignore_chats:
            if (
                msg.chat not in self._ignore_chats[community]
                or not self._ignore_chats[community]
                and msg.com != community
            ):
                return True

    def close(self):
        self._need_close = True

    async def run(
        self,
        call: Coro_return_None,
        events: dict[
            str,
            list[Coro_return_Any],
        ],
        bot,
    ) -> None:
        if not self._account.get(self._email):
            self._account.add(self._email, await self._get_sid())

        # Sometimes sid can be an invalid base64, causing a padding error in urlsafe_b64decode
        # Adding == at the end of sid solves the problem
        tmp = self._account.get(self._email)
        sid = tmp if len(tmp) == 192 else f'{tmp}=='

        obj.headers['NDCAUTH'] = f'sid={sid}'
        id_ = search(
            r'\w{8}-\w{4}-\w{4}-\w{4}-\w{12}',
            urlsafe_b64decode(sid).decode('cp437'),
        ).group(0)
        bot.id = id_
        obj.bot_id = id_
        self._events = events
        self._need_close = False

        async for m in self._connect():
            if m == State.stop_ws:
                break

            if m == State.connection_closed:
                return await self.run(call, events, bot)

            if self._can_call(m):
                with suppress(KeyError):
                    for i in {
                        '0:0': self._events['message'],
                        '100:0': self._events['message'],
                        '101:0': self._events['join_chat'],
                        '102:0': self._events['leave_chat'],
                        '0:100': self._events['image'],
                    }[f'{m.type}:{m.media_type}']:

                        self._loop.create_task(i(m))

                if self.futures:
                    for future in self.futures:
                        future.set_result(m)
                    self.futures.clear()

                self._loop.create_task(call(m))