# type imports
from pathlib import Path


def ensure_dir(dir: Path):
    if dir.is_file():
        raise NotADirectoryError(dir)
    if not dir.exists():
        dir.mkdir()
