from __future__ import annotations

# Purpose:
#     Standalone day-over-day FIXP inventory comparison report.
#
# Usage:
#     py -3.14 scripts/fixp_daily_compare.py
#     py -3.14 scripts/fixp_daily_compare.py --date 2026-07-15

import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests

requests.packages.urllib3.disable_warnings(
    requests.packages.urllib3.exceptions.InsecureRequestWarning
)


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.config.settings_loader import SettingsLoader  # noqa: E402
from app.core.models import MainframeLocationRecord  # noqa: E402
from app.core.release_rules import coerce_date  # noqa: E402
from app.reports.report_utils import export_xlsx  # noqa: E402
from app.reports.report_utils import get_unique_path  # noqa: E402
from app.reports.report_utils import make_read_only  # noqa: E402
from app.reports.report_utils import make_writable  # noqa: E402
from app.services.data_loader import DataLoader  # noqa: E402
from app.services.mainframe_location_service import MainframeLocationService  # noqa: E402


FIXP_FILE_PATTERN = re.compile(
    r"^FIXP-(?P<date>\d{8})_(?P<time>\d{6})\.txt$",
    re.IGNORECASE,
)
LATEST_OUTPUT_FILE = "fixp1-daily-analysis.xlsx"

DETAIL_HEADERS = [
    "Compare",
    "Stage",
    "System",
    "Subsys",
    "Element",
    "Type",
    "FIXP Date",
    "FIXP CCID",
    "Inventory CCIDs",
    "Owner",
    "Manager",
    "Inventory",
    "Remarks",
]


@dataclass(frozen=True, slots=True)
class InventoryReference:
    release: str
    project: str
    team_lead: str
    team_lead_name: str = ""

    @property
    def label(self) -> str:
        return "-".join(
            value
            for value in (
                self.release,
                self.project,
                self.team_lead_name or self.team_lead,
            )
            if value
        )


@dataclass(frozen=True, slots=True)
class PersonDirectoryInfo:
    name: str
    employee_id: str = ""
    supervisor_id: str = ""


@dataclass(frozen=True, slots=True)
class OwnerManagerInfo:
    owner: str
    manager: str = ""


@dataclass(frozen=True, slots=True)
class FixpSnapshotRecord:
    record: MainframeLocationRecord
    file_timestamp: datetime


@dataclass(frozen=True, slots=True)
class FixpCompareDates:
    previous_date: date
    target_date: date


