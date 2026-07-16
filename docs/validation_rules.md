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
| 7 | `selection` | `selection` | `movement`, `inventory`, `schedule`, `location`, `archive`, `fixp1` |

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
   - QUAL archive rows can be hidden/skipped when configured.
   - Skips rows already confirmed by movement markers (`MARKED_IN_PROD` or
     `MARKED_IN_QUAL`) and `DO_NOT_MOVE` rows.
   - Still runs when a marker is missing (`MARKED_ALREADY_THERE_BUT_MISSING`) so
     lower-environment evidence can help identify inventory or marker mistakes.
   - Forecast PROD can skip this rule for specific efforts whose QUAL date has
     not happened yet.

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

7. Selection rules
   - File: `app/services/validation_rules/selection_rules.py`
   - Runs last.
   - Applies settings-driven selected/selectable/visible behavior based on all
     statuses produced by earlier rules.

## Resync Report Logic

The Resync Report is not part of the element validation rule pipeline. It is a
report-only NDVR analysis in `app/reports/resync_report.py`.

For QUAL mode, `QUAL1` is treated as the newer source and is compared to
`MAIN1` and `DEVL1`. For PROD mode, `PROD1` is treated as the newer source and
is compared to `QUAL1`, `MAIN1`, and `DEVL1`. In both modes, the selected
inventory row's current moving location is ignored so the move itself does not
create a resync row. `FIXP1` is excluded.

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
