---
name: security-audit
description: "Security audit against OWASP Top 10"
argument-hint: "[scope or file path]"
---

# /security-audit — Security Audit

### Checks
1. **Injection** — SQL, NoSQL, OS command, LDAP injection vectors
2. **Broken Auth** — Weak passwords, missing MFA, session management
3. **Sensitive Data** — Hardcoded secrets, unencrypted storage, PII leaks
4. **XXE** — XML external entity processing
5. **Broken Access Control** — Missing auth checks, IDOR, privilege escalation
6. **Misconfig** — Default credentials, verbose errors, unnecessary features
7. **XSS** — Reflected, stored, DOM-based cross-site scripting
8. **Insecure Deserialization** — Untrusted data deserialization
9. **Vulnerable Components** — Known CVEs in dependencies
10. **Logging** — Insufficient logging, missing audit trails

### Output
Severity-ranked findings with specific remediation steps.
