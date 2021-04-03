from __future__ import annotations

from os import environ
from asyncio import (
    new_event_loop,
    run_coroutine_threadsafe,
    iscoroutinefunction,
    wait_for,
)
from dotenv import load_dotenv
from typing import Any, Callable, Awaitable, Coroutine
from pathlib import Path
from threading import Thread

from .ws import Ws
from .obj import Message
from .exceptions import AccountNotFoundInDotenv, InvalidDotenvKeys

Coro_return_Message = Callable[[], Coroutine[Message, None, None]]
Coro_return_Any = Callable[[], Coroutine[Any, None, None]]
Coro_return_None = Callable[[], Coroutine[None, None, None]]


class Bot:
    def __init__(
        self, 
        email: str | None = None, 
        password: str | None = None, 
        prefix: str = '/', 
        only_chats={}, 
        ignore_chats={}
    ):
        # load_dotenv is not identifying the .env,
        # so I use Path to get the absolute .env path
        load_dotenv(Path('.env').absolute())
        try:
            self._email = email or environ['EMAIL']
            self._password = password or environ['PASSWORD']
        except KeyError:
            raise InvalidDotenvKeys('Your .env must have the keys: EMAIL and PASSWORD')
        if not self._email or not self._password:
            raise AccountNotFoundInDotenv('Put your email and password in .env')

        self._prefix = prefix
        self._msg = Message()
        self.id = None

        if only_chats and ignore_chats:
            raise Exception(
                'Enter chats only in "only_chats" or "ignore_chats"')

        self.only_chats = only_chats
        self.ignore_chats = ignore_chats
        self.commands: dict[
            str,
            dict[
                str,
                Coro_return_Any | list[str]
            ]
        ] = {}
        self.events: dict[
            str,
            list[Coro_return_None]
        ] = {
            'ready': [],
            'close': [],
            'message': [],
            'join_chat': [],
            'leave_chat': [],
            'image': [],
        }

    def add(
        self, help='No help', aliases: list[str] = []
        # fmt: off
    ) -> Callable[
            [Coro_return_Message],
            None
        ]:
        # fmt: on
        def foo(f: Coro_return_Message) -> None:
            if not iscoroutinefunction(f):
                raise Exception('Command must be async')
            self.commands[f.__name__] = {'aliases': aliases, 'def': f, 'help': help}

        return foo

    def on(self) -> Callable[
        [Coro_return_Message],
        None
    ]:
        def foo(f: Coro_return_Message) -> None:
            if f.__name__ not in self.events:
                raise Exception(f'Invalid event: "{f.__name__}"')

            if not iscoroutinefunction(f):
                raise Exception('Event must be async')
            self.events[f.__name__].append(f)

        return foo

    def run(self) -> None:
        self._loop = new_event_loop()
        self._ws = Ws(self._email, self._password, self._loop, self.only_chats, self.ignore_chats)

        Thread(target=self._loop.run_forever).start()
        fut = run_coroutine_threadsafe(
            self._ws.run(self._call, self.events, self), self._loop
        )

        # "run_coroutine_threadsafe" does not raise an exception explicitly,
        # so it is necessary to take the exception and raise it
        try:
            fut.result()
            self._loop.stop()

        except:
            raise fut.exception()

    def restart(self):
        self._ws.close()
        self.run()

    async def send(
        self,
        *msgs: list[str],
        files: str | None = None,
        type_: int | None = 0,
        embed = None,
        com:   str | None = None,
        chat:  str | None = None,
    ) -> Awaitable[list[dict[str, Any]]]:

        return await self._msg.send(
            *msgs, files=files, type_=type_, embed=embed, com=com, chat=chat
        )

    async def wait_for(self, check=lambda _: True, timeout=None):
        future = self._loop.create_future()
        self._ws.futures.append(future)

        try:
            if check(msg := await wait_for(future, timeout)):
                return msg
            return await self.wait_for(check, timeout)
        except TimeoutError:
            del self._ws.futures[self._ws.futures.index(future)]

    async def _call(self, m: Message) -> None:
        if (
            m.text
            and m.text.startswith(self._prefix)
            and (
                (command_name := m.text.split()[0][len(self._prefix) :])
                in self.commands
            )
        ):
            # Remove command name from chat text
            m.text = ' '.join(m.text.split()[1:])
            self._loop.create_task(self.commands[command_name]['def'](m)) # type: ignore