class FixpDailyCompare:
    def __init__(
        self,
        settings: dict[str, Any],
        base_dir: Path,
        fixp_source: Path | None = None,
        ndvr_source: Path | None = None,
        inventory_file: Path | None = None,
        output_folder: Path | None = None,
        person_resolver=None,
        verbose: bool = False,
    ) -> None:
        self.settings = settings
        self.base_dir = base_dir
        fixp_source_value = fixp_source or settings["files"].get(
            "default_fixp_folder",
            "",
        )
        self.fixp_source = (
            self._resolve_path(fixp_source_value)
            if str(fixp_source_value).strip()
            else None
        )
        ndvr_source_value = ndvr_source or settings["files"].get(
            "default_ndvr_file",
            "",
        )
        self.ndvr_source = (
            self._resolve_path(ndvr_source_value)
            if str(ndvr_source_value).strip()
            else None
        )
        self.inventory_file = self._resolve_path(
            inventory_file or settings["files"]["default_input_file"]
        )
        self.output_folder = self._resolve_path(
            output_folder
            or settings["files"].get(
                "default_output_folder",
                "Output",
            )
        )
        self.person_resolver = person_resolver or PersonApiResolver(
            settings.get(
                "directory",
                {},
            ).get(
                "person_lookup_url",
                "",
            ),
            verbose=verbose,
        )

    def run(
        self,
        target_date: date | None,
    ) -> list[Path]:
        compare_dates = self._resolve_compare_dates(target_date)
        rows = self._build_rows(compare_dates)
        xlsx_path = self._latest_output_path()

        self._archive_latest_output(xlsx_path)
        export_xlsx(
            output_path=xlsx_path,
            sheets={
                "FIXP Compare": (
                    DETAIL_HEADERS,
                    rows or self._empty_rows(compare_dates),
                ),
            },
        )
        return [xlsx_path]

    def _latest_output_path(
        self,
    ) -> Path:
        return self.output_folder / "FIXP Daily Compare" / LATEST_OUTPUT_FILE

    def _archive_latest_output(
        self,
        latest_output_path: Path,
    ) -> None:
        if not latest_output_path.exists():
            return

        archive_path = get_unique_path(
            latest_output_path.with_name(
                f"{latest_output_path.stem} - {date.today():%Y-%m-%d}"
                f"{latest_output_path.suffix}"
            )
        )

        make_writable(latest_output_path)
        latest_output_path.rename(archive_path)
        make_read_only(archive_path)

    def build_rows(
        self,
        target_date: date | None,
    ) -> list[list[object]]:
        return self._build_rows(self._resolve_compare_dates(target_date))

    def _build_rows(
        self,
        compare_dates: FixpCompareDates,
    ) -> list[list[object]]:
        previous_snapshot = self._build_snapshot(compare_dates.previous_date)
        target_snapshot = self._build_snapshot(compare_dates.target_date)
        inventory_lookup = self._build_inventory_lookup()
        ndvr_service = self._load_latest_ndvr_service()

        rows: list[list[object]] = []
        all_keys = sorted(
            set(previous_snapshot)
            | set(target_snapshot),
        )

        for key in all_keys:
            previous_record = previous_snapshot.get(key)
            target_record = target_snapshot.get(key)

            compare = self._compare(
                previous_record=previous_record,
                target_record=target_record,
            )
            display_record = (
                target_record.record
                if target_record is not None
                else previous_record.record
                if previous_record is not None
                else None
            )

            if display_record is None:
                continue

            inventory_references = inventory_lookup.get(display_record.key, [])
            owner_info = self._resolve_owner_info(
                user_id=display_record.user,
            )
            inventory_ccids = self._format_inventory_ccids(inventory_references)
            inventory = self._format_inventory(inventory_references)
            remarks = self._build_remarks(
                fixp_record=display_record,
                ndvr_service=ndvr_service,
            )
            rows.append(
                [
                    compare,
                    display_record.env,
                    display_record.system,
                    display_record.subsystem,
                    display_record.element,
                    display_record.type,
                    self._format_fixp_date(display_record.date_generated),
                    display_record.ccid,
                    inventory_ccids,
                    owner_info.owner,
                    owner_info.manager,
                    inventory,
                    remarks,
                ]
            )

        return rows

    def _resolve_compare_dates(
        self,
        target_date: date | None,
    ) -> FixpCompareDates:
        if target_date is not None:
            return FixpCompareDates(
                previous_date=target_date - timedelta(days=1),
                target_date=target_date,
            )

        available_dates = self._available_file_dates()
        if len(available_dates) < 2:
            raise FileNotFoundError(
                "At least two FIXP file dates are required when --date is not provided."
            )

        return FixpCompareDates(
            previous_date=available_dates[-2],
            target_date=available_dates[-1],
        )

    def _build_snapshot(
        self,
        target_date: date,
    ) -> dict[tuple[str, str, str, str, str], FixpSnapshotRecord]:
        snapshot: dict[tuple[str, str, str, str, str], FixpSnapshotRecord] = {}

        for file_path, file_timestamp in self._fixp_files_for_date(target_date):
            service = MainframeLocationService().load_file(file_path)
            for record in service.records:
                key = self._record_key(record)
                candidate = FixpSnapshotRecord(
                    record=record,
                    file_timestamp=file_timestamp,
                )
                existing = snapshot.get(key)

                if existing is None or self._is_newer(candidate, existing):
                    snapshot[key] = candidate

        return snapshot

    def _fixp_files_for_date(
        self,
        target_date: date,
    ) -> list[tuple[Path, datetime]]:
        files: list[tuple[Path, datetime]] = []
        for file_path in self._fixp_source_folder().glob("FIXP-*.txt"):
            file_timestamp = self._parse_file_timestamp(file_path)
            if file_timestamp is None or file_timestamp.date() != target_date:
                continue

            files.append(
                (
                    file_path,
                    file_timestamp,
                )
            )

        return sorted(
            files,
            key=lambda item: (
                item[1],
                item[0].name,
            ),
        )

    def _available_file_dates(
        self,
    ) -> list[date]:
        return sorted(
            {
                file_timestamp.date()
                for file_path in self._fixp_source_folder().glob("FIXP-*.txt")
                if (file_timestamp := self._parse_file_timestamp(file_path))
                is not None
            }
        )

    def _fixp_source_folder(
        self,
    ) -> Path:
        source = self.fixp_source
        if source is None:
            raise FileNotFoundError(
                "FIXP source folder was not configured. Set files.default_fixp_folder "
                "or pass --fixp-source."
            )

        folder = source.parent if source.is_file() else source

        if not folder.exists():
            raise FileNotFoundError(f"FIXP source was not found: {folder}")

        if not folder.is_dir():
            raise NotADirectoryError(f"FIXP source is not a directory: {folder}")

        return folder

    def _load_latest_ndvr_service(
        self,
    ) -> MainframeLocationService | None:
        latest_file = self._latest_ndvr_file()
        if latest_file is None:
            return None

        return MainframeLocationService().load_file(latest_file)

    def _latest_ndvr_file(
        self,
    ) -> Path | None:
        source = self.ndvr_source
        if source is None:
            return None

        if source.is_file():
            return source

        if not source.exists() or not source.is_dir():
            return None

        files = [
            file_path
            for pattern in ("*.txt", "*.dat", "*.csv")
            for file_path in source.glob(pattern)
            if file_path.is_file()
        ]

        if not files:
            return None

        return max(
            files,
            key=lambda file_path: (
                file_path.stat().st_mtime,
                file_path.name,
            ),
        )

    def _parse_file_timestamp(
        self,
        file_path: Path,
    ) -> datetime | None:
        match = FIXP_FILE_PATTERN.match(file_path.name)
        if match is None:
            return None

        return datetime.strptime(
            f"{match.group('date')}{match.group('time')}",
            "%Y%m%d%H%M%S",
        )

    def _build_inventory_lookup(
        self,
    ) -> dict[tuple[str, str], list[InventoryReference]]:
        data_loader = DataLoader(
            file_path=self.inventory_file,
            required_columns=self.settings["required_columns"],
        )
        dataframe = data_loader.load()
        lookup: dict[tuple[str, str], list[InventoryReference]] = defaultdict(list)

        for _, row in dataframe.iterrows():
            element = str(row.get("Element", "")).strip().upper()
            type_ = str(row.get("Type", "")).strip().upper()

            if not element or not type_:
                continue

            lookup[
                (
                    element,
                    type_,
                )
            ].append(
                self._build_inventory_reference(row)
            )

        return dict(lookup)

    def _build_inventory_reference(
        self,
        row,
    ) -> InventoryReference:
        team_lead = str(row.get("DSN ID", "")).strip()[:4]
        team_lead_name = self.person_resolver.resolve(team_lead).name if team_lead else ""

        return InventoryReference(
            release=str(row.get("Release", "")).strip(),
            project=str(row.get("Project", "")).strip(),
            team_lead=team_lead,
            team_lead_name=team_lead_name,
        )

    def _compare(
        self,
        previous_record: FixpSnapshotRecord | None,
        target_record: FixpSnapshotRecord | None,
    ) -> str:
        if target_record is None:
            return "deleted"

        if previous_record is None:
            return "modified"

        if coerce_date(previous_record.record.date_generated) == coerce_date(
            target_record.record.date_generated
        ):
            return "no change"

        return "modified"

    def _record_key(
        self,
        record: MainframeLocationRecord,
    ) -> tuple[str, str, str, str, str]:
        return (
            record.env.strip().upper(),
            record.system.strip().upper(),
            record.subsystem.strip().upper(),
            record.element.strip().upper(),
            record.type.strip().upper(),
        )

    def _is_newer(
        self,
        candidate: FixpSnapshotRecord,
        existing: FixpSnapshotRecord,
    ) -> bool:
        candidate_date = coerce_date(candidate.record.date_generated) or date.min
        existing_date = coerce_date(existing.record.date_generated) or date.min

        return (
            candidate.file_timestamp,
            candidate_date,
            candidate.record.time_generated,
        ) > (
            existing.file_timestamp,
            existing_date,
            existing.record.time_generated,
        )

    def _format_fixp_date(
        self,
        value: str,
    ) -> str:
        parsed_date = coerce_date(value)
        if parsed_date is None:
            return str(value).strip()

        return parsed_date.strftime("%d-%b-%y")

    def _format_inventory(
        self,
        references: list[InventoryReference],
    ) -> str:
        return "; ".join(
            sorted(
                {
                    reference.label
                    for reference in references
                    if reference.label
                }
            )
        )

    def _format_inventory_ccids(
        self,
        references: list[InventoryReference],
    ) -> str:
        return "; ".join(
            sorted(
                {
                    reference.project
                    for reference in references
                    if reference.project
                }
            )
        )

    def _build_remarks(
        self,
        fixp_record: MainframeLocationRecord,
        ndvr_service: MainframeLocationService | None,
    ) -> str:
        if ndvr_service is None:
            return ""

        fixp_date = coerce_date(fixp_record.date_generated)
        if fixp_date is None:
            return ""

        has_newer_prod = any(
            record.env.strip().upper() == "PROD1"
            and (prod_date := coerce_date(record.date_generated)) is not None
            and prod_date > fixp_date
            for record in ndvr_service.find(
                element=fixp_record.element,
                type_=fixp_record.type,
            )
        )

        if has_newer_prod:
            return "Newer version in PROD"

        return ""

    def _resolve_owner_info(
        self,
        user_id: str,
    ) -> OwnerManagerInfo:
        owner = self.person_resolver.resolve(user_id)
        manager = (
            self.person_resolver.resolve_name(owner.supervisor_id)
            if owner.supervisor_id
            else ""
        )

        return OwnerManagerInfo(
            owner=owner.name,
            manager=manager,
        )

    def _empty_rows(
        self,
        compare_dates: FixpCompareDates,
    ) -> list[list[object]]:
        return [
            [
                "no change",
                "",
                "",
                "",
                "",
                "",
                compare_dates.target_date.strftime("%d-%b-%y"),
                "",
                "",
                "",
                "",
                (
                    "No FIXP records found between "
                    f"{compare_dates.previous_date.isoformat()} and "
                    f"{compare_dates.target_date.isoformat()}."
                ),
                "",
            ]
        ]

    def _resolve_path(
        self,
        value: str | Path,
    ) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        return self.base_dir / path


