from __future__ import annotations

from uuid import uuid4
from typing import (
    Any,
    Callable,
    Literal,
    NoReturn,
    Dict
)
from pathlib import Path
from asyncio import gather

from ujson import dumps, dump, load
from aiohttp import request
from filetype import guess_mime
from pybase64 import b64encode

from .enum import MediaType
from .utils import (
    get_value,
    words,
    on_limit,
    fix_ascii,
    to_list,
    one_or_list
)
from .dataclass import (
    Res,
    Reply,
    Msg,
    ChatMsg,
    Embed,
    DataUser,
    DataChat
)
from .exceptions import (
    EmptyCom,
    SmallReasonForBan,
    AminoSays
)

__all__ = [
    'Req',
    'User',
    'File',
    'Chat',
    'Community',
    'My'
]

ignore_codes = [
    1628 # Sorry, you cannot pick this member.. | Chat.config
]
headers: dict[str, str] = {'NDCDEVICEID': '0184a516841ba77a5b4648de2cd0dfcb30ea46dbb4e911a6ed122578b14c7b662c59f9a2c83101f5a1'}
actual_com:  str | None = None
actual_chat: str | None = None
bot_id:      str | None = None
API = 'https://service.narvii.com/api/v1/'


class Req:
    async def new(
        method:  str,
        url:     str,
        **kwargs
    ) -> Res:
        """
        Create a request

        **kwargs are the extra arguments of aiohttp.request
        """

        async with request(
            method  = method,
            url     = url,
            **kwargs
        ) as res:
            return await Res._make(res)

async def _req(
    method:     str,
    url:        str,
    data:       dict[str, Any] | None = None,
    need_dumps: bool                  = True
) -> Res:
    """
    Create a request for the amino api

    Headers are automatically inserted into the request

    #### need_dumps
    If need use ujson.dumps on the data
    """

    res = await Req.new(
        method  = method,
        url     = API + url,
        data    = dumps(data) if need_dumps else data,
        headers = headers
    )

    api_status_code = res.json['api:statuscode']

    if not res.ok and api_status_code and api_status_code not in ignore_codes:
        raise AminoSays(f"{res.json['api:message']}. Code: {api_status_code}")
    return res


async def upload_media(file: str) -> str:
    """
    Send a file to be used when posting a blog

    Returns the file link
    """

    return (
        await _req(
            'post',
            '/g/s/media/upload',
            await File.get(file),
            False,
        )
    ).json['mediaValue']

async def upload_chat_bg(file: str) -> str:
    """
    Send a file to be used as chat background

    Returns the file link
    """

    return (
        await _req(
            'post',
            'g/s/media/upload/target/chat-background',
            await File.get(file),
            False,
        )
    ).json['mediaValue']

async def upload_chat_icon(file: str) -> str:
    """
    Send a file to be used as chat icon

    Returns the file link
    """

    return (
        await _req(
            'post',
            'g/s/media/upload/target/chat-cover',
            await File.get(file),
            False,
        )
    ).json['mediaValue']


