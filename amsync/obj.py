from __future__ import annotations

from asyncio import gather
from typing import Any, Callable, NoReturn, Dict
from pathlib import Path

from aiohttp import request
from ujson import dumps, loads
from pybase64 import b64encode
from aiofiles import open as aiopen


from .exceptions import SmallReasonForBan

headers = {
    'NDCDEVICEID': '0146BD6CF162E40F7449AFF316BA524DDDE1A1C4E6D99A553F3472EC3F4CB2F6A9ED05E5100492DC76'
}
API = 'https://service.narvii.com/api/v1/'
actual_com: str | None = None
actual_chat: str | None = None
bot_id = None

Req_json = Dict[str, Any]


def exist(d: Req_json, k: str, *, in_str: bool = True):
    try:
        return str(d[k]) if in_str else d[k]
    except KeyError:
        return None


def on_limit(obj: list[Any], limit: int) -> bool:
    return True if limit and len(obj) >= limit else False


async def upload_media(file):
    return (
        await req(
            'post',
            '/g/s/media/upload',
            data=await File().get(file),
            need_dumps=False,
        )
    )['mediaValue']


async def req(
    method: str,
    url: str,
    *,
    data: dict[str, Any] | None = None,
    need_dumps=True,
    return_: str = 'json',
) -> Req_json | str | bytes:
    async def get_return(res):
        if return_ == 'json':
            return await res.json(loads=loads)
        if return_ == 'text':
            return await res.text()
        if return_ == 'file':
            return await res.read()
        raise Exception(f'Invalid return {return_}')

    async with request(
        method,
        API + url,
        data=dumps(data) if need_dumps else data,
        headers=headers,
    ) as _req:

        if not _req.ok:
            return _req.status
        return await get_return(_req)


class Message:
    __slots__ = (
        'author',
        'chat',
        'com',
        'extensions',
        'file_link',
        'has_mention',
        'id',
        'media_type',
        'mentioned_users',
        'nickname',
        'text',
        'type',
        'uid',
    )

    def from_ws(self, j: Req_json) -> Message:
        # fmt: off
        _cm: dict[str, Any] = j['chatMessage']

        global actual_chat, actual_com
        self.chat: str | None = exist(_cm, 'threadId')
        self.com:  str | None = exist(j, 'ndcId')

        actual_chat = self.chat
        actual_com = self.com

        self.extensions:  dict[str, Any] | None = exist(_cm, 'extensions', in_str=False)
        self.file_link:   str | None            = exist(_cm, 'mediaValue')
        self.has_mention: bool                  = (
                                                True
                                                if exist(self.extensions, 'mentionedArray')
                                                else False
                                            )
        self.id:              str | None       = exist(_cm, 'messageId')
        self.media_type:      str | None       = exist(_cm, 'mediaType')
        self.mentioned_users: list[str] | None = (
                                                [u['uid']
                                                for u in self.extensions['mentionedArray']]
                                                if self.has_mention
                                                else None
                                            )
        self.nickname: str | None = exist(_cm['author'], 'nickname') if 'author' in _cm else None
        self.text:     str | None = exist(_cm, 'content')
        self.type:     str | None = exist(_cm, 'type', in_str=False)
        self.uid:      str | None = exist(_cm, 'uid')

    
        return self
        # fmt: on

    def from_chat(self, j: Req_json) -> Message:
        # fmt: off
        self.author:      User | None           = User(exist(j, 'author', in_str=False))
        self.chat:        str  | None           = exist(j, 'threadId')
        self.extensions:  dict[str, Any] | None = exist(j, 'extensions', in_str=False)
        self.has_mention: bool                  = (
                                                True
                                                if exist(self.extensions, 'mentionedArray')
                                                else False
                                            )
        self.id:              str | None        = exist(j, 'messageId')
        self.mentioned_users: list[str] | None  = (
                                                [u['uid']
                                                for u in j['extensions']['mentionedArray']]
                                                if self.has_mention
                                                else None
                                            )
        self.text: str | None = exist(j, 'content')
        self.type: str | None = exist(j, 'type', in_str=False)
        return self
        # fmt: on

    class _CreateData:
        @staticmethod
        async def msg(type_, msgs):
            return [{'type': type_, 'content': i} for i in msgs]

        @staticmethod
        async def file(files):
            return [await File().process(i) for i in files]

        @staticmethod
        async def embed(embed: Embed):
            if embed.image:
                embed.image = [[100, await upload_media(embed.image), None]]
            return [
                {
                    'content': embed.msg_text,
                    'attachedObject': {
                        'link': embed.link,
                        'title': embed.title,
                        'content': embed.text,
                        'mediaList': embed.image,
                    },
                }
            ]

    async def send(
        self,
        *msgs: list[str],
        files: str | list[str] | None = None,
        type_: int | None = 0,
        embed: Embed | None = None,
        com: str | None = None,
        chat: str | None = None,
    ) -> list[Req_json]:

        com = actual_com or com
        chat = actual_chat or chat
        files = [files] if isinstance(files, str) else files

        if msgs:
            data = await self._CreateData.msg(type_, msgs)
        elif files:
            data = await self._CreateData.file(files)
        else:
            data = await self._CreateData.embed(embed)

        async def foo(i: msgs | files | list[Embed]) -> req:
            return await req(
                'post',
                f'x{com}/s/chat/thread/{chat}/message',
                data=i,
            )

        return await gather(*[foo(i) for i in data])


