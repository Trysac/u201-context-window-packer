"""Tests for context_window_packer."""

from __future__ import annotations

import json

import pytest

from context_window_packer import (
    Item,
    PackedItem,
    PackError,
    PackResult,
    approx_tokens,
    pack,
)


def test_approx_tokens() -> None:
    assert approx_tokens("") == 0
    assert approx_tokens("a" * 4) == 1
    assert approx_tokens("a" * 5) == 2


def test_item_dataclass() -> None:
    item = Item(id="a", text="hello", priority=2, pinned=True, truncate="head")
    assert item.id == "a"
    assert item.text == "hello"
    assert item.priority == 2
    assert item.pinned is True
    assert item.truncate == "head"


def test_packed_item_dataclass() -> None:
    pi = PackedItem(id="a", text="x", tokens=3, truncated=True)
    assert pi.id == "a"
    assert pi.text == "x"
    assert pi.tokens == 3
    assert pi.truncated is True


def test_pack_result_dataclass() -> None:
    result = PackResult(included=(), dropped=(), tokens_used=0)
    assert result.included == ()
    assert result.dropped == ()
    assert result.tokens_used == 0


def test_pack_default_counter_acceptance() -> None:
    items = [
        Item("A", "a" * 40, priority=0, pinned=True),
        Item("B", "b" * 100, priority=1),
        Item("C", "c" * 80, priority=5),
    ]
    result = pack(items, 35)
    assert [pi.id for pi in result.included] == ["A", "C"]
    assert result.dropped == ("B",)
    assert result.tokens_used == 30


def test_pack_order_and_tie() -> None:
    items = [
        Item("P", "p" * 40, priority=0, pinned=True),
        Item("X", "x" * 80, priority=1),
        Item("Y", "y" * 80, priority=1),
    ]
    result = pack(items, 30)
    assert [pi.id for pi in result.included] == ["P", "X"]
    assert result.dropped == ("Y",)


def test_head_truncation() -> None:
    text = " ".join(["word"] * 20)
    item = Item("D", text, priority=1, truncate="head")
    result = pack([item], 10)
    assert len(result.included) == 1
    pi = result.included[0]
    assert pi.id == "D"
    assert pi.text == "word word word word word word word [...]"
    assert pi.tokens == 10
    assert pi.truncated is True


def test_tail_truncation() -> None:
    text = " ".join(["word"] * 20)
    item = Item("D", text, priority=1, truncate="tail")
    result = pack([item], 10)
    assert len(result.included) == 1
    pi = result.included[0]
    assert pi.text == "[...] word word word word word word word"
    assert pi.tokens == 10
    assert pi.truncated is True


def test_fence_safety_head() -> None:
    text = "intro\n```\ncode line one\ncode line two\n```\nend"
    item = Item("F", text, priority=1, truncate="head")
    result = pack([item], 8)
    assert len(result.included) == 1
    pi = result.included[0]
    assert pi.text == "intro [...]"
    assert pi.truncated is True


def test_fence_safety_tail() -> None:
    text = "start\n```\ncode line one\ncode line two\n```\nend"
    item = Item("T", text, priority=1, truncate="tail")
    result = pack([item], 8)
    assert len(result.included) == 1
    pi = result.included[0]
    # The tail should start after the first fence line
    assert pi.text == "[...] end"
    assert pi.truncated is True


def test_pinned_over_budget() -> None:
    items = [Item("pinned", "x" * 100, pinned=True)]
    with pytest.raises(PackError) as exc:
        pack(items, 10)
    assert exc.value.code == "pinned_over_budget"


def test_duplicate_id() -> None:
    items = [Item("dup", "a"), Item("dup", "b")]
    with pytest.raises(PackError) as exc:
        pack(items, 100)
    assert exc.value.code == "duplicate_id"


def test_invalid_budget_zero() -> None:
    with pytest.raises(PackError) as exc:
        pack([], 0)
    assert exc.value.code == "invalid_budget"


def test_invalid_budget_bool() -> None:
    with pytest.raises(PackError) as exc:
        pack([], True)  # type: ignore[arg-type]
    assert exc.value.code == "invalid_budget"


def test_input_too_large_text() -> None:
    huge = "a" * 1_000_001
    item = Item("big", huge)
    with pytest.raises(PackError) as exc:
        pack([item], 10)
    assert exc.value.code == "input_too_large"


def test_max_text_accepted() -> None:
    huge = "a" * 1_000_000
    item = Item("big", huge)
    result = pack([item], 250_000)
    assert len(result.included) == 1
    assert result.included[0].tokens == 250_000


def test_invalid_counter_negative() -> None:
    with pytest.raises(PackError) as exc:
        pack([Item("a", "x")], 10, counter=lambda s: -1)
    assert exc.value.code == "invalid_counter"


def test_invalid_counter_bool() -> None:
    with pytest.raises(PackError) as exc:
        pack([Item("a", "x")], 10, counter=lambda s: True)  # type: ignore[arg-type]
    assert exc.value.code == "invalid_counter"


def test_counter_raises() -> None:
    with pytest.raises(PackError) as exc:
        pack([Item("a", "x")], 10, counter=lambda s: 1 / 0)
    assert exc.value.code == "invalid_counter"


