from __future__ import annotations

from pathlib import Path

import pytest

from app.services.mainframe_location_service import MainframeLocationService


def make_line(
    element: str,
    type_: str,
    system: str,
    subsystem: str,
    env: str,
    version: str,
    ccid: str = "CCID01",
    ndvr_rc: str = "00000",
    ndvr_package: str = "",
    source_date: str = "",
    source_time: str = "",
) -> str:
    fields = [
        (element, 8),
        (type_, 8),
        (system, 8),
        (subsystem, 4),
        (env, 5),
        ("2026/06/22", 10),
        ("12:00:00:00", 11),
        (version, 5),
        ("USER01", 8),
        (ccid, 7),
        ("COMMENTS", 40),
        (ndvr_rc, 5),
        (ndvr_package, 16),
        (source_date, 10),
        (source_time, 11),
    ]
    return " ".join(value.ljust(width)[:width] for value, width in fields)


def write_location_file(
    tmp_path: Path,
    lines: list[str],
) -> Path:
    path = tmp_path / "locations.txt"
    path.write_text(
        "\n".join(lines),
        encoding="cp1252",
    )
    return path


def test_load_file_and_find(tmp_path: Path) -> None:
    """Verifies fixed-width NDVR records load and index by element/type."""
    path = write_location_file(
        tmp_path,
        [
            make_line("PGM001", "OCOB", "SYSTEM01", "SUB1", "QUAL1", "01.02"),
            make_line("PGM001", "OCOB", "SYSTEM01", "SUB1", "PROD1", "01.01"),
        ],
    )

    service = MainframeLocationService().load_file(path)

    assert len(service.records) == 2
    assert service.exists("PGM001", "OCOB") is True
    assert service.exists_in_env("PGM001", "OCOB", "QUAL1") is True
    assert service.exists_in_env("PGM001", "OCOB", "FIXP1") is False


def test_parse_line_maps_system_and_subsystem_to_correct_widths(
    tmp_path: Path,
) -> None:
    """Verifies fixed-width parsing keeps system and subsystem separate."""
    path = write_location_file(
        tmp_path,
        [
            make_line("PGM001", "OCOB", "PRIVATE1", "SUB1", "QUAL1", "01.01"),
        ],
    )

    record = MainframeLocationService().load_file(path).records[0]

    assert record.system == "PRIVATE1"
    assert record.subsystem == "SUB1"
    assert record.env == "QUAL1"


def test_parse_line_maps_added_ndvr_fields(
    tmp_path: Path,
) -> None:
    """Verifies appended NDVR return code and package fields are parsed."""
    path = write_location_file(
        tmp_path,
        [
            make_line(
                "PGM001",
                "OCOB",
                "PRIVATE1",
                "SUB1",
                "QUAL1",
                "01.01",
                ndvr_rc="00123",
                ndvr_package="PKG001",
            ),
        ],
    )

    record = MainframeLocationService().load_file(path).records[0]

    assert record.ndvr_rc == 123
    assert record.ndvr_package == "PKG001"


def test_parse_line_maps_fixp_source_date_and_time(
    tmp_path: Path,
) -> None:
    """Verifies appended FIXP source date and time fields are parsed."""
    path = write_location_file(
        tmp_path,
        [
            make_line(
                "PGM001",
                "OCOB",
                "PRIVATE1",
                "SUB1",
                "FIXP1",
                "01.01",
                ndvr_rc="00000",
                ndvr_package="PKG001",
                source_date="2026/07/10",
                source_time="08:30:00:00",
            ),
        ],
    )

    record = MainframeLocationService().load_file(path).records[0]

    assert record.source_date == "2026/07/10"
    assert record.source_time == "08:30:00:00"


def test_parse_line_uses_single_space_between_rc_and_package(
    tmp_path: Path,
) -> None:
    """Verifies NDVR RC and package are separated by one delimiter."""
    path = write_location_file(
        tmp_path,
        [
            make_line(
                "PGM001",
                "OCOB",
                "PRIVATE1",
                "SUB1",
                "QUAL1",
                "01.01",
                ndvr_rc="00008",
                ndvr_package="PKG001",
            ),
        ],
    )

    record = MainframeLocationService().load_file(path).records[0]

    assert record.ndvr_rc == 8
    assert record.ndvr_package == "PKG001"


def test_parse_line_allows_missing_added_ndvr_fields(
    tmp_path: Path,
) -> None:
    """Verifies older NDVR rows still load if appended fields are absent."""
    old_line = " ".join(
        value.ljust(width)[:width]
        for value, width in [
            ("PGM001", 8),
            ("OCOB", 8),
            ("PRIVATE1", 8),
            ("SUB1", 4),
            ("QUAL1", 5),
            ("2026/06/22", 10),
            ("12:00:00:00", 11),
            ("01.01", 5),
            ("USER01", 8),
            ("CCID01", 7),
            ("COMMENTS", 40),
        ]
    )
    path = write_location_file(
        tmp_path,
        [
            old_line,
        ],
    )

    record = MainframeLocationService().load_file(path).records[0]

    assert record.ndvr_rc is None
    assert record.ndvr_package == ""


