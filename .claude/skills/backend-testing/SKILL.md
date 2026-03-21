---
name: backend-testing
description: "Backend testing patterns — unit, integration, API, database"
disable-model-invocation: true
context:
  - PROJECT.md
---

# /backend-testing — Backend Test Patterns (Domain Skill)

### Testing Strategy
1. **Unit tests** — Business logic, validators, transformers
2. **Integration tests** — Database queries, external service calls
3. **API tests** — Full request/response cycle
4. **Contract tests** — API contract validation

### API Testing
- Test all HTTP methods and status codes
- Test request validation (missing fields, wrong types, edge values)
- Test authentication and authorization
- Test pagination, filtering, sorting
- Test error responses format

### Database Testing
- Use test database (not mocks for integration tests)
- Reset state between tests (transactions or truncate)
- Test migrations up and down
- Test constraints and cascades

### Patterns
```
// Arrange
const user = await createTestUser()
const token = generateToken(user)

// Act
const response = await request(app)
  .post('/api/items')
  .set('Authorization', `Bearer ${token}`)
  .send({ name: 'test' })

// Assert
expect(response.status).toBe(201)
expect(response.body.data.name).toBe('test')
```

### Rules
- Test both success and error paths
- Use factories for test data (not raw SQL)
- Isolate tests — no order dependencies
- Mock external services, not internal modules