class PersonApiResolver:
    def __init__(
        self,
        lookup_url: str,
        name_resolver=None,
        verbose: bool = False,
    ) -> None:
        self.lookup_url = str(lookup_url).strip()
        self.verbose = verbose
        self.name_resolver = name_resolver or ActiveDirectoryNameResolver(
            verbose=verbose,
        )
        self._cache: dict[str, PersonDirectoryInfo] = {}
        self._debug(
            "Person lookup URL configured: "
            f"{'yes' if self.lookup_url else 'no'}"
        )

    def resolve(
        self,
        criteria: str,
    ) -> PersonDirectoryInfo:
        clean_criteria = str(criteria).strip()
        if not clean_criteria:
            return PersonDirectoryInfo(name="")

        cache_key = clean_criteria.upper()
        if cache_key not in self._cache:
            self._cache[cache_key] = self._lookup(clean_criteria)

        return self._cache[cache_key]

    def _lookup(
        self,
        criteria: str,
    ) -> PersonDirectoryInfo:
        if not self.lookup_url:
            self._debug(
                f"API lookup skipped for {criteria!r}; no person_lookup_url configured."
            )
            return PersonDirectoryInfo(
                name=self.resolve_name(criteria),
            )

        request_url = self._lookup_request_url(criteria)
        self._debug(f"API lookup for {criteria!r}: {request_url}")

        payload = self._request_payload(
            criteria=criteria,
            request_url=request_url,
        )
        if payload is None:
            return PersonDirectoryInfo(name=criteria)

        self._debug(f"API payload for {criteria!r}: {self._payload_summary(payload)}")
        person = self._extract_person_payload(payload)
        if not person:
            self._debug(f"API lookup found no person object for {criteria!r}.")
            return PersonDirectoryInfo(name=criteria)

        employee_id = self._first_value(
            person,
            (
                "employeeId",
                "employeeID",
                "adId",
                "adID",
                "id",
                "networkId",
                "networkID",
                "samAccountName",
                "sAMAccountName",
                "userId",
                "userID",
            ),
        )
        supervisor_id = self._first_value(
            person,
            (
                "supervisorId",
                "supervisorID",
                "managerId",
                "managerID",
                "supervisorAdId",
                "supervisorADID",
                "supervisorUserId",
                "supervisorUserID",
                "supervisorEmployeeId",
            ),
        )
        self._debug(
            f"API extracted for {criteria!r}: employee_id={employee_id!r}, "
            f"supervisor_id={supervisor_id!r}"
        )

        return PersonDirectoryInfo(
            name=self.resolve_name(employee_id or criteria),
            employee_id=employee_id,
            supervisor_id=supervisor_id,
        )

    def _request_payload(
        self,
        criteria: str,
        request_url: str,
    ):
        try:
            response = requests.get(
                request_url,
                timeout=10,
                verify=False,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as exc:
            self._debug(
                f"Requests API lookup failed for {criteria!r}: HTTP "
                f"{exc.response.status_code if exc.response is not None else 'unknown'}"
            )
        except requests.exceptions.SSLError as exc:
            self._debug(
                f"Requests SSL issue ignored for {criteria!r}; "
                f"falling back to PowerShell: {exc}"
            )
        except requests.exceptions.RequestException as exc:
            self._debug(
                f"Requests API lookup failed for {criteria!r}: "
                f"{type(exc).__name__}: {exc}"
            )
        except ValueError as exc:
            self._debug(
                f"Requests API lookup failed for {criteria!r}: invalid JSON {exc}"
            )

        return self._request_payload_with_powershell(
            criteria=criteria,
            request_url=request_url,
        )

    def _request_payload_with_powershell(
        self,
        criteria: str,
        request_url: str,
    ):
        self._debug(f"Trying PowerShell API lookup for {criteria!r}.")

        try:
            result = subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    self._build_api_lookup_script(request_url),
                ],
                capture_output=True,
                check=False,
                encoding="utf-8",
                errors="replace",
                timeout=15,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            self._debug(
                f"PowerShell API lookup failed for {criteria!r}: "
                f"{type(exc).__name__}: {exc}"
            )
            return None

        if result.returncode != 0 or not result.stdout.strip():
            error = result.stderr.strip() if result.stderr else "no output"
            self._debug(f"PowerShell API lookup failed for {criteria!r}: {error}")
            return None

        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            self._debug(
                f"PowerShell API lookup failed for {criteria!r}: invalid JSON {exc}"
            )
            return None

    def _build_api_lookup_script(
        self,
        request_url: str,
    ) -> str:
        escaped_url = request_url.replace(
            "'",
            "''",
        )
        return (
            "$ErrorActionPreference = 'Stop'; "
            f"$response = Invoke-RestMethod -Method Get -Uri '{escaped_url}' "
            "-UseDefaultCredentials; "
            "$response | ConvertTo-Json -Depth 10 -Compress"
        )

    def resolve_name(
        self,
        ad_id: str,
    ) -> str:
        clean_ad_id = str(ad_id).strip()
        if not clean_ad_id:
            return ""

        return self.name_resolver.resolve_name(clean_ad_id)

    def _debug(
        self,
        message: str,
    ) -> None:
        if self.verbose:
            print(
                f"[fixp-directory] {message}",
                file=sys.stderr,
            )

    def _lookup_request_url(
        self,
        criteria: str,
    ) -> str:
        if "{criteria}" in self.lookup_url:
            return self.lookup_url.replace(
                "{criteria}",
                urlencode({"": criteria})[1:],
            )

        for placeholder in (
            "xxxxx",
            "XXXXX",
        ):
            if placeholder in self.lookup_url:
                return self.lookup_url.replace(
                    placeholder,
                    urlencode({"": criteria})[1:],
                )

        if self.lookup_url.endswith(("criteria=", "criteria%3D")):
            return f"{self.lookup_url}{urlencode({'': criteria})[1:]}"

        separator = "&" if "?" in self.lookup_url else "?"
        return f"{self.lookup_url}{separator}{urlencode({'criteria': criteria})}"

    def _extract_person_payload(
        self,
        payload,
    ) -> dict[str, Any]:
        if isinstance(payload, list):
            return self._extract_person_payload(payload[0]) if payload else {}

        if not isinstance(payload, dict):
            return {}

        for key in (
            "data",
            "result",
            "results",
            "items",
            "value",
        ):
            value = payload.get(key)
            if isinstance(value, (dict, list)):
                extracted = self._extract_person_payload(value)
                if extracted:
                    return extracted

        return payload

    def _payload_summary(
        self,
        payload,
    ) -> str:
        if isinstance(payload, list):
            return f"list(len={len(payload)})"

        if isinstance(payload, dict):
            keys = ", ".join(sorted(str(key) for key in payload)[:20])
            return f"dict(keys=[{keys}])"

        return type(payload).__name__

    def _first_value(
        self,
        payload: dict[str, Any],
        keys: tuple[str, ...],
    ) -> str:
        normalized = {
            str(key).lower(): value
            for key, value in payload.items()
        }

        for key in keys:
            value = normalized.get(key.lower())
            if value is not None and str(value).strip():
                return str(value).strip()

        return ""


