from __future__ import annotations
from app.core.models import (
    ArchiveStatus,
    Element,
    FixStatus,
    InventoryStatus,
    LocationStatus,
    MovementStatus,
    ReleaseEffort,
    ScheduleStatus,
)
from app.services.status_marker_service import StatusMarkerService
from app.services.validation_service import ValidationService


class FakeLocationService:
    def __init__(self, env_records: set[tuple[str, str, str]]) -> None:
        self.env_records = {
            (e.upper(), t.upper(), v.upper()) for e, t, v in env_records
        }
        self.location_records: set[tuple[str, str, str, str, str]] = set()

    def exists_in_env(self, element: str, type_: str, env: str) -> bool:
        return (element.upper(), type_.upper(), env.upper()) in self.env_records

    def exists_in_location(
        self,
        element: str,
        type_: str,
        env: str,
        system: str,
        subsystem: str,
    ) -> bool:
        return (
            element.upper(),
            type_.upper(),
            env.upper(),
            system.upper(),
            subsystem.upper(),
        ) in self.location_records

    def find(self, element: str, type_: str) -> list:
        return []

    def exists_in_fixp1(self, element: str, type_: str) -> bool:
        return self.exists_in_env(element, type_, "FIXP1")


class FakeLocationServiceWithLocations(FakeLocationService):
    def __init__(
        self,
        location_records: set[tuple[str, str, str, str, str]],
    ) -> None:
        super().__init__(
            {
                (element, type_, env)
                for element, type_, env, _system, _subsystem in location_records
            }
        )
        self.location_records = {
            (
                element.upper(),
                type_.upper(),
                env.upper(),
                system.upper(),
                subsystem.upper(),
            )
            for element, type_, env, system, subsystem in location_records
        }


def make_service() -> ValidationService:
    marker_service = StatusMarkerService(
        status_markers={
            "marker_columns": ["Package"],
            "do_not_move": ["DO NOT MOVE"],
            "already_in_prod": ["PROD"],
            "already_in_qual": ["QUAL"],
        }
    )
    return ValidationService(
        selection_rules={
            "overlap_selectable": False,
            "duplicate_selectable": False,
            "missing_ndvr_selectable": False,
            "inventory_not_in_release_selectable": True,
            "inventory_when_sql_no_inventory_selectable": True,
            "effort_release_mismatch_selectable": True,
            "hide_archive_rows_in_qual": True,
            "potential_missing_archive_selectable": False,
            "potential_missing_program_move_selectable": True,
            "do_not_move_selectable": False,
            "marked_already_there_missing_selectable": True,
        },
        archive_pairs=[["OAPS", "OCOB"], ["XAPS", "XCOB"]],
        status_marker_service=marker_service,
    )


def make_element(
    element="PGM001", type_="OCOB", project="ABC", release="REL1", package=""
) -> Element:
    return Element(
        release=release,
        project=project,
        element=element,
        type=type_,
        source_row={
            "Package": package,
            "Act Rgn": "DV01",
            "System": "PRIVATE0",
            "Subsys": "SYS1",
        },
    )


def test_overlap_status() -> None:
    """Verifies overlap status."""
    elements = [make_element(project="ABC"), make_element(project="XYZ")]
    make_service().apply_overlap_duplicate_status(elements)
    assert all(e.inventory_status == InventoryStatus.OVERLAP for e in elements)


def test_rule_registry_rows_show_configured_hierarchy() -> None:
    """Verifies rule registry rows show configured hierarchy."""
    rows = make_service().get_rule_registry_rows()

    assert [row["name"] for row in rows] == [
        "movement",
        "inventory",
        "schedule",
        "location",
        "archive",
        "fixp1",
        "selection",
    ]
    assert rows[0]["dependencies"] == "None"
    assert rows[-1]["dependencies"] == (
        "movement, inventory, schedule, location, archive, fixp1"
    )


def test_duplicate_status() -> None:
    """Verifies duplicate status."""
    elements = [make_element(project="ABC"), make_element(project="ABC")]
    make_service().apply_overlap_duplicate_status(elements)
    assert all(e.inventory_status == InventoryStatus.DUPLICATE for e in elements)


