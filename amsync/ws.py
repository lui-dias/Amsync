from __future__ import annotations

from typing import Any, Callable, AsyncIterator, Coroutine
from asyncio import get_event_loop, AbstractEventLoop, Future
from contextlib import suppress

from ujson import dumps, loads
from aiohttp import ClientSession
from pybase64 import urlsafe_b64decode

from . import obj
from .db import DB
from .obj import Message, _req
from .enum import WsStatus

Coro_return_None = Callable[[], Coroutine[None, None, None]]
Coro_return_Message = Callable[[], Coroutine[Message, None, None]]
Coro_return_Any = Callable[[], Coroutine[Any, None, None]]


class Ws:
    def __init__(
        self,
        email:        str,
        password:     str,
        only_chats:   dict[str, list[str]] = {},
        ignore_chats: dict[str, list[str]] = {}
    ):
        self._deviceid: str               = obj.headers['NDCDEVICEID']
        self._loop:     AbstractEventLoop = get_event_loop()
        self._db:       DB                = DB()
        self.futures:   list[Future]      = []

        self._email        = email
        self._password     = password
        self._only_chats   = only_chats
        self._ignore_chats = ignore_chats


    async def _get_sid(self) -> str:
        return (await _req('post', 'g/s/auth/login', data={
            'email':    self._email,
            'secret':  f'0 {self._password}',
            'deviceID': self._deviceid,
        }))['sid']

    async def _connect(self) -> AsyncIterator[Message]:
        async with ClientSession(json_serialize=dumps) as session:
            ws = await session.ws_connect(
                f'wss://ws1.narvii.com/?signbody={self._deviceid}',
                headers=obj.headers,
            )
            self._call_events('ready')

            while True:
                if ws.closed:
                    self._call_events('close')
                    yield WsStatus.CLOSED

                # The socket sometimes receives a frame that is not a json,
                # causing a TypeError, ignoring it does not cause any problems
                with suppress(TypeError):
                    res = await ws.receive_json(loads=loads)
                    if res['t'] == 1000:
                        yield Message().from_ws(res['o'])

    def _call_events(self, event):
        for i in self._events[event]:
            self._loop.create_task(i())

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

    async def run(
        self,
        call:   Coro_return_None,
        events: dict[str, list[Coro_return_Any]],
        bot:    'Bot' # type: ignore
    ) -> None:
        if not self._db.get_account(self._email):
            self._db.add_account(self._email, await self._get_sid())

        # Sometimes sid can be an invalid base64,
        # causing a padding error in urlsafe_b64decode
        # Add = until sid has the len of 192 solve the problem
        tmp = self._db.get_account(self._email)
        sid = tmp + '=' * (192 - len(tmp))

        obj.headers['NDCAUTH'] = f'sid={sid}'
        id_ = loads(
            urlsafe_b64decode(sid[:-28])[1:] + b'}'
        )['2']

        bot.id = id_
        obj.bot_id = id_

        self._events = events
        events = {
            '0:0':   'message',
            '100:0': 'message',
            '101:0': 'join_chat',
            '102:0': 'leave_chat',
            '0:100': 'image',
        }

        async for m in self._connect():
            if m == WsStatus.CLOSED:
                return await self.run(call, self._events, bot)

            if self._can_call(m):
                with suppress(KeyError):
                    self._call_events(events[f'{m.type}:{m.media_type}'])

                if self.futures:
                    for future in self.futures:
                        future.set_result(m)
                    self.futures.clear()

                self._loop.create_task(call(m))
