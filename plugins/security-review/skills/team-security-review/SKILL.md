---
name: team-security-review
description: Security review playbook for multi-agent code delivery. Use for threat-focused audits, secure coding checks, and release gating.
---

# Team Security Review

## Scope

Use this skill to review security posture before merge/release.

## Workflow

1. Identify trust boundaries and attacker-controlled inputs.
2. Review authn/authz controls and permission checks.
3. Check for injection, traversal, SSRF, deserialization, and unsafe exec patterns.
4. Inspect secret handling and sensitive logging.
5. Output findings ordered by severity with reproducible evidence.

## Guardrails

- Prioritize exploitable critical/high issues first.
- Provide concrete remediation, not generic advice.
- Flag missing tests for security-sensitive paths.
- Remain read-only unless explicitly asked to patch.

## Handoff Notes

Escalate schema/permission issues to `team-dba-architecture`.
Escalate API attack surface concerns to `team-backend-python`.
