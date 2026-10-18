"""Parse and serialize SavedVariables as data; never execute addon code."""

import math
from dataclasses import dataclass
from lua_saved import Lua


@dataclass
class Atom:
    value: object
    raw: str = None


def quote(value):
    # Lua accepts UTF-8 directly, but not JSON's Unicode escape syntax.
    return (
        '"'
        + "".join(
            (
                "\\" + c
                if c in '\\"'
                else ("\\%03d" % ord(c) if ord(c) < 32 or ord(c) == 127 else c)
            )
            for c in value
        )
        + '"'
    )


def decode(data):
    return data.decode("utf-8", errors="surrogateescape")


def encode(text):
    return text.encode("utf-8", errors="surrogateescape")


def scalar(value):
    return value.value if isinstance(value, Atom) else value


def parse(data):
    doc = Lua(decode(data))

    def convert(n):
        if n.entries is not None:
            return {k: convert(v) for k, v in n.entries.items()}
        return Atom(n.value, doc.raw(n))

    return {k: convert(n) for k, n in doc.roots.items()}


def dump(roots):
    def value(v):
        if isinstance(v, Atom):
            if v.raw is not None:
                return v.raw
            v = v.value
        if isinstance(v, dict):
            # Preserve sequence constructors, including explicit nil slots.
            # RestedXP calls unpack on {point, nil, relativePoint, x, y}.
            # Rewriting this as hash fields can change Lua's length boundary
            # and truncate unpack at the nil slot even though x/y are present.
            if (
                v
                and all(type(k) is int for k in v)
                and set(v) == set(range(1, len(v) + 1))
            ):
                return (
                    "{\n"
                    + "".join(value(v[k]) + ",\n" for k in range(1, len(v) + 1))
                    + "}"
                )
            return (
                "{\n"
                + "".join(
                    "[" + value(k) + "] = " + value(x) + ",\n" for k, x in v.items()
                )
                + "}"
            )
        if isinstance(v, str):
            return quote(v)
        if v is None:
            return "nil"
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, (int, float)) and math.isfinite(v):
            return repr(v)
        raise ValueError("Unsupported Lua value")

    data = encode("\n".join(k + " = " + value(v) for k, v in roots.items()) + "\n")
    parse(data)
    return data


def plain(v):
    if isinstance(v, dict):
        return {k: plain(x) for k, x in v.items()}
    return scalar(v)
