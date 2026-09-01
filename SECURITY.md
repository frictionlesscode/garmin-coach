# Security policy

## Reporting a vulnerability

Please don't open a public issue for anything security-sensitive. Use GitHub's private
vulnerability reporting instead — the repository's **Security** tab → **Report a
vulnerability**.

## Scope

This repository is a **Claude Skill**: Markdown documentation (`SKILL.md`) and evaluation
cases (`evals/`). It ships no server, holds no credentials, and makes no network calls of
its own. It only tells Claude how to interpret data it already has from the companion MCP
server.

Anything involving stored data, credentials, or account access belongs to
[garmin-mcp](https://github.com/frictionlesscode/garmin-mcp), which has its own security
policy.

## No warranty

Provided "as is", without warranty of any kind — see [LICENSE](LICENSE).
