# Feature 005: Automated CI verification

Status: Approved

Design date: 2026-08-20

Approved: 2026-08-20

GitHub issue: #9

## Summary

Feature 005 adds PantryPilot's first GitHub-hosted continuous-integration
workflow. An eligible pull request targeting `main` or push to `main` creates a
fresh Ubuntu runner, reproduces the repository's supported Python and locked
dependency environment, runs the established verification contract, and
records one stable GitHub pass/fail check.

The workflow automates existing quality evidence. It does not deploy
PantryPilot, invent a new product-quality standard, or prevent a maintainer
from merging. The repository's `main` branch is currently unprotected, so
GitHub-recorded CI and required merge checks remain separate capabilities.

The design deliberately uses one job, one supported Python minor version, one
versioned Linux runner, direct named verification steps, no cache, no matrix,
no repository secrets, and no artifact uploads. This is the smallest design
that reproduces the current contract in an independent clean environment and
leaves useful GitHub evidence.

## Verified context and pre-change baseline

The design was prepared in the linked worktree
`C:\Users\sathv\Projects\pantrypilot\.worktrees\automated-ci-verification`
on branch `feat/automated-ci-verification` at starting commit
`321a620c69d3a73270c4e212f1fbaae3dd997596`. The tracked working tree was
clean.

Repository inspection established:

- `.github` contains only `pull_request_template.md`; no Actions workflow or
  CI subsystem exists.
- `.python-version` declares Python `3.12`.
- `pyproject.toml` declares `requires-python = "==3.12.*"`.
- `uv.lock` is committed, includes development dependencies, and records
  package artifact hashes.
- `pantrypilot.evaluation` exits nonzero when resolver recall does not improve
  over the exact-name baseline or when false positives are nonzero.
- Tests use isolated temporary SQLite files rather than a developer-local
  PantryPilot database.
- GitHub Issue #9 is open and defines Feature 005 as CI verification rather
  than deployment or merge enforcement.
- The public repository's default branch is `main`; Actions are enabled;
  allowed actions are currently unrestricted; default workflow permissions
  are read-only; and `main` is not protected.

The complete pre-change contract was rerun during design:

- local uv version: `0.11.32`;
- local Python version: `3.12.13`;
- `uv lock --check`: passed;
- `uv run pytest`: collected and passed 252 tests;
- pytest emitted one existing Starlette/httpx `TestClient` deprecation
  warning;
- ingredient-resolution evaluation: resolver precision `1.0`, recall `1.0`,
  zero false positives, and recall strictly greater than the exact-name
  baseline's `0.6667`;
- `uv run ruff format --check src tests`: passed;
- `uv run ruff check src tests`: passed;
- `git diff --check`: passed; and
- the working tree remained clean.

The warning is baseline evidence. Feature 005 does not suppress or fix it.

## Demonstrated problem

Features 001 through 004 established deterministic ranking, canonical
ingredient resolution, a versioned quality evaluation, durable SQLite recipe
and pantry state, migrations, transaction evidence, API contracts, and 252
tests. Their merge-readiness evidence was produced on a developer machine and
copied into pull-request prose.

That process cannot independently prove that a clean machine can reproduce the
environment or run the same gates. GitHub records neither a workflow run nor a
stable check when verification exists only in local terminal output.

Feature 005 adds the missing independent layer:

```text
eligible GitHub event
    -> fresh GitHub-hosted runner
    -> reviewed toolchain and locked environment
    -> established PantryPilot verification contract
    -> stable GitHub job/check conclusion and logs
```

The workflow supplements local engineering review. It does not replace local
verification, code review, owner judgment, or future production validation.

## Goals

- Run PantryPilot's established verification contract automatically for
  proposed and integrated `main` changes.
- Reproduce the supported Python 3.12 and locked dependency environment from
  committed repository contracts on a clean hosted runner.
- Preserve the ingredient-resolution evaluator as a real quality gate whose
  existing exit status controls CI.
- Preserve the intent of the local whitespace gate with meaningful hosted
  commit ranges.
- Produce one stable, inspectable GitHub check with named failure stages and
  ordinary workflow logs.
- Use least-privilege token permissions and remain safe for untrusted fork pull
  requests without repository secrets.
- Keep the workflow small enough for the owner to understand, maintain, and
  explain.
- Teach CI architecture, reproducibility, security, troubleshooting, evidence,
  and limitations in a Feature 005 learning guide.

