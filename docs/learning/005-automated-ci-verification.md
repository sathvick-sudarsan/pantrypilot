# Feature 005: Automated CI verification

## What we built and why now

Features 001–004 established a meaningful verification contract: deterministic
ranking, measured ingredient resolution, durable SQLite state, migrations, API
contracts, 252 tests, an evaluator, and static-quality checks. Those checks were
run on a developer machine, so GitHub had no independent record that a clean
machine could reproduce the same result.

Feature 005 adds one GitHub Actions workflow, `CI`, with one job/check named
`PantryPilot verification`. The workflow is configured for pull requests
targeting `main` and pushes to `main`. It reproduces the approved environment on
`ubuntu-24.04` and runs the established gates as directly named steps.

The workflow has been implemented and reviewed locally. At this stage it has
not been published, so local inspection cannot prove that GitHub recognizes the
file, starts either event, or completes a hosted run. That evidence requires a
later owner-authorized push and pull request.

## CI, delivery, deployment, and CD

Continuous integration (CI) automatically integrates proposed work with a
shared base and verifies it frequently. Feature 005 is CI because it checks a
proposed or integrated commit and records pass/fail evidence.

Continuous delivery keeps verified work in a state that could be released, but
still leaves the release decision to a person. Continuous deployment goes one
step further and automatically releases successful changes. A deployment is
the act of putting a particular version into an environment where it runs.

PantryPilot Feature 005 performs verification only. It does not package,
publish, deploy, merge, or make the repository continuously deliverable.

## Clean runner versus a developer machine

A local pass proves that the commands worked with a developer's checkout,
operating system, installed tools, caches, and machine state. That feedback is
fast and remains the first line of defense, but invisible machine state can
help a local run accidentally.

A GitHub-hosted runner starts as a fresh, temporary machine. The job must obtain
the repository, uv, Python, and locked dependencies from declared inputs before
it can verify the project. This is stronger evidence that verification does not
depend on one developer's machine.

The runner is still not perfectly frozen. `ubuntu-24.04` fixes the Ubuntu image
generation, while GitHub may patch that image. The project allows compatible
Python 3.12 patch releases. The workflow therefore records resolved versions
in its logs so environmental changes remain diagnosable.

## GitHub Actions vocabulary and event flow

- A **workflow** is the YAML definition in `.github/workflows/ci.yml`.
- An **event** is repository activity that can start the workflow. Feature 005
  accepts only a pull request targeting `main` or a push to `main`.
- A **run** is one execution of the workflow for one event and commit context.
- A **job** is a group of steps assigned to one runner. This workflow has job
  ID `verification` and visible name `PantryPilot verification`.
- A **runner** is the machine executing a job. Feature 005 uses one
  GitHub-hosted `ubuntu-24.04` runner.
- A **step** is one setup action or command within a job.
- A **log** records normal action and command output for a run, job, and step.
- A **check** is the pass/fail result GitHub records for the job.
- A **required check** is a check that branch protection or a ruleset requires
  before merge. Merely producing a check does not make it required.

For a pull request, GitHub tests the merge commit it creates against the base
state recorded for that run. This gives evidence about the proposed integration
with that recorded base, not with later changes to `main`. After an authorized
merge, the push event tests the commit actually integrated into `main` and also
proves that the separate push trigger operates.

## Reproducing Python and dependencies with uv

Three files or commands divide responsibility:

- `.python-version` contains `3.12`, which tells uv which Python line to
  install.
- `pyproject.toml` declares `requires-python = "==3.12.*"`, the project's
  supported compatibility contract.
- `uv.lock` records the resolved dependency graph and distribution hashes.

The workflow runs `uv python install`, then checks the lockfile and runs
`uv sync --locked`. Locked synchronization creates the project environment but
refuses to update a stale lockfile silently. It does not replace the separate
`uv lock --check` quality gate.

The workflow then logs both `uv --version` and `uv run python --version`. The
Python patch may move within compatible 3.12 releases, so logging the resolved
value makes each run auditable without redefining the repository contract as
one patch version.

The authoritative local verification sequence is:

```powershell
uv lock --check
uv run pytest
uv run python -m pantrypilot.evaluation evaluations/ingredient-resolution-v1.json
uv run ruff format --check src tests
uv run ruff check src tests
git diff --check
```

The workflow deliberately keeps these commands visible as named steps. The
local list and workflow must be reviewed together when either changes. A shared
wrapper script can be reconsidered only if real drift or duplication becomes a
maintenance problem.

## Immutable actions and uv supply-chain controls

An action release tag such as `v7.0.1` is readable but can move. The workflow
therefore executes every external action, including GitHub-owned actions, at a
reviewed full 40-character commit SHA. A release-version comment remains beside
each SHA so a maintainer can understand the intended upstream release:

```text
actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
astral-sh/setup-uv@c771a70e6277c0a99b617c7a806ffedaca235ff9 # v9.0.0
```

uv is a CI tool outside `uv.lock`. Its declaration point is
`.github/workflows/ci.yml`, which pins version `0.11.32`. For the Linux x86-64
runner, setup-uv selects the official
`uv-x86_64-unknown-linux-gnu.tar.gz` release artifact. The workflow supplies
this raw hexadecimal SHA-256 checksum:

```text
aab924fd522efd06f1c5f3b93a243864fc453132c94b2dc49f1371b528a4b967
```

`download-from-astral-mirror: false` overrides setup-uv v9's default and selects
the reviewed official GitHub release artifact rather than the Astral mirror.
The pinned setup action validates the downloaded artifact against the supplied
checksum. `enable-cache: false` disables uv cache persistence, and
`cache-python: false` disables managed-Python cache persistence.

These pins improve reproducibility, but they require deliberate maintenance.
They do not prove that upstream code is harmless; review of the intended
release and source change remains part of an upgrade.

## Least privilege, fork pull requests, and secrets

The workflow declares only `permissions: contents: read`. When one permission
is declared, unspecified `GITHUB_TOKEN` scopes are unavailable. Checkout also
uses `persist-credentials: false`, so later commands do not retain the token in
Git configuration. The workflow consumes no repository or environment secret.

Under the ordinary `pull_request` event, the workflow definition comes from
the tested pull-request merge commit. A fork can therefore propose changes to
the workflow itself. GitHub restricts the token for fork pull requests,
withholds repository secrets, and may require maintainer approval according to
repository policy. PantryPilot independently limits the job to read-only
contents and no secrets because it executes untrusted proposed workflow,
application, and test code.

`pull_request_target` is intentionally rejected. It runs the trusted
base-branch workflow in a more privileged base-repository context and is not
needed for this verification design. Combining that context with execution of
untrusted proposed code would enlarge the risk unnecessarily.

Maintainers must review changes under `.github/workflows/**` as
security-sensitive code. A green PR check says the workflow definition in the
tested merge commit reported success; it does not prove that the PR left the
check, permissions, or required commands unchanged.

GitHub Actions normally produces workflow and step logs. Feature 005 does not
explicitly upload pantry data, request bodies, SQLite databases,
ranking/request histories, or other user-derived application data as
artifacts. Tests use temporary SQLite files rather than a developer or
production database.

## Direct quality gates and exit-code propagation

The single job uses direct named steps for lock checking, environment setup,
version logging, tests, evaluation, formatting, lint, and committed whitespace.
There is no wrapper that parses or rewrites results and no
`continue-on-error`. A command returning nonzero fails its step, which fails
the job and the `PantryPilot verification` check.

The evaluator prints deterministic JSON to the normal step log. Its existing
process contract remains authoritative:

- exit `0` when alias-aware recall strictly improves over exact-name recall and
  false positives are zero;
- exit `1` when either acceptance condition fails; and
- exit `2` when the evaluation fixture is invalid or unreadable.

CI does not duplicate these thresholds. That avoids two definitions of what
ingredient-resolution success means.

## Event-aware committed-whitespace verification

Local `git diff --check` examines working-tree and index changes, which is
useful before committing. A clean hosted checkout has no such local edits, so a
bare hosted command would miss the intent of the gate. The workflow instead
checks a committed event range after checkout with `fetch-depth: 0`.