def test_overlap_keeps_duplicate_reason_for_repeated_project() -> None:
    """Verifies overlap keeps duplicate reason for repeated project."""
    elements = [
        make_element(project="ABC"),
        make_element(project="ABC"),
        make_element(project="XYZ"),
    ]

    make_service().apply_overlap_duplicate_status(elements)

    assert all(e.inventory_status == InventoryStatus.OVERLAP for e in elements)
    assert all("duplicated" in e.display_reason for e in elements[:2])
    assert "duplicated" not in elements[2].display_reason


def test_inventory_not_in_release_status() -> None:
    """Verifies inventory not in release status."""
    element = make_element(project="NOTSQL")
    make_service().apply_schedule_status(
        [element], [ReleaseEffort(effort_id="ABC")], {}, "REL1"
    )
    assert element.schedule_status == ScheduleStatus.INVENTORY_NOT_IN_RELEASE


def test_no_inventory_with_inventory_status() -> None:
    """Verifies no inventory with inventory status."""
    element = make_element(project="ABC")
    make_service().apply_schedule_status(
        [element], [ReleaseEffort(effort_id="ABC", no_inventory=True)], {}, "REL1"
    )
    assert element.schedule_status == ScheduleStatus.INVENTORY_WHEN_SQL_NO_INVENTORY


def test_withdrawn_effort_with_inventory_status() -> None:
    """Verifies withdrawn effort with inventory status."""
    element = make_element(project="ABC")
    make_service().apply_schedule_status(
        [element], [ReleaseEffort(effort_id="ABC", exit_date="2026-06-24")], {}, "REL1"
    )
    assert element.schedule_status == ScheduleStatus.INVENTORY_WHEN_SQL_NO_INVENTORY


def test_wrong_release_status() -> None:
    """Verifies wrong release status."""
    element = make_element(project="ABC", release="REL1")
    make_service().apply_schedule_status(
        [element], [ReleaseEffort(effort_id="ABC")], {"ABC": "REL2"}, "REL1"
    )
    assert element.schedule_status == ScheduleStatus.EFFORT_RELEASE_MISMATCH


def test_missing_location_status() -> None:
    """Verifies missing location status."""
    element = make_element()
    make_service().apply_location_status([element], FakeLocationService(set()), "PROD")
    assert element.location_status == LocationStatus.NOT_FOUND


def test_validate_elements_can_skip_location_validation_for_forecast() -> None:
    """Verifies validate elements can skip location validation for forecast."""
    element = make_element()
    validated, _issues = make_service().validate_elements(
        elements=[element],
        all_release_elements=[element],
        release_efforts=[ReleaseEffort(effort_id="ABC")],
        effort_release_lookup={},
        location_service=FakeLocationService(set()),
        mode="PROD",
        release="REL1",
        skip_location_validation=True,
    )

    assert validated[0].location_status == LocationStatus.OK


def test_found_location_status() -> None:
    """Verifies found location status."""
    element = make_element()
    make_service().apply_location_status(
        [element],
        FakeLocationServiceWithLocations(
            {("PGM001", "OCOB", "QUAL1", "PRIVATE1", "SYS1")}
        ),
        "PROD",
    )
    assert element.location_status == LocationStatus.FOUND


def test_prod_archive_location_status_looks_for_archive_in_prod() -> None:
    """Verifies PROD archive location status looks for archive in PROD."""
    element = make_element(type_="OAPS", package="ARCHIVE")
    make_service().apply_location_status(
        [element],
        FakeLocationServiceWithLocations(
            {("PGM001", "OAPS", "PROD1", "PRIVATE1", "SYS1")}
        ),
        "PROD",
    )
    assert element.location_status == LocationStatus.FOUND


def test_prod_archive_package_location_status_looks_in_prod() -> None:
    """Verifies PROD archive package location status looks in PROD."""
    element = make_element(type_="OCOB", package="ARCHIVE")
    make_service().apply_location_status(
        [element],
        FakeLocationServiceWithLocations(
            {("PGM001", "OCOB", "PROD1", "PRIVATE1", "SYS1")}
        ),
        "PROD",
    )
    assert element.location_status == LocationStatus.FOUND


