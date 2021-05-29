from __future__ import annotations

from dis import Bytecode
from typing import Dict, Any, List, Tuple
from platform import system
from subprocess import run
from contextlib import suppress
from unicodedata import normalize


class MetaSlots(type):
    def __new__(cls, name, base, attrs):
        cls_slots      = [i for i in attrs['__slots__']]                                   if '__slots__' in attrs       else []
        cls_attrs      = [i for i in attrs['__annotations__']]                             if '__annotations__' in attrs else []
        instance_attrs = [i.argval for i in Bytecode(attrs['__init__']) if i.opcode == 95] if '__init__' in attrs        else []

        slots = cls_slots + cls_attrs + instance_attrs
        slots = [i for i in slots if i not in [i for i in attrs if not i.startswith('__')]]

        attrs['__slots__'] = slots
        return super().__new__(cls, name, base, attrs)


class Slots(metaclass=MetaSlots):
    """
    Creates the __slots__ automatically of the class

    Adds the existing __slots__, class attributes and the instance attributes (self.x) in __init__, to the subclass
    """

in_win = system() == 'Windows'
def clear() -> None:
    run('cls' if in_win else 'clear', shell=True)

def words(s):
    return s.strip().count(' ')+1

def get_value(
    d:       Dict[str, Any],
    *k:      str,
    convert: Any | None = None
) -> Any | None:

    with suppress(KeyError):
        tmp = d[k[0]]
        for i in k[1:]:
            tmp = tmp[i]

        if convert:
            return convert(tmp)
        return tmp

def fix_ascii(s: str) -> str:
    return normalize('NFKD', s).encode('ASCII', 'ignore').decode().strip()

def on_limit(
    obj:   list[Any],
    limit: int
) -> bool:
    return limit and len(obj) >= limit

def to_list(obj: Any):
    if obj:
        return [obj] if not isinstance(obj, (tuple, list)) else obj

def one_or_list(obj: List | Tuple):
    if len(obj) == 1:
        return obj[0]
    return obj
