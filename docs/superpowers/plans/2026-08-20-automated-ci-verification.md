# Automated CI Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the smallest secure GitHub Actions workflow that reproduces
PantryPilot's established verification contract on a clean hosted runner and
records a stable, inspectable GitHub check.

**Architecture:** One `CI` workflow runs one `PantryPilot verification` job on
`ubuntu-24.04` for pull requests targeting `main` and pushes to `main`. It uses
immutable action pins, a checksum-pinned uv `0.11.32`, uv-managed Python from
`.python-version`, direct named verification steps, and an event-aware committed
whitespace range. Repository documentation explains the system without adding
merge enforcement, deployment, caching, matrices, secrets, or application
behavior.

**Tech Stack:** GitHub Actions YAML, Bash on `ubuntu-24.04`, Git, uv `0.11.32`,
Python `3.12.*`, Pytest, Ruff, PowerShell for local inspection, and GitHub CLI
for read-only upstream verification.

**Spec:**
`docs/superpowers/specs/2026-08-20-automated-ci-verification-design.md`

## Global Constraints

- The approved design is the architecture source of truth. Stop for owner
  review if implementation exposes a contradiction; do not redesign during
  execution.
- Work only in the existing `feat/automated-ci-verification` worktree. Approved
  design commit `a735ffeb6e16a3782b677b6a5b8fb935dc17e514` is the architecture
  baseline; derive the later implementation baseline from the committed plan
  file as specified in Task 1 rather than hard-coding its future commit SHA.
- The final implementation surface is exactly `.github/workflows/ci.yml`,
  `README.md`, and
  `docs/learning/005-automated-ci-verification.md`. If any application, test,
  evaluator, lockfile, dependency, product-vision, roadmap, or repository-setting
  change appears necessary, stop and return the blocker to the owner.
- Use one Linux runner (`ubuntu-24.04`), one Python compatibility line
  (`3.12.*`), and one job. Do not add a Python or OS matrix, Windows hosted CI,
  caching, artifacts, secrets, path filters, schedules, manual dispatch,
  deployment, a shared verification script, or a new validation dependency.
- Windows remains a supported local-development environment through the
  documented uv commands. The Linux hosted target does not make PantryPilot
  Linux-only. Add Windows hosted CI only after evidence of OS-specific behavior
  or a portability requirement.
- `pull_request` workflow code comes from the tested PR merge commit, so a fork
  PR may propose workflow changes. Execute proposed code only with explicit
  `contents: read`, no secrets, and GitHub's fork restrictions. Never replace
  this trigger with `pull_request_target`.
- Treat `.github/workflows/**` as security-sensitive. A green check does not
  prove that a PR left the check unchanged.
- Pin every external action, including GitHub-owned actions, to a reviewed full
  40-character commit SHA and retain a release-version comment. Pin uv to
  `0.11.32` with the exact Linux x86-64 artifact checksum. Re-verify all pins
  immediately before the workflow commit.
- GitHub Actions may produce normal job and step logs. Do not explicitly upload
  pantry data, request bodies, SQLite databases, ranking/request histories, or
  other user-derived application data as artifacts.
- The existing Starlette/httpx `TestClient` deprecation warning is accepted
  baseline evidence. Do not suppress or fix it in Feature 005.
- Every commit below remains subject to explicit owner authorization. A planned
  commit command is not authorization to execute it.
- Stop before any push, Draft PR, hosted run, merge, or repository-setting
  change until the owner separately authorizes publication.

---

## Final File and Responsibility Map

| File | Action | Exact responsibility |
|---|---|---|
| `.github/workflows/ci.yml` | Create | Define the two approved events, least-privilege single hosted job, reproducible uv/Python setup, direct quality gates, and event-aware whitespace range. |
| `docs/learning/005-automated-ci-verification.md` | Create | Teach the implemented CI model, security and reproducibility decisions, failure diagnosis, evidence limits, exercises, and mock-interview answers. |
| `README.md` | Modify before publication, then modify its current-status paragraph only after successful owner-authorized PR-hosted evidence | Before publication, document the configured CI workflow, authoritative local commands, Windows/Linux boundary, governance boundary, and Feature 005 document links while retaining Feature 004 as the current accepted feature. Only after successful PR-hosted proof may the current-status paragraph advance to Feature 005. |

No implementation task changes `src/`, `tests/`, `evaluations/`,
`.python-version`, `pyproject.toml`, `uv.lock`, `docs/product/vision.md`,
`docs/roadmap.md`, or repository settings.

---

### Task 1: Re-verify the Supply Chain and Pre-implementation Baseline

**Files:**

- Inspect: approved design, `.python-version`, `pyproject.toml`, `uv.lock`,
  `.github/`, official `actions/checkout`, official `astral-sh/setup-uv`, and
  official `astral-sh/uv` release metadata
- Modify: none

- [ ] **Step 1: Reconfirm the authorized starting state**

Run in PowerShell:

```powershell
$designBase = 'a735ffeb6e16a3782b677b6a5b8fb935dc17e514'
$planPath = 'docs/superpowers/plans/2026-08-20-automated-ci-verification.md'

$branch = (git branch --show-current).Trim()
if ($branch -ne 'feat/automated-ci-verification') {
    throw "Unexpected branch: $branch"
}

git cat-file -e "${designBase}^{commit}"
if ($LASTEXITCODE -ne 0) { throw 'Approved design commit is unavailable' }

git merge-base --is-ancestor $designBase HEAD
if ($LASTEXITCODE -ne 0) { throw 'Approved design commit is not an ancestor of HEAD' }

$implementationBase = (git log -1 --format=%H -- $planPath).Trim()
if ($implementationBase -notmatch '^[0-9a-f]{40}$') {
    throw 'Could not derive a committed implementation-plan commit'
}
git cat-file -e "${implementationBase}^{commit}"
if ($LASTEXITCODE -ne 0) { throw 'Derived implementation-plan commit is unavailable' }

$headSha = (git rev-parse HEAD).Trim()
if ($headSha -ne $implementationBase) {
    throw 'Implementation must start with the committed plan at HEAD'
}

$committedPlanPath = (git ls-tree --name-only $implementationBase -- $planPath).Trim()
if ($committedPlanPath -ne $planPath) {
    throw 'Implementation plan is not committed at the derived baseline'
}

$baselineChanges = @(git diff --name-status $designBase $implementationBase --)
$expectedPlanAddition = "A`t$planPath"
if ($baselineChanges.Count -ne 1 -or $baselineChanges[0] -ne $expectedPlanAddition) {
    $baselineChanges | Out-Host
    throw 'Only the implementation plan may differ between design and implementation baselines'
}

$status = @(git status --porcelain)
if ($status.Count -ne 0) {
    $status | Out-Host
    throw 'Implementation must start from a clean working tree'
}

if (Test-Path .github/workflows/ci.yml) {
    throw '.github/workflows/ci.yml already exists'
}