| Event | Base | Target |
|---|---|---|
| Pull request targeting `main` | `github.event.pull_request.base.sha` | tested `github.sha` merge commit |
| Push to `main` | `github.event.before` | pushed `github.sha` |
| Initial push with an all-zero before SHA | Git empty-tree hash | pushed `github.sha` |

The Bash step accepts only `pull_request` and `push`, requires full lowercase
40-character object IDs, validates the target as a commit with `git cat-file`,
and validates the base as a commit or the computed empty tree. It then runs
`git diff --check <base> <target>`.

An all-zero push base has a defined meaning: compare every introduced file
against Git's empty tree. If an unexpected nonzero base is missing, the step
attempts one targeted, read-only public fetch and validates the commit again.
A malformed target, unsupported event, failed target validation, or base that
remains unresolved produces a clear failure. No branch silently skips the
whitespace gate, and event text is never evaluated as shell code.

## Job layout, timeout, concurrency, caching, and matrices

One job means checkout, uv installation, Python installation, and dependency
synchronization happen once. It also produces one stable check. The trade-off
is that the job stops at its first failure rather than reporting every
independent failure in parallel. The current single-digit-second local suite
does not justify duplicated setup across jobs.

`timeout-minutes: 10` bounds a stuck runner or network operation while leaving
room for clean downloads. A measured hosted runtime near that limit would
justify reviewing it; speculation does not.

The concurrency group uses the PR number when one exists, and
`cancel-in-progress` is true only for pull requests. A newer run of the same PR
cancels obsolete work. Push runs use their unique run ID and are retained so
each integrated `main` commit keeps its own evidence.

Caching is disabled because current runtime evidence does not justify cache
keys, invalidation, stale state, or fork-visibility complexity. There is no
Python or OS matrix because the project supports one Python minor line and
Feature 005 has one hosted OS target. Add parallel jobs, caching, or a matrix
only after measured cost, a compatibility requirement, or a real failure mode
shows their value.

## Reading GitHub Actions evidence

After owner-authorized publication, open the pull request's checks or the
repository's **Actions** tab, choose workflow `CI`, open the relevant run, then
open job `PantryPilot verification`. The run page identifies the event, commit,
conclusion, duration, runner, and each named step. Step logs expose the resolved
uv/Python versions and command output, including pytest and evaluator results.

The first required hosted evidence is a pull-request run. Record its run URL,
source commit, tested merge SHA, recorded base SHA, event, names, conclusion,
runtime, versions, and quality-step results. After an owner-authorized merge,
record the corresponding push-to-main run and its before/pushed range. The two
runs prove different event paths.

Before publication, these pages and runs do not yet exist for Feature 005.
Reading the YAML can establish intent and local consistency, not hosted
recognition, permissions, runner availability, trigger behavior, or a result.

## Failure categories and troubleshooting

Start with the first failed named step rather than treating every red run as a
product regression:

| Failure category | Typical evidence | Safe response |
|---|---|---|
| Workflow/setup | YAML recognition, checkout, action, network, Python, or locked-sync error | Compare the failing setup step with the pinned workflow and resolved versions; diagnose before changing a gate. |
| Product/test | Pytest collection or assertion failure | Reproduce the failing test locally, fix the root cause in a separately authorized scope, then run the complete contract. |
| Evaluation | Evaluator exit `1` or `2` and its JSON/error output | Determine whether acceptance failed or the fixture was invalid; never weaken the evaluator to make CI green. |
| Static quality | Ruff format or lint output | Run the exact named Ruff command locally and correct the reported file in scope. |
| Whitespace range | Invalid/missing endpoint, failed targeted fetch, or whitespace finding | Verify the event and recorded SHAs; reproduce the exact range rather than replacing it with a bare clean-tree diff. |

For any failure, inspect the run, job, failed step, version log, and exact
command output. Reproduce it locally where possible, correct the root cause,
rerun the complete local contract, and repeat required reviews before seeking
fresh hosted evidence. A first hosted failure is diagnostic evidence, not
permission to skip, weaken, or mark a gate optional.