class ActiveDirectoryNameResolver:
    def __init__(
        self,
        verbose: bool = False,
    ) -> None:
        self.verbose = verbose
        self._cache: dict[str, str] = {}

    def resolve_name(
        self,
        ad_id: str,
    ) -> str:
        clean_ad_id = str(ad_id).strip()
        if not clean_ad_id:
            return ""

        cache_key = clean_ad_id.upper()
        if cache_key not in self._cache:
            self._cache[cache_key] = self._lookup_name(clean_ad_id)

        return self._cache[cache_key]

    def _lookup_name(
        self,
        ad_id: str,
    ) -> str:
        try:
            self._debug(f"AD lookup for {ad_id!r}.")
            result = subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    self._build_lookup_script(ad_id),
                ],
                capture_output=True,
                check=False,
                encoding="utf-8",
                errors="replace",
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired):
            self._debug(f"AD lookup failed for {ad_id!r}: process error or timeout.")
            return ad_id

        if result.returncode != 0 or not result.stdout.strip():
            error = result.stderr.strip() if result.stderr else "no output"
            self._debug(f"AD lookup failed for {ad_id!r}: {error}")
            return ad_id

        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            self._debug(f"AD lookup failed for {ad_id!r}: invalid JSON.")
            return ad_id

        display_name = str(payload.get("DisplayName") or ad_id).strip()
        self._debug(f"AD lookup result for {ad_id!r}: {display_name!r}")
        return display_name

    def _debug(
        self,
        message: str,
    ) -> None:
        if self.verbose:
            print(
                f"[fixp-directory] {message}",
                file=sys.stderr,
            )

    def _build_lookup_script(
        self,
        ad_id: str,
    ) -> str:
        escaped_ad_id = ad_id.replace(
            "'",
            "''",
        )
        return (
            "$ErrorActionPreference = 'Stop'; "
            "Import-Module ActiveDirectory; "
            f"$lookup = '{escaped_ad_id}'; "
            "$user = $null; "
            "try { "
            "$user = Get-ADUser -Identity $lookup -Properties DisplayName "
            "} catch { "
            "$safeLookup = $lookup.Replace(\"'\", \"''\"); "
            "$user = Get-ADUser "
            "-Filter \"EmployeeID -eq '$safeLookup' -or SamAccountName -eq '$safeLookup'\" "
            "-Properties DisplayName | Select-Object -First 1 "
            "}; "
            "[PSCustomObject]@{ "
            "DisplayName = $user.DisplayName "
            "} | ConvertTo-Json -Compress"
        )


