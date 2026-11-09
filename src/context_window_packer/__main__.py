"""Command-line interface for context-window-packer."""

from __future__ import annotations

import argparse
import json
import os
import sys

from . import Item, PackError, pack


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="context-window-packer")
    parser.add_argument("--budget", type=int, required=True)
    parser.add_argument("--marker", default="[...]")
    parser.add_argument("json_file")
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return 2

    if args.budget < 1:
        print("error: --budget must be an integer >= 1", file=sys.stderr)
        return 2

    file_path = args.json_file
    try:
        stat = os.stat(file_path)
        if stat.st_size > 50 * 1024 * 1024:
            print("error: file too large (max 50 MB)", file=sys.stderr)
            return 2
        with open(file_path, encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError) as e:
        print(f"error: cannot read JSON file: {e}", file=sys.stderr)
        return 2

    if not isinstance(raw, list):
        print("error: JSON root must be a list", file=sys.stderr)
        return 2

    items: list[Item] = []
    for i, obj in enumerate(raw):
        if not isinstance(obj, dict):
            print(f"error: item {i} must be an object", file=sys.stderr)
            return 2
        try:
            item_id = obj["id"]
            text = obj["text"]
        except KeyError as e:
            print(f"error: item {i} missing key {e}", file=sys.stderr)
            return 2
        if not isinstance(item_id, str):
            print(f"error: item {i} id must be a string", file=sys.stderr)
            return 2
        if not isinstance(text, str):
            print(f"error: item {i} text must be a string", file=sys.stderr)
            return 2
        priority = obj.get("priority", 0)
        pinned = obj.get("pinned", False)
        truncate = obj.get("truncate", "none")
        if isinstance(priority, bool) or not isinstance(priority, int):
            print(f"error: item {i} priority must be an integer", file=sys.stderr)
            return 2
        if not isinstance(pinned, bool):
            print(f"error: item {i} pinned must be a boolean", file=sys.stderr)
            return 2
        if truncate not in ("none", "head", "tail"):
            print(
                f"error: item {i} truncate must be 'none', 'head', or 'tail'",
                file=sys.stderr,
            )
            return 2
        items.append(
            Item(
                id=item_id,
                text=text,
                priority=priority,
                pinned=pinned,
                truncate=truncate,
            )
        )

    try:
        result = pack(items, args.budget, marker=args.marker)
    except PackError as e:
        print(e.code, file=sys.stderr)
        return 1

    output = {
        "included": [
            {"id": pi.id, "text": pi.text, "tokens": pi.tokens, "truncated": pi.truncated}
            for pi in result.included
        ],
        "dropped": list(result.dropped),
        "tokens_used": result.tokens_used,
    }
    print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
