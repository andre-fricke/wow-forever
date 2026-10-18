"""Path validation, hashing and atomic file operations."""

import datetime as dt
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass


def sha(data):
    return hashlib.sha256(data).hexdigest()


def file_sha(p):
    if not p.exists():
        return None
    h = hashlib.sha256()
    with p.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def stamp():
    return dt.datetime.now().astimezone().strftime("%Y%m%d-%H%M%S-%f")


def backup_name_part(value):
    # Keep Unicode names readable, but exclude path separators and reserved characters.
    cleaned = "".join(c if c.isalnum() or c in " -_" else "-" for c in value)
    cleaned = re.sub(r"[\s-]+", "-", cleaned).strip("-_")
    return (
        cleaned.encode("utf-8")[:80].decode("utf-8", errors="ignore").rstrip("-_")
        or "Unknown"
    )


def backup_folder_part(value):
    # Use underscores as separators, keeping Unicode letters and digits readable.
    cleaned = "".join(c if c.isalnum() else "_" for c in value)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return (
        cleaned.encode("utf-8")[:80].decode("utf-8", errors="ignore").rstrip("_")
        or "Unknown"
    )


def json_write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2))
    os.replace(temp, path)


def valid_relative(name):
    p = PurePosixPath(name)
    if p.is_absolute() or ".." in p.parts or not p.parts:
        raise ValueError("Unsafe archive path: " + name)
    return p


def rooted(root, relative):
    valid_relative(relative)
    p = root / relative
    if not p.resolve().is_relative_to(root.resolve()):
        raise ValueError("Path leaves the destination directory: " + relative)
    # Reject symlinks, including ones that still point inside the client.
    cur = p
    while cur != root:
        if cur.is_symlink():
            raise ValueError("Symlink in destination path: " + str(cur))
        cur = cur.parent
    return p


@dataclass
class Archived:
    archive: Path
    member: str
    digest: str


def payload_hash(value):
    return (
        value.digest
        if isinstance(value, Archived)
        else sha(value) if value is not None else None
    )


def atomic_payload(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".wow-ui-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as dst:
            if isinstance(value, Archived):
                with zipfile.ZipFile(value.archive) as z, z.open(value.member) as src:
                    shutil.copyfileobj(src, dst, 1024 * 1024)
            else:
                dst.write(value)
            dst.flush()
            os.fsync(dst.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
