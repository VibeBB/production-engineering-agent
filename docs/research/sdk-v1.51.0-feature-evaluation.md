# OpenHands SDK v1.51.0 feature evaluation (production-engineering-agent)

Scope: `openhands-sdk` and `openhands-tools` move from 1.50.1 to 1.51.0
(PyPI upload 2026-10-03T07:38Z). The complete upstream range
`v1.50.1..v1.51.0` (17 commits) was reviewed. uv moves from 0.12.21 to
0.12.22 (2026-10-01). Ruff was already locked at 0.16.10 and
`anchore/sbom-action` was already pinned at v0.24.3, so no change was
required for either.

Primary sources:
[OpenHands SDK v1.51.0 release](https://github.com/OpenHands/software-agent-sdk/releases/tag/v1.51.0),
[uv 0.12.22 release](https://github.com/astral-sh/uv/releases/tag/0.12.22).

## SDK 1.50.1 -> 1.51.0

| Upstream change | Decision | Evaluation |
| --- | --- | --- |
| #5151 `tools` is the only tool control, selected from one server catalog | adopted implicitly | `enable_sub_agents` and `enable_switch_llm_tool` are deprecated in 1.51.0 (removal 1.56.0) and fold into the profile `tools` list. All `plugins/prodeng/agents/*.md` frontmatter already selects `task_tool_set` inside `tools:` and uses no legacy switch, so the plugin is already on the canonical model; sub-agent delegation stays enabled. |
| #5358 keep delegated sub-agents within the profile's tools and MCP servers | adopted implicitly | Delegated sub-agents can no longer escape the profile's tool/MCP scope. This matches the repository invariant that sibling cooperation happens only through declared delegation; the review agent remains read-only with no MCP configuration. |
| #5449 let a profile replace the agent's persona | not adopted | Each agent's persona is authored in its own `plugins/prodeng/agents/*.md` frontmatter; no profile-level persona override is wanted, since planner/liaison/ftm/review personas are deliberately distinct. |
| #5450 loaded tools supply their own system-prompt guidance (browser) | not applicable | No VibeBB plugin ships or enables a browser tool. |
| #5332 resolve `prompt_cache_key` via the real provider for proxied models | adopted implicitly | Internal fix; plugins do not set `prompt_cache_key` and no proxied provider is configured. No action needed. |
| #5274 OpenRouter becomes a verified provider | not adopted | Informational only: profiles continue to use their configured providers; no profile gains OpenRouter in this bump. |
| #5412 router sends system+user classifier messages for direct routing; #5417 `/switch_llm` provider resolution | upstream image | This repository does not build or manage an OpenHands agent-server image; agent-server/router-only fixes need no plugin change. |
| #5434 deprecate `ACPAgentSettings.llm` | not applicable | Plugins run local conversations, not ACP agents. |
| #1326 fix `find_dotenv` assertion error in local conversation | adopted implicitly | Bug fix picked up with the pin; local conversations no longer assert when no `.env` file exists. |
| #5419 pydantic 2.13.5 dependency bump | lock-only | Picked up through `uv.lock`; contract models already validate under Pydantic v2. |
| #4945, #5415, #5425, #5428, #5397, #5470 CI/test/release housekeeping | not applicable | Upstream CI and release chores; no repository behavior to adopt. |

## uv 0.12.21 -> 0.12.22

| Upstream change | Decision | Evaluation |
| --- | --- | --- |
| #22104 record default groups for non-project workspace roots in lockfiles | adopted implicitly | `uv.lock` now records `default-groups = ["dev", "sdk-check"]` at the file head; harmless metadata that documents the project default groups. |
| #22147 add CPython 3.10.22, 3.11.17, 3.12.15, 3.13.16, 3.14.8 | adopted implicitly | The tools image runs `uv python install 3.12`, so the next image build picks up 3.12.15 automatically; no Dockerfile change required. |
| #22098 `UV_PYTHON_ARCH` selects interpreter architecture | not adopted | The image pins CPython by version only on a single architecture; no need for an architecture selector. |
| #22083 verify unchanged requirements against existing lockfile hashes when relocking | adopted implicitly | Integrity fix; makes `--locked`/`--frozen` flows in the publish Dockerfile more trustworthy. |
| #22015, #22101, #22112, #22113, #22103, #22104 workspace/lockfile and wheel-tag fixes | not applicable | This repository is a single-project package, not a workspace; none of the workspace-member resolution fixes alter its resolution. |
| #21937, #22124 CLI message formatting and `uv publish` help cleanup | not adopted | Cosmetic CLI changes; no workflow depends on uv publish output. |
| #22090, #22114 `uv audit` preview improvements | not adopted | Preview feature; the dependency checker audits pins itself rather than running `uv audit`. |
| #22126 compress embedded Python download metadata; #22121 Rust 1.97/1.99 toolchain | not applicable | Build/binary internals; no repository surface. |

## Other components

- **ruff**: already locked at 0.16.10 before this bump; `uv lock --upgrade`
  left it unchanged. No new diagnostics expected; `ruff check` and
  `ruff format --check` still pass.
- **anchore/sbom-action**: already pinned to commit
  `66cbf4bc1f1c0d2edc94016e65bc221b6bb0ad6c` (`# v0.24.3`) in
  `publish-prodeng-images.yml`; no change required.

## Compatibility deferrals

MCP 2.x remains deferred: installed SDK 1.51.0 metadata continues to
require `fastmcp>=3.2.0,<4`, which caps `mcp<2`. The deferral entry in
`scripts/dependency_update_deferrals.json` now records `latest: 2.3.0`
(current PyPI release) and cites openhands-sdk 1.51.0; `review_by` is
unchanged. The `openhands-agent-server` image tag `1.51.0-python` is
available upstream; no committed image lock is edited by this bump.