def test_no_whitespace_truncate_dropped() -> None:
    item = Item("no_ws", "a" * 100, priority=1, truncate="head")
    result = pack([item], 10)
    assert len(result.included) == 0
    assert result.dropped == ("no_ws",)


def test_exact_fit() -> None:
    item = Item("exact", "a" * 40)
    result = pack([item], 10)
    assert len(result.included) == 1
    pi = result.included[0]
    assert pi.truncated is False
    assert pi.tokens == 10


def test_empty_items() -> None:
    result = pack([], 10)
    assert result.included == ()
    assert result.dropped == ()
    assert result.tokens_used == 0


def test_len_counter() -> None:
    items = [Item("a", "hello"), Item("b", "world")]
    result = pack(items, 5, counter=len)
    assert [pi.id for pi in result.included] == ["a"]
    assert result.dropped == ("b",)
    assert result.tokens_used == 5


def test_more_than_max_items() -> None:
    items = [Item(f"id{i}", "x") for i in range(10_001)]
    with pytest.raises(PackError) as exc:
        pack(items, 100_000)
    assert exc.value.code == "input_too_large"


def test_invalid_id_length_empty() -> None:
    items = [Item("", "x")]
    with pytest.raises(PackError) as exc:
        pack(items, 10)
    assert exc.value.code == "invalid_item"


def test_invalid_id_length_long() -> None:
    items = [Item("a" * 129, "x")]
    with pytest.raises(PackError) as exc:
        pack(items, 10)
    assert exc.value.code == "invalid_item"


def test_invalid_id_message_length_bounded() -> None:
    items = [Item("a" * 200, "x")]
    with pytest.raises(PackError) as exc:
        pack(items, 10)
    assert exc.value.code == "invalid_item"
    assert len(exc.value.message) <= 200


def test_invalid_priority_bool() -> None:
    items = [Item("a", "x", priority=True)]  # type: ignore[arg-type]
    with pytest.raises(PackError) as exc:
        pack(items, 10)
    assert exc.value.code == "invalid_item"


def test_invalid_truncate_value() -> None:
    items = [Item("a", "x", truncate="bad")]  # type: ignore[arg-type]
    with pytest.raises(PackError) as exc:
        pack(items, 10)
    assert exc.value.code == "invalid_item"


def test_pack_error_str() -> None:
    err = PackError("invalid_budget", "bad")
    assert str(err) == "invalid_budget: bad"


# CLI tests


def test_main_success(tmp_path, capsys) -> None:
    import context_window_packer.__main__ as main_mod

    f = tmp_path / "items.json"
    f.write_text(
        json.dumps(
            [
                {"id": "A", "text": "a" * 40, "priority": 0, "pinned": True},
                {"id": "B", "text": "b" * 100, "priority": 1},
                {"id": "C", "text": "c" * 80, "priority": 5},
            ]
        )
    )
    ret = main_mod.main(["--budget", "35", str(f)])
    captured = capsys.readouterr()
    assert ret == 0
    output = json.loads(captured.out)
    assert output["tokens_used"] == 30
    assert [x["id"] for x in output["included"]] == ["A", "C"]
    assert output["dropped"] == ["B"]
    assert set(output.keys()) == {"included", "dropped", "tokens_used"}
    # check sorted keys
    assert list(json.loads(captured.out).keys()) == ["dropped", "included", "tokens_used"]


def test_main_pack_error(tmp_path, capsys) -> None:
    import context_window_packer.__main__ as main_mod

    f = tmp_path / "items.json"
    f.write_text(json.dumps([{"id": "p", "text": "x" * 100, "pinned": True}]))
    ret = main_mod.main(["--budget", "10", str(f)])
    captured = capsys.readouterr()
    assert ret == 1
    assert "pinned_over_budget" in captured.err


def test_main_missing_file(capsys) -> None:
    import context_window_packer.__main__ as main_mod

    ret = main_mod.main(["--budget", "10", "nonexistent.json"])
    captured = capsys.readouterr()
    assert ret == 2
    assert "error" in captured.err


def test_main_invalid_budget_arg(capsys) -> None:
    import context_window_packer.__main__ as main_mod

    ret = main_mod.main(["--budget", "0", "file.json"])
    captured = capsys.readouterr()
    assert ret == 2
    assert "--budget" in captured.err


def test_main_invalid_json(tmp_path, capsys) -> None:
    import context_window_packer.__main__ as main_mod

    f = tmp_path / "bad.json"
    f.write_text("{not json")
    ret = main_mod.main(["--budget", "10", str(f)])
    captured = capsys.readouterr()
    assert ret == 2
    assert "error" in captured.err


def test_main_missing_id(tmp_path, capsys) -> None:
    import context_window_packer.__main__ as main_mod

    f = tmp_path / "items.json"
    f.write_text('[{"text": "x"}]')
    ret = main_mod.main(["--budget", "10", str(f)])
    captured = capsys.readouterr()
    assert ret == 2
    assert "error" in captured.err


def test_main_wrong_priority_type(tmp_path, capsys) -> None:
    import context_window_packer.__main__ as main_mod

    f = tmp_path / "items.json"
    f.write_text('[{"id": "a", "text": "x", "priority": "high"}]')
    ret = main_mod.main(["--budget", "10", str(f)])
    captured = capsys.readouterr()
    assert ret == 2
    assert "error" in captured.err
