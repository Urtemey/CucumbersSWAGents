---
name: auth-patterns
description: "Authentication and authorization patterns"
disable-model-invocation: true
context:
  - PROJECT.md
---

# /auth-patterns — Auth Design (Domain Skill)

Auto-loaded when working with authentication/authorization.

### Authentication
- Use industry standards: OAuth 2.0, OpenID Connect, JWT
- Tokens: short-lived access tokens (15min), long-lived refresh tokens (7d)
- Store refresh tokens securely (httpOnly cookies or encrypted DB)
- Hash passwords with bcrypt/scrypt/argon2 (never MD5/SHA)
- Implement rate limiting on auth endpoints
- Account lockout after N failed attempts

### Authorization
- RBAC (Role-Based Access Control) for simple cases
- ABAC (Attribute-Based) for complex policies
- Check permissions at the API layer, not just UI
- Principle of least privilege — default deny
- Audit log all privilege escalations

### Session Management
- Invalidate sessions on password change
- Implement session timeout (idle + absolute)
- Support concurrent session limits
- Provide "revoke all sessions" functionality

### Checklist
- [ ] Passwords hashed with strong algorithm
- [ ] Tokens have appropriate expiry
- [ ] Auth checks on every protected endpoint
- [ ] Rate limiting on login/register
- [ ] No sensitive data in JWT payload
- [ ] CSRF protection for cookie-based auth
