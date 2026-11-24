"""Inspect a Windows distribution without starting devices or Node-RED."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def inspect(root):
    required = [
        'motion_server.exe', 'config.example.txt',
        'device/cmmt/config.example.txt', 'device/cpx_ap_i_ec/config.example.txt',
        'device/io_link/iodd',
        'Tools/axis_control_panel/axis_control_panel.exe',
        'Tools/io_control_panel/io_control_panel.exe',
        'Tools/gamepad_control_panel/gamepad_control_panel.exe',
        'Manual/Motion_Server_User_Manual_KR.md',
        'Manual/Motion_Server_Installation_Manual_Basic_Mode.md',
        'Manual/motion_server_api_basic.md', 'Manual/deployment_validation.md',
        '_internal/motion_server/api/schema/axis.json',
        '_internal/device/cmmt/esi', '_internal/device/cpx_ap_i_ec/esi',
        '_internal/device/io_link/iodd', 'Reference/cmmt_error_catalog.json',
        'Reference Clients/node_red/node-red-contrib-motion-server/package.json',
        'Reference Clients/node_red/node-red-contrib-motion-server/examples/flows',
        'AI Reference/docs/ai/README.md',
    ]
    errors = [f'Missing: {path}' for path in required if not (root/path).exists()]
    for relative in ('_internal/device/cmmt/esi', '_internal/device/cpx_ap_i_ec/esi',
                     '_internal/device/io_link/iodd'):
        if not list((root/relative).rglob('*.xml')):
            errors.append(f'No XML catalog: {relative}')
    if list((root/'Manual').glob('*.docx')):
        errors.append('Unreviewed legacy DOCX manual included')
    if list(root.rglob('.env')):
        errors.append('Source .env included in Windows package')
    if not list((root/'_internal/pysoem').glob('*.pyd')):
        errors.append('PySOEM native module missing')
    files = []
    for path in sorted(root.rglob('*')):
        if path.is_file() and path.name != 'artifact-manifest.json':
            with path.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            files.append({'path': path.relative_to(root).as_posix(), 'bytes': path.stat().st_size,
                          'sha256': digest})
    return errors, files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', type=Path)
    args = parser.parse_args()
    root = args.package.resolve()
    if not root.is_dir():
        parser.error('Package directory does not exist')
    errors, files = inspect(root)
    commit = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(['git', 'status', '--porcelain', '--untracked-files=no'], capture_output=True, text=True).stdout
    report = {'source_commit': commit, 'source_dirty': bool(dirty), 'errors': errors,
              'npcap_installer_included': bool(list((root/'Tools').glob('npcap-*.exe'))),
              'files': files}
    (root/'artifact-manifest.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(f'Package: {len(files)} files, {len(errors)} errors')
    for error in errors:
        print(error)
    return bool(errors)


if __name__ == '__main__':
    raise SystemExit(main())
