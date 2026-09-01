# Validation Rules

## Purpose

This project validates inventory rows in a fixed order so the UI, exports, and
reports all explain the same decisions.

## Current Hierarchy

Each rule module must define `RULE = RuleDefinition(...)`. Startup validation
fails if a rule is missing `RULE`, missing `apply(context)`, duplicates another
rule name, lists an unknown dependency, or creates a dependency cycle.

`VALIDATION_RULE_MODULES` is a registration list. Execution order is resolved
from each rule's dependency list. `RulePhase` is used only as a tie-breaker when
two rules are otherwise independent.

| Order | Rule | Phase | Dependencies |
| --- | --- | --- | --- |
| 1 | `movement` | `movement` | None |
| 2 | `inventory` | `inventory` | `movement` |
| 3 | `schedule` | `schedule` | `movement`, `inventory` |
| 4 | `location` | `location` | `movement`, `schedule` |
| 5 | `archive` | `archive` | `movement`, `schedule`, `location` |
| 6 | `fixp1` | `fix` | `movement`, `location` |
| 7 | `awareness` | `awareness` | `schedule` |
| 8 | `packaging` | `packaging` | `location` |
| 9 | `selection` | `selection` | `movement`, `inventory`, `schedule`, `location`, `archive`, `fixp1`, `packaging` |

1. Movement rules
   - File: `app/services/validation_rules/movement_rules.py`
   - Marks rows as `DO_NOT_MOVE`.
   - Validates explicit package markers such as `PROD`, `IN PROD`, `QUAL`, or
     `IN QUAL` against the environment named by the marker, regardless of the
     current run mode.
   - Sets `MARKED_IN_PROD` or `MARKED_IN_QUAL` when NDVR confirms the marker.
   - Flags `MARKED_ALREADY_THERE_BUT_MISSING` when marker text is present but
     NDVR does not confirm the marked environment.
   - Runs first because later rules need to know if a row should be ignored.

2. Inventory rules
   - File: `app/services/validation_rules/inventory_rules.py`
   - Marks duplicate element/type rows in the same project.
   - Marks overlap when the same element/type appears in multiple projects.
   - Does not count rows marked `DO_NOT_MOVE`.

3. Schedule rules
   - File: `app/services/validation_rules/schedule_rules.py`
   - Compares inventory projects against SQL release effort data.
   - Marks inventory not connected to the selected release.
   - Marks inventory present when SQL says no inventory is expected.
   - Stores the SQL/RSET release on mismatch rows so reports can show the
     expected release separately from the inventory release.
   - Treats withdrawn efforts as no-inventory expected, but does not create
     missing-inventory issues for withdrawn efforts.
   - Builds SQL missing-inventory issues when SQL expects inventory and none is
     found.

4. Location rules
   - File: `app/services/validation_rules/location_rules.py`
   - Checks expected NDVR environment, system, and subsystem.
   - PROD normally validates from `QUAL1`.
   - PROD archive moves validate from `PROD1`.
   - QUAL validates that the element/type is in the system/standard lifecycle
     stage, accepted as either `SYST1` or `STDV1`.
   - Unit lifecycle records (`UNIT1` or `UTDV1`) are lower-stage evidence for
     QUAL moves, but do not satisfy the expected source location.
   - QUAL archive rows can be hidden/skipped when configured.
   - Skips rows already confirmed by movement markers (`MARKED_IN_PROD` or
     `MARKED_IN_QUAL`) and `DO_NOT_MOVE` rows.
   - Still runs when a marker is missing (`MARKED_ALREADY_THERE_BUT_MISSING`) so
     lower-environment evidence can help identify inventory or marker mistakes.
   - For PROD moves, if the expected `QUAL1` source location is missing but the
     effort's `BundleQualMoveDate` is still in the future, marks
     `NOT_EXPECTED_YET` as a warning instead of the hard `NOT_FOUND` error. The
     row is still not packageable by default.
   - Forecast PROD can skip this rule for specific efforts whose QUAL date has
     not happened yet when running the three-month forecast.

5. Archive rules
   - File: `app/services/validation_rules/archive_rules.py`
   - PROD-only.
   - Detects potential missing archive counterpart rows.
   - Detects potential missing program moves for archive movement.
   - Uses `settings.json` `type_archive_pairs`.

6. FIXP1 rules
   - File: `app/services/validation_rules/fix_rules.py`
   - PROD-only.
   - Flags elements that also exist in `FIXP1`.

7. Awareness rules
   - File: `app/services/validation_rules/awareness_rules.py`
   - Adds informational HIPPA Listener and ODS Element status/reasons from
     configured reference CSVs.