def test_qual_location_status_uses_act_region_source_env() -> None:
    """Verifies QUAL location status uses act region source env."""
    element = make_element()
    make_service().apply_location_status(
        [element],
        FakeLocationServiceWithLocations(
            {("PGM001", "OCOB", "DEVL1", "PRIVATE0", "SYS1")}
        ),
        "QUAL",
    )
    assert element.location_status == LocationStatus.FOUND


def test_qual_archive_location_status_is_not_flagged() -> None:
    """Verifies QUAL archive location status is not flagged."""
    element = make_element(type_="OAPS", package="ARCHIVE")
    make_service().apply_location_status([element], FakeLocationService(set()), "QUAL")
    assert element.location_status == LocationStatus.OK
    assert element.reasons == []


def test_qual_archive_package_location_status_is_not_flagged() -> None:
    """Verifies QUAL archive package location status is not flagged."""
    element = make_element(type_="OCOB", package="ARCHIVE")
    make_service().apply_location_status([element], FakeLocationService(set()), "QUAL")
    assert element.location_status == LocationStatus.OK
    assert element.reasons == []


def test_qual_archive_package_with_sql_issue_still_runs_location_status() -> None:
    """Verifies QUAL archive package with SQL issue still runs location status."""
    element = make_element(type_="OCOB", package="ARCHIVE")
    element.schedule_status = ScheduleStatus.INVENTORY_NOT_IN_RELEASE

    make_service().apply_location_status([element], FakeLocationService(set()), "QUAL")

    assert element.location_status == LocationStatus.NOT_FOUND


def test_qual_archive_row_is_hidden_and_unselected() -> None:
    """Verifies QUAL archive row is hidden and unselected."""
    element = make_element(type_="OAPS", package="ARCHIVE")
    make_service().apply_selection_rules([element], mode="QUAL")
    assert element.visible is False
    assert element.selected is False
    assert element.selectable is False


def test_qual_archive_package_row_is_hidden_and_unselected() -> None:
    """Verifies QUAL archive package row is hidden and unselected."""
    element = make_element(type_="OCOB", package="ARCHIVE")
    make_service().apply_selection_rules([element], mode="QUAL")
    assert element.visible is False
    assert element.selected is False
    assert element.selectable is False


def test_qual_archive_package_row_with_sql_issue_stays_visible() -> None:
    """Verifies QUAL archive package row with SQL issue stays visible."""
    element = make_element(type_="OCOB", package="ARCHIVE")
    element.schedule_status = ScheduleStatus.INVENTORY_NOT_IN_RELEASE

    make_service().apply_selection_rules([element], mode="QUAL")

    assert element.visible is True
    assert element.selected is False
    assert element.selectable is True


def test_missing_location_overrides_not_in_sql_selectable_rule() -> None:
    """Verifies missing location overrides not in SQL selectable rule."""
    element = make_element()
    element.schedule_status = ScheduleStatus.INVENTORY_NOT_IN_RELEASE
    element.location_status = LocationStatus.NOT_FOUND

    make_service().apply_selection_rules([element], mode="PROD")

    assert element.visible is True
    assert element.selected is False
    assert element.selectable is False


def test_qual_archive_hide_rule_can_be_disabled() -> None:
    """Verifies QUAL archive hide rule can be disabled."""
    element = make_element(type_="OCOB", package="ARCHIVE")
    service = make_service()
    service.selection_rules["hide_archive_rows_in_qual"] = False

    service.apply_location_status([element], FakeLocationService(set()), "QUAL")
    service.apply_selection_rules([element], mode="QUAL")

    assert element.location_status == LocationStatus.NOT_FOUND
    assert element.visible is True


def test_missing_archive_rule_opposite_type_exists_in_prod_and_missing_inventory() -> (
    None
):
    """Verifies missing archive rule opposite type exists in PROD and missing inventory."""
    element = make_element(type_="OCOB")
    make_service().apply_archive_status(
        [element], FakeLocationService({("PGM001", "OAPS", "PROD1")}), "PROD"
    )
    assert element.archive_status == ArchiveStatus.POTENTIAL_MISSING_ARCHIVE


