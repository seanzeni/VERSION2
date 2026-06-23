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
    elements = [make_element(project="ABC"), make_element(project="XYZ")]
    make_service().apply_overlap_duplicate_status(elements)
    assert all(e.inventory_status == InventoryStatus.OVERLAP for e in elements)


def test_duplicate_status() -> None:
    elements = [make_element(project="ABC"), make_element(project="ABC")]
    make_service().apply_overlap_duplicate_status(elements)
    assert all(e.inventory_status == InventoryStatus.DUPLICATE for e in elements)


def test_inventory_not_in_release_status() -> None:
    element = make_element(project="NOTSQL")
    make_service().apply_schedule_status(
        [element], [ReleaseEffort(effort_id="ABC")], {}, "REL1"
    )
    assert element.schedule_status == ScheduleStatus.INVENTORY_NOT_IN_RELEASE


def test_no_inventory_with_inventory_status() -> None:
    element = make_element(project="ABC")
    make_service().apply_schedule_status(
        [element], [ReleaseEffort(effort_id="ABC", no_inventory=True)], {}, "REL1"
    )
    assert element.schedule_status == ScheduleStatus.INVENTORY_WHEN_SQL_NO_INVENTORY


def test_wrong_release_status() -> None:
    element = make_element(project="ABC", release="REL1")
    make_service().apply_schedule_status(
        [element], [ReleaseEffort(effort_id="ABC")], {"ABC": "REL2"}, "REL1"
    )
    assert element.schedule_status == ScheduleStatus.EFFORT_RELEASE_MISMATCH


def test_missing_location_status() -> None:
    element = make_element()
    make_service().apply_location_status([element], FakeLocationService(set()), "PROD")
    assert element.location_status == LocationStatus.NOT_FOUND


def test_found_location_status() -> None:
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
    element = make_element(type_="OAPS", package="ARCHIVE")
    make_service().apply_location_status([element], FakeLocationService(set()), "QUAL")
    assert element.location_status == LocationStatus.OK
    assert element.reasons == []


def test_qual_archive_package_location_status_is_not_flagged() -> None:
    element = make_element(type_="OCOB", package="ARCHIVE")
    make_service().apply_location_status([element], FakeLocationService(set()), "QUAL")
    assert element.location_status == LocationStatus.OK
    assert element.reasons == []


def test_qual_archive_package_with_sql_issue_still_runs_location_status() -> None:
    element = make_element(type_="OCOB", package="ARCHIVE")
    element.schedule_status = ScheduleStatus.INVENTORY_NOT_IN_RELEASE

    make_service().apply_location_status([element], FakeLocationService(set()), "QUAL")

    assert element.location_status == LocationStatus.NOT_FOUND


def test_qual_archive_row_is_hidden_and_unselected() -> None:
    element = make_element(type_="OAPS", package="ARCHIVE")
    make_service().apply_selection_rules([element], mode="QUAL")
    assert element.visible is False
    assert element.selected is False
    assert element.selectable is False


def test_qual_archive_package_row_is_hidden_and_unselected() -> None:
    element = make_element(type_="OCOB", package="ARCHIVE")
    make_service().apply_selection_rules([element], mode="QUAL")
    assert element.visible is False
    assert element.selected is False
    assert element.selectable is False


def test_qual_archive_package_row_with_sql_issue_stays_visible() -> None:
    element = make_element(type_="OCOB", package="ARCHIVE")
    element.schedule_status = ScheduleStatus.INVENTORY_NOT_IN_RELEASE

    make_service().apply_selection_rules([element], mode="QUAL")

    assert element.visible is True
    assert element.selected is False
    assert element.selectable is True


def test_missing_location_overrides_not_in_sql_selectable_rule() -> None:
    element = make_element()
    element.schedule_status = ScheduleStatus.INVENTORY_NOT_IN_RELEASE
    element.location_status = LocationStatus.NOT_FOUND

    make_service().apply_selection_rules([element], mode="PROD")

    assert element.visible is True
    assert element.selected is False
    assert element.selectable is False


def test_qual_archive_hide_rule_can_be_disabled() -> None:
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
    element = make_element(type_="OCOB")
    make_service().apply_archive_status(
        [element], FakeLocationService({("PGM001", "OAPS", "PROD1")}), "PROD"
    )
    assert element.archive_status == ArchiveStatus.POTENTIAL_MISSING_ARCHIVE


def test_do_not_move_suppresses_missing_archive_rule() -> None:
    element = make_element(type_="OCOB")
    element.movement_status = MovementStatus.DO_NOT_MOVE

    make_service().apply_archive_status(
        [element], FakeLocationService({("PGM001", "OAPS", "PROD1")}), "PROD"
    )

    assert element.archive_status == ArchiveStatus.OK


