# Context window packing with priority, pinning, and safe truncation

Status: accepted (generated, pending human review)

## Context

Applications need to compose prompts from a mix of pinned system messages and lower-priority content, respecting a token budget while preserving input order and avoiding mid-word or mid-code-fence cuts.

## Decision

Implement a pure-Python packer with frozen dataclasses Item/PackedItem/PackResult, a PackError hierarchy, and a pack() algorithm that validates all inputs, includes pinned items verbatim, sorts non-pinned items by descending priority (stable by input position), and truncates using binary search over word boundaries with code-fence safety.

## Consequences

The library is deterministic, typed, and dependency-free. Token counting is user-injectable. Truncation is limited to boundary positions and may drop items that cannot be safely truncated; this provides predictable outputs but may underutilise budget in pathological texts without whitespace or with unbalanced fences.
