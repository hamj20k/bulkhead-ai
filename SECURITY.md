# Security Policy

Bulkhead is a security-adjacent library, so vulnerability reports are welcome and
taken seriously.

## Supported versions

| Version | Supported |
| ------- | --------- |
| 0.1.x | Yes |

## Reporting a vulnerability

Please do not open a public issue for a vulnerability. Email the maintainer or
use GitHub's private vulnerability reporting if it is enabled on the repository.

Include:

- A short description of the issue.
- Reproduction steps or a minimal example.
- Affected package: npm, Python, demo GUI, docs, or all.
- Whether the issue can expose secrets, bypass separation, or mislead users.

Expected response: acknowledgement within 7 days, then a public advisory or
changelog entry once a fix is available. There is no paid bug bounty at this
time.

## Scope

In scope:

- Package behavior that places untrusted content in a higher-authority role.
- Wrapper behavior that flattens trusted and untrusted content into prompt soup.
- Incorrect gating behavior that contradicts documented policy.
- Secret leakage in demos, logs, workflows, or examples.

Out of scope:

- General model jailbreaks that do not involve Bulkhead's separation behavior.
- False negatives in the heuristic scorer unless they contradict documented
  behavior.
- Attacks requiring compromised user code, compromised registry credentials, or
  malicious dependencies outside Bulkhead.
