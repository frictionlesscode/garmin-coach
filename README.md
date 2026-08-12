# garmin-coach

A Claude Skill that teaches Claude how to correctly read and reason about data from [garmin-mcp](https://github.com/frictionlesscode/garmin-mcp) — a companion MCP server exposing a Garmin Connect account's activities, sleep, HRV, body-weight trend, and more.

This skill is deliberately **just the "how to read the data" layer** — which tool answers which question, what each field's units and `null`s mean, which numbers are directly comparable and which aren't (e.g. HR zone minutes across a zone-config change). It contains **no training philosophy, thresholds, or programming rules of its own.** Your training plan lives in the conversation with Claude, not baked into this skill — see "The one rule that matters" in [SKILL.md](SKILL.md).

## Why this exists

MCP tools return raw, correct data — but a model reading `hr_zones` minutes across two activities with different `zone_config_id`s, or treating `avg_hr: null` as `0`, or comparing `get_training_load`'s TRIMP figure to Garmin Connect's own displayed number without noting they're not the same calculation, will confidently produce wrong conclusions from *correct* inputs. This skill exists to close that gap — it's tool documentation written for an LLM to act on, not for a human to read once and remember.

## Requirements

- A running instance of [garmin-mcp](https://github.com/frictionlesscode/garmin-mcp), connected to Claude as a custom connector.
- Claude with Skills support (claude.ai, Claude Code, or the Claude app).

## Installing

1. Set up `garmin-mcp` first (see its README) and connect it to Claude.
2. Install this skill via Claude's Skills UI (or drop `SKILL.md` into your skills directory, depending on how you're running Claude).
3. Ask Claude something like "how should I train today" or "log my weight, 182.4" — it should reach for the right `garmin-mcp` tool on its own.

## Evals

`evals/evals.json` has a small set of scenario-based checks (does the skill call the right tool, does it correctly flag a `null`/edge case rather than guessing) — useful if you're modifying `SKILL.md` and want a sanity check that it still triggers and reasons correctly.

## Related

- [garmin-mcp](https://github.com/frictionlesscode/garmin-mcp) — the MCP server this skill is written against. Keep the two in sync: if a tool's return shape changes there, `SKILL.md` here needs the matching update (this has bitten the project once already — see its git history).