## Non-goals

Feature 005 does not add or change:

- continuous delivery, continuous deployment, application deployment, cloud
  hosting, release or package publishing;
- Docker, registries, Kubernetes, Terraform, or self-hosted runners;
- model training, MLOps infrastructure, Codecov, coverage thresholds, broad
  security scanning, dependency bots, or notification integrations;
- scheduled, manual, deployment, or arbitrary-branch workflows;
- path filters, caches, artifacts, matrices, auto-merge, or automatic branch
  deletion;
- branch protection, rulesets, required status checks, Actions permissions, or
  other repository settings;
- application behavior, APIs, schemas, ranking, ingredient resolution,
  evaluator logic, request tracing, persistence, or tests;
- warning cleanup or unrelated Feature 004 findings; or
- a shared verification script or reusable workflow abstraction.

The existing deferred Feature 004 assertions, migration-history detail,
historical design amendment, inline-list bounds, request tracing, and
multi-worker limitations remain separate unless later evidence shows one
directly blocks CI correctness.

## Approaches considered

### 1. One job with direct named steps — recommended

One Ubuntu job performs checkout, toolchain setup, one locked environment sync,
and every verification gate in a separately named step.

Advantages:

- one setup and dependency installation;
- one stable check suitable for later optional branch-policy configuration;
- direct correspondence between a failed command and a GitHub step;
- no script or reusable-workflow interface to maintain;
- minimal action, permission, cache, and artifact surface; and
- complete fit with the current single-digit-second local test suite.

Cost: the job stops at the first failing gate, so one run may not reveal every
independent failure. Fixing the first failure and rerunning is preferable to
duplicated setup at the present scale.

### 2. Separate test, evaluation, and static-quality jobs

This option provides multiple simultaneous check conclusions and may reveal
several independent failures in one run.

It is rejected because every job would repeat checkout, uv/Python setup, and
dependency synchronization. The current suite is too small to justify that
runtime, network, and maintenance duplication. Multiple job names would also
create a broader future required-check policy surface.

### 3. Shared local/CI verification script or reusable workflow

This option would put command ordering in one wrapper and have local and hosted
verification call it.

It is rejected because six stable quality commands do not yet create a
maintenance problem. A wrapper would hide GitHub failure stages and introduce
another interface, platform behavior, and testing obligation. It can be
reconsidered only if local/CI drift or duplication becomes a demonstrated
problem.

Adding `actions/setup-python` beside `setup-uv` was also considered. It is not
needed because uv can install the interpreter selected by `.python-version`.
Implementation may return to design review if real hosted evidence shows that
this assumption fails; it must not add the action speculatively.

## Chosen architecture

Implementation later creates exactly one workflow file:

```text
.github/workflows/ci.yml
```

The workflow identity is:

| Element | Approved value |
|---|---|
| Workflow name | `CI` |
| Job ID | `verification` |
| Stable job/check name | `PantryPilot verification` |
| Runner | `ubuntu-24.04` |
| Timeout | 10 minutes |

The job name is the stable GitHub check that a future separately authorized
branch-protection change could reference. Feature 005 does not configure it as
required.

The single versioned Linux runner is the hosted verification target. Windows
remains a supported local-development environment through the documented uv
commands. This choice does not make PantryPilot Linux-only. A Windows hosted
job or OS matrix requires future evidence of OS-specific behavior, a
portability requirement, or a defect that the Linux job cannot expose.

`ubuntu-24.04` fixes the runner's operating-system generation. It does not pin
every preinstalled package or prevent GitHub from maintaining the image. The
job logs identify the actual hosted image and resolved toolchain used by each
run.

## Trigger and event model

The workflow responds only to:

- `pull_request` events for pull requests targeting `main`; and
- `push` events updating `main`.

No path filters apply. Documentation, workflow, dependency, evaluation, and
source changes can all invalidate some part of the contract, and no proven
safe skipped-path set exists.

No `workflow_dispatch` trigger is included. GitHub's existing rerun control is
sufficient for retrying a completed run, and a manual event has no approved
whitespace comparison range. Manual dispatch can be designed later if a
concrete maintainer use case emerges.

### Pull-request behavior

GitHub tests the merge commit it prepares for that workflow run, including the
workflow definition present in that merge commit. A fork PR can therefore
propose changes to `.github/workflows/**` as well as to application or test
code. The evidence covers integration with the PR base state recorded for that
run; it does not promise compatibility with future changes to `main`.

