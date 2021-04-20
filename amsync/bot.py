from __future__ import annotations

import sys
from os import environ, execl

from asyncio import (
    get_event_loop,
    run_coroutine_threadsafe,
    iscoroutinefunction,
    wait_for,
    AbstractEventLoop
)
from dotenv import load_dotenv
from typing import Any, Callable, Awaitable, Coroutine, NoReturn
from pathlib import Path
from threading import Thread
from subprocess import run

from ujson import loads
from aiohttp import ClientSession
from colorama import Fore, init
init()

from . import obj
from .ws import Ws
from .db import DB
from .obj import Message
from .exceptions import (
    AccountNotFoundInDotenv,
    EventIsntAsync,
    InvalidDotenvKeys,
    CommandIsntAsync,
    InvalidChatChoice,
    InvalidEvent
)

Coro_return_Message = Callable[[], Coroutine[Message, None, None]]
Coro_return_Any = Callable[[], Coroutine[Any, None, None]]
Coro_return_None = Callable[[], Coroutine[None, None, None]]

version = '0.0.28'

class Bot:
    def __init__(
        self,
        email:        str | None           = None,
        password:     str | None           = None,
        prefix:       str                  = '/',
        only_chats:   dict[str, list[str]] = {},
        ignore_chats: dict[str, list[str]] = {}
    ):
        # load_dotenv is not identifying the .env on project folder,
        # so I use Path to get the absolute .env path
        load_dotenv(Path('.env').absolute())
        try:
            self._email    = email    or environ['EMAIL']
            self._password = password or environ['PASSWORD']
        except KeyError:
            raise InvalidDotenvKeys('Your .env must have the keys: EMAIL and PASSWORD')

        if not self._email or not self._password:
            raise AccountNotFoundInDotenv('Put your email and password in .env')
        if only_chats and ignore_chats:
            raise InvalidChatChoice('Enter chats only in "only_chats" or "ignore_chats"')

        obj.clear()

        self.id:      str | None        = None
        self._db:     DB                = DB()
        self._msg:    Message           = Message()
        self._loop:   AbstractEventLoop = get_event_loop()
        self._prefix = prefix

        self.only_chats   = only_chats
        self.ignore_chats = ignore_chats

        self.commands:    dict[str, dict[str, list[str] | Coro_return_None | str]] = {}
        self.events:      dict[str, list[Coro_return_None]] = {
                                                        'ready':      [],
                                                        'close':      [],
                                                        'message':    [],
                                                        'join_chat':  [],
                                                        'leave_chat': [],
                                                        'image':      []
                                                    }

    def add(
        self,
        help:    str       = 'No help',
        aliases: list[str] = []
    ) -> Callable[[Coro_return_Message], None]:

        def foo(f: Coro_return_Message) -> None:
            if not iscoroutinefunction(f):
                raise CommandIsntAsync('Command must be async: "async def ..."')
            self.commands[f.__name__] = {
                                    'aliases': aliases,
                                    'def': f,
                                    'help': help
                                }
        return foo

    def on(self) -> Callable[[Coro_return_Message], None]:
        def foo(f: Coro_return_Message) -> None:
            if f.__name__ not in self.events:
                raise InvalidEvent(f.__name__)

            if not iscoroutinefunction(f):
                raise EventIsntAsync('Event must be async: "async def ..."')
            self.events[f.__name__].append(f)

        return foo

    async def check_update(self) -> NoReturn | None:
        if (
            'DYNO' not in environ   # not in heroku
            and self._db.lib_need_update()
        ):
            async with ClientSession(json_serialize=loads) as s:
                async with s.get('https://pypi.org/pypi/Amsync/json') as res:
                    new = (await res.json(loads=loads))['info']['version']
                    if new != version:
                        print(f'There is a new version: {Fore.CYAN}{new}{Fore.WHITE}\nDo you want to update it? (Y/n) ', end='')
                        if input().lower() == 'y':
                            obj.clear()
                            print('Updating')
                            if self._db.deps_need_update():
                                run('pip install -U --force-reinstall --no-cache amsync', capture_output=True, text=True)
                            run('pip uninstall -y amsync && pip install amsync', capture_output=True, text=True)
                            obj.clear()
                            print('Restarting...\n')
                            execl(sys.executable, Path(__file__).absolute(), *sys.argv)
                        obj.clear()

    def run(self) -> None:
        self._loop.run_until_complete(self.check_update())
        self._ws: Ws = Ws(
            email        = self._email,
            password     = self._password,
            only_chats   = self.only_chats,
            ignore_chats = self.ignore_chats
        )

        Thread(target=self._loop.run_forever).start()
        fut = run_coroutine_threadsafe(
            self._ws.run(
                call   = self._call,
                events = self.events,
                bot    = self),
            self._loop
        )

        # On error "run_coroutine_threadsafe" pauses the program as a raise Exception,
        # but does not print the exception on the screen.
        # So it is necessary to take the exception and raise it to show
        try:
            fut.result()
        except:
            raise fut.exception()

    async def send(
        self,
        *msgs: list[str],
        files: str     | None = None,
        type_: int     | None = 0,
        embed: 'Embed' | None = None, # type: ignore
        com:   str     | None = None,
        chat:  str     | None = None,
    ) -> Awaitable[list[dict[str, Any]]]:

        return await self._msg.send(
            *msgs,
            files = files,
            type_ = type_,
            embed = embed,
            com   = com,
            chat  = chat
        )

    async def wait_for(self, check=lambda _: True, timeout=None):
        future = self._loop.create_future()
        self._ws.futures.append(future)

        try:
            if check(msg := await wait_for(future, timeout)):
                return msg

            # Calls wait_for until the condition is met
            return await self.wait_for(check, timeout)
        except TimeoutError:
            # Delete the future canceled by asyncio.wait_for
            del self._ws.futures[self._ws.futures.index(future)]

    async def _call(self, m: Message) -> None:
        if (
            m.text
            and m.text.startswith(self._prefix)
            and (
                (command_name := m.text.split()[0][len(self._prefix):])
                in self.commands
            )
        ):
            # Remove command name from text
            m.text = ' '.join(m.text.split()[1:])
            self._loop.create_task(self.commands[command_name]['def'](m))
