from __future__ import annotations

import sys
from re import search
from os import environ, execl

from asyncio import (
    gather,
    wait_for,
    new_event_loop,
    iscoroutinefunction,
    run_coroutine_threadsafe,
    AbstractEventLoop,
    TimeoutError,
    Future
)
from dotenv import load_dotenv
from typing import (
    Any,
    Callable,
    Awaitable,
    Coroutine,
    Dict,
    Literal,
    NoReturn
)
from pathlib import Path
from threading import Thread
from subprocess import run

from colorama import Fore, Style, init

from .ws import Ws
from .db import _DB
from .obj import Message, Req, Community, _req, My, actual_com
from .utils import Slots, clear, one_or_list, to_list
from .dataclass import Msg, Embed, Res
from .exceptions import (
    AccountNotFoundInDotenv,
    EventIsntAsync,
    InvalidDotenvKeys,
    CommandIsntAsync,
    InvalidChatChoice,
    InvalidEvent,
    InvalidRole
)

__all__ = ['Bot']
with open(f'{Path(__file__).parent}/__init__.py') as f:
    version = search(r'[0-9]+.[0-9]+.[0-9]+', f.read()).group()

Coro_return_ws_msg = Callable[[], Coroutine[Msg, None, None]]
Coro_return_Any    = Callable[[], Coroutine[Any, None, None]]
Coro_return_None   = Callable[[], Coroutine[None, None, None]]

