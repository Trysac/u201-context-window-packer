# Project record

## Objective

Pack messages and documents into an LLM context window by priority, keep pinned items and input order, and truncate safely at word and code fence boundaries

## Scope

- In scope: the public API documented in [README.md](../README.md), typed and tested.
- Out of scope: anything that needs runtime dependencies or I/O without an accepted ADR.

## Timeline

| Date | Event |
|---|---|
| 2026 | Repository created from the factory utility template. |

## Effort metrics

Measured values only; a value that has not been measured stays "pending measurement".

| Metric | Value |
|---|---|
| Tokens (input / output) | 494731 / 55103 |
| Hours (human) | pending measurement |
| Cost (USD) | 0.0736 |

## Factory run u201 (measured from API usage)

| Phase | Model | Batch | Input | Output | Cache write | Cache read | Cost (USD) |
|---|---|---|---|---|---|---|---|
| generation | deepseek-v4-pro | yes | 1697 | 23386 | 0 | 3200 | 0.0475 |
| fix-1 | deepseek-flash | no | 9079 | 2618 | 0 | 44800 | 0.0031 |
| audit | deepseek-flash | no | 20198 | 26896 | 0 | 358400 | 0.0202 |
| fix-2 | deepseek-flash | no | 8973 | 2203 | 0 | 48384 | 0.0028 |

Total: $0.0736. Prices: deepseek line, as measured by its adapter.
