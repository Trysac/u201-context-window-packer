# context-window-packer

[![PyPI version](https://img.shields.io/pypi/v/trysac-context-window-packer)](https://pypi.org/project/trysac-context-window-packer/)
[![License: MIT](https://img.shields.io/pypi/l/trysac-context-window-packer)](LICENSE)
[![CI](https://github.com/Trysac/u201-context-window-packer/actions/workflows/ci.yml/badge.svg)](https://github.com/Trysac/u201-context-window-packer/actions/workflows/ci.yml)

Pack messages and documents into an LLM context window by priority, keep pinned items and input order, and truncate safely at word and code fence boundaries

## Problem

Describe in two or three sentences the concrete problem this utility solves, who hits it, and what
they do today without it. Replace this paragraph when the first real feature lands.

## Install

```sh
pip install trysac-context-window-packer
# or
uv add trysac-context-window-packer
```

Requires Python 3.10 or newer. No runtime dependencies.

## Usage

```python
import context_window_packer

# normalize() trims surrounding whitespace and lower-cases the text.
print(context_window_packer.normalize("  Hello World "))  # -> "hello world"

# Blank input is rejected explicitly instead of returning an empty string.
try:
    context_window_packer.normalize("   ")
except ValueError as exc:
    print(f"rejected: {exc}")
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md) and [decisions](docs/decisions/)
- [Testing](docs/TESTING.md) and [security](docs/SECURITY.md)
- [Project record](docs/PROJECT.md) and [stack](docs/STACK.md)
- [Changelog](CHANGELOG.md) and [contributing guide](CONTRIBUTING.md)

## License

[MIT](LICENSE) (c) 2026 Miguel Gomez
