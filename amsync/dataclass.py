from __future__ import annotations

from typing import Dict, Any
from dataclasses import dataclass

from ujson import loads

from .utils import Slots, get_value

__all__ = [
    'Res',
    'Reply',
    'Msg',
    'ChatMsg',
    'Embed',
    'DataUser',
    'DataChat'
]

@dataclass
class Res(Slots):
    """
    Represents a response from Req
    """

    bytes:   bytes
    headers: Dict[str, str]
    json:    Dict[str, Any]
    ok:      bool
    status:  int
    text:    str
    url:     str

    @classmethod
    async def _make(cls, req) -> Res:
        return cls(
            bytes   = await req.read(),
            headers = req.headers,
            json    = await req.json(loads=loads),
            ok      = req.status < 400,
            status  = req.status,
            text    = await req.text(),
            url     = req.real_url
        )

@dataclass
class Reply(Slots):
    """
    Represents the message that was replied to
    """

    icon:     str | None
    id:       str | None
    nickname: str | None
    uid:      str | None

@dataclass
class Msg(Slots):
    """
    Represents a websocket message
    """

    chat:            str | None
    com:             str | None
    extensions:      dict[str, Any]
    file_link:       str | None
    icon:            str | None
    id:              str | None
    level:           int | None
    media_type:      str | None
    mentioned_users: list[str]
    nickname:        str | None
    ref_id:          int | None
    reply:           Reply
    text:            str | None
    type:            str | None
    uid:             str | None

    @classmethod
    def _make(cls, j) -> Msg:
        cm:  dict[str, Any] = j['chatMessage']
        ext: dict[str, Any] = get_value(cm, 'extensions') or {}

        r = None
        if 'replyMessage' in ext:
            r = Reply(
                icon     = get_value(ext, 'replyMessage', 'author', 'icon'),
                id       = get_value(ext, 'replyMessageId'),
                nickname = get_value(ext, 'replyMessage', 'author', 'nickname'),
                uid      = get_value(ext, 'replyMessage', 'author', 'uid')
            )

        return cls(
            chat             = get_value(cm, 'threadId', convert=str),
            com              = get_value(j, 'ndcId', convert=str),
            extensions       = ext,
            file_link        = get_value(cm, 'mediaValue'),
            icon             = get_value(cm, 'author', 'icon'),
            id               = get_value(cm, 'messageId'),
            level            = get_value(cm, 'author', 'level'),
            media_type       = get_value(cm, 'mediaType'),
            mentioned_users  = [u['uid'] for u in get_value(ext, 'mentionedArray') or []],
            nickname         = get_value(cm, 'author', 'nickname'),
            ref_id           = get_value(cm, 'clientRefId'),
            reply            = r,
            text             = get_value(cm, 'content'),
            type             = get_value(cm, 'type'),
            uid              = get_value(cm, 'uid')
        )

@dataclass
class ChatMsg(Slots):
    """
    Represents a message obtained from Chat.messages
    """

    chat:            str | None
    com:             str | None
    extensions:      dict[str, Any]
    file_link:       str | None
    icon:            str | None
    id:              str | None
    level:           int | None
    media_type:      int | None
    mentioned_users: list[str]
    nickname:        str | None
    ref_id:          int | None
    reply:           Reply | None
    text:            str | None
    type:            str | None
    uid:             str | None

    @classmethod
    def _make(cls, j) -> ChatMsg:
        ext: dict[str, Any] = get_value(j, 'extensions') or {}

        r = None
        if 'replyMessage' in ext:
            r = Reply(
                icon     = get_value(ext, 'replyMessage', 'author', 'icon'),
                id       = get_value(ext, 'replyMessageId'),
                nickname = get_value(ext, 'replyMessage', 'author', 'nickname'),
                uid      = get_value(ext, 'replyMessage', 'author', 'uid')
            )

        return cls(
            chat             = get_value(j, 'threadId', convert=str),
            com              = get_value(j, 'ndcId', convert=str),
            extensions       = ext,
            file_link        = get_value(j, 'mediaValue'),
            icon             = get_value(j, 'author', 'icon'),
            id               = get_value(j, 'messageId'),
            level            = get_value(j, 'author', 'level'),
            media_type       = get_value(j, 'mediaType'),
            mentioned_users  = [u['uid'] for u in get_value(ext, 'mentionedArray') or []],
            nickname         = get_value(j, 'author', 'nickname'),
            ref_id           = get_value(j, 'clientRefId'),
            reply            = r,
            text             = get_value(j, 'content'),
            type             = get_value(j, 'type'),
            uid              = get_value(j, 'uid')
        )


@dataclass
class Embed(Slots):
    """
    Represents the Embed that will be sent in Message.send
    """

    msg_text: str
    title:    str
    text:     str
    link:     str
    image:    str | bytes = None


@dataclass
class DataUser(Slots):
    """
    Represents information from a user profile
    """

    bio:             str | None
    blogs_count:     int | None
    com:             str | None
    comments_count:  int | None
    followers_count: str | None
    following_count: str | None
    im_following:    bool
    level:           str | None
    nickname:        str | None
    posts_count:     int | None
    id:              str | None
    reputation:      int | None
    role:            str | None
    visitors_count:  int | None

    @classmethod
    def _make(cls, j) -> DataUser:
        return cls(
            bio             = get_value(j, 'content'),
            blogs_count     = get_value(j, 'blogsCount'),
            com             = get_value(j, 'ndcId', convert=str),
            comments_count  = get_value(j, 'commentsCount'),
            followers_count = get_value(j, 'membersCount'),
            following_count = get_value(j, 'joinedCount'),
            im_following    = get_value(j, 'followingStatus') == 1,
            level           = get_value(j, 'level'),
            nickname        = get_value(j, 'nickname'),
            posts_count     = get_value(j, 'postsCount'),
            id              = get_value(j, 'uid'),
            reputation      = get_value(j, 'reputation'),
            role            = {0: 'member', 101: 'curator', 100: 'leader', 102: 'agent'}[j['role']],
            visitors_count  = get_value(j, 'visitoresCount')
        )

@dataclass
class DataChat(Slots):
    """
    Represents information from a chat
    """

    adm:                str | None
    announcement:       str | None
    bg:                 str | None
    can_send_coins:     bool
    co_hosts:           list[str]
    extensions:         Dict[str, Any]
    icon:               str | None
    id:                 str | None
    is_pinned:          bool
    is_private:         bool
    members_can_invite: bool
    name:               str | None
    only_fans:          bool
    only_view:          bool
    text:               str | None

    @classmethod
    def _make(cls, j):
        t:   Dict[str, Any] = j['thread']
        ext: Dict[str, Any] = get_value(t, 'extensions') or {}

        return cls(
            adm                = get_value(t, 'author', 'uid'),
            announcement       = get_value(ext, 'announcement') or '',
            bg                 = get_value(ext, 'bm')[1] if 'bm' in ext else None,
            can_send_coins     = get_value(t, 'tipInfo', 'tippable'),
            co_hosts           = get_value(ext, 'coHost') or [],
            extensions         = ext,
            icon               = get_value(t, 'icon'),
            id                 = get_value(t, 'threadId'),
            is_pinned          = get_value(t, 'isPinned'),
            is_private         = get_value(t, 'membersQuota') == 2,
            members_can_invite = get_value(t, 'membersCanInvite') or True,
            name               = get_value(t, 'title'),
            only_fans          = get_value(ext, 'fansOnly'),
            only_view          = get_value(ext, 'viewOnly') or False,
            text               = get_value(t, 'content') or ''
        )
