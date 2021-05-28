from __future__ import annotations

from re import search
from typing import AsyncIterator, Literal
from asyncio import AbstractEventLoop, Future, sleep
from contextlib import suppress

from ujson import loads
from aiohttp import ClientSession, WSServerHandshakeError
from colorama import Fore
from pybase64 import urlsafe_b64decode

from . import obj
from .db import DB
from .obj import Message, _req
from .enum import WsStatus
from .utils import Slots, clear
from .dataclass import Msg


class Ws(Slots):
    __slots__ = [
        '_events',
        '_decoded'
    ]

    def __init__(
        self,
        loop:          AbstractEventLoop, 
        email:        'Bot.email',             # type: ignore
        password:     'Bot.password',          # type: ignore
        only_chats:   'Bot.only_chats'   = {}, # type: ignore
        ignore_chats: 'Bot.ignore_chats' = {}  # type: ignore
    ):
        self._deviceid: str               = obj.headers['NDCDEVICEID']
        self._loop:     AbstractEventLoop = loop
        self._db:       DB                = DB()
        self.futures:   list[Future]      = []
        self._msg = Message()

        self._email        = email
        self._password     = password
        self._only_chats   = only_chats
        self._ignore_chats = ignore_chats
        self._status       = WsStatus.OPEN


    async def _get_sid(self) -> str:
        """
        Get the account sid
        """

        return (await _req('post', 'g/s/auth/login', data={
            'email':    self._email,
            'secret':  f'0 {self._password}',
            'deviceID': self._deviceid,
        })).json['sid']

    async def _connect(self) -> AsyncIterator[Msg]:
        """
        Connect the websocket
        """

        async with ClientSession() as session:
            while True:
                try:
                    ws = await session.ws_connect(
                        f'wss://ws1.narvii.com/?signbody={self._deviceid}',
                        headers=obj.headers,
                    )
                    break
                except WSServerHandshakeError as e:
                    if str(e)[0] == '5':
                        clear()
                        for i in range(5):
                            print(f'Amino servers died, wait {Fore.CYAN}{5-i}{Fore.WHITE}s')
                            await sleep(1)
                            clear()

                        print(f'{Fore.GREEN}Reconnecting...{Fore.WHITE}')
                    else:
                        raise

            clear()
            self._call_events('ready')

            while self._status == WsStatus.OPEN: # for tests
                if ws.closed:
                    self._call_events('close')
                    yield WsStatus.CLOSED

                # The socket sometimes receives a frame that is not a json,
                # causing a TypeError, ignoring it does not cause any problems
                with suppress(TypeError):
                    res = await ws.receive_json(loads=loads)
                    if res['t'] == 1000:
                        yield self._msg.from_ws(res['o'])

    def _call_events(
        self,
        name: str,
        *m: list[Msg]
    ) -> None:
        """
        Calls all events with the specific name
        """

        for i in self._events[name]:
            self._loop.create_task(i(*m))

    def _fix_sid(self, sid: str) -> str:
        """
        Fix the size of the sid
        """

        # Sometimes sid can be an invalid base64,
        # causing a padding error in urlsafe_b64decode
        # Add = until sid has the len of 192 or len % 4 == 0 solve the problem
        return sid + '=' * (192 - len(sid))

    def _can_call(self, msg: Msg) -> Literal[True] | None:
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
        call:   'Bot._call',  # type: ignore
        events: 'Bot.events', # type: ignore
        bot:    'Bot'         # type: ignore
    ) -> None:
        """
        Start the bot
        """
    
        if not self._db.get_account(self._email):
            self._db.add_account(self._email, self._fix_sid(await self._get_sid()))

        sid = self._db.get_account(self._email)

        obj.headers['NDCAUTH'] = f'sid={sid}'
        self._decoded = urlsafe_b64decode(sid).decode('cp437')
        id_ = search(r'\w{8}-\w{4}-\w{4}-\w{4}-\w{12}', self._decoded,).group()

        bot.sid = sid
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
                # Reconnect
                return await self.run(call, self._events, bot)

            if self._can_call(m):
                with suppress(KeyError):
                    self._call_events(events[f'{m.type}:{m.media_type}'], m)

                if self.futures:
                    for future in self.futures:
                        future.set_result(m)
                    self.futures.clear()

                self._loop.create_task(call(m))
