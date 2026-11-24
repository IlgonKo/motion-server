"""Offline reset and read-only history for virtual device parameters."""
import argparse
import json
import sqlite3
from pathlib import Path
from .store import ParameterStore, StoreLock, StoreError, open_readonly


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--path', required=True, type=Path)
    parser.add_argument('--json', action='store_true')
    parser.add_argument('command', choices=['list','history','show','factory-reset'])
    parser.add_argument('--storage-id')
    parser.add_argument('--revision', type=int)
    args = parser.parse_args(argv)
    if args.command != 'list' and not args.storage_id:
        parser.error('--storage-id is required')
    if args.command == 'show' and args.revision is None:
        parser.error('--revision is required')
    try:
        if not args.path.is_file():
            raise StoreError('Parameter store does not exist')
        if args.command == 'factory-reset':
            with StoreLock(args.path):
                store = ParameterStore(args.path)
                try:
                    result = {'storage_id':args.storage_id,'revision':store.factory_reset(args.storage_id),'kind':'factory_reset'}
                finally:
                    store.close()
        else:
            db = open_readonly(args.path)
            db.row_factory = sqlite3.Row
            try:
                if db.execute('PRAGMA user_version').fetchone()[0] != 1:
                    raise StoreError('Unsupported parameter database version')
                if args.command == 'list':
                    result = [dict(r) for r in db.execute('SELECT id AS storage_id,revision FROM devices ORDER BY id')]
                elif args.command == 'history':
                    result = [dict(r) for r in db.execute('SELECT revision,saved_at,profile,version,kind FROM snapshots WHERE id=? ORDER BY revision',(args.storage_id,))]
                else:
                    db.execute('BEGIN')
                    row = db.execute('SELECT * FROM snapshots WHERE id=? AND revision=?',(args.storage_id,args.revision)).fetchone()
                    if row is None:
                        raise StoreError('Unknown snapshot')
                    result = dict(row)
                    result['parameters'] = [{'address':json.loads(r[0]),'data_type':r[1],'raw_hex':bytes(r[2]).hex()}
                        for r in db.execute('SELECT address,dtype,raw FROM snapshot_values WHERE id=? AND revision=? ORDER BY address',(args.storage_id,args.revision))]
            finally:
                db.close()
        if args.json:
            print(json.dumps(result, ensure_ascii=False))
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (StoreError, sqlite3.Error, OSError) as exc:
        print(json.dumps({'error':str(exc)}) if args.json else f'Failed: {exc}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