Get-Content .python-version
Select-String -Path pyproject.toml -Pattern 'requires-python = "==3.12\.\*"'
```

Expected:

- branch is `feat/automated-ci-verification`;
- design commit `a735ffeb6e16a3782b677b6a5b8fb935dc17e514` exists and is an
  ancestor of HEAD;
- `$implementationBase` is a valid commit derived from the committed plan file
  and equals HEAD at implementation start;
- the plan exists in that commit;
- the only change from the design commit through the implementation-plan commit
  is addition of
  `docs/superpowers/plans/2026-08-20-automated-ci-verification.md`;
- the working tree is clean;
- the workflow path does not exist;
- `.python-version` is `3.12`;
- `pyproject.toml` requires `==3.12.*`.

Stop if any result differs. Do not delete, overwrite, or reconcile an existing
workflow.

- [ ] **Step 2: Record a fresh local pre-change verification baseline**

Run each command separately:

```powershell
uv --version
uv run python --version
uv lock --check
uv run pytest
uv run python -m pantrypilot.evaluation evaluations/ingredient-resolution-v1.json
uv run ruff format --check src tests
uv run ruff check src tests
git diff --check
```

Expected: uv reports `0.11.32`; Python reports `3.12.*`; the lock check passes;
pytest collects and passes 252 tests with the one existing Starlette/httpx
warning allowed and unsuppressed; evaluation reports precision `1.0`, recall
`1.0`, zero false positives, and improved recall over the exact-name baseline;
both Ruff checks and the whitespace check pass. Stop and diagnose any different
product-quality result before creating the workflow.

- [ ] **Step 3: Verify the repositories are the intended official upstreams**

Run:

```powershell
gh repo view actions/checkout --json nameWithOwner,visibility,url
gh repo view astral-sh/setup-uv --json nameWithOwner,visibility,url
gh repo view astral-sh/uv --json nameWithOwner,visibility,url
```

Expected: the exact `nameWithOwner` values are `actions/checkout`,
`astral-sh/setup-uv`, and `astral-sh/uv`; all are public GitHub repositories at
their canonical GitHub URLs. Do not accept a similarly named fork, redirected
download host, copied release, or search result as evidence.

- [ ] **Step 4: Re-verify each action release tag to its immutable commit**

Run:

```powershell
$checkoutRef = gh api repos/actions/checkout/git/ref/tags/v7.0.1 | ConvertFrom-Json
$setupUvRef = gh api repos/astral-sh/setup-uv/git/ref/tags/v9.0.0 | ConvertFrom-Json
$checkoutRef.object | Format-List type,sha,url
$setupUvRef.object | Format-List type,sha,url
```

Expected lightweight-tag evidence:

```text
actions/checkout v7.0.1 -> commit 3d3c42e5aac5ba805825da76410c181273ba90b1
astral-sh/setup-uv v9.0.0 -> commit c771a70e6277c0a99b617c7a806ffedaca235ff9
```

If either ref reports type `tag`, dereference its official `object.url` with
`gh api`, record the final commit object, and compare that commit SHA with the
candidate above. If either final SHA differs, stop for owner review; a moved tag
is security-relevant and must not be silently accepted.

- [ ] **Step 5: Verify setup-uv's pinned inputs and direct-download semantics**

Run:

```powershell
$setupUvSha = 'c771a70e6277c0a99b617c7a806ffedaca235ff9'
$actionResponse = gh api "repos/astral-sh/setup-uv/contents/action.yml?ref=$setupUvSha" | ConvertFrom-Json
$actionYaml = [Text.Encoding]::UTF8.GetString(
    [Convert]::FromBase64String(($actionResponse.content -replace '\s', ''))
)
$actionYaml -split "`n" | Select-String -Pattern 'version:','checksum:','download-from-astral-mirror:','enable-cache:','cache-python:' -Context 0,4
```

Then retrieve and decode the official source files at that same pinned commit,
not the repository's current default branch:

```powershell
function Get-PinnedSetupUvSource {
    param([Parameter(Mandatory)] [string] $Path)

    $response = gh api "repos/astral-sh/setup-uv/contents/$Path`?ref=$setupUvSha" | ConvertFrom-Json
    if ($response.type -ne 'file' -or $response.sha -notmatch '^[0-9a-f]{40}$') {
        throw "Pinned setup-uv source file is unavailable: $Path"
    }
    return [Text.Encoding]::UTF8.GetString(
        [Convert]::FromBase64String(($response.content -replace '\s', ''))
    )
}

$pinnedSources = [ordered]@{
    'src/download/download-version.ts' = Get-PinnedSetupUvSource 'src/download/download-version.ts'
    'src/download/variant-selection.ts' = Get-PinnedSetupUvSource 'src/download/variant-selection.ts'
    'src/download/checksum/checksum.ts' = Get-PinnedSetupUvSource 'src/download/checksum/checksum.ts'
    'src/download/manifest.ts' = Get-PinnedSetupUvSource 'src/download/manifest.ts'
    'src/utils/platforms.ts' = Get-PinnedSetupUvSource 'src/utils/platforms.ts'
    'src/utils/constants.ts' = Get-PinnedSetupUvSource 'src/utils/constants.ts'
}

foreach ($entry in $pinnedSources.GetEnumerator()) {
    Write-Output "PINNED SOURCE: $($entry.Key)"
    Write-Output $entry.Value
}

$downloadSource = $pinnedSources['src/download/download-version.ts']
$variantSource = $pinnedSources['src/download/variant-selection.ts']
$checksumSource = $pinnedSources['src/download/checksum/checksum.ts']
$manifestSource = $pinnedSources['src/download/manifest.ts']
$platformSource = $pinnedSources['src/utils/platforms.ts']
$constantSource = $pinnedSources['src/utils/constants.ts']