def parse_args(
    argv: list[str] | None = None,
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a day-over-day FIXP comparison report."
    )
    parser.add_argument(
        "--settings",
        default=str(REPO_ROOT / "settings.json"),
        help="Path to settings.json. Defaults to the repository settings file.",
    )
    parser.add_argument(
        "--date",
        help=(
            "Report date in YYYY-MM-DD format. Defaults to the latest two FIXP "
            "file dates available."
        ),
    )
    parser.add_argument(
        "--fixp-source",
        help="Optional FIXP source directory. Defaults to files.default_fixp_folder.",
    )
    parser.add_argument(
        "--ndvr-source",
        help="Optional NDVR inventory source directory or file. Defaults to settings.",
    )
    parser.add_argument(
        "--inventory-file",
        help="Optional inventory spreadsheet path. Defaults to settings.",
    )
    parser.add_argument(
        "--output-folder",
        help="Optional output folder. Defaults to settings.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print person API and AD lookup diagnostics to stderr.",
    )
    return parser.parse_args(argv)


def parse_target_date(
    value: str | None,
    today: date | None = None,
) -> date | None:
    if not value:
        return None

    return datetime.strptime(value, "%Y-%m-%d").date()


def main(
    argv: list[str] | None = None,
) -> int:
    args = parse_args(argv)
    settings_path = Path(args.settings).resolve()
    settings = SettingsLoader(settings_path).load()
    base_dir = settings_path.parent
    target_date = parse_target_date(args.date)

    generated_files = FixpDailyCompare(
        settings=settings,
        base_dir=base_dir,
        fixp_source=Path(args.fixp_source) if args.fixp_source else None,
        ndvr_source=Path(args.ndvr_source) if args.ndvr_source else None,
        inventory_file=Path(args.inventory_file) if args.inventory_file else None,
        output_folder=Path(args.output_folder) if args.output_folder else None,
        verbose=args.verbose,
    ).run(target_date)

    print("Generated:")
    for file_path in generated_files:
        print(f"- {file_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
