# Repository agent instructions

## Purpose

`cloudflare-ai-gateway-analyzer` is a Python CLI that collects Cloudflare AI Gateway log metadata into one local SQLite database, extracts token usage from response payloads, and exposes local query/export commands.

## Codex Startup Behavior

- Codex is expected to start from the repository root.
- This root `AGENTS.md` is the primary startup instruction for this repository.
- There are currently no child `AGENTS.md` files. If one is added later, read it before editing files under that subtree.
- If a future directory contains `AGENTS.override.md`, stop and ask the user before changing the ordinary `AGENTS.md` strategy for that same directory.
- Do not infer commands from habits. Use commands listed here or confirmed from `pyproject.toml`, `requirements.txt`, `README.md`, or `docs/`.

## Directory Map

| Path | Responsibility | Local AGENTS.md | Read when |
|---|---|---:|---|
| `src/cf_aigw_analyzer/` | Python package and CLI implementation | No | Always inspect relevant modules before code changes |
| `tests/` | `unittest` coverage for parser, database, and paths | No | Add or update tests with behavior changes |
| `docs/` | Human-facing architecture, operations, security, and development docs | No | Update when behavior, data model, or safety guidance changes |
| `local/` | Private runtime data and SQLite databases | No | Do not edit for source changes; never stage or commit |
| `.gitignore` | Keeps runtime data, SQLite files, and Python artifacts out of git | No | Review before adding new generated or private paths |
| `README.md` | User-facing quickstart and command overview | No | Update when public CLI usage changes |
| `pyproject.toml` | Packaging metadata and console scripts | No | Update when dependencies, Python version, or entry points change |
| `requirements.txt` | Runtime dependency mirror for simple installs | No | Keep aligned with `pyproject.toml` runtime dependencies |

## On-demand Cat Protocol

Before editing a subtree that later gains a local `AGENTS.md`, read it with:

```bash
cat <path>/AGENTS.md
```

If multiple nested `AGENTS.md` files exist on the target path, read them from shallow to deep before making changes. The closest file to the edited path wins on conflicts.

## Commands

| Command | Purpose | Scope | Sandbox notes |
|---|---|---|---|
| `python3 -m venv .venv` | Create local virtual environment | repo | Writes `.venv/`, ignored by git |
| `source .venv/bin/activate` | Activate local virtual environment | repo | Shell-local only |
| `pip install -e .` | Install package and CLI in editable mode | repo | Needs network if dependencies are missing |
| `PYTHONPATH=src python3 -m compileall -q src tests` | Syntax/bytecode check | repo | OK in sandbox |
| `PYTHONPATH=src python3 -m unittest discover -s tests` | Unit tests | repo | OK in sandbox |
| `PYTHONPATH=src python3 -m cf_aigw_analyzer.cli --help` | CLI smoke test without install | repo | OK in sandbox |
| `cf-aigw-analyzer --help` | Installed CLI smoke test | repo | Requires editable install |
| `cf-aigw-analyzer accounts` | List Cloudflare accounts | runtime | Requires network and Cloudflare credentials |
| `cf-aigw-analyzer gateways -a <ACCOUNT_ID>` | List AI Gateway resources | runtime | Requires network and Cloudflare credentials |
| `cf-aigw-analyzer sync ...` | Sync log metadata to SQLite | runtime | Requires network and Cloudflare credentials; writes `local/` |
| `cf-aigw-analyzer sync-usage ...` | Fetch response usage and parse token data | runtime | Requires network and Cloudflare credentials; writes `local/` |
| `cf-aigw-analyzer query ...` | Query local SQLite data | runtime | Requires existing local DB; data may be sensitive |
| `cf-aigw-analyzer status` | Show local DB status | runtime | Requires existing local DB for useful output |
| `git diff --check` | Check whitespace errors before commit | repo | OK in sandbox |
| `git status --short --ignored` | Confirm staged/untracked/ignored boundaries | repo | OK in sandbox |

## Global Rules