def test_do_not_move_suppresses_missing_archive_rule() -> None:
    """Verifies do not move suppresses missing archive rule."""
    element = make_element(type_="OCOB")
    element.movement_status = MovementStatus.DO_NOT_MOVE

    make_service().apply_archive_status(
        [element], FakeLocationService({("PGM001", "OAPS", "PROD1")}), "PROD"
    )

    assert element.archive_status == ArchiveStatus.OK


def test_missing_archive_rule_does_not_fire_when_opposite_type_in_inventory() -> None:
    """Verifies missing archive rule does not fire when opposite type in inventory."""
    elements = [make_element(type_="OCOB"), make_element(type_="OAPS")]
    make_service().apply_archive_status(
        elements, FakeLocationService({("PGM001", "OAPS", "PROD1")}), "PROD"
    )
    assert elements[0].archive_status == ArchiveStatus.OK


def test_missing_program_move_archive_side_in_inventory_program_side_in_qual_missing_inventory() -> (
    None
):
    """Verifies missing program move archive side in inventory program side in QUAL missing inventory."""
    element = make_element(type_="OAPS", package="ARCHIVE")
    make_service().apply_archive_status(
        [element], FakeLocationService({("PGM001", "OCOB", "QUAL1")}), "PROD"
    )
    assert element.archive_status == ArchiveStatus.POTENTIAL_MISSING_PROGRAM_MOVE


def test_missing_program_move_archive_side_missing_inventory_even_when_program_not_in_qual() -> None:
    """Verifies missing program move archive side missing inventory even when program not in QUAL."""
    element = make_element(type_="OAPS", package="ARCHIVE")

    make_service().apply_archive_status([element], FakeLocationService(set()), "PROD")

    assert element.archive_status == ArchiveStatus.POTENTIAL_MISSING_PROGRAM_MOVE
    assert "Expected opposite program type" in element.reasons[0]


def test_program_type_without_archive_package_does_not_trigger_missing_program_move() -> None:
    """Verifies program type without archive package does not trigger missing program move."""
    element = make_element(type_="OAPS")

    make_service().apply_archive_status(
        [element],
        FakeLocationService({("PGM001", "OCOB", "QUAL1")}),
        "PROD",
    )

    assert element.archive_status == ArchiveStatus.OK


def test_do_not_move_suppresses_missing_program_move_rule() -> None:
    """Verifies do not move suppresses missing program move rule."""
    element = make_element(type_="OAPS", package="ARCHIVE")
    element.movement_status = MovementStatus.DO_NOT_MOVE

    make_service().apply_archive_status(
        [element], FakeLocationService({("PGM001", "OCOB", "QUAL1")}), "PROD"
    )

    assert element.archive_status == ArchiveStatus.OK


def test_missing_program_move_only_prod() -> None:
    """Verifies missing program move only PROD."""
    element = make_element(type_="OAPS")
    make_service().apply_archive_status(
        [element], FakeLocationService({("PGM001", "OCOB", "QUAL1")}), "QUAL"
    )
    assert element.archive_status == ArchiveStatus.OK


def test_fixp1_warning_never_blocks_by_itself() -> None:
    """Verifies FIXP1 warning never blocks by itself."""
    element = make_element()
    service = make_service()
    service.apply_fixp1_status(
        [element], FakeLocationService({("PGM001", "OCOB", "FIXP1")}), "PROD"
    )
    service.apply_selection_rules([element])
    assert element.fix_status == FixStatus.EXISTS_IN_FIXP1
    assert element.selected is True and element.selectable is True


def test_do_not_move_marker_info_hidden_unselectable() -> None:
    """Verifies do not move marker info hidden unselectable."""
    element = make_element(package="DO NOT MOVE")
    service = make_service()
    service.apply_movement_status([element], FakeLocationService(set()), "PROD")
    service.apply_selection_rules([element])
    assert element.movement_status == MovementStatus.DO_NOT_MOVE
    assert element.selected is False and element.selectable is False


