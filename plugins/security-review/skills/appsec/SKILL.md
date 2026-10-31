---
name: appsec
description: Application security playbook for threat modeling (STRIDE), supply-chain security (SBOM/SLSA), vulnerability management with SLAs, and CI/CD security guardrails. Use for security reviews, secure-by-default architecture, release gating, and incident triage.
---

# AppSec — Application Security

## Scope

Use for threat modeling new features, reviewing security architecture, managing vulnerability findings with SLA enforcement, hardening CI/CD pipelines, and validating supply-chain integrity.

## Workflow

1. **Threat model (STRIDE)**: For each new feature or significant change, identify risks across all six STRIDE categories. Define mitigations and acceptance criteria per risk.
2. **Secure by default**: Auth, authz, input validation, output encoding, and least-privilege applied at design time — not as patches after review.
3. **Vulnerability management**: Triage CVEs by CVSS score plus exploitability context. Apply SLAs: Critical ≤ 24h, High ≤ 7d, Medium ≤ 30d, Low ≤ 90d.
4. **Supply-chain security**: Generate SBOM per artifact. Sign images with Cosign. Enforce SLSA level appropriate to service risk profile.
5. **CI/CD guardrails**: SAST (Semgrep), SCA (Snyk/Dependabot), secrets detection, IaC scanning, policy-as-code (OPA) — all as blocking pipeline gates.
6. **Release gating**: Sign off on critical/high findings resolution before release. Document accepted risks with owner and expiry date.

## Toolbelt (via Bash)

- **SAST**: `semgrep --config=auto --json`, `bandit -r src/` (Python), `eslint-plugin-security`
- **SCA**: `snyk test --json`, `pip-audit --format=json`, `npm audit --json`, `trivy fs .`
- **SBOM**: `syft dir:. -o spdx-json > sbom.json`, `cosign sign --key cosign.key image:tag`
- **DAST**: `zap-baseline.py -t https://target -r baseline.html`, `zap-full-scan.py`
- **Secrets**: `trufflehog git file://. --json`, `gitleaks detect --source . --report-format json`
- **IaC scan**: `trivy config .`, `checkov -d . --output json`, `conftest test --policy policy/ plan.json`
- **IAM**: Review IAM policies, `vault audit list`, AWS IAM Access Analyzer

## STRIDE Threat Model Matrix

| Threat | Example Attack | Primary Controls |
|--------|---------------|-----------------|
| **S**poofing | Credential theft, session hijack | MFA, strong authn, cert pinning, short-lived tokens |
| **T**ampering | Parameter injection, MITM, file manipulation | Input validation, HMAC, TLS, signed artifacts |
| **R**epudiation | Deny performing an action | Tamper-evident audit logs, non-repudiation tokens |
| **I**nformation Disclosure | Data leakage, verbose errors, path traversal | Encryption at rest/transit, secrets rotation, least privilege |
| **D**enial of Service | Resource exhaustion, large payload attacks | Rate limiting, quotas, circuit breakers, input size limits |
| **E**levation of Privilege | IDOR, privilege escalation, injection | RBAC, least privilege, deny-by-default, input sanitization |

## Vulnerability SLA Policy

| Severity | CVSS Range | Response SLA | Escalation |
|----------|-----------|--------------|------------|
| Critical | 9.0–10.0 | ≤ 24h patch | Immediate incident |
| High | 7.0–8.9 | ≤ 7 days | Engineering lead |
| Medium | 4.0–6.9 | ≤ 30 days | Sprint planning |
| Low | 0.1–3.9 | ≤ 90 days | Backlog |

## Required Security Gates in CI

```yaml
gates:
  - secrets_detection   # trufflehog / gitleaks (block on any finding)
  - sast                # semgrep (block on critical/high)
  - sca                 # snyk / pip-audit (block on critical)
  - image_scan          # trivy (block on critical/high in final image)
  - sbom_generation     # syft (attach as release artifact)
  - iac_policy          # checkov / conftest (block on failed policies)
```

## Guardrails

- Critical/High vulnerabilities block release — no exceptions without documented risk acceptance signed by security lead.
- Every new external-facing endpoint or auth flow requires threat model before implementation.
- No hardcoded secrets — enforce via pre-commit hooks and CI gate. Rotation required on any confirmed exposure.
- Secrets found in git history require immediate rotation and incident declaration.
- SBOM must be generated and signed for every production release artifact.

## Handoff Notes

- To `backend-engineer`: auth/authz implementation requirements, input validation patterns, secure coding fixes.
- To `frontend-engineer`: client-side security controls, CSP policy requirements, token handling standards.
- To `devops-platform`: pipeline security gates, IAM policy constraints, image signing workflow, IaC policy rules.
- To `tech-lead`: architectural security risks, trust boundary recommendations, security NFR trade-offs.
