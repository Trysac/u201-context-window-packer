"""Pack messages and documents into an LLM context window by priority.

Keeps pinned items and input order, and truncates safely at word and code
fence boundaries.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from math import ceil
from typing import Literal

__all__ = [
    "Item",
    "PackError",
    "PackResult",
    "PackedItem",
    "approx_tokens",
    "pack",
]

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

MAX_ITEMS = 10_000
MAX_TEXT_LENGTH = 1_000_000
MAX_ID_LENGTH = 128


class PackError(Exception):
    """Raised when a packing operation cannot be completed."""

    def __init__(
        self,
        code: Literal[
            "invalid_item",
            "duplicate_id",
            "invalid_budget",
            "pinned_over_budget",
            "invalid_counter",
            "input_too_large",
        ],
        message: str,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


@dataclass(frozen=True)
class Item:
    id: str
    text: str
    priority: int = 0
    pinned: bool = False
    truncate: Literal["none", "head", "tail"] = "none"


@dataclass(frozen=True)
class PackedItem:
    id: str
    text: str
    tokens: int
    truncated: bool


@dataclass(frozen=True)
class PackResult:
    included: tuple[PackedItem, ...]
    dropped: tuple[str, ...]
    tokens_used: int


def approx_tokens(text: str) -> int:
    """Return an approximate token count: ceil(len(text) / 4)."""
    return ceil(len(text) / 4)


def _safe_message_id(item_id: str) -> str:
    if len(item_id) <= 200:
        return item_id
    return item_id[:197] + "..."


def _call_counter(counter: Callable[[str], int], text: str) -> int:
    try:
        value = counter(text)
    except Exception as e:
        raise PackError("invalid_counter", "counter raised an exception") from e
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise PackError("invalid_counter", "counter must return a non-negative integer")
    return value


def _validate_items(items: Sequence[Item]) -> None:
    if len(items) > MAX_ITEMS:
        raise PackError("input_too_large", f"at most {MAX_ITEMS} items allowed")
    seen_ids: set[str] = set()
    for item in items:
        if not isinstance(item, Item):
            raise PackError("invalid_item", "items must be Item objects")
        if not (1 <= len(item.id) <= MAX_ID_LENGTH):
            if not item.id:
                msg = "invalid item id length: 0"
            else:
                prefix = "invalid item id '"
                suffix = f"': length must be 1-{MAX_ID_LENGTH}"
                room = 200 - len(prefix) - len(suffix)
                shown = item.id
                if len(shown) > room:
                    shown = shown[: room - 3] + "..."
                msg = prefix + shown + suffix
            raise PackError("invalid_item", msg)
        if len(item.text) > MAX_TEXT_LENGTH:
            safe_id = _safe_message_id(item.id)
            raise PackError(
                "input_too_large",
                f"item '{safe_id}' text exceeds {MAX_TEXT_LENGTH} characters",
            )
        if item.id in seen_ids:
            raise PackError("duplicate_id", f"duplicate item id: {item.id}")
        seen_ids.add(item.id)
        if isinstance(item.priority, bool) or not isinstance(item.priority, int):
            raise PackError("invalid_item", f"item '{item.id}' priority must be an integer")
        if not isinstance(item.pinned, bool):
            raise PackError("invalid_item", f"item '{item.id}' pinned must be a boolean")
        if item.truncate not in ("none", "head", "tail"):
            raise PackError(
                "invalid_item", f"item '{item.id}' truncate must be 'none', 'head', or 'tail'"
            )


def _count_fence_lines(text: str) -> int:
    return sum(1 for line in text.splitlines() if line.lstrip().startswith("```"))


def _last_fence_line_start(text: str) -> int | None:
    offset = 0
    last = None
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith("```"):
            last = offset
        offset += len(line)
    return last


def _first_fence_line_end(text: str) -> int | None:
    offset = 0
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith("```"):
            return offset + len(line)
        offset += len(line)
    return None


def _head_boundaries(text: str) -> list[int]:
    """Return all p such that p == len(text) or text[p] is whitespace, plus 0."""
    p_vals = {0}
    for i, ch in enumerate(text):
        if ch.isspace():
            p_vals.add(i)
    p_vals.add(len(text))
    return sorted(p_vals)


def _tail_boundaries(text: str) -> list[int]:
    """Return all p such that p == 0 or text[p-1] is whitespace."""
    p_vals = {0}
    for i in range(1, len(text) + 1):
        if text[i - 1].isspace():
            p_vals.add(i)
    return sorted(p_vals)


def _truncate_head(
    text: str,
    remaining: int,
    counter: Callable[[str], int],
    marker: str,
    item_id: str,
) -> tuple[str, int] | None:
    boundaries = _head_boundaries(text)
    lo, hi = 0, len(boundaries) - 1
    best = None
    while lo <= hi:
        mid = (lo + hi) // 2
        p = boundaries[mid]
        candidate = text[:p].rstrip() + " " + marker
        tok = _call_counter(counter, candidate)
        if tok <= remaining:
            best = p
            lo = mid + 1
        else:
            hi = mid - 1
    if best is None:
        return None
    kept = text[:best].rstrip()
    if _count_fence_lines(kept) % 2 == 1:
        last_start = _last_fence_line_start(kept)
        if last_start is not None:
            best = last_start
            kept = text[:best].rstrip()
    if kept == "":
        return None
    final_text = kept + " " + marker
    final_tokens = _call_counter(counter, final_text)
    if final_tokens > remaining:
        return None
    return final_text, final_tokens


def _truncate_tail(
    text: str,
    remaining: int,
    counter: Callable[[str], int],
    marker: str,
    item_id: str,
) -> tuple[str, int] | None:
    boundaries = _tail_boundaries(text)
    lo, hi = 0, len(boundaries) - 1
    best = None
    while lo <= hi:
        mid = (lo + hi) // 2
        p = boundaries[mid]
        candidate = marker + " " + text[p:].lstrip()
        tok = _call_counter(counter, candidate)
        if tok <= remaining:
            best = p
            hi = mid - 1
        else:
            lo = mid + 1
    if best is None:
        return None
    lead = len(text[best:]) - len(text[best:].lstrip())
    q = best + lead
    tail_kept = text[q:]
    if _count_fence_lines(tail_kept) % 2 == 1:
        first_end_rel = _first_fence_line_end(tail_kept)
        if first_end_rel is not None:
            q = q + first_end_rel
            tail_kept = text[q:].lstrip()
    if tail_kept == "":
        return None
    final_text = marker + " " + tail_kept
    final_tokens = _call_counter(counter, final_text)
    if final_tokens > remaining:
        return None
    return final_text, final_tokens


def pack(
    items: Sequence[Item],
    budget: int,
    *,
    counter: Callable[[str], int] = approx_tokens,
    marker: str = "[...]",
) -> PackResult:
    """Pack items into a token budget.

    Args:
        items: Sequence of Item objects.
        budget: Maximum total tokens allowed. Must be int >= 1.
        counter: Token counting function (default approx_tokens).
        marker: Truncation marker (default '[...]').

    Returns:
        PackResult with included items in input order, dropped ids in input order,
        and tokens_used = sum of included tokens.

    Raises:
        PackError: if validation fails (see PackError codes).
    """
    if isinstance(budget, bool) or not isinstance(budget, int) or budget < 1:
        raise PackError("invalid_budget", "budget must be an integer >= 1")
    if not callable(counter):
        raise PackError("invalid_counter", "counter must be callable")
    # Validate counter with a probe call
    _call_counter(counter, "a")

    _validate_items(list(items))

    remaining = budget

    pinned_packed: dict[str, PackedItem] = {}
    for item in items:
        if item.pinned:
            tokens = _call_counter(counter, item.text)
            pinned_packed[item.id] = PackedItem(item.id, item.text, tokens, False)
            remaining -= tokens

    if remaining < 0:
        raise PackError("pinned_over_budget", "pinned items require more tokens than budget")

    non_pinned = [(idx, item) for idx, item in enumerate(items) if not item.pinned]
    non_pinned_sorted = sorted(non_pinned, key=lambda x: (-x[1].priority, x[0]))

    included_others: dict[int, PackedItem] = {}
    dropped: dict[int, str] = {}

    for idx, item in non_pinned_sorted:
        if remaining == 0:
            dropped[idx] = item.id
            continue
        whole_tokens = _call_counter(counter, item.text)
        if whole_tokens <= remaining:
            included_others[idx] = PackedItem(item.id, item.text, whole_tokens, False)
            remaining -= whole_tokens
        else:
            if item.truncate == "none":
                dropped[idx] = item.id
                continue
            if item.truncate == "head":
                result = _truncate_head(item.text, remaining, counter, marker, item.id)
            else:  # tail
                result = _truncate_tail(item.text, remaining, counter, marker, item.id)
            if result is None:
                dropped[idx] = item.id
            else:
                final_text, final_tokens = result
                included_others[idx] = PackedItem(item.id, final_text, final_tokens, True)
                remaining -= final_tokens

    included_final: list[PackedItem] = []
    for idx, item in enumerate(items):
        if item.pinned:
            included_final.append(pinned_packed[item.id])
        else:
            if idx in included_others:
                included_final.append(included_others[idx])

    dropped_final = tuple(dropped[idx] for idx in sorted(dropped))
    return PackResult(
        included=tuple(included_final),
        dropped=dropped_final,
        tokens_used=budget - remaining,
    )
