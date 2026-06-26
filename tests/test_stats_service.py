from __future__ import annotations

from app.core.models import Element
from app.services.stats_service import StatsService


def make_service() -> StatsService:
    return StatsService(
        workload_settings={
            "default_thread_count": 1,
            "type_categories": {
                "APS": ["OAPS", "XAPS"],
                "COBOL": ["OCOB", "XCOB"],
                "JCL": ["JCL"],
                "LINKDECK": ["LINK"],
                "NON_COMPILE": ["PROC"],
                "X_ELEMENTS": ["XML"],
            },
            "types_per_hour_per_thread": {
                "PROD": {
                    "APS": 5,
                    "COBOL": 10,
                    "JCL": 30,
                    "LINKDECK": 10,
                    "NON_COMPILE": 20,
                    "X_ELEMENTS": 10,
                },
                "QUAL": {
                    "APS": 5,
                    "COBOL": 10,
                    "JCL": 30,
                    "LINKDECK": 10,
                    "NON_COMPILE": 20,
                    "X_ELEMENTS": 10,
                },
            },
        }
    )


def test_categorize_type_known() -> None:
    """Verifies configured element types map to their workload category."""
    assert make_service().categorize_type("OCOB") == "COBOL"


def test_categorize_type_unknown_defaults_to_jcl() -> None:
    """Verifies unknown element types fall back to JCL handling."""
    assert make_service().categorize_type("UNKNOWN") == "JCL"


def test_hidden_elements_do_not_count() -> None:
    """Verifies hidden elements are excluded from workload counts."""
    elements = [
        Element("REL", "ABC", "PGM001", "OCOB"),
        Element("REL", "ABC", "PGM002", "OCOB", visible=False),
    ]

    counts = make_service().build_category_counts(elements)

    assert counts["COBOL"] == 1


def test_unselected_elements_do_not_count() -> None:
    """Verifies unselected elements are excluded from workload counts."""
    elements = [
        Element("REL", "ABC", "PGM001", "OCOB"),
        Element("REL", "ABC", "PGM002", "OCOB", selected=False),
    ]

    counts = make_service().build_category_counts(elements)

    assert counts["COBOL"] == 1


def test_thread_count_reduces_minutes() -> None:
    """Verifies extra threads reduce estimated runtime."""
    service = make_service()
    elements = [
        Element("REL", "ABC", f"PGM{i:03}", "OCOB")
        for i in range(10)
    ]

    assert service.build_estimate(elements, "PROD", 1)["total_minutes"] == 60
    assert service.build_estimate(elements, "PROD", 2)["total_minutes"] == 30


def test_zero_rate_defaults_one_minute_per_element() -> None:
    """Verifies missing workload rates fall back to one minute per element."""
    service = StatsService(
        workload_settings={
            "default_thread_count": 1,
            "type_categories": {
                "JCL": ["JCL"],
            },
            "types_per_hour_per_thread": {
                "PROD": {
                    "JCL": 0,
                }
            },
        }
    )
    elements = [
        Element("REL", "ABC", "PGM001", "JCL"),
        Element("REL", "ABC", "PGM002", "JCL"),
    ]

    estimate = service.build_estimate(elements, "PROD", 1)

    assert estimate["total_minutes"] == 2
    assert estimate["estimated_time"] == "00:02"