def test_invalid_ndvr_rc_raises(tmp_path: Path) -> None:
    """Verifies non-numeric NDVR return code text fails fast."""
    path = write_location_file(
        tmp_path,
        [
            make_line(
                "PGM001",
                "OCOB",
                "SYSTEM01",
                "SUB1",
                "QUAL1",
                "01.01",
                ndvr_rc="BAD",
            ),
        ],
    )

    with pytest.raises(ValueError, match="Invalid ndvr_rc"):
        MainframeLocationService().load_file(path)


def test_exists_in_fixp1(tmp_path: Path) -> None:
    """Verifies FIXP1 lookup finds matching element/type records."""
    path = write_location_file(
        tmp_path,
        [
            make_line("PGM001", "OCOB", "SYSTEM01", "SUB1", "FIXP1", "01.01"),
        ],
    )

    service = MainframeLocationService().load_file(path)

    assert service.exists_in_fixp1("PGM001", "OCOB") is True


def test_exists_in_location_matches_env_system_and_subsystem(
    tmp_path: Path,
) -> None:
    """Verifies location lookup requires env, system, and subsystem match."""
    path = write_location_file(
        tmp_path,
        [
            make_line("PGM001", "OCOB", "PRIVATE1", "SUB1", "QUAL1", "01.01"),
        ],
    )

    service = MainframeLocationService().load_file(path)

    assert service.exists_in_location(
        "pgm001",
        "ocob",
        "qual1",
        "private1",
        "sub1",
    ) is True
    assert service.exists_in_location(
        "PGM001",
        "OCOB",
        "QUAL1",
        "PRIVATE2",
        "SUB1",
    ) is False
    assert service.exists_in_location(
        "PGM001",
        "OCOB",
        "QUAL1",
        "PRIVATE1",
        "SUB2",
    ) is False


def test_resync_excludes_fixp1(tmp_path: Path) -> None:
    """Verifies FIXP1 records are ignored for resync comparison."""
    path = write_location_file(
        tmp_path,
        [
            make_line("PGM001", "OCOB", "SYSTEM01", "SUB1", "QUAL1", "01.01"),
            make_line("PGM001", "OCOB", "SYSTEM01", "SUB1", "FIXP1", "99.99"),
        ],
    )

    service = MainframeLocationService().load_file(path)

    assert service.has_resync_issue("PGM001", "OCOB") is False


def test_resync_details_include_higher_version_in_lower_environment(
    tmp_path: Path,
) -> None:
    """A newer lower-environment copy needs to be resynced upward."""
    path = write_location_file(
        tmp_path,
        [
            make_line("PGM001", "OCOB", "SYSTEM01", "SUB1", "DEVL1", "01.02"),
            make_line("PGM001", "OCOB", "SYSTEM01", "SUB1", "QUAL1", "01.01"),
        ],
    )

    details = MainframeLocationService().load_file(path).get_resync_details(
        "PGM001",
        "OCOB",
    )

    assert details[0]["lower_env"] == "QUAL1"
    assert details[0]["higher_env"] == "DEVL1"
    assert "Higher version" in details[0]["reason"]


def test_resync_ignores_ccid_mismatch(tmp_path: Path) -> None:
    """CCID differences alone do not indicate a resync."""
    path = write_location_file(
        tmp_path,
        [
            make_line(
                "PGM001",
                "OCOB",
                "SYSTEM01",
                "SUB1",
                "DEVL1",
                "01.01",
                "CCID01",
            ),
            make_line(
                "PGM001",
                "OCOB",
                "SYSTEM01",
                "SUB1",
                "QUAL1",
                "01.01",
                "CCID02",
            ),
        ],
    )

    details = MainframeLocationService().load_file(path).get_resync_details(
        "PGM001",
        "OCOB",
    )

    assert details == []


def test_resync_includes_higher_version_in_equal_environment(
    tmp_path: Path,
) -> None:
    """A newer copy in the same environment is also a resync candidate."""
    path = write_location_file(
        tmp_path,
        [
            make_line("PGM001", "OCOB", "SYSTEM01", "SUB1", "QUAL1", "01.01"),
            make_line("PGM001", "OCOB", "SYSTEM02", "SUB2", "QUAL1", "01.02"),
        ],
    )

    details = MainframeLocationService().load_file(path).get_resync_details(
        "PGM001",
        "OCOB",
    )

    assert len(details) == 1
    assert details[0]["lower_version"] == "01.01"
    assert details[0]["higher_version"] == "01.02"


def test_invalid_version_raises(tmp_path: Path) -> None:
    """Verifies invalid version text fails fast during load."""
    path = write_location_file(
        tmp_path,
        [
            make_line("PGM001", "OCOB", "SYSTEM01", "SUB1", "QUAL1", "BAD"),
        ],
    )

    with pytest.raises(ValueError):
        MainframeLocationService().load_file(path)