The security boundary does not depend on treating the workflow definition as
trusted. GitHub restricts the token for fork-originated `pull_request` runs,
withholds repository secrets, and applies fork-workflow approval policies where
configured. This workflow independently declares only `contents: read` and no
secrets. The resulting job executes untrusted proposed workflow, application,
and test code only inside that deliberately restricted environment.

Maintainers must review proposed `.github/workflows/**` changes as
security-sensitive code. A green PR check proves that the workflow definition
in the tested merge commit reported success; it does not prove that the PR left
the check definition or its required steps unchanged.

### Push-to-main behavior

The `push` run records independent evidence for the commit integrated into
`main`. It is not redundant with the PR run: the event, commit identity, and
repository state are different, and the push trigger itself needs eventual
hosted evidence.

No direct push to `main` is justified solely to test the workflow. The normal
owner-authorized merge produces the required push event.

## Concurrency and cancellation

Superseded runs for the same pull request are cancelled. The concurrency group
uses the workflow identity and pull-request number so a new synchronization of
that PR replaces obsolete work.

Push-to-main runs use a unique run-specific group and are not cancelled by a
newer push. Each integrated commit should retain its own recorded conclusion.
The approved behavior is conceptually:

```text
pull request -> stable PR-specific group -> cancel superseded run
push to main -> unique run-specific group -> retain every run
```

There is no queue, cross-PR cancellation, or deployment serialization.

## Python and uv reproducibility

Three reviewed repository/tool contracts cooperate:

1. `.python-version` selects Python `3.12` for local and hosted uv commands.
2. `pyproject.toml` requires `==3.12.*` and therefore defines the supported
   Python compatibility boundary.
3. `uv.lock` fixes the resolved dependency graph and distribution hashes.

CI does not redefine the Python contract as the locally observed patch
`3.12.13`. `uv python install` reads `.python-version` and may select a newer
compatible 3.12 patch later. The workflow prints the resolved interpreter
version so every run remains auditable. Pinning an exact Python patch would
require a separate repository compatibility decision.

uv itself is a build/verification tool outside `uv.lock`. Feature 005 pins it
to the locally verified `0.11.32` release in the workflow. The workflow is the
single declaration point for that CI tool version and its Linux artifact
checksum. An uv upgrade is an explicit reviewed tooling change, not an
automatic consequence of a new upstream release.

The setup sequence is:

```text
install pinned uv with pinned setup action, direct GitHub release download,
and verified checksum
    -> uv python install
    -> uv lock --check
    -> uv sync --locked
    -> log uv and resolved Python versions
```

`uv sync --locked` creates the clean project environment, installs the project,
and includes the default development group containing pytest and Ruff. It is
environment setup rather than a new quality gate. The separate lock check is
retained because lock consistency is an explicit established contract and
deserves its own named result.

## External actions and supply-chain policy

Every external action, including GitHub-owned actions, must use a reviewed
full 40-character commit SHA. A release-version comment appears beside the SHA
for readability. Mutable major, minor, latest, or branch references are not
accepted.

Current design-time candidates are:

```text
actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
astral-sh/setup-uv@c771a70e6277c0a99b617c7a806ffedaca235ff9 # v9.0.0
```

The current design-time candidate SHA-256 digest for uv `0.11.32`'s
`uv-x86_64-unknown-linux-gnu.tar.gz` release artifact is:

```text
aab924fd522efd06f1c5f3b93a243864fc453132c94b2dc49f1371b528a4b967
```

These values are evidence, not permission to copy stale identifiers blindly.
Immediately before committing the workflow, implementation must re-verify:

- each tag exists in the named official upstream repository;
- the tag resolves to the proposed commit SHA rather than a fork;
- the release notes and relevant action metadata match the intended upgrade;
- the uv release is final rather than draft or prerelease;
- the checksum is for the exact Linux x86-64 artifact that `setup-uv` will
  install; and
- the workflow's checksum input uses the format expected by the pinned action.

`setup-uv` version 9 defaults `download-from-astral-mirror` to `true`. The
workflow must override that default so the reviewed checksum binds the exact
direct GitHub release artifact selected by this design. The approved inputs
are conceptually:

```text
version: "0.11.32"
checksum: "<freshly re-verified Linux x86-64 artifact SHA-256>"
download-from-astral-mirror: false
enable-cache: false
cache-python: false
```