if ($downloadSource -notmatch 'downloadFromAstralMirror\s*\?\s*rewriteToMirror\(artifact\.downloadUrl\)\s*:\s*undefined' -or
    $downloadSource -notmatch 'downloadUrl\s*=\s*mirrorUrl\s*\?\?\s*artifact\.downloadUrl') {
    throw 'Pinned source does not prove false selects the original artifact URL'
}
if ($constantSource -notmatch 'https://github\.com/astral-sh/uv/releases/download/') {
    throw 'Pinned GitHub release URL prefix is missing'
}
if ($downloadSource -notmatch 'await validateChecksum\(checksum, downloadPath, arch, platform, version\)') {
    throw 'Downloaded artifact does not pass through checksum validation'
}
if ($checksumSource -notmatch 'hasProvidedChecksum\s*\?\s*checksum\s*:\s*KNOWN_CHECKSUMS\[key\]' -or
    $checksumSource -notmatch 'crypto\.createHash\("sha256"\)' -or
    $checksumSource -notmatch 'hash\.digest\("hex"\)' -or
    $checksumSource -notmatch 'actual === expected') {
    throw 'Pinned source does not compare a raw hexadecimal SHA-256 digest'
}
if ($platformSource -notmatch 'x64:\s*"x86_64"' -or
    $platformSource -notmatch 'linux:\s*"unknown-linux-gnu"') {
    throw 'Pinned source does not map Linux x64 to the approved target strings'
}
if (-not $manifestSource.Contains('const targetPlatform = `${arch}-${platform}`;') -or
    $manifestSource -notmatch 'candidate\.platform === targetPlatform' -or
    $manifestSource -notmatch 'selectDefaultVariant\(' -or
    $variantSource -notmatch 'variant === undefined \|\| variant === "default"') {
    throw 'Pinned manifest selection does not select the default exact platform artifact'
}
if (-not $downloadSource.Contains('`uv-${arch}-${platform}`')) {
    throw 'Pinned download source does not preserve the uv target artifact name'
}
```

Expected: the pinned action declares all five inputs; v9 defaults
`download-from-astral-mirror` to `true`, so the workflow must override it with
`false`; the decoded pinned source shows that `false` leaves `mirrorUrl`
undefined and therefore selects the manifest's original official GitHub release
URL; the downloaded file passes through `validateChecksum`; the supplied value
wins over the built-in checksum and is compared to `hash.digest("hex")` from
SHA-256, so the approved raw hexadecimal format is correct; x64 maps to
`x86_64`, Linux maps to `unknown-linux-gnu`, and exact platform/default-variant
selection yields `uv-x86_64-unknown-linux-gnu`. `enable-cache: false` disables
uv caching, and `cache-python: false` disables Python cache persistence. Record
the relevant pinned-source output in implementation review notes.

- [ ] **Step 6: Re-verify the exact uv release artifact and checksum**

Run:

```powershell
$release = gh release view 0.11.32 --repo astral-sh/uv --json tagName,isDraft,isPrerelease,publishedAt,assets | ConvertFrom-Json
$release | Select-Object tagName,isDraft,isPrerelease,publishedAt
$artifact = $release.assets | Where-Object name -eq 'uv-x86_64-unknown-linux-gnu.tar.gz'
$artifact | Select-Object name,digest,url
```

Expected:

- exact final release tag `0.11.32`;
- `isDraft` and `isPrerelease` are both `False`;
- exactly one artifact named `uv-x86_64-unknown-linux-gnu.tar.gz`;
- digest
  `sha256:aab924fd522efd06f1c5f3b93a243864fc453132c94b2dc49f1371b528a4b967`;
- the asset URL belongs to the official `astral-sh/uv` GitHub release.

This is the GNU Linux x86-64 artifact selected for an x64
`ubuntu-24.04` runner when the mirror override is `false`. If the release state,
artifact identity, digest, or setup-uv input semantics differ, stop for owner
review instead of substituting another version, mirror, checksum, or action.

- [ ] **Step 7: Review and preserve the evidence boundary**

Reviewer gate: compare the terminal evidence with the approved design's
candidate values and confirm that every lookup named the canonical upstream and
an immutable ref where available. Confirm that no credential, release artifact,
or generated evidence file entered the worktree:

```powershell
git status --short
```

Expected: empty output. This task has no commit.

---

### Task 2: Add and Locally Validate the CI Workflow

**Files:**

- Create: `.github/workflows/ci.yml`
- Modify: no other file

- [ ] **Step 1: Create the workflow with the verified immutable values**

Create `.github/workflows/ci.yml` with exactly this structure. Use the values
re-verified in Task 1; the expected values below must remain unchanged unless
the owner resolves a stopped supply-chain discrepancy.

```yaml
name: CI

on:
  pull_request:
    branches:
      - main
  push:
    branches:
      - main

permissions:
  contents: read

concurrency:
  group: ci-${{ github.event.pull_request.number || github.run_id }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}

jobs:
  verification:
    name: PantryPilot verification
    runs-on: ubuntu-24.04
    timeout-minutes: 10
    steps:
      - name: Check out repository
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          fetch-depth: 0
          persist-credentials: false

      - name: Install uv
        uses: astral-sh/setup-uv@c771a70e6277c0a99b617c7a806ffedaca235ff9 # v9.0.0
        with:
          version: "0.11.32"
          checksum: "aab924fd522efd06f1c5f3b93a243864fc453132c94b2dc49f1371b528a4b967"
          download-from-astral-mirror: false
          enable-cache: false
          cache-python: false

      - name: Install Python
        run: uv python install

      - name: Check lockfile
        run: uv lock --check

      - name: Synchronize locked environment
        run: uv sync --locked

      - name: Record tool versions
        run: |
          uv --version
          uv run python --version

      - name: Run tests
        run: uv run pytest

      - name: Evaluate ingredient resolution
        run: uv run python -m pantrypilot.evaluation evaluations/ingredient-resolution-v1.json

      - name: Check formatting
        run: uv run ruff format --check src tests

      - name: Check lint
        run: uv run ruff check src tests

      - name: Check committed whitespace
        env:
          EVENT_NAME: ${{ github.event_name }}
          PR_BASE_SHA: ${{ github.event.pull_request.base.sha }}
          PUSH_BEFORE_SHA: ${{ github.event.before }}
          TARGET_SHA: ${{ github.sha }}
        shell: bash
        run: |
          set -euo pipefail

          readonly zero_sha='0000000000000000000000000000000000000000'
          readonly sha_pattern='^[0-9a-f]{40}$'
          base_kind='commit'

          case "$EVENT_NAME" in
            pull_request)
              base_sha="$PR_BASE_SHA"
              ;;
            push)
              if [[ "$PUSH_BEFORE_SHA" == "$zero_sha" ]]; then
                base_sha="$(git hash-object -t tree /dev/null)"
                base_kind='tree'
              else
                base_sha="$PUSH_BEFORE_SHA"
              fi
              ;;
            *)
              echo "::error::Unsupported workflow event: $EVENT_NAME"
              exit 1
              ;;
          esac

          if [[ ! "$TARGET_SHA" =~ $sha_pattern ]]; then
            echo "::error::Target SHA is not a full lowercase hexadecimal commit ID"
            exit 1
          fi

          if [[ ! "$base_sha" =~ $sha_pattern ]]; then
            echo "::error::Base object is not a full lowercase hexadecimal Git object ID"
            exit 1
          fi

          if ! git cat-file -e "${TARGET_SHA}^{commit}" 2>/dev/null; then
            echo "::error::Target commit $TARGET_SHA is unavailable"
            exit 1
          fi

          if [[ "$base_kind" == 'commit' ]] && ! git cat-file -e "${base_sha}^{commit}" 2>/dev/null; then
            echo "Base commit $base_sha is not present; attempting one read-only fetch"
            if ! git fetch --no-tags --depth=1 origin "$base_sha"; then
              echo "::warning::The targeted base fetch did not succeed"
            fi
          fi

          if [[ "$base_kind" == 'commit' ]]; then
            if ! git cat-file -e "${base_sha}^{commit}" 2>/dev/null; then
              echo "::error::Base commit $base_sha remains unavailable after the targeted fetch"
              exit 1
            fi
          elif ! git cat-file -e "${base_sha}^{tree}" 2>/dev/null; then
            echo "::error::Computed empty-tree object $base_sha is unavailable"
            exit 1
          fi

          git diff --check "$base_sha" "$TARGET_SHA"