class Bot(Slots):
    """
    Represents the bot
    """

    __slots__ = ['_ws']

    def __init__(
        self,
        email:        str | None           = None,
        password:     str | None           = None,
        prefix:       str                  = '/',
        only_chats:   dict[str, list[str]] = {},
        ignore_chats: dict[str, list[str]] = {}
    ):
        """
        #### only_chats
        
        Dictionary of chats that the bot will *hear* the commands

        #### ignore_chats
        
        Dictionary of chats that the bot will ignore the commands
    
        #### Example:

        ```
        chats = {
            '1111111': ['00000000-0000-0000-0000-000000000000', '11111111-1111-1111-1111-111111111111'],
            '2222222': [] # Empty list means all chats`
        }

        bot = Bot(only_chats=chats)
        ```

        The bot had listened to the 00000.... 11111.... chats from the 1111111 community,
        and had listened to all the chats in the community 2222222.
        """

        init()
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

        self.id:    str                             = 'ws.run'
        self.sid:   str                             = 'ws.run'
        self.staff: Dict[str, Dict[str, list[str]]] = {}
        self._db:   _DB                             = _DB()
        self._msg:  Message                         = Message()
        self._loop: AbstractEventLoop               = new_event_loop()
        self.prefix = prefix

        self.only_chats   = only_chats
        self.ignore_chats = ignore_chats

        self.commands: dict[str, dict[str, list[str], Coro_return_None, str]] = {}
        self.events:   dict[str, list[Coro_return_None]] = {
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
        aliases: list[str] = [],
        staff:   Literal['any', 'curator', 'leader'] | None = None
    ) -> Callable[[Coro_return_ws_msg], None]:
        """
        Adds a command to the bot

        ```
        @bot.add()
        async def hi(m: Msg):
            await bot.send(f'Hi, {m.nickname}')
        ```

        Created the `hi` command
        """

        def foo(f: Coro_return_ws_msg) -> None:
            if not iscoroutinefunction(f):
                raise CommandIsntAsync('Command must be async: "async def ..."')

            if staff not in ['any', 'curator', 'leader', None]:
                raise InvalidRole(
                    f'{Fore.RED}{staff}{Fore.WHITE}. Choose between '
                    f'{Fore.CYAN}any{Fore.WHITE}, '
                    f'{Fore.CYAN}curator{Fore.WHITE}, '
                    f'{Fore.CYAN}leader{Fore.WHITE}'
                )

            self.commands[f.__name__] = {
                                    'aliases': aliases,
                                    'def': f,
                                    'help': help,
                                    'staff': staff
                                }
        return foo

    def on(self) -> Callable[[Coro_return_ws_msg], None]:
        """
        Adds a event to the bot

        ```
        @bot.on()
        async def message(m: Msg):
            print(m.text)
        ```

        Created the `message` event
        """
        def foo(f: Coro_return_ws_msg) -> None:
            if f.__name__ not in self.events:
                raise InvalidEvent(f.__name__)

            if not iscoroutinefunction(f):
                raise EventIsntAsync('Event must be async: "async def ..."')
            self.events[f.__name__].append(f)

        return foo

    async def check_update(self) -> NoReturn | None:
        """
        Checks whether lib or lib dependencies need updating

        Checks each day if the lib needs to update
        Checks every 3 days if the dependencies need to update

        If the program runs on heroku, the program will not check for updates
        """

        def try_update() -> NoReturn | None:
            if self._db.deps_need_update():
                cmd = run('pip install -U amsync', capture_output=True, text=True)
            else:
                cmd = run('pip install -U amsync --no-deps', capture_output=True, text=True)

            if cmd.returncode:
                clear()
                print(f'Error updating from version {Style.BRIGHT}{version}{Style.NORMAL} to {Fore.CYAN}{new}{Fore.WHITE}\n\n')
                print(cmd.stderr or cmd.stdout)
                sys.exit(1)

        if (
            'DYNO' not in environ   # not in heroku
            and self._db.lib_need_update()
        ):      
            new = (await Req.new('get', 'https://pypi.org/pypi/Amsync/json')).json['info']['version']
            if new != version:
                print(f'There is a new version: {Fore.CYAN}{new}{Fore.WHITE}')
                print(f'Actual version: {Style.BRIGHT}{version}{Style.NORMAL}\n')
                print(f'Do you want to update it? (Y/n) ', end='')
                if input().lower() == 'y':
                    clear()
                    print('Updating...')
                    try_update()
                    clear()
                    print('Restarting...\n')
                    execl(sys.executable, Path(__file__).absolute(), *sys.argv)
                clear()

    def run(self) -> None:
        """
        Start the bot
        """

        self._loop.run_until_complete(self.check_update())
        self._ws: Ws = Ws(
            loop         = self._loop,
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

    async def status(
        self,
        s:           Literal['on', 'off'],
        com:         str | list[str] | None = None
    ) -> Res | list[Res]:
        """
        Changes the status of the bot

        'on' the bot goes online

        'off' the bot goes offline

        By default, the bot changes the status in all communities where it is

        However you can insert the communities so it stays online or offline
        """

        assert s in ['on', 'off'], f"Choose 'on' or 'off', not {s}"

        async def foo(i):
            return await _req('post', f'x{i}/s/user-profile/{self.id}/online-status', data)

        data = {'onlineStatus': 1} if s == 'on' else {'onlineStatus': 2, 'duration': 86400} # 1 day
        com = to_list(com or [i for i in (await My.communities(False)).values()])

        return one_or_list(await gather(*[foo(i) for i in com]))

    async def send(
        self,
        *msgs: list[str],
        files: str   | None = None,
        type_: int   | None = 0,
        embed: Embed | None = None,
        reply: str   | None = None,
        com:   str   | None = None,
        chat:  str   | None = None
    ) -> Res | list[Res]:
        """
        Send a message, file, embed or reply

        #### reply

        Message id to reply
        """

        return await self._msg.send(
            *msgs,
            files = files,
            type_ = type_,
            embed = embed,
            reply = reply,
            com   = com,
            chat  = chat
        )

    async def wait_for(
        self,
        check:   Callable[[Msg], bool] = lambda _: True,
        timeout: int | None              = None
    ) -> Awaitable[Future, int | None] | None:
        """
        Wait for a message until the check is met or timeout finish

        If the condition is met, the message returns, if not returns None

        ```
        def check(_m: Msg):
            return _m.text == 'Hello'

        await bot.wait_for(check=check, timeout=10)
        ```

        Wait for a message to have the text "Hello" or pass 10 seconds    
        """

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

    def _is_alias(self, name):
        for command_name, args in self.commands.items():
            if name in args['aliases']:
                return command_name

    async def _is_staff(self, m: Msg, role: Literal['any', 'curator', 'leader']) -> bool:
        if m.com not in self.staff:
            self.staff[m.com] = await Community.staff(m.com)

        leaders  = [i['uid'] for i in self.staff[m.com]['leaders']]
        curators = [i['uid'] for i in self.staff[m.com]['curators']]

        if role == 'any':
            return m.uid in leaders + curators
        if role == 'leader':
            return m.uid in leaders
        if role == 'curator':
            return m.uid in curators

    async def _call(self, m: Msg) -> None:
        if m.text and m.text.startswith(self.prefix):
            splited      = m.text.split()
            name         = splited[0][len(self.prefix):]
            command_name = self._is_alias(name) or name

            if command_name in self.commands:
                cmd          = self.commands[command_name]
                staff        = cmd['staff']

                if not staff or await self._is_staff(m, staff):
                    if (
                        len(splited) > 1 
                        and splited[1] in (f'{self.prefix}h', f'{self.prefix}help')
                    ):
                        await self.send(cmd['help'])
                    else:
                        # Remove command name from text
                        m.text = ' '.join(splited[1:])
                        self._loop.create_task(cmd['def'](m))