The action therefore installs uv `0.11.32` from the direct official GitHub
release, verifies the approved checksum, and disables uv and managed-Python
cache persistence explicitly. Its action ref, uv version, checksum, download
source, and cache settings change only through a reviewed tooling update.

An action upgrade process is:

1. select an intended upstream release;
2. read its release notes and security/runtime requirements;
3. resolve its official tag to the full commit SHA using GitHub metadata;
4. inspect the committed action metadata and distributed runtime sufficiently
   for the change;
5. update the SHA and release comment together;
6. rerun local workflow review and the full PantryPilot contract; and
7. require fresh hosted evidence after owner-authorized publication.

An uv upgrade additionally verifies the official release artifact checksum,
updates the workflow's version/checksum together, confirms local compatibility,
and records the new resolved versions in hosted logs.

No dependency bot is introduced to automate these decisions.

## Permissions and untrusted pull-request security

The workflow declares only:

```text
contents: read
```

Declaring one permission makes unspecified token scopes `none`. The job does
not need `checks: write` or `statuses: write`; GitHub itself records the
workflow and job conclusions. It does not need `actions: write` for
concurrency cancellation, which is workflow-scheduler behavior rather than a
job API call.

Checkout sets `persist-credentials: false` because later commands do not fetch
private content, push, tag, publish, or call authenticated repository APIs.
The repository is public. A narrowly targeted read-only fetch used to resolve a
whitespace base may use public repository access.

The ordinary `pull_request` event is required. Its workflow definition comes
from the tested PR merge commit, so proposed workflow changes are untrusted and
must run with the same deliberately restricted token/no-secret boundary as all
other proposed code.

`pull_request_target` is rejected. It runs the trusted base-branch workflow in
a more privileged base-repository context, which is unnecessary for this CI
design and unsafe to combine with checkout or execution of untrusted proposed
code.

No repository or environment secret is declared or consumed. GitHub creates a
job-scoped `GITHUB_TOKEN`, but its explicit effective permission is only
repository-content read. No personal access token, OIDC identity, deployment
credential, signing key, or private package credential exists in this design.

The ephemeral hosted runner executes proposed tests and project build steps.
Those steps must not receive secrets. The workflow does not explicitly upload
pantry contents, request bodies, SQLite databases, ranking/request histories,
or other user-derived application data as artifacts. Ordinary GitHub
workflow/step logs are expected and retained under GitHub's normal Actions
behavior.

Tests continue to use temporary SQLite paths. No production or developer-local
database is present on a clean runner.

## Authoritative hosted command sequence

After checkout and toolchain setup, direct named workflow steps run:

```text
uv lock --check
uv sync --locked
uv --version
uv run python --version
uv run pytest
uv run python -m pantrypilot.evaluation evaluations/ingredient-resolution-v1.json
uv run ruff format --check src tests
uv run ruff check src tests
event-aware git diff --check
```

The two version commands are diagnostics, and `uv sync --locked` is clean
environment setup. The remaining commands preserve the established quality
contract. Each substantive gate has a plain-language step name so the failed
stage is visible without opening every log.

No wrapper script parses results or changes exit codes. The runner shell's
normal nonzero-exit behavior fails the step, the job, and the stable
`PantryPilot verification` check. Later steps need not run after an earlier
failure; the branch is corrected and the complete job reruns.

### Test behavior

`uv run pytest` executes the repository-configured `tests` suite. It must
collect the complete suite, not a curated Feature 005 subset. The existing
Starlette/httpx warning remains visible in normal logs and does not change the
exit code.

### Evaluation behavior

The evaluator command remains unchanged. Its existing process contract is:

- exit `0`: alias-aware recall is strictly greater than exact-name recall and
  false positives equal zero;
- exit `1`: one or both acceptance conditions fail; and
- exit `2`: the fixture is invalid or unreadable.

The deterministic JSON printed by the evaluator remains ordinary step output.
CI adds no JSON parser, threshold duplicate, output annotation, or evaluator
special case. The evaluator process is the single acceptance authority.

### Ruff behavior

Format and lint remain separate named steps over `src tests`. This matches the
approved current contract and distinguishes formatting drift from lint-rule
violations.

## Hosted whitespace semantics

A bare `git diff --check` examines only working-tree/index changes. In a clean
checkout it would say little about the committed change under test. Hosted CI
therefore supplies an explicit event range while local merge-readiness retains
the existing bare command against local changes.