def test_missing_archive_rule_does_not_fire_when_opposite_type_in_inventory() -> None:
    elements = [make_element(type_="OCOB"), make_element(type_="OAPS")]
    make_service().apply_archive_status(
        elements, FakeLocationService({("PGM001", "OAPS", "PROD1")}), "PROD"
    )
    assert elements[0].archive_status == ArchiveStatus.OK


def test_missing_program_move_archive_side_in_inventory_program_side_in_qual_missing_inventory() -> (
    None
):
    element = make_element(type_="OAPS", package="ARCHIVE")
    make_service().apply_archive_status(
        [element], FakeLocationService({("PGM001", "OCOB", "QUAL1")}), "PROD"
    )
    assert element.archive_status == ArchiveStatus.POTENTIAL_MISSING_PROGRAM_MOVE


def test_missing_program_move_archive_side_missing_inventory_even_when_program_not_in_qual() -> None:
    element = make_element(type_="OAPS", package="ARCHIVE")

    make_service().apply_archive_status([element], FakeLocationService(set()), "PROD")

    assert element.archive_status == ArchiveStatus.POTENTIAL_MISSING_PROGRAM_MOVE
    assert "Expected opposite program type" in element.reasons[0]


def test_program_type_without_archive_package_does_not_trigger_missing_program_move() -> None:
    element = make_element(type_="OAPS")

    make_service().apply_archive_status(
        [element],
        FakeLocationService({("PGM001", "OCOB", "QUAL1")}),
        "PROD",
    )

    assert element.archive_status == ArchiveStatus.OK


def test_do_not_move_suppresses_missing_program_move_rule() -> None:
    element = make_element(type_="OAPS", package="ARCHIVE")
    element.movement_status = MovementStatus.DO_NOT_MOVE

    make_service().apply_archive_status(
        [element], FakeLocationService({("PGM001", "OCOB", "QUAL1")}), "PROD"
    )

    assert element.archive_status == ArchiveStatus.OK


def test_missing_program_move_only_prod() -> None:
    element = make_element(type_="OAPS")
    make_service().apply_archive_status(
        [element], FakeLocationService({("PGM001", "OCOB", "QUAL1")}), "QUAL"
    )
    assert element.archive_status == ArchiveStatus.OK


def test_fixp1_warning_never_blocks_by_itself() -> None:
    element = make_element()
    service = make_service()
    service.apply_fixp1_status(
        [element], FakeLocationService({("PGM001", "OCOB", "FIXP1")}), "PROD"
    )
    service.apply_selection_rules([element])
    assert element.fix_status == FixStatus.EXISTS_IN_FIXP1
    assert element.selected is True and element.selectable is True


def test_do_not_move_marker_info_hidden_unselectable() -> None:
    element = make_element(package="DO NOT MOVE")
    service = make_service()
    service.apply_movement_status([element], FakeLocationService(set()), "PROD")
    service.apply_selection_rules([element])
    assert element.movement_status == MovementStatus.DO_NOT_MOVE
    assert element.selected is False and element.selectable is False


def test_confirmed_already_in_target_hidden() -> None:
    element = make_element(package="PROD")
    service = make_service()
    service.apply_movement_status(
        [element], FakeLocationService({("PGM001", "OCOB", "PROD1")}), "PROD"
    )
    service.apply_selection_rules([element])
    assert element.source_row["_confirmed_already_in_target"] is True
    assert (
        element.visible is False
        and element.selected is False
        and element.selectable is False
    )


def test_confirmed_already_in_target_with_sql_issue_stays_visible() -> None:
    element = make_element(package="QUAL")
    element.schedule_status = ScheduleStatus.INVENTORY_NOT_IN_RELEASE
    service = make_service()

    service.apply_movement_status(
        [element], FakeLocationService({("PGM001", "OCOB", "QUAL1")}), "QUAL"
    )
    service.apply_selection_rules([element], mode="QUAL")

    assert element.source_row["_confirmed_already_in_target"] is True
    assert element.visible is True
    assert element.selected is False
    assert element.selectable is True


def test_marked_already_there_but_missing_warning_selectable() -> None:
    element = make_element(package="PROD")
    service = make_service()
    service.apply_movement_status([element], FakeLocationService(set()), "PROD")
    service.apply_selection_rules([element])
    assert element.movement_status == MovementStatus.MARKED_ALREADY_THERE_BUT_MISSING
    assert element.selected is False and element.selectable is True


def test_build_inventory_issues_for_missing_expected_inventory() -> None:
    issues = make_service().build_inventory_issues(
        "REL1", [], [ReleaseEffort(effort_id="ABC", no_inventory=False)]
    )
    assert len(issues) == 1
    assert issues[0].issue_type == ScheduleStatus.SQL_EXPECTED_INVENTORY_MISSING
