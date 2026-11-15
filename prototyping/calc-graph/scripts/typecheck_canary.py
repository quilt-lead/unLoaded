"""Type-check canary - never run, never imported (scripts/check_types.py reads pyright's verdict on it).

Each line marked `# CANARY` must get a pyright error of rule reportArgumentType, and each line marked
`# CLEAN` must get none, or check_types.py fails. The CANARY lines are the bug class of a410607: a caller
(since deleted) passed a dict to as_of.impact_timeline after 7319505 retyped it to take a
move_model.Move, an AttributeError on every call at runtime. The untyped variant proves the check covers functions
with no annotations at all (where mypy's default settings check nothing).
"""
from calcgraph import as_of as asof
from calcgraph.move_model import Move


def dict_for_move(plan: dict, as_of_value: str | None) -> None:
    asof.impact_timeline({**plan["move"], "as_of": as_of_value})  # CANARY


def dict_for_move_untyped(plan, as_of_value):
    asof.impact_timeline({**plan["move"], "as_of": as_of_value})  # CANARY


def typed_move(as_of_value: str | None) -> None:
    asof.impact_timeline(Move(column="2B", dx=5.0, as_of=as_of_value))  # CLEAN
