# Security Policy

RegulaForge handles sensitive regulatory and compliance data. We take the security of our platform seriously and appreciate the community's help in disclosing vulnerabilities responsibly.

---

## Supported Versions

We currently support the following major versions with security updates:

| Version | Supported |
|---------|-----------|
| 1.x (current) | ✅ Supported |
| < 1.0 | ❌ Not supported |

Only the latest major release receives security patches. Users are strongly encouraged to always run the most recent stable version.

---

## Reporting a Vulnerability

If you discover a security vulnerability, please **do not** open a public GitHub issue. Instead, report it privately to our security team:

**Email**: security@regulaforge.dev

We aim to acknowledge receipt within **24 hours** and provide an initial assessment within **72 hours**.

### What to Include

- Type of vulnerability (e.g., SQL injection, XSS, privilege escalation)
- Full steps to reproduce the issue
- Affected components, endpoints, or modules
- Any proof-of-concept code (non-destructive)
- Your name and affiliation (optional, for credit)

### PGP Encryption (Optional)

For highly sensitive disclosures, you may encrypt your report using our PGP key:

```
-----BEGIN PGP PUBLIC KEY BLOCK-----

Comment: RegulaForge Security <security@regulaforge.dev>
Comment: Fingerprint: A1B2 C3D4 E5F6 7890 1234 5678 9ABC DEF0 1234 5678

xjMEAAAAAAYJKwYBBAHaRw8BAQdAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADCRgQoAAAAAAAN
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAA==
-----END PGP PUBLIC KEY BLOCK-----
```

**Fingerprint**: `A1B2 C3D4 E5F6 7890 1234  5678 9ABC DEF0 1234 5678`

*Note: This is a placeholder key. Contact security@regulaforge.dev for the current key before sending encrypted mail.*

---

## Disclosure Policy

We follow a **coordinated disclosure** process:

1. **Report received** — Acknowledged within 24 hours
2. **Triage and validation** — Initial assessment within 72 hours
3. **Fix development** — Remediation developed and tested
4. **Patch release** — Fix shipped in a new release
5. **Public disclosure** — After **90 days** from fix release, or earlier if a patch is already available

We ask that reporters:
- Allow up to **90 days** for a fix before any public disclosure
- Do not exploit the vulnerability or access unauthorized data
- Do not publicly disclose the issue before the coordinated disclosure date

---

## Bug Bounty Scope

We operate a limited bug bounty program for confirmed vulnerabilities. The following areas are **in scope**:

### In Scope

- Backend API endpoints (`/api/v1/*`)
- Authentication and authorization mechanisms
- Data isolation between tenants
- AI/ML prompt injection and hallucination attacks
- SQL injection, XSS, CSRF, SSRF, IDOR
- Remote code execution and file inclusion
- Privilege escalation
- Insecure direct object references

### Out of Scope

- Denial of Service (DoS/DDoS) attacks
- Physical security attacks
- Social engineering of team members
- Self-XSS
- Missing HTTP headers (without demonstrated exploit)
- Rate limiting bypass (without demonstrated impact)
- Third-party services (GitHub, Docker Hub, PyPI, npm)
- Issues in dependencies that are already fixed in newer versions
- Theoretical vulnerabilities without a working proof of concept
- Automated scanner output without manual verification

### Rewards

| Severity | Reward |
|----------|--------|
| Critical | Up to $5,000 |
| High | Up to $2,000 |
| Medium | Up to $500 |
| Low | Recognition + swag |

All rewards are at the discretion of the security team. Valid findings also qualify for a place in our security hall of fame.

---

## Security Best Practices for Users

- Always run the latest stable release
- Use strong, unique passwords and enable MFA where available
- Restrict network access to PostgreSQL, Redis, and RabbitMQ to trusted hosts only
- Use HTTPS in production — never expose the API over plain HTTP
- Rotate API keys and secrets regularly
- Enable audit logging and monitor for suspicious activity
- Review and apply the principle of least privilege for all RBAC roles

---

## Contact

**Security Team**: security@regulaforge.dev  
**PGP Fingerprint**: `A1B2 C3D4 E5F6 7890 1234  5678 9ABC DEF0 1234 5678`  
**Keybase**: [keybase.io/regulaforge](https://keybase.io/regulaforge)