```

The PR group is stable by PR number, so a newer synchronization cancels only
an older run for that PR. Push events fall back to unique `github.run_id`
groups, so integrated `main` evidence is retained.

- [ ] **Step 2: Inspect the YAML structure without adding a parser**

Run:

```powershell
Get-Content .github/workflows/ci.yml
```

Read the complete file and verify indentation and nesting. Confirm only
`pull_request` and `push` target `main`; the permissions mapping contains only
`contents: read`; the job ID/name are `verification`/`PantryPilot verification`;
the runner is `ubuntu-24.04`; timeout is 10; and every verification command is
a direct named step. Do not add a YAML package or Actions linter for this one
workflow.

- [ ] **Step 3: Run deterministic workflow-policy scans**

Run this PowerShell block:

```powershell
$path = '.github/workflows/ci.yml'
$workflow = Get-Content $path -Raw

$required = @(
    'name: CI',
    'pull_request:',
    'push:',
    'permissions:',
    '  contents: read',
    'group: ci-${{ github.event.pull_request.number || github.run_id }}',
    "cancel-in-progress: `${{ github.event_name == 'pull_request' }}",
    'name: PantryPilot verification',
    'runs-on: ubuntu-24.04',
    'timeout-minutes: 10',
    'fetch-depth: 0',
    'persist-credentials: false',
    'version: "0.11.32"',
    'download-from-astral-mirror: false',
    'enable-cache: false',
    'cache-python: false',
    'uv python install',
    'uv lock --check',
    'uv sync --locked',
    'uv run pytest',
    'pantrypilot.evaluation',
    'uv run ruff format --check src tests',
    'uv run ruff check src tests',
    'git diff --check "$base_sha" "$TARGET_SHA"'
)
foreach ($item in $required) {
    if (-not $workflow.Contains($item)) { throw "Missing required workflow text: $item" }
}

$forbidden = @(
    'workflow_dispatch:',
    'pull_request_target:',
    'schedule:',
    'paths:',
    'paths-ignore:',
    'strategy:',
    'matrix:',
    'continue-on-error:',
    'actions/cache@',
    'actions/upload-artifact@',
    'actions/download-artifact@',
    '${{ secrets.',
    'environment:',
    'deploy'
)
foreach ($item in $forbidden) {
    if ($workflow.Contains($item)) { throw "Forbidden workflow text: $item" }
}

$usesLines = Select-String -Path $path -Pattern '^\s*uses:'
if ($usesLines.Count -ne 2) { throw "Expected exactly two external actions" }
foreach ($line in $usesLines.Line) {
    if ($line -notmatch '^\s*uses: [^@\s]+@[0-9a-f]{40} # v\d') {
        throw "Action is not pinned to a full SHA with a release comment: $line"
    }
}

if ($workflow -notmatch '(?ms)^permissions:\r?\n  contents: read\r?\n\r?\nconcurrency:') {
    throw 'Permissions are not exactly contents: read'
}
```

Expected: no output and exit code 0. Also run:

```powershell
rg -n 'T[B]D|T[O]DO|F[I]XME|implement la[t]er|fill i[n]' .github/workflows/ci.yml
git diff --check -- .github/workflows/ci.yml
```

Expected: the unfinished-marker scan returns no matches; the diff check passes.

- [ ] **Step 4: Extract and syntax-check the exact hosted Bash range logic**

Because the whitespace step is the workflow's final step, extract its final
literal block without adding a repository script:

```powershell
$lines = Get-Content .github/workflows/ci.yml
$runMarker = [Array]::LastIndexOf($lines, '        run: |')
if ($runMarker -lt 0) { throw 'Whitespace run block not found' }
$indentedScript = $lines[($runMarker + 1)..($lines.Count - 1)]
if ($indentedScript | Where-Object { $_ -and -not $_.StartsWith('          ') }) {
    throw 'Unexpected indentation in whitespace run block'
}
$rangeScript = ($indentedScript | ForEach-Object {
    if ($_.Length -ge 10) { $_.Substring(10) } else { '' }
}) -join "`n"
& bash -n -c $rangeScript
if ($LASTEXITCODE -ne 0) { throw 'Whitespace Bash syntax check failed' }
```

Expected: no syntax error. This executes no workflow and makes no repository
change.

- [ ] **Step 5: Exercise PR, normal-push, and initial-push range branches**

Define a local runner for the extracted script:

```powershell
function Invoke-RangeCheck {
    param(
        [Parameter(Mandatory)] [string] $RepositoryPath,
        [Parameter(Mandatory)] [string] $EventName,
        [string] $PrBaseSha = '',
        [string] $PushBeforeSha = '',
        [Parameter(Mandatory)] [string] $TargetSha
    )
    Push-Location $RepositoryPath
    try {
        $env:EVENT_NAME = $EventName
        $env:PR_BASE_SHA = $PrBaseSha
        $env:PUSH_BEFORE_SHA = $PushBeforeSha
        $env:TARGET_SHA = $TargetSha
        & bash -c $rangeScript | Out-Host
        return $LASTEXITCODE
    }
    finally {
        Remove-Item Env:EVENT_NAME,Env:PR_BASE_SHA,Env:PUSH_BEFORE_SHA,Env:TARGET_SHA -ErrorAction SilentlyContinue
        Pop-Location
    }
}

$repositoryPath = (Resolve-Path .).Path
$targetSha = git rev-parse HEAD
$baseSha = git rev-parse HEAD^
$zeroSha = '0000000000000000000000000000000000000000'