8. Packaging rules
   - File: `app/services/validation_rules/packaging_rules.py`
   - PROD-only.
   - Checks the expected source NDVR row's return code.
   - Blocks non-archive rows when `ndvr_rc` is greater than
     `selection_rules.ndvr_rc_max_allowed`.

9. Selection rules
   - File: `app/services/validation_rules/selection_rules.py`
   - Runs last.
   - Applies settings-driven selected/selectable/visible behavior based on all
     statuses produced by earlier rules.
   - Keeps `NOT_EXPECTED_YET` rows unselected and unselectable unless
     `selection_rules.not_expected_ndvr_yet_selectable` is enabled.

## Selection Rules

Most selectable behavior is controlled from `settings.json`.

The current selectable switches are documented in
`docs/settings_and_deployment.md`. The higher-risk defaults are:

- `missing_ndvr_selectable`: `false`; missing from expected source location
  after it is expected there.
- `not_expected_ndvr_yet_selectable`: `false`; PROD row missing from `QUAL1`
  before its upstream QUAL move date.
- `ndvr_rc_too_high_selectable`: `false`; expected source NDVR return code is
  above the configured threshold.
- `assignment_error_selectable`: `true`; inventory assigned to another release
  remains selectable by default so coordinators can correct SQL/inventory
  alignment while still seeing the element row.
- `highly_likely_missing_program_selectable`: `true`; archive/opposite-program
  evidence from a lower environment is a warning by default.

## Reported Location Statuses

- `OK`: location validation did not apply or did not find a problem.
- `FOUND`: expected source location was confirmed.
- `NOT_EXPECTED_YET`: expected source location is missing, but SQL indicates
  the upstream QUAL movement date has not arrived yet. This is a warning and is
  not packageable by default.
- `NOT_FOUND`: expected source location is missing on or after the date it is
  expected. This is an error.

## Release Tree Grouping

The release tree is grouped to keep active issue review quick:

- `NoExpectedInv`: SQL efforts where no inventory is expected. These are grouped
  alphabetically under the move date instead of showing `NOINV` or `missing`
  child nodes.
- `assign_err`: inventory exists, but the inventory release does not match the
  selected release. The tree shows one child entry: the release currently named
  in inventory. The element rows still load into the Element Table, and
  selectability is controlled by `selection_rules.assignment_error_selectable`.
- `missing`: SQL expects inventory for an effort, but no matching inventory rows
  were found.

## Resync Report Logic

The Resync Report is not part of the element validation rule pipeline. It is a
report-only NDVR analysis in `app/reports/resync_report.py`.

The UI release-specific Resync Report is sandbox/authorization based, not
version based. It reviews all elements tied to efforts moving on the selected
release date, including rows that are not currently selectable because of other
validation issues.

Only system lifecycle records are included: `SYST1` and `STDV1`. Unit records
(`UNIT1` and `UTDV1`), release records (`QUAL1` and `PROD1`), and `FIXP1` are
ignored.

System values are translated to Testing Region with the lookup loaded from
`MiscEnvironmentSystem` for `DEVL1` and `MAIN1`. Records in the active
authorized testing region for the moving effort are skipped. Records tied to
another active effort or a different CCID are marked `plan for retrofit`.
Matching-effort records outside an authorized sandbox are marked
`plan to delete - no authorized sandbox`.

The standalone Global Resync Report is the version-based analysis. It scans all
non-FIXP lifecycle environments and reports same element/type records where an
equal or higher lifecycle environment has a higher version than the target row.

## How To Add A Rule

1. Add or update a status enum in `app/core/models.py` if the rule needs a new
   reportable status. Include a `description` entry for the new value.
2. Add the user-facing reason text in `app/core/status_messages.py`.
3. Add rule logic under `app/services/validation_rules/`.
4. Define `RULE = RuleDefinition(...)` with a unique name, phase, dependency
   tuple, and short description.
5. Expose the rule through an `apply(context: ValidatorContext) -> None`
   function.
6. Add the module to the `VALIDATION_RULE_MODULES` registration list in
   `app/services/validation_service.py`.
7. Update selection behavior in `selection_rules.py` if the status should change
   visibility or selectability.
8. Add tests in `tests/test_validation_service.py` or a focused rule test.

The registry guard lives in `app/services/validation_rules/base.py`. Use
`resolve_rule_modules(...)` or `validate_rule_modules(...)` in tests when
checking a new dependency shape.

## Report Glossary

The Issues Report writes a companion file:

`Issues_Report_Status_Glossary.csv`

Status rows are generated from enum `description` properties in
`app/core/models.py`. Column rows are generated from
`app/reports/report_schemas.py`.
