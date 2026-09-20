# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| v0.3.x (current) | ✅ Yes |
| v0.1–v0.2 | Bug fixes only, if a critical issue is found |

## Reporting a Vulnerability

**Please do not report security issues in public issues.**

If you believe you've found a security vulnerability in CodeForge AI, please:

1. **Email us** at [Nofacetryharder@gmail.com](mailto:Nofacetryharder@gmail.com) with:
   - A description of the issue and its potential impact
   - Steps to reproduce (PoC preferred)
   - The affected version
2. We aim to acknowledge receipt within **48 hours** and to ship a fix within
   a reasonable timeframe (typically 14 days for confirmed critical issues).
3. We will **never** publish your identity as the reporter.

### Out of scope
- Attacks requiring access to local files, the local disk, or the Ollama daemon (CodeForge is a local-first tool; the machine owner controls this surface)
- Issues already publicly disclosed with a known workaround
- Vulnerabilities in third-party dependencies (please report upstream first; we will re-audit)

## Security Practices

- Local-first by design: no telemetry, no analytics, no remote code execution paths in local mode
- Uploaded files are written outside the repository and cleared on restart
- We plan to run automated dependency audits and a vulnerability-testing pass
  before the public launch and at each subsequent release

## Dependencies We Audit

- Python: `pip-audit` (requirements in `src/backend/requirements.txt`)
- JavaScript: `npm audit` (frontend dependencies)