class Message:
    def from_ws(self, j: Dict[str, Any]) -> Msg:
        """
        Returns a Msg containing the information from the websocket message
        
        Update actual_com and actual_chat with the chat and community of the message received
        """

        global actual_chat, actual_com

        actual_chat = get_value(j, 'chatMessage', 'threadId', convert=str)
        actual_com  = get_value(j, 'ndcId', convert=str)

        return Msg._make(j)

    def from_chat(self, j: Dict[str, Any]) -> ChatMsg:
        """
        Returns a ChatMsg containing information from Chat.messages messages
        """

        return ChatMsg._make(j)

    class _CreateData:
        """
        Stores methods for creating Message.send data
        """

        async def msg(
            type:  int,
            msgs:  list[str],
            reply: Reply
        ) -> list[Dict[str, Any]]:
            """
            Creates the data for sending a message
            """

            return [
                {'type': type, 'content': i, 'replyMessageId': reply}
                if reply
                else {'type': type, 'content': i}
                for i in msgs
            ]

        async def file(files: list[str | bytes]) -> list[Dict[str, Any]]:
            """
            Creates the data for sending a file
            """

            return [await File.process(i) for i in files]

        async def embed(embed: Embed) -> list[Dict[str, Any]]:
            """
            Creates the data for sending a embed
            """

            if embed.image:
                embed.image = [[100, await upload_media(embed.image), None]]
            return [
                {
                    'content': embed.msg_text,
                    'attachedObject': {
                        'link':      embed.link,
                        'title':     embed.title,
                        'content':   embed.text,
                        'mediaList': embed.image,
                    },
                }
            ]

    async def send(
        self,
        *msgs: list[str],
        files: str   | list[str] | None = None,
        type_: int   | None             = 0,
        embed: Embed | None             = None,
        reply: str   | None             = None,
        com:   str   | None             = None,
        chat:  str   | None             = None,
    ) -> Res | list[Res]:
        """
        Send a message, file, embed or reply

        #### reply

        Message id to reply
        """

        com   = com or actual_com
        chat  = chat or actual_chat
        files = to_list(files)

        if msgs:
            data = await self._CreateData.msg(type_, msgs, reply)
        elif files:
            data = await self._CreateData.file(files)
        else:
            data = await self._CreateData.embed(embed)

        async def foo(i) -> Res:
            return await _req(
                'post',
                f'x{com}/s/chat/thread/{chat}/message',
                data=i
            )

        return one_or_list(await gather(*[foo(i) for i in data]))


class User:
    async def search(
        uids: str | list[str],
        com:  str | None = None
    ) -> DataUser | list[DataUser]:
        """
        Get profile information for a community user
        """

        com = com or actual_com
        uids = to_list(uids)

        async def foo(uid: str) -> DataUser:
            return DataUser._make((await _req('get', f'x{com}/s/user-profile/{uid}')).json['userProfile'])

        return one_or_list(await gather(*[foo(uid) for uid in uids]))

    async def ban(
        uid:    str,
        *,
        reason: str,
        com:    str | None = None
    ) -> Res:
        """
        Ban a user
        """

        if words(reason) < 3:
            raise SmallReasonForBan('Put a reason with at least three words')

        return await _req(
            'post',
            f'x{com or actual_com}/s/user-profile/{uid}/ban',
            data={'reasonType': 200, 'note': {'content': reason}},
        )

    async def unban(
        uid:    str,
        *,
        reason: str        = '',
        com:    str | None = None
    ) -> Res:
        """
        Unban a user
        """

        return await _req(
            'post',
            f'x{com or actual_com}/s/user-profile/{uid}/unban',
            data={'note': {'content': reason}} if reason else None,
        )


class File:
    """
    Stores methods for handling a file
    """

    def type(file: str | bytes) -> Literal[MediaType.LINK, MediaType.BYTES, MediaType.PATH]:
        """
        Checks whether the file is a link, bytes or path
        """

        if isinstance(file, str) and file.startswith('http'):
            return MediaType.LINK

        if isinstance(file, bytes):
            return MediaType.BYTES

        return MediaType.PATH

    async def get(file: str | bytes) -> bytes:
        """
        Returns the bytes of a file

        If the file is a link, download the file
        """

        type = File.type(file)

        if type == MediaType.LINK:
            async with request('get', file) as res:
                return await res.read()

        if type == MediaType.BYTES:
            return file

        with open(file, 'rb') as f:
            return f.read()

    def b64(file_bytes: bytes) -> str:
        """
        Convert bytes to base64
        """

        return b64encode(file_bytes).decode()

    async def process(file: str | bytes) -> dict[str, Any] | NoReturn:
        """
        Returns the data to be used Message.send
        """

        if (
            File.type(file) not in (MediaType.LINK, MediaType.BYTES)
            and not Path(file).exists()
        ):
            raise FileNotFoundError(file)

        b = await File.get(file)
        b64 = File.b64(b)
        type = (guess_mime(b) or 'audio/mp3').split('/')

        if type[-1] == 'gif':
                return {
                'mediaType': 100,
                'mediaUploadValue': b64,
                'mediaUploadValueContentType': 'image/gif',
                'mediaUhqEnabled': True,
            }

        if type[0] == 'image':
            return {
                'mediaType': 100,
                'mediaUploadValue': b64,
                'mediaUhqEnabled': True,
            }

        if type[-1] == 'mp3':
            return {
                'type': 2,
                'mediaType': 110,
                'mediaUploadValue': b64,
                'mediaUhqEnabled': True,
            }


