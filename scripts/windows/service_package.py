"""Assemble a pinned, checksum-verified WinSW dependency; never install a service."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import urllib.request


ROOT = Path(__file__).resolve().parents[2]


def build(destination, *, download=urllib.request.urlopen):
    destination = Path(destination)
    source = ROOT / "packaging" / "windows_service"
    dependency = json.loads((source / "dependency.json").read_text(encoding="utf-8"))
    service = destination / "Tools" / "service"
    service.mkdir(parents=True, exist_ok=True)
    with download(dependency["url"], timeout=60) as response:
        binary = response.read()
    if hashlib.sha256(binary).hexdigest() != dependency["sha256"]:
        raise ValueError("WinSW download SHA-256 mismatch")
    with download(dependency["license_url"], timeout=60) as response:
        license_text = response.read()
    (service / "MotionServerService.exe").write_bytes(binary)
    (service / "WinSW-LICENSE.txt").write_bytes(license_text)
    for name in ("MotionServerService.default.xml", "dependency.json"):
        shutil.copy2(source / name, service / name)
    shutil.copy2(ROOT / "scripts/windows/register_service.ps1", destination / "register_service.ps1")
    return service


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", required=True)
    args = parser.parse_args()
    print(build(args.destination))
