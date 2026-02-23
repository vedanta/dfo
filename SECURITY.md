# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 0.1.x   | Yes                |

## Reporting a Vulnerability

If you discover a security vulnerability in dfo, please report it responsibly.

**Do NOT open a public GitHub issue for security vulnerabilities.**

### How to Report

1. **GitHub Private Advisory** (preferred): Use [GitHub Security Advisories](https://github.com/vedanta/dfo/security/advisories/new) to report the issue privately.
2. **Email**: Send details to the maintainer via the email listed on the [GitHub profile](https://github.com/vedanta).

### What to Include

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

### Response Timeline

- **Acknowledgment**: Within 48 hours
- **Initial assessment**: Within 5 business days
- **Fix or mitigation**: Depends on severity, typically within 30 days

### Scope

Security issues in the following areas are in scope:

- Command injection or arbitrary code execution
- Credential or secret exposure
- Unsafe handling of Azure SDK credentials
- DuckDB injection or data corruption
- Unsafe defaults in execution commands

### Out of Scope

- Issues requiring physical access to the machine running dfo
- Social engineering attacks
- Denial of service against local CLI usage
