from enum import Enum


class MediaType(Enum):
    BYTES = 0
    LINK = 1
    PATH = 2

class WsStatus(Enum):
    CLOSED = 0