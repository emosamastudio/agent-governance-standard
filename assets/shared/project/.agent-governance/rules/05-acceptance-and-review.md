# Acceptance, Review, and Comment Policy

1. Each feature must have explicit acceptance criteria before implementation.
2. Prefer scriptable, testable, automatable acceptance.
3. If acceptance cannot be automated, mark it explicitly and route it to an independent expert agent or human review.
4. Implementation is not done when code exists; it is done when acceptance passes.
5. After implementation, schedule review and cleanup:
   - architecture alignment
   - boundary integrity
   - coupling
   - duplication
   - abstraction quality
   - maintainability
   - debt capture
6. Record cleanup work even when it is deferred.
7. Avoid low-value comments. Add comments only when they preserve non-obvious protocol, constraints, boundaries, or rationale.
