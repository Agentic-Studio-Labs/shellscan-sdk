# ShellScan

Security scanning for AI agents. Scan skills, MCP servers, and agent codebases for vulnerabilities before deployment.

ShellScan runs four specialist scanners in parallel to detect prompt injection, credential leaks, code injection, obfuscation, supply chain attacks, and more.

## Install

```bash
pip install shellscan
```

## Quick Start

```bash
export SHELLSCAN_API_KEY="sk_live_..."

# Scan a skill
shellscan SKILL.md handler.py

# JSON output for CI pipelines
shellscan --json SKILL.md handler.py
```

## Exit Codes

| Code | Verdict | Meaning |
|------|---------|---------|
| 0 | PASS | No issues found |
| 1 | FAIL | Critical or high severity findings |
| 2 | REVIEW | Medium severity findings worth reviewing |

## What It Checks

ShellScan runs four scanners in parallel:

- **Prompt injection** — instruction overrides, jailbreak patterns, role reassignment
- **Code injection** — eval/exec, subprocess calls, reverse shells, command injection
- **Secret detection** — API keys, tokens, credentials (AWS, Stripe, Slack, GitHub, etc.)
- **Obfuscation** — base64 payloads, hex/unicode escapes, chr() concatenation, string assembly

## CI/CD Integration

ShellScan returns non-zero exit codes on findings, so it works as a gate in any CI pipeline:

```yaml
# GitHub Actions
- name: Scan agent skill
  env:
    SHELLSCAN_API_KEY: ${{ secrets.SHELLSCAN_API_KEY }}
  run: shellscan SKILL.md handler.py
```

## Configuration

| Environment Variable | Description | Default |
|---------------------|-------------|---------|
| `SHELLSCAN_API_KEY` | API key (required) | — |
| `SHELLSCAN_API_URL` | API base URL | `https://api.shellscan.dev` |

## REST API

The CLI wraps the ShellScan REST API. You can also use the API directly:

```bash
# Submit a scan
curl -X POST https://api.shellscan.dev/v1/scan \
  -H "Authorization: Bearer $SHELLSCAN_API_KEY" \
  -F "files=@SKILL.md"

# Check status / get report
curl https://api.shellscan.dev/v1/scan/{run_id} \
  -H "Authorization: Bearer $SHELLSCAN_API_KEY"

# Org profile and scan history
curl https://api.shellscan.dev/v1/org \
  -H "Authorization: Bearer $SHELLSCAN_API_KEY"

# Manage API keys (list, create, revoke)
curl https://api.shellscan.dev/v1/org/keys \
  -H "Authorization: Bearer $SHELLSCAN_API_KEY"
```

## Roadmap

- **Deep scan** — behavioral analysis, dataflow tracing, supply chain integrity checks
- **Assess** — AI-powered semantic reasoning, OWASP Agentic Top 10 mapping, risk scoring
- **Fix** — automated remediation guidance with concrete code suggestions
- **Per-key permissions** — scoped API keys with custom rate limits and depth restrictions
- **Python client library** — programmatic access beyond the CLI
- **MCP server scanning** — configuration and permissions analysis
- **Moltlaunch integration** — automatic scanning of skills published to the marketplace

## Test Fixtures

The `tests/skills/` directory contains reference skills for testing scanner coverage:

- **`known-malicious/backdoor-skill/`** — C2 communication, reverse shells, credential harvesting, AWS keys
- **`known-malicious/sqli-traversal-skill/`** — SQL injection, path traversal, Slack/GitHub tokens
- **`known-malicious/obfuscation-skill/`** — Base64, hex, unicode, chr() concatenation, Stripe key
- **`known-safe/`** — Clean skills that should produce zero findings

## License

MIT
