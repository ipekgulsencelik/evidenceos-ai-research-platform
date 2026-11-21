# ADR-0001: Modular monolith and ports/adapters

Status: Accepted for foundation

## Context

The team needs one codebase for academic and legal research with shared citation
and provenance logic; there is not yet a separate service deployment need.

## Decision

Adopt a modular monolith and hexagonal (ports/adapters) architecture.
Domain and use-case code depend only on domain abstractions. Infrastructure
implements the interfaces. Transactions are committed explicitly by use cases.

## Consequences

Advantages: small deployment surface, local transactions, testable use cases,
provider independence. Tradeoffs: discipline needed at module boundaries;
future service extraction requires bounded contexts and API contracts.
