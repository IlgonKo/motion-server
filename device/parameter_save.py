"""Device-owned nonblocking completion check, independent of transport/API."""
from dataclasses import dataclass
from typing import Callable


@dataclass
class PendingParameterSave:
    poll: Callable
    cancel: Callable