- Keep this as a small Python CLI project. Do not introduce a server, daemon, web UI, or scheduler unless explicitly requested.
- Default storage is one SQLite file at `local/data/cloudflare_ai_gateway.sqlite`.
- Keep all accounts and gateways in the same SQLite database, scoped by `(account_id, gateway_id, log_id)`.
- `logs` is for sanitized log metadata only.
- `log_usage` and `log_metrics` are 1:1 side tables keyed by the same log identity.
- Do not persist request or response body content. The `/response` endpoint is used only for usage parsing.
- Keep runtime dependencies minimal. New dependencies need a clear reason and must be added to both `pyproject.toml` and `requirements.txt` when they are runtime dependencies.
- Use `unittest` for current tests unless the project is deliberately migrated to another test runner.
- Public-facing docs should avoid private machine paths, personal account identifiers, real gateway names, and credentials.
- The project currently has no selected open-source license. Do not add license claims or SPDX headers until the user chooses a license.

## Security and Privacy Rules

- Never commit `local/`, SQLite databases, WAL/SHM files, exports, `.env`, credentials, or private runtime data.
- Do not print or paste real Cloudflare tokens or Global API keys into docs, tests, commit messages, or PR text.
- Treat account IDs, gateway IDs, model usage, cost data, token counts, timestamps, and operational metadata as potentially sensitive.
- Before commits, run a targeted secret/privacy scan with `rg` and inspect `git status --short --ignored`.
- When using credentials for live validation, pass them via environment variables or transient shell context. Do not write them into tracked files.
- Do not add sample data copied from a real Cloudflare account. Use small synthetic fixtures in tests.

## Do Not

- Do not stage or commit anything under `local/`.
- Do not add a `LICENSE` file or license section that grants reuse until the user chooses an open-source license.
- Do not push to `origin` unless explicitly asked.
- Do not commit generated Python artifacts such as `__pycache__/`, `*.egg-info/`, `.pytest_cache/`, or `.DS_Store`.
- Do not store full request/response payloads in SQLite for convenience.
- Do not replace the standard-library HTTP client with a larger framework without a concrete need.
- Do not add XLSX support unless the scope changes.
- Do not broaden live sync commands in tests; unit tests should remain offline and deterministic.

## Validation

For code changes, run:

```bash
PYTHONPATH=src python3 -m compileall -q src tests
PYTHONPATH=src python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m cf_aigw_analyzer.cli --help
```

For packaging or CLI entry-point changes, also verify in a temporary virtual environment:

```bash
python3 -m venv /tmp/cf-aigw-analyzer-venv
. /tmp/cf-aigw-analyzer-venv/bin/activate
pip install -e .
cf-aigw-analyzer --help
```

For live Cloudflare behavior changes, first run small limits:

```bash
cf-aigw-analyzer accounts
cf-aigw-analyzer gateways -a <ACCOUNT_ID>
cf-aigw-analyzer sync -a <ACCOUNT_ID> --gateway-name <GATEWAY_NAME> --limit 10
cf-aigw-analyzer sync-usage -a <ACCOUNT_ID> --gateway-name <GATEWAY_NAME> --missing-only --limit 10
```

Live commands require network and Cloudflare credentials. If they are skipped, state that clearly in the final response.

## Commit Boundaries

Prefer focused local commits:

1. Guardrails and packaging (`.gitignore`, `pyproject.toml`, `requirements.txt`).
2. Implementation and tests (`src/`, `tests/`).
3. Documentation and agent instructions (`README.md`, `docs/`, `AGENTS.md`).

Before each commit:

```bash
git status --short --ignored
git diff --check
```

After staging, inspect staged files with:

```bash
git diff --cached --stat
git diff --cached --name-only
```

Do not mix private runtime data with source commits.

## Notes for Future Agents

- `certifi` is used because some local Python installations do not have a working default CA chain for Cloudflare API calls.
- `sync-usage --missing-only` should not repeatedly fetch confirmed `no_usage` rows.
- Cloudflare response-body-unavailable 404 cases should be recorded as `no_usage`, not permanent `failed`.
- If the data model changes, update `docs/data-model.md`, tests, and any migration notes together.