Checkout fetches complete history (`fetch-depth: 0`) so ordinary PR and push
range endpoints are present. The whitespace step then selects:

| Event/state | Base | Target |
|---|---|---|
| Pull request to `main` | `github.event.pull_request.base.sha` | tested `github.sha` merge commit |
| Push to `main` | `github.event.before` | pushed `github.sha` |
| All-zero initial push base | Git empty-tree hash | pushed `github.sha` |

The algorithm is:

1. accept only the two approved event names;
2. select the event-specific base and target without evaluating untrusted text
   as shell code;
3. recognize only the all-zero push sentinel as initial history and replace it
   with the Git empty-tree hash;
4. validate the target and ordinary base as commit objects with `git cat-file`;
5. if an unexpected nonzero base is missing, attempt one targeted read-only
   public fetch and validate it again;
6. fail with a concise diagnostic if either endpoint is still unusable; and
7. run `git diff --check <base> <target>`.

The empty-tree branch checks every file introduced by an initial push. An
unknown event, blank SHA, malformed endpoint, failed fetch, or unresolved
nonzero base fails the step. No branch silently skips whitespace verification.

For a pull request, the target is GitHub's merge commit for that workflow run.
Comparing the recorded base to that target checks the proposed integrated tree
against the base state used for the run. It does not claim compatibility with
later `main` changes.

For a multi-commit push, `github.event.before` to `github.sha` checks the entire
pushed update rather than only the final commit. Full-history checkout is an
intentional small cost for correct semantics in this currently small
repository.

## Failure behavior and diagnostics

One failing command produces one failed named step and a failed stable job
check. Normal command output and stderr remain available in GitHub logs.

Failure classes remain distinguishable:

- workflow/setup failure: checkout, action, runner, Python, network, or locked
  environment preparation failed;
- product/test failure: pytest found a regression or could not collect tests;
- evaluation failure: quality acceptance returned exit `1` or fixture handling
  returned exit `2`;
- static-quality failure: Ruff format or lint rejected committed content; and
- whitespace-range failure: endpoint resolution failed or Git found whitespace
  errors.

A green rerun is required after remediation. A check is never disabled,
weakened, conditionally bypassed, or marked continue-on-error merely to obtain
a successful conclusion.

The 10-minute job timeout prevents indefinite runner use while leaving ample
room above the current local runtime for fresh Python and dependency downloads.
If legitimate runs approach the timeout, logs and measured hosted durations
must justify a reviewed adjustment rather than a speculative increase.

No artifact upload is needed for diagnostics. Named steps, ordinary logs, and
the evaluator's JSON provide the present required evidence.

## Caching, matrices, and runner scope

Caching is explicitly disabled. The current suite and dependency graph are
small, and no hosted runtime measurement demonstrates a problem. Avoiding a
cache removes key design, invalidation, trust, fork-visibility, and stale-tool
questions. Hosted durations may support a later cache design if download cost
becomes material.

There is no Python matrix. The project supports one minor line,
`==3.12.*`. Patch variation is observed in logs rather than multiplied into
jobs.

There is no OS matrix. Ubuntu is the Feature 005 hosted target, while Windows
remains supported through local verification. Future OS-specific requirements
must provide their own evidence and design.

There is no job matrix, sharding, retry policy, self-hosted runner, service
container, Docker container, or artifact fan-in/fan-out.

## Local versus hosted verification boundary

The owner and implementation agents continue to run locally:

```powershell
uv lock --check
uv run pytest
uv run python -m pantrypilot.evaluation evaluations/ingredient-resolution-v1.json
uv run ruff format --check src tests
uv run ruff check src tests
git diff --check
```

Windows developers remain supported by these documented PowerShell-compatible
commands. Local verification is faster for iteration, can inspect uncommitted
changes, and remains required before review and publication.

Hosted verification adds a clean environment, Linux execution, event-aware
committed whitespace comparison, GitHub logs, and an independently recorded
check. It cannot be fully substituted by local YAML inspection.

Before publication, local Feature 005 validation includes:

- careful workflow review against GitHub's documented syntax;
- scans for mutable action refs, non-40-character pins, unexpected
  permissions, secrets, cache behavior, matrices, path filters, deployments,
  manual/scheduled triggers, and unfinished markers;
