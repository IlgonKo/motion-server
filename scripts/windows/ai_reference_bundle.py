"""Copy the AI source bundle with repository-relative links preserved; no local settings."""
import argparse
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2]


def build(destination):
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError(destination)
    files = set((ROOT / "docs").rglob("*.md"))
    for directory, suffixes in (("reference_clients/python", {".py", ".md", ".toml", ".json"}),
                                ("motion_server/api/schema", {".json"}),
                                ("configuration", {".py"})):
        files.update(p for p in (ROOT / directory).rglob("*") if p.is_file() and p.suffix in suffixes
                     and "__pycache__" not in p.parts)
    for name in (".env.example", "device/cmmt/.env.example", "device/cpx_ap_i_ec/.env.example",
                 "control_panel/axis_control_panel/statusword.py"):
        files.add(ROOT / name)
    for source in sorted(files):
        target = destination / source.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    print(f"AI reference bundle: {len(files)} files -> {destination}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination", required=True)
    build(parser.parse_args().destination)
