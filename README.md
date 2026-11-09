# context-window-packer

[![PyPI version](https://img.shields.io/pypi/v/trysac-context-window-packer)](https://pypi.org/project/trysac-context-window-packer/)
[![License: MIT](https://img.shields.io/pypi/l/trysac-context-window-packer)](LICENSE)
[![CI](https://github.com/Trysac/u201-context-window-packer/actions/workflows/ci.yml/badge.svg)](https://github.com/Trysac/u201-context-window-packer/actions/workflows/ci.yml)

Pack messages and documents into an LLM context window by priority, keep pinned items and input order, and truncate safely at word and code fence boundaries

## Problem

Applications that build prompts from a system message, chat history and retrieved documents
overflow the context window or cut text mid-word, mid-code block or in the wrong place. Ad hoc
slicing drops the system prompt, reorders the conversation or leaves an unclosed code fence that
confuses the model. This library decides what fits a token budget by priority, never drops pinned
items, keeps the original order and truncates only at safe boundaries with a visible marker.

## Install

```sh
pip install trysac-context-window-packer
# or
uv add trysac-context-window-packer
```

Requires Python 3.10 or newer. No runtime dependencies.

## Usage

```python
from context_window_packer import Item, pack

result = pack(
    [
        Item("system", "you are a helpful assistant", pinned=True),
        Item("doc", "word " * 50, priority=1, truncate="head"),
    ],
    budget=20,
)
print(result.tokens_used, [pi.id for pi in result.included], result.dropped)
```

From the command line, pass a JSON array of item objects and a required budget:

```sh
python -m context_window_packer --budget 35 items.json
```

The result is printed as one JSON object with `included`, `dropped` and `tokens_used` keys;
errors exit non-zero (`1` for a `PackError`, `2` for usage or IO problems).

## Documentation

- [Architecture](docs/ARCHITECTURE.md) and [decisions](docs/decisions/)
- [Testing](docs/TESTING.md) and [security](docs/SECURITY.md)
- [Project record](docs/PROJECT.md) and [stack](docs/STACK.md)
- [Changelog](CHANGELOG.md) and [contributing guide](CONTRIBUTING.md)

## License

[MIT](LICENSE) (c) 2026 Miguel Gomez