- fresh official tag-to-SHA and uv artifact-checksum verification;
- local exercise of PR, push, empty-tree, targeted-fetch, and explicit-failure
  whitespace branches;
- the complete PantryPilot verification contract; and
- `git diff --check` over the local design/implementation diff.

No YAML parser or Actions-specific linter is currently installed. Adding a
project dependency solely to parse one small workflow is not justified.
Implementation may return to design review if a real syntax or tooling problem
demonstrates that need.

Local checks cannot prove:

- GitHub recognizes the workflow file;
- event and branch filters trigger as intended;
- the hosted runner and action runtimes are available;
- effective hosted permissions and fork behavior match the design;
- the stable check appears with the intended name;
- concurrency cancellation behaves as configured; or
- network installation and every command succeed on the hosted image.

Only an owner-authorized hosted run provides that evidence.

## Review, publication, and remediation lifecycle

The Feature 005 lifecycle is:

```text
local implementation and verification
    -> internal Codex review
    -> independent read-only Claude Code review
    -> owner-authorized push and Draft PR
    -> actual GitHub-hosted PR execution
    -> diagnosis and reviewed remediation if necessary
    -> fresh complete local and hosted verification
    -> owner acceptance
    -> eventual owner-authorized merge
    -> observe and record the resulting push-to-main run
```

Codex review checks correctness, scope, security, action identities,
permissions, shell safety, trigger semantics, test quality, documentation, and
consistency with this design. Claude Code remains independent and read-only
unless separately authorized.

No push merely to test YAML occurs during design. Publication remains an
explicit owner gate. A first hosted failure is evidence to diagnose, not
automatically a design failure. Fixes follow the normal reviewed branch
workflow and receive fresh local and hosted verification.

The PR run proves the proposed integration path for the base state used in that
run. The eventual merge-generated push run proves that the `main` trigger
actually operates on integrated history. Directly pushing to `main` solely to
manufacture this evidence is not justified.

## Required live GitHub evidence

The successful hosted PR evidence records:

- workflow-run URL;
- source commit SHA, tested GitHub merge SHA, and PR base SHA;
- `pull_request` event;
- workflow name `CI`;
- stable job/check name `PantryPilot verification`;
- conclusion and runtime;
- resolved uv and Python versions;
- runner image identification;
- named verification stages executed;
- pytest count and warning summary;
- evaluator recall/precision/false-positive output; and
- Ruff and whitespace conclusions.

After the eventual owner-authorized merge, record the corresponding `push`
run URL, integrated `main` SHA, event, stable check name, conclusion, runtime,
and step results. If it fails, diagnose and remediate through a new reviewed
change; do not rewrite or bypass the evidence.

No artificial failing hosted commit is required. Existing evaluator tests
prove local nonzero failure propagation. A naturally occurring hosted failure
may provide useful negative-path evidence, but the project does not pollute
history merely to create one.

## Documentation and learning deliverables

Implementation later changes only:

- `.github/workflows/ci.yml`;
- `README.md`; and
- `docs/learning/005-automated-ci-verification.md`.

If implementation discovers a direct blocker requiring any application, test,
evaluator, lockfile, roadmap, product-vision, or repository-setting change, it
stops and returns for owner approval rather than expanding scope.

### README

README will:

- update the current status to Feature 005 after hosted evidence exists;
- identify `PantryPilot verification` as the visible hosted CI check;
- list the authoritative local verification commands;
- explain that Windows remains supported for local development;
- distinguish a recorded check from a required merge check;
- state that `main` is unprotected unless separately changed; and
- link the Feature 005 design and learning guide.

No CI badge is added. It would show only the latest default-branch status and
adds insufficient value beyond GitHub's native check/run evidence.

### Feature 005 learning guide

`docs/learning/005-automated-ci-verification.md` will teach:

- continuous integration versus continuous delivery, continuous deployment,
  and deployment;
- why CI became justified after Features 001 through 004;
- local developer state versus a clean hosted runner;
- workflow, event, job, step, run, log, check, and required check;
- PR-to-main and push-to-main triggers and their distinct evidence;
- supported Python contracts, uv-managed Python, `uv.lock`, locked sync, and
  resolved-version logging;
- external action full-SHA pinning, release comments, tag-to-SHA verification,
  uv checksums, and intentional upgrade procedures;
