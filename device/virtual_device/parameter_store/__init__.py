"""Virtual-device persistence. No device command or OD interpretation."""
from .store import ParameterStore, StoreError, StoreLock, open_readonly
from .worker import StoreWorker