class Embed:
    __slots__ = ('msg_text', 'title', 'text', 'link', 'image')

    def __init__(self, msg_text, title, text, link, image=None):
        self.msg_text = msg_text
        self.title = title
        self.text = text
        self.link = link
        self.image = image


class User:
    __slots__ = (
        'bio',
        'blogs_count',
        'com',
        'comments_count',
        'created_time',
        'followers_count',
        'following_count',
        'id',
        'im_following',
        'is_online',
        'level',
        'nickname',
        'posts_count',
        'reputation',
        'role',
        'visitors_count',
    )

    def __init__(self, j: Req_json | None = None):
        # fmt: off
        if j:
            self.bio             = exist(j, 'content')
            self.blogs_count     = exist(j, 'blogsCount', in_str=False)
            self.com             = exist(j, 'ndcId')
            self.comments_count  = exist(j, 'commentsCount', in_str=False)
            self.created_time    = exist(j, 'createdTime')
            self.following_count = exist(j, 'membersCount')
            self.im_following    = (True if j['followingStatus'] == 1 else False) if exist(j, 'followingStatus') else None
            self.level           = exist(j, 'level', in_str=False)
            self.nickname        = exist(j, 'nickname')
            self.posts_count     = exist(j, 'postsCount', in_str=False)
            self.id              = exist(j, 'uid')
            self.reputation      = exist(j, 'reputation', in_str=False)
            self.role            = {0: 'member', 101: 'curator', 100: 'leader', 102: 'leader-agent'}[j['role']]
            self.visitors_count  = exist(j, 'visitoresCount', in_str=False)
        # fmt: on

    @classmethod
    async def search(
        cls, uids: str | list[str], com: str | None = None
    ) -> list[User]:

        com = actual_com or com
        uids = [uids] if not isinstance(uids, (list, tuple)) else uids

        async def foo(uid: str) -> User:
            return cls(
                (await req('get', f'x{com}/s/user-profile/{uid}'))[
                    'userProfile'
                ]
            )

        return await gather(*[foo(uid) for uid in uids])

    async def ban(self, uid, *, reason, com=None):
        com = actual_com or com
        if len(reason.split()) < 3:
            raise SmallReasonForBan('Put a reason with at least three words')

        return await req(
            'post',
            f'x{com}/s/user-profile/{uid}/ban',
            data={'reasonType': 200, 'note': {'content': reason}},
        )

    async def unban(self, uid, *, reason='', com=None):
        com = com or actual_com

        return await req(
            'post',
            f'x{com}/s/user-profile/{uid}/unban',
            data={'note': {'content': reason}} if reason else None,
        )