- least-privilege `GITHUB_TOKEN` permissions;
- workflow-definition selection for `pull_request`, fork token restrictions,
  withheld secrets, applicable fork-workflow approval policies, security review
  of `.github/workflows/**`, `pull_request_target`, and secret exposure;
- exit codes and direct failure propagation, including evaluator exits;
- single versus multiple jobs and the chosen setup/diagnostic trade-off;
- job timeouts;
- PR concurrency and cancellation versus retained `main` runs;
- caching, invalidation, and why caching is currently disabled;
- Python/OS matrices and the evidence required to add them;
- local/CI command drift and the conditions for reconsidering a shared script;
- event-aware Git whitespace checks and the empty-tree edge case;
- GitHub Actions logs and required live evidence;
- workflow/setup failures versus product, test, evaluation, static-quality,
  and whitespace failures;
- practical diagnosis and safe rerun/remediation;
- what green CI proves and does not prove;
- visible checks versus branch protection and required checks; and
- Windows local verification and the evidence needed for future hosted Windows
  CI.

The guide includes runnable local commands, a workflow walkthrough, practical
exercises with observable outcomes, common troubleshooting examples,
instructions for finding PR and `main` Actions evidence, and guided
mock-interview questions with concise answer guidance.

## Repository-governance boundary

GitHub executing and recording `PantryPilot verification` is Feature 005.
GitHub refusing a merge when that check is absent or failing is not.

Branch protection or a ruleset could later require the stable job/check name,
but that decision needs separate owner authorization and should consider
bypass actors, administration, stale checks, branch creation, and failure
recovery. This design does not mutate settings or imply that a green badge,
check, or PR message enforces policy.

Final merge remains an owner decision. The workflow provides evidence for that
decision.

## Risks and deliberate trade-offs

### Versioned runner images still evolve

`ubuntu-24.04` is more stable than `ubuntu-latest` because it does not migrate
to a new OS generation automatically. GitHub still patches and refreshes the
image. A hosted setup failure may reflect runner-image change rather than a
PantryPilot regression; logs and reruns distinguish the cause.

### Compatible Python patches may change

The project contract is Python 3.12, not exactly the locally observed 3.12.13.
A new compatible patch may expose a real compatibility issue. Logging the
resolved version makes that change diagnosable. Exact patch pinning can be
designed if patch movement becomes too disruptive.

### One job reveals the first failure

The workflow favors one setup and one stable check over collecting every
independent failure in parallel. This keeps maintenance and network cost low,
but a second defect may appear only after the first is fixed. Current runtime
does not justify duplicated jobs.

### Full history increases checkout work

Correct PR and multi-commit push whitespace ranges require both endpoints.
Fetching full history is simple and reliable for the current small repository.
If history scale becomes material, a later design can fetch only event
endpoints while preserving explicit failure behavior.

### No cache repeats downloads

Clean downloads cost time and network access. They also avoid cache poisoning,
fork visibility, invalidation, and stale-environment questions. Hosted runtime
measurements, not expectation, determine whether caching is later worthwhile.

### Pinned tools require maintenance

Immutable action SHAs, uv versions, and checksums do not update automatically.
That is intentional reproducibility and supply-chain control, but maintainers
must review upgrades. The learning guide makes the declaration points and
process explicit.

### Unprotected main does not enforce CI

The workflow can be green, red, skipped, or absent without GitHub blocking a
merge. The stable check is suitable for a later required-check policy, but this
feature provides evidence rather than enforcement.

### Green CI has a narrow meaning

A green run proves that the tested commit satisfied the approved commands on
the recorded Ubuntu runner with the recorded Python/uv environment at that
time. Because a PR can modify the workflow definition that produces its check,
maintainers must also review the workflow diff; green status does not prove the
check itself or its required steps were unchanged. Green CI also does not
prove:

- Windows hosted compatibility;
- deployment or production readiness;
- correctness outside existing tests and evaluation data;
- absence of security vulnerabilities;
- performance, load, reliability, or privacy in production;
- merge-policy enforcement; or
- success for future dependency, runner, Python, or `main` states.

## Acceptance criteria

Feature 005 implementation is acceptable when:

1. `.github/workflows/ci.yml` is the only workflow added.
2. It triggers only for PRs targeting `main` and pushes to `main`.
3. It has one `ubuntu-24.04` job named `PantryPilot verification` with a
   10-minute timeout.
4. Superseded runs cancel only within the same PR; `main` push runs remain.
5. Workflow permissions are exactly repository-content read and all other
   scopes are absent.