Use GitHub's **Re-run jobs** for a justified retry, such as a diagnosed
transient network failure. Re-running an unchanged product failure is not a
fix. If a workflow or supply-chain correction is required, it goes through the
same owner-authorized commit and publication process as other security-sensitive
changes.

## What green CI proves—and does not prove

A green run proves that the tested commit completed this declared contract on
the recorded Ubuntu runner with the resolved uv/Python environment at that
time. A PR run covers the recorded base state for that run; a later push run
covers the integrated commit and push trigger.

Green CI does not prove:

- that the PR left its workflow definition unchanged;
- compatibility with future changes to `main`;
- Windows compatibility or every operating-system behavior;
- deployment readiness or that any deployment occurred;
- production correctness, reliability, privacy, or performance;
- correctness outside the current tests and evaluation fixture;
- absence of security vulnerabilities; or
- that GitHub will prevent a merge.

It is one strong, inspectable piece of engineering evidence, not a universal
quality certificate.

## Checks, required checks, and branch protection

The workflow creates the stable visible check `PantryPilot verification` when
an eligible event runs. GitHub recording that result is Feature 005's core
capability.

A required check is repository governance. Branch protection or a ruleset can
tell GitHub to refuse a merge when the named check is missing or failing.
PantryPilot's `main` branch remains unprotected unless the owner separately
authorizes and configures that policy. The workflow needs no `checks: write` or
`statuses: write` permission for GitHub to record its ordinary conclusion.

If enforcement is considered later, maintainers must separately decide bypass
rules, administrator behavior, stale-check handling, failure recovery, and the
exact required check name. Feature 005 neither mutates those settings nor
implies that maintainers cannot merge around a red or absent check today.

## Windows local development and future portability evidence

Windows remains a supported local-development environment. Developers can use
the authoritative uv commands in PowerShell, including the bare local
`git diff --check`, just as they did before Feature 005.

`ubuntu-24.04` is the single hosted verification target, not a declaration
that PantryPilot is Linux-only. Feature 005 has no Windows hosted matrix because
there is no current portability requirement or demonstrated OS-specific defect
that a second job would catch.

Evidence that could justify Windows hosted CI later includes a reproduced
Windows-only failure, a product requirement promising Windows runtime
compatibility, recurring platform-sensitive path/shell behavior, or a release
target that must be tested on Windows. That evidence should drive an explicit
design rather than adding a matrix preemptively.

## Safe tool and action upgrades

For an action upgrade:

1. Choose the intended release in the canonical upstream repository.
2. Review its release notes, runtime requirements, and relevant source changes.
3. Resolve the official release tag through GitHub metadata to the final full
   commit SHA; do not copy a similarly named fork or trust a mutable tag alone.
4. Inspect the action metadata and the semantics PantryPilot depends on.
5. Replace the workflow SHA and release-version comment together.
6. Rerun local policy/range checks, the complete PantryPilot contract, review,
   and later owner-authorized hosted evidence.

For an uv upgrade, also confirm the release is final, select the exact official
Linux x86-64 GNU artifact, obtain its SHA-256 digest, and verify how the pinned
setup action selects and validates it. Change `version` and `checksum`
together, preserve the explicit direct-download/cache inputs unless a new
design changes them, and record the new resolved versions in hosted logs.

An upstream release existing is not sufficient reason to upgrade. Tooling
changes are explicit reviewed repository changes so CI behavior cannot move
independently of the codebase.

## Practical exercises

1. **Trace a PR run.** Starting from the `pull_request` trigger, trace workflow
   `CI` through job `PantryPilot verification`, setup, each quality gate, and
   the recorded conclusion. Before publication, use the YAML; afterward,
   compare the trace with the real run and logs.
2. **Explain retained push evidence.** Describe why a successful PR run does
   not prove the `push` trigger or the final integrated `main` commit, and why a
   newer push must not cancel an earlier push run.
3. **Derive whitespace ranges.** Given a PR base SHA and merge SHA, select the
   PR range. Given normal before/after push SHAs, select the push range. Given
   forty zeroes as the before SHA, explain why the empty tree is the base.