class Chat:
    async def search(
        chat: str | None = None,
        com:  str | None = None
    ) -> DataChat:
        """
        Search for chat information
        """

        return DataChat._make((await _req('get', f'x{com or actual_com}/s/chat/thread/{chat or actual_chat}')).json)

    async def messages(
        check: Callable[[ChatMsg], bool] = lambda _: True,
        start: int | None = None,
        end:   int | None = None,
        com:   str | None = None,
        chat:  str | None = None,
    ) -> list[ChatMsg]:
        """
        Returns a list containing the most recent to the oldest messages in a chat

        ### check
        ```
        def check(m: ChatMsg):
            return m.level > 8

        await Chat.messages(check=check)
        ```

        Get all messages from people with a level > 8

        ### start, end
        ```
        msgs = (await Chat.messages())[10: 100]
            
        msgs = await Chat.messages(start=10, end=100)
        ```

        The two are the same, the advantage of the second way is that the first gets all the messages and then gets the 10-100 messages

        The second gets only 10-100 messages instead of getting all, it is faster
        """

        com = com or actual_com
        chat = chat or actual_chat
        messages = []

        res = await _req(
            'get',
            f'x{com}/s/chat/thread/{chat}/message?v=2&pagingType=t&size=100',
        )
        token = res.json['paging']['nextPageToken']
        for msg_ in res.json['messageList']:
            if check(msg := MESSAGE.from_chat(msg_)):
                messages.append(msg)

        while True:
            res = await _req(
                'get',
                f'x{com}/s/chat/thread/{chat}/message?v=2&pagingType=t&pageToken={token}&size=100',
            )
            for msg in res.json['messageList']:
                if check(msg := MESSAGE.from_chat(msg)):
                    messages.append(msg)

            if on_limit(messages, end):
                break

            try:
                token = res.json['paging']['nextPageToken']
            except KeyError:
                break

        return messages[start:end]

    async def clear(
        msgs:  str | list[str] | None    = None,
        check: Callable[[ChatMsg], bool] = lambda _: True,
        com:   str | None = None,
        chat:  str | None = None,
        start: int | None = None,
        end:   int | None = None,
    ) -> Res | list[Res]:
        """
        Delete chat messages

        ## If msgs == None, it will delete all chat messages

        ### msgs
        Message ids to be deleted

        ### check
        ```
        def check(m: ChatMsg):
            return m.level > 8

        await Chat.messages(check=check)
        ```

        Delete all messages from people with a level > 8

        ### start, end
        Explanation in Chat.message
        """

        com = com or actual_com
        chat = chat or actual_chat
        msgs = (
            to_list(msgs)
            if msgs
            else [
                msg.id for msg in await Chat.messages(
                    check=check, com=com, chat=chat, start=start, end=end
                )
            ]
        )

        async def foo(msg):
            return await _req(
                'post',
                f'x{com}/s/chat/thread/{chat}/message/{msg}/admin',
                data={'adminOpName': 102},
            )

        return one_or_list(await gather(*[foo(msg) for msg in msgs]))

    async def members(
        check: Callable[[DataUser], bool] = lambda _: True,
        com:   str | None = None,
        chat:  str | None = None,
        start: int | None = None,
        end:   int | None = None,
    ) -> list[DataUser]:
        """
        Returns members of a chat

        ### check
        ```
        def check(m: DataUser):
            return 'L' in m.nickname 

        await Chat.members(check=check)
        ```

        Get all members that have 'L' in the nickname

        ### start, end
        ```
        msgs = (await Chat.members())[10: 100]
            
        msgs = await Chat.members(start=10, end=100)
        ```

        The two are the same, the advantage of the second way is that the first gets all the members and then gets the 10-100 members

        The second gets only 10-100 members instead of getting all, it is faster
        """

        com = com or actual_com
        chat = chat or actual_chat

        async def foo(i):
            res = await _req(
                'get',
                f'x{com}/s/chat/thread/{chat}/member?start={i}&size=100&type=default&cv=1.2',
            )
            return [
                i for i in [
                    DataUser._make(i) for i in res.json['memberList'] if res.json['memberList']
                ]
                if check(i)
            ]

        members_count = (await _req(
            'get', f'x{com}/s/chat/thread/{chat}'
        )).json['thread']['membersCount']

        MAX_MEMBERS_COUNT_IN_CHAT = 1000
        return (
            await gather(
                *[
                    foo(i) for i in range(0, MAX_MEMBERS_COUNT_IN_CHAT, 100)
                    if i <= members_count
                ]
            )
        )[0][start:end]

    async def join(
        chats: str | list[str],
        com:   str | None = None
    ) -> Res | list[Res]:
        """
        Enter a chat
        """

        async def foo(i):
            return await _req(
                'post', f'x{com or actual_com}/s/chat/thread/{i}/member/{bot_id}'
            )

        return one_or_list(await gather(*[foo(i) for i in to_list(chats)]))

    async def leave(
        chats: str | list[str],
        com:   str | None = None
    ) -> Res | list[Res]:
        """
        Leave a chat
        """

        async def foo(i):
            return await _req(
                'delete', f'x{com or actual_com}/s/chat/thread/{i}/member/{bot_id}'
            )

        return one_or_list(await gather(*[foo(i) for i in to_list(chats)]))

    async def create(
        name:           str,
        text:           str | None  = None,
        bg:             str | bytes = None,
        icon:           str | bytes = None,
        only_fans:      bool        = False,
        invite_members: list[str]   = [],
        com:            str | None  = None
    ) -> Res:
        """
        Create a chat
        """

        img = [100, await upload_chat_bg(bg), None] if bg else bg
        data = {
            'backgroundMedia': img,
            'extensions': {
                'bm': img,
                'fansOnly': only_fans
            },
            'title': name,
            'content': text,
            'icon': await upload_chat_icon(icon) if icon else icon,
            'inviteeUids': invite_members,

            # need this to work
            'type': 2,
            'eventSource': 'GlobalComposeMenu'
        }

        return await _req('post', f'x{com or actual_com}/s/chat/thread', data=data)

    async def delete(
        chat: str | None = None,
        com:  str | None = None
    ) -> Res:
        """
        Delete a chat
        """

        return await _req('delete', f'x{com or actual_com}/s/chat/thread/{chat or actual_chat}')

    async def edit(
        name:               str  | None         = None,
        text:               str  | None         = None,
        bg:                 str  | bytes | None = None,
        pin:                bool | None         = None,
        announcement:       str  | None         = None,
        only_view:          bool | None         = None,
        members_can_invite: bool | None         = None,
        can_send_coins:     bool | None         = None,
        change_adm_to:      str  | None         = None,
        com:                str  | None         = None,
        chat:               str  | None         = None
    ) -> None:
        """
        Edit a chat
        """

        com = com or actual_com
        chat = chat or actual_chat

        info = await Chat.search(chat=chat)
        if name or text:
            data = {
                'extensions': {
                    'bm': [100, await upload_chat_bg(bg), None] if bg else bg,
                    'fansOnly': info.only_fans
                },
                'title': name or info.name,
                'content': text or info.text,
                'icon': await upload_chat_icon(info.icon) if info.icon else info.icon,

                # need this to work
                'type': 2,
                'eventSource': 'GlobalComposeMenu'
            }
            await _req('post', f'x{com}/s/chat/thread/{chat}', data=data)


        if bg:
            await _req('post', f'x{com}/s/chat/thread/{chat}/member/{bot_id}/background', data=await File.process(bg))
        elif bg == False:
            await _req('delete', f'x{com}/s/chat/thread/{chat}/member/{bot_id}/background')

        if pin:
            await _req('post', f'x{com}/s/chat/thread/{chat}/pin')
        elif pin == False:
            await _req('post', f'x{com}/s/chat/thread/{chat}/unpin')

        if announcement:
            await _req('post', f'x{com}/s/chat/thread/{chat}', data={'announcement': announcement, 'pinAnnouncement': True})
        elif announcement == False:
            await _req('post', f'x{com}/s/chat/thread/{chat}', data={'pinAnnouncement': False})

        if only_view:
            await _req('post', f'x{com}/s/chat/thread/{chat}/view-only/enable')
        elif only_view == False:
            await _req('post', f'x{com}/s/chat/thread/{chat}/view-only/disable')

        if members_can_invite:
            await _req('post', f'x{com}/s/chat/thread/{chat}/members-can-invite/enable')
        elif members_can_invite == False:
            await _req('post', f'x{com}/s/chat/thread/{chat}/members-can-invite/disable')

        if can_send_coins:
            await _req('post', f'x{com}/s/chat/thread/{chat}/tipping-perm-status/enable')
        elif can_send_coins == False:
            await _req('post', f'x{com}/s/chat/thread/{chat}/tipping-perm-status/disable')

        if change_adm_to:
            await _req('post', f'x{com}/s/chat/thread/{chat}/transfer-organizer', data={'uidList': [change_adm_to]})

    async def change_co_hosts(
        add:    list[str] | str | None = None,
        remove: list[str] | str | None = None,
        com:    str | None = None,
        chat:   str | None = None
    ) -> Res | list[Res]:
        """
        Add or remove co-hosts
        """

        com = com or actual_com
        chat = chat or actual_chat
        add = to_list(add)

        if add:
            return await _req('post', f'x{com}/s/chat/thread/{chat}/co-host', data={'uidList': add})
        elif remove:
            async def foo(i):
                return await _req('delete', f'x{com}/s/chat/thread/{chat}/co-host/{i}')
            return one_or_list(await gather(*[foo(i) for i in remove]))

    async def save(filename: str | None = None) -> None:
        """
        Saves all information from a chat to a .json
        """

        chat = await Chat.search()
        info = {
            'name': chat.name,
            'text': chat.text,
            'announcement': chat.announcement,

            'bg': chat.bg,
            'icon': chat.icon,

            'adm': chat.adm,
            'co_hosts': chat.co_hosts,

            'members_can_invite': chat.members_can_invite,
            'can_send_coins': chat.can_send_coins,
            'is_pinned': chat.is_pinned,
            'only_view': chat.only_view,
            'only_fans': chat.only_fans,

            'members': [i.id for i in await Chat.members()]
        }

        n = 0
        while Path(f'{n}.json').exists():
            n += 1
        with open(filename or f'{n}.json', 'w') as f:
            dump(info, f, indent=4, escape_forward_slashes=False)

    async def load(filename: str) -> str:
        """
        Creates a chat containing the .json information created by Chat.save

        The name will be a uuid4 in the beginning for the program to identify the chat that was created,
        after that it will change to the correct name
        """

        with open(filename, 'r') as f:
            f = load(f)

        tmp_chat_name = str(uuid4())
        await Chat.create(
            name           = tmp_chat_name,
            text           = f['text'],
            bg             = f['bg'],
            icon           = f['icon'],
            only_fans      = f['only_fans'],
            invite_members = f['members']
        )

        chats = await Community.chats()
        names = [i['name'] for i in chats]
        ids   = [i['id'] for i in chats]
        chat  = ids[names.index(tmp_chat_name)]

        await Chat.edit(
            name               = f['name'],
            pin                = f['is_pinned'],
            announcement       = f['announcement'],
            only_view          = f['only_view'],
            members_can_invite = f['members_can_invite'],
            can_send_coins     = f['can_send_coins'],
            change_adm_to      = f['adm'] if f['adm'] != bot_id else None,
            chat               = chat
        )

        await Chat.change_co_hosts(f['co_hosts'])
        return chat

