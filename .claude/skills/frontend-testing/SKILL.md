---
name: frontend-testing
description: "Frontend testing patterns — unit, component, integration, E2E"
disable-model-invocation: true
context:
  - PROJECT.md
---

# /frontend-testing — Frontend Test Patterns (Domain Skill)

### Testing Pyramid
1. **Unit tests** — Pure logic, utilities, formatters, validators
2. **Component tests** — Render, props, events, state changes
3. **Integration tests** — Feature flows across components
4. **E2E tests** — Critical user journeys only

### Component Testing
- Test behavior, not implementation
- Query by role/label/text, not CSS selectors
- Test user interactions: click, type, submit
- Test loading, error, and empty states
- Mock API calls, not child components

### Patterns
```
// Arrange
render(<Component prop="value" />)

// Act
await userEvent.click(screen.getByRole('button', { name: 'Submit' }))

// Assert
expect(screen.getByText('Success')).toBeInTheDocument()
```

### Rules
- No snapshot tests for large components (too fragile)
- Mock timers for async tests (no real delays)
- Clean up after each test (no shared state)
- Test accessibility: roles, labels, keyboard navigation
