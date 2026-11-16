# Coverage baselines

Committed per-package branch-coverage baselines, captured and checked by
`utilities/coverage-baseline`. See
`.ai/sdd/specs/004-coverage-baseline-harness/design.md` for the tool's
design and `.ai/sdd/specs/004-coverage-baseline-harness/requirements.md`
for the requirements these baselines satisfy.

## Deletion-mapping convention

A legacy (nose-based) test file may only be deleted during a cutover
feature (F04-F07) if its behavior is already covered by a surviving
test. `utilities/coverage-baseline check <package>` confirms that a
package's *overall* branch coverage held up after a cutover — it does
not, and cannot, confirm that any individual deleted file's specific
behavior is actually re-covered by a specific surviving test. A passing
`check` run is necessary but not sufficient to justify a deletion.

Each cutover feature that deletes or relocates legacy test files must
therefore record an explicit mapping from each deleted file to the
surviving test(s) that cover its behavior — for example, a
`decisions.md` entry per deleted file, or a table in the feature's PR
description. A coverage percentage alone never licenses a deletion.

`utilities/coverage-baseline` does not enforce this mapping in code: it
is a reviewer-verified process requirement on each cutover feature, not
a mechanism this tool checks or can check.

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
  28,549 counted statements — half the metric was noise. F05 T6 hit this
  as a false `-66.19pp` FAIL on a tree whose production coverage had
  actually improved.
- **Version 2** (current): adds `--omit=*/tests/*,*/test_*.py`, so the
  baseline tracks production code only.

The three committed baselines are still version 1 and will be rejected
by `check`. Each is recaptured at the start of its own cutover feature
rather than upfront, since a package's number is only actionable while
its cutover is in progress.