class Community:
    async def chats(
        need_print:   bool       = False,
        ignore_ascii: bool       = False,
        com:          str | None = None
    ) -> dict[str, list[DataChat]]:
        """
        Returns the chats that you are in the community

        ### need_print
        Print the chats in a readable form

        ### ignore_ascii
        Removes special characters, which can disrupt the need_print
        """

        if not (com := to_list(com or actual_com)):
            raise EmptyCom('Enter a com or send a message in a chat')

        async def foo(i):
            res = await _req(
                'get', f'x{i}/s/chat/thread?type=public-all&start=0&size=100'
            )
            return {str(i): [{'name': i['title'], 'id': i['threadId']} for i in res.json['threadList']]}

        a = await gather(*[foo(i) for i in com])
        chats = {k: v for i in a for k, v in i.items()}

        if need_print:
            for i, e in chats.items():
                max_name = len(
                    max(
                        [
                            i['name'] if not ignore_ascii else fix_ascii(i['name'])
                            for i in e
                        ],
                        key=len,
                    )
                )
                print(i)
                for n in e:
                    name = n['name'] if not ignore_ascii else fix_ascii(n['name'])
                    a = max_name - len(name)
                    print(f"    {name} {' '*a}-> {n['id']}")
                print()
        return [j for i in chats.values() for j in i]

    async def staff(com=None) -> Dict[list[Dict[str, str]]]:
        """
        Returns a dictionary containing community leaders and curators
        """

        if not (com := com or actual_com):
            raise EmptyCom('Enter a com or send a message in a chat')

        leaders  = [{'nickname': i['nickname'], 'uid': i['uid']} for i in (await _req('get', f'x{com}/s/user-profile?type=leaders&start=0&size=100')).json['userProfileList']]
        curators = [{'nickname': i['nickname'], 'uid': i['uid']} for i in (await _req('get', f'x{com}/s/user-profile?type=curators&start=0&size=100')).json['userProfileList']]
        return {'leaders': leaders, 'curators': curators}