4. **Classify failures.** Classify a setup-uv download failure, a pytest
   assertion, evaluator exit `1`, a Ruff formatting report, and an unresolved
   whitespace base. For each, identify the first log and local command to use.
5. **Audit trust boundaries.** Inspect the workflow and list every action ref,
   declared permission, checkout credential setting, secret reference, cache,
   artifact upload, and trigger. Success means finding two full-SHA actions,
   only `contents: read`, no persisted credentials or secrets, disabled caches,
   no artifact upload, and only the approved events.
6. **Plan an uv upgrade without mutation.** Choose a hypothetical later final
   release and describe how to verify its canonical release, exact GNU Linux
   x86-64 asset, checksum, and pinned setup-action semantics. Do not edit the
   repository.
7. **Decide whether to add infrastructure.** For caching, a Python matrix, a
   shared script, manual dispatch, and Windows hosted CI, name the concrete
   measurement or requirement that would justify each addition.

## Mock-interview questions and answer guidance

1. **Why is this CI rather than CD or deployment?** It verifies proposed and
   integrated commits and records results; it neither releases nor deploys.
2. **What does a clean runner prove that a local pass does not?** It shows the
   declared repository inputs can recreate the environment without relying on
   one developer machine's installed state or caches.
3. **How do `.python-version`, `requires-python`, `uv.lock`, and
   `uv sync --locked` divide responsibility?** The first selects Python 3.12,
   the second defines supported 3.12 compatibility, the lockfile fixes the
   dependency graph, and locked sync installs it without accepting drift.
4. **Why pin both action SHAs and the uv artifact checksum?** The action SHA
   fixes executable setup code; the checksum binds the exact downloaded uv
   bytes. They protect different supply-chain links.
5. **Why explicitly disable the Astral mirror and caching?** Direct GitHub
   download makes the reviewed checksum refer to the selected official release
   artifact; disabled caches remove unjustified mutable state and invalidation
   rules.
6. **Why is an ordinary fork PR still untrusted when using `pull_request`?**
   The workflow definition and proposed code come from the tested PR merge
   commit. Safety comes from restricted token permissions, withheld secrets,
   applicable approval policy, and review—not from trusting the workflow.
7. **Why is `pull_request_target` wrong here?** It uses the trusted base
   workflow in a more privileged context that Feature 005 does not need and
   should not combine with execution of untrusted proposed code.
8. **Why does a green check not prove its own workflow was unchanged?** A PR
   can modify `.github/workflows/**`; green means that tested definition
   reported success, so reviewers must inspect the workflow diff.
9. **How does the evaluator fail the job?** Its existing exit `1` or `2`
   propagates directly through the named command, failing the step, job, and
   check; CI does not reinterpret its JSON.
10. **Why is `git diff --check` event-aware in hosted CI?** A clean checkout
    has no local diff. Recorded PR or push endpoints preserve the intent of
    checking committed changes, with empty-tree and fail-closed edge handling.
11. **Why one job, one OS, one Python line, and a ten-minute timeout?** They
    match current requirements with one setup and one check; the timeout bounds
    hangs. No measured need justifies duplication or a matrix.
12. **Why cancel superseded PR runs but retain `main` runs?** Old PR evidence
    becomes obsolete when that PR updates, while every integrated `main` commit
    should keep its recorded conclusion.
13. **How do workflow failures differ from product/test failures?** Workflow
    failures prevent or disrupt setup/execution; product failures are valid
    command executions reporting a regression. The failed named step and logs
    identify the class.
14. **What does green CI not prove?** It does not prove an unchanged workflow,
    future-base or Windows compatibility, deployment/production readiness,
    broad security, correctness beyond current gates, or merge enforcement.
15. **What changes when `PantryPilot verification` becomes a required check?**
    Separate branch governance makes a passing recorded check a merge
    condition; the workflow itself does not acquire deployment authority or
    broader token permissions.
16. **What evidence would justify caching, a matrix, a shared script, manual
    dispatch, or Windows hosted CI later?** Measured download/runtime cost,
    multiple supported compatibility targets, demonstrated command drift, a
    concrete manual event/range use case, or an OS-specific requirement or
    defect, respectively.