if ((Invoke-RangeCheck $repositoryPath pull_request $baseSha '' $targetSha) -ne 0) {
    throw 'PR range failed'
}
if ((Invoke-RangeCheck $repositoryPath push '' $baseSha $targetSha) -ne 0) {
    throw 'Normal push range failed'
}
if ((Invoke-RangeCheck $repositoryPath push '' $zeroSha $targetSha) -ne 0) {
    throw 'Initial push empty-tree range failed'
}
```

Expected: all three return 0. The PR case compares `HEAD^` to `HEAD` as the
local analogue of recorded PR base to tested merge commit; the push case uses
before to target; the initial case compares the Git empty tree to target.

- [ ] **Step 6: Exercise successful targeted fetch and explicit unresolved failure**

Use a temporary shallow clone so the current worktree's history is untouched:

```powershell
$tempBase = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$tempRoot = [IO.Path]::GetFullPath((Join-Path $tempBase ("pantrypilot-ci-range-" + [guid]::NewGuid())))
if (-not $tempRoot.StartsWith($tempBase, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Temporary path escaped the system temp directory'
}
$tempRepo = Join-Path $tempRoot 'repo'

try {
    New-Item -ItemType Directory -Path $tempRoot | Out-Null
    git clone --no-local --depth 1 --branch feat/automated-ci-verification $repositoryPath $tempRepo
    if ($LASTEXITCODE -ne 0) { throw 'Temporary shallow clone failed' }

    if ((Invoke-RangeCheck $tempRepo push '' $baseSha $targetSha) -ne 0) {
        throw 'Targeted fetch did not recover the missing base'
    }

    $missingSha = '1111111111111111111111111111111111111111'
    if ((Invoke-RangeCheck $tempRepo push '' $missingSha $targetSha) -eq 0) {
        throw 'Unresolvable nonzero base was silently accepted'
    }
}
finally {
    if (Test-Path -LiteralPath $tempRoot) {
        $resolvedTempRoot = [IO.Path]::GetFullPath($tempRoot)
        if (-not $resolvedTempRoot.StartsWith($tempBase, [StringComparison]::OrdinalIgnoreCase)) {
            throw 'Refusing to remove a path outside the system temp directory'
        }
        Remove-Item -LiteralPath $resolvedTempRoot -Recurse -Force
    }
}
```

Expected: the shallow clone initially lacks `HEAD^`; one read-only fetch from
its local `origin` supplies that valid base and the check returns 0. The fake
nonzero base causes the fetch warning, explicit unavailable-base error, and a
nonzero result. No branch, commit, ref, or working-tree file in the actual
repository changes.

- [ ] **Step 7: Run the complete local PantryPilot contract against the workflow diff**

Run each command separately:

```powershell
uv lock --check
uv run pytest
uv run python -m pantrypilot.evaluation evaluations/ingredient-resolution-v1.json
uv run ruff format --check src tests
uv run ruff check src tests
git diff --check
```

Expected: 252 tests pass with only the existing warning; evaluator precision
and recall are `1.0`, false positives are zero, and alias-aware recall improves
over baseline; all other commands pass. The evaluator's existing process exit
code is the gate—do not parse its JSON or weaken its acceptance condition.

- [ ] **Step 8: Perform the workflow reviewer gate**

Review the complete diff and confirm:

- event, concurrency, permission, runner, timeout, and check naming match the
  design;
- both actions use the freshly verified full SHAs and release comments;
- uv version, checksum, direct GitHub download override, and both cache-disable
  inputs are exact;
- `.python-version` governs `uv python install`, and logs show resolved uv and
  Python versions;
- the PR base means the base state GitHub used for this run, not future `main`;
- event values enter Bash through quoted environment variables, must match full
  SHA syntax before Git use, and are never evaluated as shell code;
- missing endpoints fail closed, and the all-zero sentinel alone selects the
  empty tree;
- no secret, artifact, cache, matrix, deployment, mutable ref, credential
  persistence, or `continue-on-error` exists.

Material findings must be corrected, followed by Steps 2–7 again.

- [ ] **Step 9: Stage only the workflow and inspect the exact staged diff**

Immediately before staging, rerun Task 1 Steps 3–6 and require the same official
upstream, tag-to-SHA, action-input, final-release, artifact, and checksum results.
This is the implementation-time re-verification gate, not permission to trust
the earlier evidence indefinitely.

Only after that fresh evidence passes and the owner authorizes this
implementation commit:

```powershell
git add .github/workflows/ci.yml
git diff --cached --name-only
git diff --cached --check
git diff --cached -- .github/workflows/ci.yml
```

Expected: exactly `.github/workflows/ci.yml` is staged and its staged diff is
the reviewed workflow. Then, and only with commit authorization:

```powershell
git commit -m "ci: add automated verification workflow"
```

Do not push.

---

### Task 3: Write the Feature 005 Documentation Without Overstating Hosted Proof

**Files:**

- Create: `docs/learning/005-automated-ci-verification.md`
- Modify: `README.md`

- [ ] **Step 1: Establish the documentation absence baseline**

Run:

```powershell
Test-Path docs/learning/005-automated-ci-verification.md
```

Expected: `False`. Stop rather than overwrite an unexpected file.

- [ ] **Step 2: Create the learning guide with this exact teaching structure**

Write `docs/learning/005-automated-ci-verification.md` using these headings and
responsibilities:

```markdown
# Feature 005: Automated CI verification

## What we built and why now
## CI, delivery, deployment, and CD
## Clean runner versus a developer machine
## GitHub Actions vocabulary and event flow
## Reproducing Python and dependencies with uv
## Immutable actions and uv supply-chain controls
## Least privilege, fork pull requests, and secrets
## Direct quality gates and exit-code propagation
## Event-aware committed-whitespace verification
## Job layout, timeout, concurrency, caching, and matrices
## Reading GitHub Actions evidence
## Failure categories and troubleshooting
## What green CI proves—and does not prove
## Checks, required checks, and branch protection
## Windows local development and future portability evidence
## Safe tool and action upgrades
## Practical exercises
## Mock-interview questions and answer guidance
```

The prose must teach all of the following accurately:

- CI automatically integrates and verifies proposed work; continuous delivery
  keeps work releasable; continuous deployment automatically releases; a
  deployment is the act of putting a version into an environment. Feature 005
  performs verification only.
- CI is justified now because Features 001–004 produced a meaningful local
  contract whose evidence GitHub did not independently execute or record.
- A workflow is the YAML file; an event starts a run; the run contains jobs;
  a job uses a runner and contains steps; logs record step output; a check is
  GitHub's result; a required check exists only through separate governance.
- PR runs test the merge commit against the base state recorded for that run;
  they do not prove compatibility with later changes to `main`. Push runs test
  the integrated commit after merge.
- `.python-version` and `requires-python ==3.12.*` are the compatibility
  contract; uv installs a compatible interpreter; the workflow logs the
  resolved patch version. `uv.lock` fixes the dependency graph, and
  `uv sync --locked` refuses unapproved lock drift.
- Every action ref is a reviewed SHA with a readable release comment. uv
  `0.11.32` and its Linux x86-64 artifact checksum are declared in
  `.github/workflows/ci.yml`; `download-from-astral-mirror: false` binds setup
  to the reviewed official GitHub release artifact; both caches are disabled.
- `permissions: contents: read`, `persist-credentials: false`, and no secrets
  constrain proposed code. Under `pull_request`, the workflow definition comes
  from the PR merge commit, so a fork can modify it. GitHub restricts fork
  tokens, withholds repository secrets, and may require approval under repository
  policy; `.github/workflows/**` still requires security-sensitive review.
- `pull_request_target` is rejected because it runs the trusted base workflow
  in a more privileged context and is unnecessary here. A green PR check does
  not prove the PR did not modify the check itself.
- Normal workflow logs exist, but this workflow does not upload pantry data,
  request bodies, SQLite databases, ranking/request histories, or other
  user-derived application data as artifacts.
- Each named command controls the job through its process exit code. The
  evaluator prints deterministic JSON to normal logs and exits nonzero unless
  recall improves over exact matching with zero false positives.
- The whitespace step uses recorded event SHAs, validates Git object endpoints,
  maps only an all-zero initial push to the empty tree, attempts one read-only
  fetch for an unexpected missing nonzero base, and otherwise fails closed.
- One job avoids duplicated setup; ten minutes bounds runaway work; only
  superseded runs for the same PR cancel; push-to-main runs remain as evidence;
  no cache or matrix is justified at current scale.
- Direct named steps improve failure diagnosis. The local command list must be
  deliberately maintained beside workflow changes; reconsider a shared script
  only after real drift or duplication becomes a maintenance problem.
- Distinguish setup/network/action/YAML failures from product tests, evaluator,
  Ruff, lockfile, and whitespace failures. Explain how to open Actions, choose
  the run/job/failed step, inspect versions and command output, fix locally,
  rerun the complete contract, obtain review, and use GitHub's **Re-run jobs**
  only for a justified retry.
- A green check proves the tested commit completed this narrow Linux/Python
  contract. It does not prove Windows compatibility, future-base compatibility,
  deployment readiness, production correctness, broad security, or merge
  enforcement.
- `main` remains unprotected unless separately changed. Branch protection or a
  ruleset can later require the stable `PantryPilot verification` check, but
  that is a distinct owner-authorized governance change.
- Windows developers continue using uv locally. Add Windows hosted CI only when
  an OS-specific defect or explicit portability requirement provides evidence.
- Upgrade actions by selecting an intended upstream release, resolving its tag
  through the canonical repository to the final commit, reviewing release/source
  changes, replacing the SHA and comment together, and rerunning local/hosted
  evidence. Upgrade uv by reviewing the official final release, selecting the
  exact platform artifact, replacing version and checksum together, and
  revalidating setup-uv semantics.

Include the authoritative commands exactly:

```powershell
uv lock --check
uv run pytest
uv run python -m pantrypilot.evaluation evaluations/ingredient-resolution-v1.json
uv run ruff format --check src tests
uv run ruff check src tests
git diff --check
```

Include practical exercises that ask the owner to trace a PR run, explain why
a push run is retained, derive the correct whitespace range for each event,
classify sample failures, audit action pins/permissions, and describe a safe uv
upgrade without performing a repository mutation.

Finish with concise answer guidance for at least these mock-interview questions:

- Why is this CI rather than CD or deployment?
- What does a clean runner prove that a local pass does not?
- How do `.python-version`, `requires-python`, `uv.lock`, and `uv sync --locked`
  divide responsibility?
- Why pin both action SHAs and the uv artifact checksum?
- Why explicitly disable the Astral mirror and caching?
- Why is an ordinary fork PR still untrusted when using `pull_request`?
- Why is `pull_request_target` wrong here?
- Why does a green check not prove its own workflow was unchanged?
- How does the evaluator fail the job?
- Why is `git diff --check` event-aware in hosted CI?
- Why one job, one OS, one Python line, and a ten-minute timeout?
- Why cancel superseded PR runs but retain `main` runs?
- How do workflow failures differ from product/test failures?
- What does green CI not prove?
- What changes when `PantryPilot verification` becomes a required check?
- What evidence would justify caching, a matrix, a shared script, manual
  dispatch, or Windows hosted CI later?

- [ ] **Step 3: Add the stable README documentation while preserving the current-status truth**

Leave the `## Current status` paragraph at Feature 004 until an actual
owner-authorized PR run succeeds. Add an `## Automated verification` section
containing this authoritative local contract:

```powershell
uv lock --check
uv run pytest
uv run python -m pantrypilot.evaluation evaluations/ingredient-resolution-v1.json
uv run ruff format --check src tests
uv run ruff check src tests
git diff --check
```

State explicitly:

- `.github/workflows/ci.yml` configures GitHub to run the visible
  `PantryPilot verification` check for PRs targeting `main` and pushes to
  `main`, but local inspection cannot prove hosted recognition or execution;
- Windows developers continue to run the uv contract locally;
- `ubuntu-24.04` is Feature 005's single hosted target, not a declaration that
  PantryPilot is Linux-only;
- the visible check is not a required merge check, and `main` remains
  unprotected unless separately changed;
- green CI does not prove deployment readiness, production correctness, broad
  security, Windows compatibility, or merge enforcement;
- no CI badge is included.

Add these project-document links:

```markdown
- [Feature 005 design](docs/superpowers/specs/2026-08-20-automated-ci-verification-design.md)
- [Feature 005 learning guide](docs/learning/005-automated-ci-verification.md)
```

- [ ] **Step 4: Verify both documents against the implemented workflow**

Run:

```powershell
Select-String -Path docs/learning/005-automated-ci-verification.md -Pattern 'PantryPilot verification','ubuntu-24.04','0.11.32','download-from-astral-mirror','contents: read','pull_request_target','uv sync --locked','git diff --check','Windows','branch protection'
Select-String -Path README.md -Pattern 'Feature 004','PantryPilot verification','ubuntu-24.04','Windows','unprotected','required','uv lock --check','git diff --check'
rg -n 'T[B]D|T[O]DO|F[I]XME|implement la[t]er|fill i[n]' README.md docs/learning/005-automated-ci-verification.md
git diff --check -- README.md docs/learning/005-automated-ci-verification.md
```

Expected: every required subject appears, README still says Feature 004 is the
current completed feature, the unfinished-marker scan has no matches, and the
whitespace check passes. Read both documents once beside
`.github/workflows/ci.yml`; all names, values, commands, trust statements, and
limitations must agree.

- [ ] **Step 5: Perform the documentation reviewer gate**

Review for technical accuracy, owner explainability, security, scope, and
lifecycle truthfulness. In particular, confirm neither document claims that a
hosted run, Feature 005 current-status acceptance, branch protection, Windows
hosted compatibility, deployment, or production acceptance already exists.
Material findings require correction and a fresh Step 4.

- [ ] **Step 6: Stage only the two documentation files and inspect the staged diff**

Only after the owner authorizes this documentation commit:

```powershell
git add README.md docs/learning/005-automated-ci-verification.md
git diff --cached --name-only
git diff --cached --check
git diff --cached -- README.md docs/learning/005-automated-ci-verification.md
```

Expected: exactly `README.md` and the learning guide are staged and match the
reviewer-approved content. Then, and only with commit authorization:

```powershell
git commit -m "docs: explain automated CI verification"
```

Do not push.

---

### Task 4: Complete Local Verification, Internal Codex Review, and Independent Review Gate

**Files:**

- Review: `.github/workflows/ci.yml`,
  `README.md`, `docs/learning/005-automated-ci-verification.md`, approved design,
  and the complete branch diff
- Modify: only the three implementation files above when remediating an
  approved in-scope finding
- Create: none

- [ ] **Step 1: Run fresh whole-branch static and scope checks**

Run:

```powershell
$designBase = 'a735ffeb6e16a3782b677b6a5b8fb935dc17e514'
$planPath = 'docs/superpowers/plans/2026-08-20-automated-ci-verification.md'
$implementationBase = (git log -1 --format=%H -- $planPath).Trim()

if ($implementationBase -notmatch '^[0-9a-f]{40}$') {
    throw 'Could not derive the implementation-plan commit'
}
git cat-file -e "${implementationBase}^{commit}"
if ($LASTEXITCODE -ne 0) { throw 'Derived implementation-plan commit is unavailable' }
git merge-base --is-ancestor $designBase $implementationBase
if ($LASTEXITCODE -ne 0) { throw 'Design commit is not an ancestor of the implementation baseline' }
git merge-base --is-ancestor $implementationBase HEAD
if ($LASTEXITCODE -ne 0) { throw 'Implementation-plan commit is not an ancestor of HEAD' }

$planBaselineChanges = @(git diff --name-status $designBase $implementationBase --)
$expectedPlanAddition = "A`t$planPath"
if ($planBaselineChanges.Count -ne 1 -or $planBaselineChanges[0] -ne $expectedPlanAddition) {
    $planBaselineChanges | Out-Host
    throw 'Implementation baseline contains changes other than the added plan'
}

$expectedImplementationFiles = @(
    '.github/workflows/ci.yml',
    'README.md',
    'docs/learning/005-automated-ci-verification.md'
)
$actualImplementationFiles = @(git diff --name-only $implementationBase HEAD --)
$scopeDifference = @(Compare-Object $expectedImplementationFiles $actualImplementationFiles)
if ($scopeDifference.Count -ne 0) {
    $scopeDifference | Format-Table | Out-Host
    throw 'Implementation diff does not contain exactly the three approved files'
}

$status = @(git status --porcelain)
if ($status.Count -ne 0) {
    $status | Out-Host
    throw 'Whole-branch review requires a clean working tree'
}

git diff $implementationBase HEAD --name-status
git diff $implementationBase HEAD --stat
git diff $implementationBase HEAD --check
```

Expected before publication: only `.github/workflows/ci.yml`, `README.md`, and
`docs/learning/005-automated-ci-verification.md` differ from the derived
implementation-plan baseline. The plan commit remains separate from that
implementation-only diff, while design commit
`a735ffeb6e16a3782b677b6a5b8fb935dc17e514` remains the architecture baseline.
README documents the configured system but deliberately retains Feature 004 as
the current accepted status until actual hosted PR evidence exists.

Repeat Task 2 Step 3's policy scans and Task 2 Steps 4–6's Bash range tests.

- [ ] **Step 2: Run the complete local verification contract fresh**

Run each command separately:

```powershell
uv lock --check
uv run pytest
uv run python -m pantrypilot.evaluation evaluations/ingredient-resolution-v1.json
uv run ruff format --check src tests
uv run ruff check src tests
git diff --check
```

Expected: 252 tests pass with the one known warning allowed and unsuppressed;
evaluation precision and recall are `1.0`, false positives are zero, and recall
beats the exact-name baseline; lockfile, Ruff, and whitespace checks pass.

- [ ] **Step 3: Conduct the internal Codex implementation review**

Review the approved design, issue, workflow, learning guide, staged/committed
diffs, and fresh command output. Record severity-ordered findings for:

- exact design compliance and approved-file scope;
- GitHub expression/YAML structure and stable naming;
- Bash safety, event routing, object validation, fetch behavior, and range
  semantics;
- action tag-to-SHA and uv artifact checksum evidence;
- least privilege, fork behavior, no-secret execution, and workflow-change
  review risk;
- direct failure propagation and absence of bypasses;
- documentation accuracy and owner explainability;
- local baseline and complete regression evidence;
- the publication/governance boundary.

Material findings must be remediated in the owning Task 2 or Task 3 file,
reviewed again at that task gate, committed only with owner authorization, and
followed by fresh Steps 1–3. Do not broaden scope to clear a deferred warning or
Feature 004 observation.

- [ ] **Step 4: Stop for the mandatory independent Claude Code review**

Do not invoke Claude from this plan and do not author its prompt. The owner or
architect supplies the separately authored read-only review prompt. Provide the
approved design, branch diff, supply-chain evidence, static/range evidence, and
complete local verification output for review.

Any material independent finding returns to the owning implementation task,
then requires fresh local verification and a fresh internal review before the
independent gate is cleared.

- [ ] **Step 5: Produce the pre-publication handoff and stop**

Record:

- workflow and pre-publication documentation commit SHAs/messages/files;
- action release-to-SHA evidence and uv release/artifact/checksum evidence;
- static scan and five range-test outcomes;
- complete local verification outcomes, including the accepted warning;
- internal Codex review result;
- independent Claude Code review result;
- the output of these exact commands:

  ```powershell
  $designBase = 'a735ffeb6e16a3782b677b6a5b8fb935dc17e514'
  $planPath = 'docs/superpowers/plans/2026-08-20-automated-ci-verification.md'
  $implementationBase = (git log -1 --format=%H -- $planPath).Trim()
  git show -s --format='design %H %s' $designBase
  git show -s --format='implementation-plan %H %s' $implementationBase
  git status --short --branch
  git log --oneline "$implementationBase..HEAD"
  ```

Then stop. Do not push, open a Draft PR, trigger GitHub Actions, mutate branch
protection/rulesets/permissions, or update README under the pre-publication
authorization.

---

### Task 5: Complete the Separately Authorized Hosted Lifecycle and README

**Authorization gate:** None of this task is authorized by approval of this
plan or by local implementation authorization. Execute it only after the owner
explicitly authorizes publication following Task 4.

**Files:**

- Modify after successful PR-hosted evidence: `README.md`
- Inspect: GitHub Draft PR and Actions run/check evidence
- Modify during remediation: only the approved Feature 005 files, and only when
  a diagnosed failure requires it

- [ ] **Step 1: Publish only with explicit owner authorization**

Push the reviewed branch and open a Draft PR only under the owner's separate
instructions. Do not mutate repository settings. Confirm the `pull_request`
event recognizes workflow `CI` and creates job/check `PantryPilot verification`.

- [ ] **Step 2: Collect PR-hosted evidence**

Record the run URL, tested commit SHA, `pull_request` event, workflow and job
names, conclusion, runtime, resolved uv/Python versions, and each executed
quality step. Confirm effective permissions, no secret/artifact/cache behavior,
the recorded PR base and tested merge SHA, and normal evaluator JSON/exit-code
propagation. This proves only integration with the base state used for that run.

Do not create an artificial failing commit. If the first hosted run fails,
classify the workflow/setup/product failure from logs, diagnose normally, fix
only the root cause inside the design, rerun the full local contract and both
reviews, obtain authorization for remediation commits/pushes, and collect fresh
hosted evidence. Never weaken, skip, or bypass a gate merely to obtain green.

- [ ] **Step 3: Update README only after successful PR-hosted evidence exists**

Replace the Feature 004 current-status paragraph with a truthful Feature 005
paragraph that says automated CI verification is implemented and that GitHub
records `PantryPilot verification` for PRs targeting `main` and pushes to
`main`. Do not claim the eventual push-to-main trigger has succeeded before
merge. Leave Task 3's already-reviewed command list, platform boundary,
governance wording, limitations, and document links unchanged unless the hosted
evidence reveals a specific factual correction.

- [ ] **Step 4: Review and verify the README evidence update**

Run:

```powershell
Select-String -Path README.md -Pattern 'Feature 005','PantryPilot verification','ubuntu-24.04','Windows','unprotected','required','uv lock --check','git diff --check'
rg -n 'badge|Linux-only|deployment readiness|production correctness' README.md
git diff --check -- README.md
```

Expected: Feature 005 is now the current status; the required statements and
commands appear; any badge match is only an explicit no-badge statement or
there is no match; no unsupported push-to-main, deployment, production, Windows,
or enforcement claim exists; whitespace passes. Review the README against the
actual successful PR-run evidence.

Then run the complete local contract from Task 4 Step 2 and repeat the internal
Codex review for the final three-file diff. Material findings require normal
remediation and fresh verification.

- [ ] **Step 5: Commit the evidence-backed README update only with authorization**

```powershell
git add README.md
git diff --cached --name-only
git diff --cached --check
git diff --cached -- README.md
```

Expected: exactly `README.md` is staged. Only with explicit owner commit
authorization:

```powershell
git commit -m "docs: document automated CI verification"
```

Obtain separate authorization before pushing this commit. The resulting PR run
must be green again because it is the evidence for the final proposed state.

- [ ] **Step 6: Obtain final owner acceptance and verify the later main push**

After the final PR run is green, present fresh local evidence, final review
results, README truthfulness, and hosted run evidence for owner acceptance.
Merge only with separate owner authorization. After merge, inspect the resulting
`push` run on `main` and record the same evidence fields, including that the
before-to-pushed range executed and `PantryPilot verification` succeeded.

A successful PR run proves the proposed integration path. The successful
post-merge push run proves the integrated `main` trigger. Neither turns the
check into merge enforcement; branch protection remains separate.

---

## Planned Commit Boundaries

| Task | Exact staged files | Intended conventional commit |
|---|---|---|
| 2 | `.github/workflows/ci.yml` | `ci: add automated verification workflow` |
| 3 | `README.md`, `docs/learning/005-automated-ci-verification.md` | `docs: explain automated CI verification` |
| 5, only after successful authorized hosted evidence | `README.md` | `docs: document automated CI verification` |

Tasks 1 and 4 produce evidence and review gates, not commits. Every listed
commit requires owner authorization; every push requires a later, separate
authorization.

## Approved Design Coverage Map

| Approved concern | Implementation task/evidence |
|---|---|
| PR and push triggers; no dispatch, schedule, or paths | Task 2 exact YAML and policy scan |
| Same-PR cancellation; retained main runs | Task 2 concurrency expression; Task 5 hosted inspection |
| Single `ubuntu-24.04` job, 10-minute timeout, no matrix | Task 2 YAML and scans |
| Full-SHA actions and release comments | Task 1 official tag verification; Task 2 exact pins |
| uv 0.11.32, artifact checksum, direct GitHub source | Task 1 decoded pinned-action source plus official release/artifact evidence; Task 2 four explicit setup inputs |
| `.python-version`, `3.12.*`, locked dependencies, version logs | Task 1 baseline; Task 2 install/sync/log steps |
| `contents: read`, no credentials/secrets/artifacts | Task 2 permissions, checkout, scans, and review |
| Accurate fork PR and workflow-change trust model | Global constraints; Task 3 security teaching; Task 4 review |
| Direct tests/evaluator/Ruff steps and exit-code failure | Task 2 exact named steps; Tasks 2 and 4 local evidence |
| Event-aware whitespace, empty tree, fetch, fail-closed behavior | Task 2 exact Bash and five local branch exercises |
| No cache, matrices, shared script, deployment, or extra tooling | Global constraints and Task 2 policy scans |
| Current warning remains baseline only | Tasks 1, 2, and 4 expected verification evidence |
| Learning topics, exercises, troubleshooting, interviews | Task 3 exact structure and content checklist |
| Internal Codex and independent Claude review | Task 4 mandatory sequential gates |
| No publication implied by local YAML | Task 4 hard stop; Task 5 separate authorization gate |
| Required hosted PR and post-merge push evidence | Task 5 evidence and remediation lifecycle |
| README commands, Windows/governance boundaries, links, and no badge | Task 3 exact pre-publication content |
| README current status only after hosted proof | Task 5 evidence-gated status update |
| Checks versus required checks; no settings mutation | Global constraints, Tasks 3 and 5 |

## Plan Self-Review Record

- **Spec coverage:** Every material requirement in Issue #9 and the approved
  design maps to a task and concrete evidence in the table above.
- **Placeholder scan:** The plan contains no unfinished marker, deferred
  implementation instruction, unnamed file, unspecified command, or vague
  error path. Supply-chain discrepancies stop for owner review rather than
  selecting new architecture implicitly.
- **Naming consistency:** Workflow `CI`, job ID `verification`, visible check
  `PantryPilot verification`, runner `ubuntu-24.04`, timeout `10`, uv `0.11.32`,
  all six quality commands, action candidates, checksum, and setup inputs agree
  throughout.
- **Baseline consistency:** The design SHA remains the architecture reference;
  implementation start derives and validates the committed plan SHA without a
  future placeholder; whole-branch scope and handoff logs use that derived plan
  commit so the plan itself cannot pollute the three-file implementation diff.
- **Pinned-source consistency:** Task 1 decodes `action.yml` and the pinned
  download, variant, checksum, manifest, platform, and constant sources. Its
  executable assertions prove direct GitHub selection, checksum invocation,
  raw hexadecimal SHA-256 comparison, and Linux x64 target construction rather
  than treating Git blob IDs as behavioral evidence.
- **Whitespace consistency:** PR, normal push, all-zero initial push, successful
  missing-base fetch, and unresolved-base failure all exercise the same extracted
  Bash body. Only the two approved events are accepted; endpoints are validated
  before `git diff --check`.
- **Security consistency:** The plan uses ordinary `pull_request`, accurately
  treats workflow code as proposed/untrusted, rejects `pull_request_target`,
  declares only `contents: read`, persists no credential, uses no secret, and
  uploads no artifact.
- **Scope consistency:** No application, test, evaluator, lockfile, dependency,
  vision, roadmap, Feature 004 cleanup, warning cleanup, deployment, branch
  protection, ruleset, or other repository-setting work appears.
- **Lifecycle consistency:** README documents the configured workflow before
  publication but keeps Feature 004 as current status; that status advances
  only after real PR-hosted evidence. The pre-publication task stops after local
  and independent review.
  Push, Draft PR, hosted execution, merge, and main-run inspection are isolated
  behind explicit later owner authorization.
- **Reviewability:** Supply-chain evidence is separate from file creation; the
  workflow and pre-publication documentation have focused commits; the small
  evidence-backed README status change follows hosted proof. Each file has a
  meaningful reviewer gate and fresh verification before its authorized commit.

No implementation blocker or approved-design contradiction was found during
planning.