class My:
    async def chats(
        need_print:   bool = False,
        ignore_ascii: bool = False
    ) -> dict[str, list[str, list[str]]]:
        """
        Returns chats in which you are from all communities

        ### need_print
        Print the chats in a readable form

        ### ignore_ascii
        Removes special characters, which can disrupt the need_print
        """

        res = await _req('get', 'g/s/community/joined?v=1&start=0&size=50')
        coms = {str(i['ndcId']): [i['name'], []] for i in res.json['communityList']}

        async def foo(i):
            return (await _req(
                'get', f'x{i}/s/chat/thread?type=joined-me&start=0&size=100'
            )).json

        chats = await gather(*[foo(i) for i in coms])

        for i in chats:
            for j in i['threadList']:
                com_id = str(j['ndcId'])
                chat_id = j['threadId']
                is_private_chat = j['membersQuota'] == 2
                chat_name = (
                    j['membersSummary'][1]['nickname']
                    if is_private_chat
                    else j['title']
                )

                coms[com_id][1].append(
                    (
                        chat_name if not ignore_ascii else fix_ascii(chat_name),
                        chat_id,
                    )
                )

        if need_print:
            for i, e in coms.items():
                max_name = (
                    len(max([i[0] for i in e[1]], key=len)) if e[1] else 0
                )
                print(f'{coms[i][0]} - {i}')
                for j in coms[i][1]:
                    a = (max_name - len(j[0])) + 1
                    print(f'    {j[0]} {" "*a}-> {j[1]}')
                print()

        return [j for i in list(coms.values()) for j in i[1]]

    async def communities(
        need_print:   bool = False,
        ignore_ascii: bool = False
    ) -> dict[str, str]:
        """
        Returns all the communities you are in

        ### need_print
        Print the chats in a readable form

        ### ignore_ascii
        Removes special characters, which can disrupt the need_print
        """

        res = await _req('get', f'g/s/community/joined?v=1&start=0&size=100')
        coms = {
            i['name']
            if not ignore_ascii
            else fix_ascii(i['name']): str(i['ndcId'])
            for i in res.json['communityList']
        }

        if need_print:
            max_name = len(max(coms.keys(), key=len))
            for i, e in coms.items():
                a = max_name - len(i)
                print(f'{i} {" "*a} -> {e}')

        return coms


# # # # # # #
#   Cache   #
# # # # # # #

MESSAGE = Message()
