from dataclasses import dataclass


@dataclass(frozen=True)
class DeferredResponse:
    """Marks a request whose correlated response will be sent by the server loop."""
