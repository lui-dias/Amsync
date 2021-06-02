import sys

from .bot import *
from .obj import *
from .image import *
from .dataclass import *
from .exceptions import InvalidPythonVersion

# Production
__version__ = '0.0.51'

# Test
#__version__ = '0.0.51'


if sys.version_info < (3, 8):
    raise InvalidPythonVersion(f"Your python {'.'.join(map(str, sys.version_info[:2]))}, use python >= 3.8")
