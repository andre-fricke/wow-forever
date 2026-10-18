"""Internal data models. On-disk schema 1 stays compatible with existing backups."""

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class StoragePaths:
    tool: Path
    backups: Path
    recovery: Path
    legacy_recovery: Path


@dataclass(frozen=True)
class CharacterIdentity:
    name: str
    full: str
    realm: str
    guid: str
    class_name: str

    @classmethod
    def from_mapping(cls, value):
        fields = ("name", "full", "realm", "guid", "class")
        if not isinstance(value, dict) or any(
            not isinstance(value.get(k), str) or not value[k] for k in fields
        ):
            raise ValueError(
                "Invalid character identity; record it again with the identity addon."
            )
        return cls(*(value[k] for k in fields))


@dataclass(frozen=True)
class BackupManifest:
    metadata: Mapping

    @classmethod
    def from_mapping(cls, value):
        if not isinstance(value, dict) or value.get("schema") != 1:
            raise ValueError("Unknown backup version")
        CharacterIdentity.from_mapping(value.get("source_identity"))
        for key in ("files", "addons"):
            if not isinstance(value.get(key), dict):
                raise ValueError("Invalid backup manifest: " + key)
        if not isinstance(value.get("source_character"), str):
            raise ValueError("Invalid backup source character path")
        if value.get("kind", "combined") not in ("addons", "macros", "combined"):
            raise ValueError("Unknown backup kind")
        if not isinstance(value.get("unsupported", []), list):
            raise ValueError("Invalid backup review list")
        if any(not isinstance(item, str) for item in value.get("unsupported", [])):
            raise ValueError("Invalid backup review entry")
        for name, entry in value["files"].items():
            if not isinstance(name, str) or not isinstance(entry, dict):
                raise ValueError("Invalid backup file entry")
            digest = entry.get("sha256")
            if (
                not isinstance(digest, str)
                or len(digest) != 64
                or any(c not in "0123456789abcdef" for c in digest)
            ):
                raise ValueError("Invalid backup checksum")
            if type(entry.get("size")) is not int or entry["size"] < 0:
                raise ValueError("Invalid backup file size")
        return cls(value)


@dataclass
class FilePlan:
    files: dict
    before: dict

    @classmethod
    def capture(cls, client, files, rooted, file_sha):
        return cls(files, {name: file_sha(rooted(client, name)) for name in files})

    def check_destination(self, client, rooted, file_sha):
        for name, digest in self.before.items():
            if file_sha(rooted(client, name)) != digest:
                raise ValueError(
                    "Destination changed after preview; retry the operation: " + name
                )
