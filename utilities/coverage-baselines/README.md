# Coverage baselines

Per-package branch-coverage baselines, captured and checked by
`utilities/coverage-baseline` (see that script's docstring for usage).
This is a migration-duration harness for the pytest cutover: a package's
post-cutover pytest-only branch coverage must meet or exceed its
pre-cutover baseline, within a small tolerance band.

Baselines are committed here only while a package's cutover is in
progress — each is captured at the start of that package's cutover,
since a package's number is only actionable then. There is no point
committing a baseline upfront: any change to what the tool measures
(see *Metric versions*) makes older numbers non-comparable, and `check`
refuses to use them.

## Deletion-mapping convention

A legacy (nose-based) test file may only be deleted during a cutover if
its behavior is already covered by a surviving test.
`utilities/coverage-baseline check <package>` confirms that a package's
*overall* branch coverage held up after a cutover — it does not, and
cannot, confirm that any individual deleted file's specific behavior is
actually re-covered by a specific surviving test. A passing `check` run
is necessary but not sufficient to justify a deletion.

Each cutover that deletes or relocates legacy test files must therefore
record an explicit mapping from each deleted file to the surviving
test(s) that cover its behavior — for example, a table in the PR
description. A coverage percentage alone never licenses a deletion.

`utilities/coverage-baseline` does not enforce this mapping in code: it
is a reviewer-verified process requirement, not a mechanism this tool
checks or can check.

## Metric versions

Baselines carry a `metric_version`, bumped whenever a change to what the
tool measures makes older numbers non-comparable. `check` refuses to
compare across versions and tells you to recapture.

- **Version 1** (no `metric_version` key): `--include=src/<pkg>/*` only.
  coverage.py expands a trailing `/*` recursively, so a package's own
  test files counted as measured source. They are ~100% self-covered
  while their suite runs and 0% once it stops, so relocating tests out
  of `src/<pkg>/` during a cutover crashed the number without any
  production code changing. For `provisioningserver` this was 14,231 of
  28,549 counted statements — half the metric was noise.
- **Version 2** (current): adds `--omit=*/tests/*,*/test_*.py`, so the
  baseline tracks production code only.
