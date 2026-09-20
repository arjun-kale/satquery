# ADR-007: Deterministic semantic router

## Decision

Use local sentence-transformer similarity against versioned canonical templates,
then compile a fixed typed DAG.

## Context

The execution trace must be predictable and safe. Regex alone is brittle against
paraphrases; an LLM controller adds cost and stochastic behaviour.

## Options considered

- Local embedding-template matching + fixed DAGs
- Keyword/regex routing
- Local constrained LLM controller

## Chosen approach and trade-offs

Fixed thresholds and an ambiguity rejection path keep routing deterministic while
handling normal paraphrases. The supported query surface is intentionally bounded.

## Future migration path

A local constrained LLM can be evaluated later behind the same trace schema.
