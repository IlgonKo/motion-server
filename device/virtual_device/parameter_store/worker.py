from concurrent.futures import ThreadPoolExecutor
from threading import BoundedSemaphore
import sqlite3
from .store import ParameterStore, StoreLock, StoreError


class StoreWorker:
    def __init__(self, path):
        try:
            self.lock = StoreLock(path)
        except OSError as exc:
            raise StoreError(f"Cannot lock parameter store: {exc}") from exc
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='virtual-parameter-store')
        self.capacity = BoundedSemaphore(16)
        self.closed = False
        try:
            self.store = self.executor.submit(ParameterStore, path).result()
        except Exception as exc:
            self.executor.shutdown()
            self.lock.close()
            raise StoreError(f"Cannot open parameter store: {exc}") from exc

    def load(self, identity):
        # Initialization only, before cyclic operation.
        try:
            return self.executor.submit(self.store.load, identity).result()
        except (sqlite3.Error, ValueError, TypeError) as exc:
            raise StoreError(f"Cannot restore parameters for {identity}: {exc}") from exc

    def save(self, identity, profile, version, values):
        if self.closed or not self.capacity.acquire(blocking=False):
            raise StoreError('Parameter persistence unavailable or queue full')
        try:
            future = self.executor.submit(self.store.save, identity, profile, version, tuple((tuple(a), t, bytes(raw)) for a, t, raw in values))
        except Exception:
            self.capacity.release()
            raise
        future.add_done_callback(lambda unused: self.capacity.release())
        return future

    def close(self):
        if not self.closed:
            self.closed = True
            try:
                # Drain accepted writes before releasing ownership, outside the PDO loop.
                self.executor.submit(self.store.close).result()
            finally:
                self.executor.shutdown(wait=True)
                self.lock.close()
