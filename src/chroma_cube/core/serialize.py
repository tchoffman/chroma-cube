"""Clues to and from plain JSON-compatible dicts, so puzzles can be stored as data.

Colors are written as strings: an id (`"black"`) or an initial (`"B"`), told apart the
same way as `clues.ref`. Every node is `{"type": ..., ...}`; see docs/CLUE_LANGUAGE.md.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from chroma_cube.core.clues import (
    And,
    AtLeast,
    BoardRule,
    Clue,
    Exactly,
    Not,
    Or,
    Property,
    Relation,
    ref,
)


def clue_to_dict(clue: Clue) -> dict[str, Any]:
    match clue:
        case Relation(kind=kind, colors=colors):
            return {"type": "relation", "kind": kind, "colors": [str(c) for c in colors]}
        case Property(kind=kind, color=color, index=index):
            data: dict[str, Any] = {"type": "property", "kind": kind, "color": str(color)}
            if index is not None:
                data["index"] = index
            return data
        case BoardRule(kind=kind):
            return {"type": "board_rule", "kind": kind}
        case Not(clue=inner):
            return {"type": "not", "clue": clue_to_dict(inner)}
        case And(clues=clues):
            return {"type": "and", "clues": [clue_to_dict(sub) for sub in clues]}
        case Or(clues=clues):
            return {"type": "or", "clues": [clue_to_dict(sub) for sub in clues]}
        case Exactly(n=n, clues=clues):
            return {"type": "exactly", "n": n, "clues": [clue_to_dict(sub) for sub in clues]}
        case AtLeast(n=n, clues=clues):
            return {"type": "at_least", "n": n, "clues": [clue_to_dict(sub) for sub in clues]}
    raise TypeError(f"not a clue: {clue!r}")


def clue_from_dict(data: Mapping[str, Any]) -> Clue:
    """Rebuild a clue. Raises `ValueError` for anything that is not a well-formed clue."""
    try:
        return _from_dict(data)
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError(f"malformed clue data: {data!r}") from error


def _from_dict(data: Mapping[str, Any]) -> Clue:
    if not isinstance(data, Mapping):
        raise TypeError(data)
    match data["type"]:
        case "relation":
            return Relation(data["kind"], tuple(ref(_str(c)) for c in data["colors"]))
        case "property":
            index = data.get("index")
            if index is not None and not isinstance(index, int):
                raise TypeError(index)
            return Property(data["kind"], ref(_str(data["color"])), index)
        case "board_rule":
            return BoardRule(data["kind"])
        case "not":
            return Not(_from_dict(data["clue"]))
        case "and":
            return And(_children(data))
        case "or":
            return Or(_children(data))
        case "exactly":
            return Exactly(_int(data["n"]), _children(data))
        case "at_least":
            return AtLeast(_int(data["n"]), _children(data))
    raise ValueError(f"unknown clue type {data['type']!r}")


def _children(data: Mapping[str, Any]) -> tuple[Clue, ...]:
    return tuple(_from_dict(sub) for sub in data["clues"])


def _str(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError(value)
    return value


def _int(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(value)
    return value
