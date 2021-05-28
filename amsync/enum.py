from enum import Enum


class MediaType(Enum):
    BYTES = 0
    LINK = 1
    PATH = 2

class WsStatus(Enum):
    CLOSED = 0
    OPEN = 1

class RandomThingsState(Enum):
    START = 0
    STOP  = 1
    WAIT  = 2