6. No repository secret, write token, OIDC permission, deployment credential,
   or artifact upload is used.
7. Checkout and setup actions use freshly re-verified full commit SHAs with
   release comments; checkout does not persist credentials.
8. uv `0.11.32` and the exact Linux artifact checksum are freshly re-verified
   before commit and explicitly declared; `download-from-astral-mirror: false`,
   `enable-cache: false`, and `cache-python: false` are explicit.
9. uv installs Python from `.python-version`, locked sync succeeds, and logs
   record the resolved uv and Python versions.
10. The complete pytest suite, evaluator, Ruff format, Ruff lint, and hosted
    whitespace gate are separate named steps whose nonzero exits fail the job.
11. The evaluator's existing exit codes and JSON remain authoritative and
    unchanged.
12. PR, push, initial-empty-tree, and unresolved-base whitespace paths are
    locally exercised; missing nonzero endpoints fail explicitly.
13. The existing local contract passes fresh without changing application
    behavior or suppressing the known warning.
14. Local workflow/security scans find no mutable refs, unexpected permissions,
    secret use, caching, matrices, path filters, manual triggers, deployments,
    unfinished markers, or unrelated scope.
15. Codex internal review and independent read-only Claude Code review treat
    `.github/workflows/**` as security-sensitive code and clear all material
    findings before publication.
16. An owner-authorized Draft PR produces a successful hosted run with the
    required recorded evidence.
17. Any hosted failure is diagnosed and remediated normally, followed by fresh
    complete local and hosted verification.
18. README and `docs/learning/005-automated-ci-verification.md` accurately
    explain the implemented system, commands, security, troubleshooting,
    evidence, limitations, exercises, and mock-interview topics.
19. The eventual owner-authorized merge produces a successful recorded
    push-to-main run, or any failure is corrected through a new reviewed
    change.
20. No branch protection, ruleset, repository setting, deployment, badge,
    application code, test, evaluator, lockfile, roadmap, product-vision, or
    unrelated cleanup change enters the feature.

## Design self-review

- **Draft-completeness scan:** No unfinished marker or undecided action,
  trigger, runner, check name, command, permission, timeout, cache, matrix,
  documentation, or evidence requirement remains.
- **Context review:** The design records the exact starting branch/commit,
  clean state, existing workflow absence, current repository governance, and
  freshly rerun 252-test/evaluator/Ruff/lock/whitespace baseline.
- **Architecture review:** One workflow, one job, one runner, one setup, direct
  named steps, and one stable check agree throughout.
- **Trigger review:** PR and push evidence are distinct; manual dispatch,
  schedules, arbitrary branches, and path filters remain absent.
- **Reproducibility review:** `.python-version`, `requires-python`, uv version,
  uv artifact checksum, `uv.lock`, locked sync, and version logs have separate
  explicit responsibilities.
- **Supply-chain review:** Every external action is full-SHA pinned; current
  candidates are recorded but must be freshly re-verified before commit.
- **Security review:** The PR merge commit can contain proposed workflow
  changes; content read is the only declared permission; credentials are not
  persisted; fork code receives no repository secrets or write authority;
  `pull_request_target` and artifacts are absent.
- **Verification review:** Every established command maps to a named hosted
  step, and evaluator exit behavior remains the single quality authority.
- **Whitespace review:** PR, push, empty-tree, missing-base fetch, validation,
  and explicit failure semantics are all defined without a silent skip.
- **Hosted-boundary review:** Local inspection limitations, owner publication
  gate, live PR evidence, and post-merge push evidence are explicit.
- **Governance review:** A visible check is never described as a required
  check; repository-setting changes remain separately authorized.
- **Scope review:** The design changes CI and its documentation only. No
  product, test, persistence, ranking, evaluator, deployment, cache, matrix,
  badge, or cleanup work entered the feature.
- **Ambiguity review:** The implementation-time values requiring fresh
  upstream verification are identified; no architecture decision is deferred
  to the later implementation plan.

## Scope conclusion

Feature 005 is one repository-level verification slice: one secure pinned
workflow, one clean Ubuntu job, one uv-managed Python 3.12 locked environment,
the established quality commands as visible steps, correct event-aware
whitespace semantics, least privilege, and owner-facing learning evidence. It
stops before deployment, merge enforcement, matrices, caching, scripts,
security platforms, or application changes.
