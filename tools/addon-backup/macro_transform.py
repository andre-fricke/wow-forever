"""Single macro import policy, shared by offline restores and compiled templates.

Lua selects a precompiled variant; it must never duplicate this text parser.
Only explicit spell commands are rewritten. /use, tooltips, scripts, item IDs,
macro names and conditional expressions are intentionally not guessed.
"""
import copy
import re

from saved_variables import decode, encode

POLICY_VERSION = 1
COMMAND = re.compile(r"^(\s*/(?:castsequence|castrandom|cast|spell)\s+)(.*?)(\r?\n)?$", re.I)
PREFIX = re.compile(r"^(\s*(?:(?:\[[^\]]*\]|reset=\S+)\s*)*)(.*?)(\s*)$", re.I)


def transform_body(body, different_class=False):
    if not different_class:
        return body
    result = []
    for line in body.splitlines(keepends=True):
        match = COMMAND.match(line)
        if not match:
            result.append(line)
            continue
        # Delimiters inside conditions are not action separators.
        parts = re.split(r"(\[[^\]]*\]|[;,])", match[2])
        output, pending = [], ""
        def action(text):
            parsed = PREFIX.match(text)
            if not parsed or not parsed[2]:
                return text
            value = parsed[2]
            replacement = value if value.isdigit() or value.lower().startswith("item:") else "null"
            return parsed[1] + replacement + parsed[3]
        for part in parts:
            if part in (";", ","):
                output.extend((action(pending), part))
                pending = ""
            else:
                pending += part
        output.append(action(pending))
        result.append(match[1] + "".join(output) + (match[3] or ""))
    return "".join(result)


def transform_entries(entries, different_class=False):
    result = copy.deepcopy(entries)
    for entry in result.values():
        entry["body"] = transform_body(entry["body"], different_class)
    return result


def transform_cache(data, different_class=False):
    if not different_class:
        return data
    result, body, inside = [], [], False
    for line in decode(data).splitlines(keepends=True):
        if not inside:
            if line.startswith("VER "):
                inside = True
            elif line.strip():
                raise ValueError("Unsupported macro cache format; cannot transform safely.")
            result.append(line)
        elif line.rstrip("\r\n") == "END":
            result.extend((transform_body("".join(body), True), line))
            body, inside = [], False
        else:
            body.append(line)
    if inside:
        raise ValueError("Incomplete macro cache entry.")
    return encode("".join(result))


def compile_variants(template):
    template["macroPolicy"] = POLICY_VERSION
    template["differentClass"] = {
        key: transform_entries(template.get(key, {}), True)
        for key in ("macros", "slots", "clickMacros")
    }