def test_confirmed_already_in_target_hidden() -> None:
    """Verifies confirmed already in target hidden."""
    element = make_element(package="IN PROD")
    service = make_service()
    service.apply_movement_status(
        [element], FakeLocationService({("PGM001", "OCOB", "PROD1")}), "PROD"
    )
    service.apply_selection_rules([element])
    assert element.source_row["_confirmed_already_in_target"] is True
    assert element.movement_status == MovementStatus.MARKED_IN_PROD
    assert "found in PROD1" in element.display_reason
    assert (
        element.visible is False
        and element.selected is False
        and element.selectable is False
    )


def test_confirmed_already_in_target_with_sql_issue_stays_visible() -> None:
    """Verifies confirmed already in target with SQL issue stays visible."""
    element = make_element(package="QUAL")
    element.schedule_status = ScheduleStatus.INVENTORY_NOT_IN_RELEASE
    service = make_service()

    service.apply_movement_status(
        [element], FakeLocationService({("PGM001", "OCOB", "QUAL1")}), "QUAL"
    )
    service.apply_selection_rules([element], mode="QUAL")

    assert element.source_row["_confirmed_already_in_target"] is True
    assert element.movement_status == MovementStatus.MARKED_IN_QUAL
    assert element.visible is True
    assert element.selected is False
    assert element.selectable is True


def test_qual_run_confirms_prod_marker_in_prod() -> None:
    """Verifies QUAL run confirms PROD marker in PROD."""
    element = make_element(package="PROD")
    service = make_service()

    service.apply_movement_status(
        [element],
        FakeLocationService({("PGM001", "OCOB", "PROD1")}),
        "QUAL",
    )
    service.apply_selection_rules([element], mode="QUAL")

    assert element.source_row["_confirmed_already_in_target"] is True
    assert element.movement_status == MovementStatus.MARKED_IN_PROD
    assert "found in PROD1" in element.display_reason
    assert element.visible is False
    assert element.selected is False
    assert element.selectable is False


def test_qual_run_flags_missing_prod_marker_location() -> None:
    """Verifies QUAL run flags missing PROD marker location."""
    element = make_element(package="IN PROD")

    make_service().apply_movement_status(
        [element],
        FakeLocationService(set()),
        "QUAL",
    )

    assert element.movement_status == MovementStatus.MARKED_ALREADY_THERE_BUT_MISSING
    assert "PROD1" in element.display_reason


def test_prod_run_flags_missing_prod_marker_location() -> None:
    """Verifies PROD run validates PROD marker against PROD1."""
    element = make_element(package="IN PROD")

    make_service().apply_movement_status(
        [element],
        FakeLocationService(set()),
        "PROD",
    )

    assert element.movement_status == MovementStatus.MARKED_ALREADY_THERE_BUT_MISSING
    assert "PROD1" in element.display_reason


def test_marked_already_there_but_missing_warning_selectable() -> None:
    """Verifies marked already there but missing warning selectable."""
    element = make_element(package="PROD")
    service = make_service()
    service.apply_movement_status([element], FakeLocationService(set()), "PROD")
    service.apply_selection_rules([element])
    assert element.movement_status == MovementStatus.MARKED_ALREADY_THERE_BUT_MISSING
    assert element.selected is False and element.selectable is True


def test_build_inventory_issues_for_missing_expected_inventory() -> None:
    """Verifies build inventory issues for missing expected inventory."""
    issues = make_service().build_inventory_issues(
        "REL1", [], [ReleaseEffort(effort_id="ABC", no_inventory=False)]
    )
    assert len(issues) == 1
    assert issues[0].issue_type == ScheduleStatus.SQL_EXPECTED_INVENTORY_MISSING


def test_build_inventory_issues_ignores_withdrawn_missing_inventory() -> None:
    """Verifies build inventory issues ignores withdrawn missing inventory."""
    issues = make_service().build_inventory_issues(
        "REL1", [], [ReleaseEffort(effort_id="ABC", exit_date="2026-06-24")]
    )
    assert issues == []
