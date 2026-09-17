from __future__ import annotations

from app.ui.report_center import ReportCenter


def make_report_center(
    reports_settings: dict,
) -> ReportCenter:
    report_center = ReportCenter.__new__(ReportCenter)
    report_center.reports_settings = reports_settings
    return report_center


def test_report_center_uses_default_format_settings() -> None:
    """Verifies normal Report Center format defaults come from settings."""
    report_center = make_report_center(
        {
            "default_formats": {
                "csv": False,
                "xlsx": True,
                "pdf": False,
            }
        }
    )

    assert report_center._default_format_enabled("csv") is False
    assert report_center._default_format_enabled("xlsx") is True
    assert report_center._default_format_enabled("pdf") is False


def test_report_center_defaults_unknown_reports_to_selected() -> None:
    """Verifies new reports remain selected unless explicitly disabled."""
    report_center = make_report_center(
        {
            "default_selected_reports": {
                "Issues Report": False,
            }
        }
    )

    assert report_center._default_report_enabled("Issues Report") is False
    assert report_center._default_report_enabled("New Report") is True