class File:
    def is_link(self, file: str) -> bool:
        return type(file) == str and file.startswith('http')

    async def get(self, file: str) -> bytes:
        if self.is_link(file):
            async with request('get', file) as res:
                return await res.read()

        async with aiopen(file, 'rb') as a:
            return await a.read()

    def to_b64(self, file_bytes: bytes) -> str:
        return b64encode(file_bytes).decode()

    async def process(self, file: str) -> dict[str, Any] | NoReturn:
        if not self.is_link(file) and not Path(file).exists():
            raise FileNotFoundError(file)

        ext = file.split('.')[-1]
        if ext in ('png', 'jpeg', 'jpg', 'webp'):
            return {
                'mediaType': 100,
                'mediaUploadValue': self.to_b64(await self.get(file)),
                'mediaUhqEnabled': True,
            }

        elif ext in ('mp3', 'aac', 'wav', 'm4a'):
            return {
                'type': 2,
                'mediaType': 110,
                'mediaUploadValue': self.to_b64(await self.get(file)),
                'mediaUhqEnabled': True,
            }

        elif ext == 'gif':
            return {
                'mediaType': 100,
                'mediaUploadValue': self.to_b64(await self.get(file)),
                'mediaUploadValueContentType': 'image/gif',
                'mediaUhqEnabled': True,
            }

        raise TypeError(f'Invalid file extension: {ext}')


class Chat:
    async def messages(
        self,
        *,
        check: Callable[[Message], bool] = lambda _: True,
        com: str | None = None,
        chat: str | None = None,
        start: int | None = None,
        end: int | None = None,
    ) -> list[Message.from_chat]:

        com = actual_com or com
        chat = actual_chat or chat
        messages = []

        res = await req(
            'get',
            f'x{com}/s/chat/thread/{chat}/message?v=2&pagingType=t&size=100',
        )
        token = res['paging']['nextPageToken']
        for msg_ in res['messageList']:
            if check(msg := Message().from_chat(msg_)):
                messages.append(msg)

        while True:
            res = await req(
                'get',
                f'x{com}/s/chat/thread/{chat}/message?v=2&pagingType=t&pageToken={token}&size=100',
            )
            for msg in res['messageList']:
                if check(msg := Message().from_chat(msg)):
                    messages.append(msg)

            if on_limit(messages, end):
                break

            try:
                token = res['paging']['nextPageToken']
            except KeyError:
                break

        return messages[start:end]

    async def clear(
        self,
        msgs: str | list[str] | None = None,
        check: Callable[[Message], bool] = lambda _: True,
        com: str | None = None,
        chat: str | None = None,
        start: int | None = None,
        end: int | None = None,
    ) -> list[Req_json]:

        com = actual_com or com
        chat = actual_chat or chat
        msgs = ([msgs] if not isinstance(msgs, (tuple, list)) else msgs) if msgs else [
            msg.id for msg in await self.messages(check=check, com=com, chat=chat, start=start, end=end)
        ]

        async def foo(msg):
            return await req(
                'post',
                f'x{com}/s/chat/thread/{chat}/message/{msg}/admin',
                data={'adminOpName': 102},
            )

        return await gather(*[foo(msg) for msg in msgs])

    async def members(
        self,
        check: Callable[[Message], bool] = lambda _: True,
        com: str | None = None,
        chat: str | None = None,
        start: int | None = None,
        end: int | None = None,
    ):
        com = actual_com or com
        chat = actual_chat or chat

        async def foo(i):
            res = await req(
                'get',
                f'x{com}/s/chat/thread/{chat}/member?start={i}&size=100&type=default&cv=1.2',
            )
            return [i for i in [User(i) for i in res['memberList'] if res['memberList']] if check(i)]

        members_count = (await req('get', f'x{com}/s/chat/thread/{chat}'))['thread']['membersCount']
        MAX_MEMBERS_COUNT_IN_CHAT = 1000
        return (
            await gather(
                *[foo(i) for i in range(0, MAX_MEMBERS_COUNT_IN_CHAT, 100) if i <= members_count]
            )
        )[0][start:end]

    async def join(self, chat: str, com: str | None = None):
        com = actual_com or com
        chat = [chat] if not isinstance(chat, (list, tuple)) else chat

        async def foo(i):
            return await req(
                'post', f'x{com}/s/chat/thread/{i}/member/{bot_id}'
            )

        return await gather(*[foo(i) for i in chat])

    async def leave(self, chat: str, com: str | None = None):
        com = actual_com or com
        chat = [chat] if not isinstance(chat, (list, tuple)) else chat

        async def foo(i):
            return await req(
                'delete', f'x{com}/s/chat/thread/{i}/member/{bot_id}'
            )

        return await gather(*[foo(i) for i in chat])
