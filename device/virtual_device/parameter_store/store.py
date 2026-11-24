import hashlib
import json
import os
from pathlib import Path
import sqlite3
from datetime import datetime, timezone


from device.exceptions import DeviceModelException


class StoreError(DeviceModelException):
    pass


class StoreLock:
    """OS lifetime lock shared by a server writer and offline maintenance."""
    def __init__(self, path):
        self.file = None
        path = Path(path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        stream = open(str(path) + '.lock', 'a+b')
        try:
            stream.seek(0, 2)
            if stream.tell() == 0:
                stream.write(b'0'); stream.flush()
            stream.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            stream.close()
            raise StoreError('Parameter store is in use') from exc
        self.file = stream

    def close(self):
        if self.file is not None:
            self.file.close()
            self.file = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def open_readonly(path):
    return sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True, timeout=0.1)


def canonical(values):
    # address is an opaque, canonical tuple; dtype/raw bytes are device-owned.
    rows = sorted((json.dumps(address, separators=(',', ':')), dtype, bytes(raw))
                  for address, dtype, raw in values)
    if len({row[0] for row in rows}) != len(rows):
        raise StoreError('Duplicate parameter address')
    return rows


def digest(profile, version, rows):
    encoded = json.dumps([profile, version, [(a, t, b.hex()) for a,t,b in rows]],
                         separators=(',', ':')).encode()
    return hashlib.sha256(encoded).hexdigest()


class ParameterStore:
    """Connection is owned exclusively by the persistence worker (or offline CLI)."""
    def __init__(self, path):
        existing = Path(path).exists()
        self.db = sqlite3.connect(path, timeout=0.1)
        try:
            version = self.db.execute('PRAGMA user_version').fetchone()[0]
            tables = self.db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            # Only a newly created file may have no schema. An existing empty
            # or unversioned file is not evidence that this is first startup.
            if version not in (0, 1) or (version == 0 and (existing or tables)):
                raise StoreError('Unsupported parameter database version')
            if version == 1 and {row[0] for row in tables} != {'devices', 'snapshots', 'snapshot_values'}:
                raise StoreError('Incomplete parameter database schema')
            self.db.execute('PRAGMA journal_mode=WAL')
            self.db.execute('PRAGMA synchronous=FULL')
            self.db.execute('PRAGMA foreign_keys=ON')
            self.db.executescript('''
                CREATE TABLE IF NOT EXISTS devices(id TEXT PRIMARY KEY, revision INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS snapshots(
                    id TEXT NOT NULL, revision INTEGER NOT NULL, saved_at TEXT NOT NULL,
                    profile TEXT NOT NULL, version INTEGER NOT NULL, kind TEXT NOT NULL,
                    digest TEXT NOT NULL, PRIMARY KEY(id, revision));
                CREATE TABLE IF NOT EXISTS snapshot_values(
                    id TEXT NOT NULL, revision INTEGER NOT NULL, address TEXT NOT NULL,
                    dtype TEXT NOT NULL, raw BLOB NOT NULL,
                    PRIMARY KEY(id,revision,address),
                    FOREIGN KEY(id,revision) REFERENCES snapshots(id,revision));
                PRAGMA user_version=1;
            ''')
            if self.db.execute('PRAGMA foreign_key_check').fetchone() is not None:
                raise StoreError('Invalid snapshot references')
            if self.db.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise StoreError('Corrupt parameter database')
        except Exception:
            self.db.close()
            raise

    def close(self):
        self.db.close()

    def load(self, identity):
        row = self.db.execute('''SELECT s.revision,s.profile,s.version,s.kind,s.digest
            FROM snapshots s JOIN devices d ON d.id=s.id AND d.revision=s.revision
            WHERE s.id=?''', (identity,)).fetchone()
        if row is None:
            if self.db.execute('SELECT 1 FROM devices WHERE id=?',(identity,)).fetchone():
                raise StoreError('Missing active snapshot')
            if self.db.execute('SELECT 1 FROM snapshots WHERE id=? LIMIT 1', (identity,)).fetchone():
                raise StoreError('Snapshot history exists without an active device record')
            return None
        revision, profile, version, kind, expected = row
        rows = self.db.execute('SELECT address,dtype,raw FROM snapshot_values WHERE id=? AND revision=? ORDER BY address',
                               (identity,revision)).fetchall()
        if kind == 'factory_reset':
            if rows:
                raise StoreError('Invalid reset record')
            return None
        if kind != 'save' or digest(profile, version, rows) != expected:
            raise StoreError('Snapshot integrity check failed')
        return profile, version, tuple((tuple(json.loads(a)),t,bytes(b)) for a,t,b in rows)

    def save(self, identity, profile, version, values):
        rows = canonical(values)
        fingerprint = digest(profile, version, rows)
        with self.db:
            self.load(identity)  # Reject orphan history as well as corrupt active data.
            current = self.db.execute('SELECT revision FROM devices WHERE id=?',(identity,)).fetchone()
            revision = current[0] if current else 0
            if current:
                prior = self.db.execute('SELECT kind,digest FROM snapshots WHERE id=? AND revision=?',
                                        (identity,revision)).fetchone()
                if prior == ('save',fingerprint):
                    return revision
            revision += 1
            self.db.execute('INSERT INTO snapshots VALUES(?,?,?,?,?,?,?)',
                            (identity,revision,datetime.now(timezone.utc).isoformat(),profile,version,'save',fingerprint))
            self.db.executemany('INSERT INTO snapshot_values VALUES(?,?,?,?,?)',
                                [(identity,revision,*row) for row in rows])
            self.db.execute('INSERT INTO devices VALUES(?,?) ON CONFLICT(id) DO UPDATE SET revision=excluded.revision',
                            (identity,revision))
        return revision

    def factory_reset(self, identity):
        with self.db:
            current = self.db.execute('SELECT revision FROM devices WHERE id=?',(identity,)).fetchone()
            if current is None:
                raise StoreError('Unknown storage_id')
            revision = current[0]+1
            self.db.execute('INSERT INTO snapshots VALUES(?,?,?,?,?,?,?)',
                            (identity,revision,datetime.now(timezone.utc).isoformat(),' ',0,'factory_reset',''))
            self.db.execute('UPDATE devices SET revision=? WHERE id=?',(revision,identity))
        return revision
