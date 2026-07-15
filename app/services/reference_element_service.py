from __future__ import annotations

# Purpose:
#     Load infrequently changed element/type reference files once.

from pathlib import Path

import pandas as pd


class ReferenceElementService:
    REQUIRED_COLUMNS = ("Element", "Type")

    def __init__(self) -> None:
        self._lists: dict[str, dict[tuple[str, str], dict[str, str]]] = {}

    def load(
        self,
        name: str,
        file_path: str | Path,
    ) -> None:
        path = Path(file_path)
        dataframe = self._read_file(path)
        column_lookup = {
            str(column).strip().upper(): column
            for column in dataframe.columns
        }
        missing = [
            column
            for column in self.REQUIRED_COLUMNS
            if column.upper() not in column_lookup
        ]
        if missing:
            raise ValueError(
                f"{path.name} is missing required columns: {', '.join(missing)}"
            )

        element_column = column_lookup["ELEMENT"]
        type_column = column_lookup["TYPE"]
        rows: dict[tuple[str, str], dict[str, str]] = {}

        for _, row in dataframe.iterrows():
            element = str(row[element_column]).strip()
            type_ = str(row[type_column]).strip()

            if not element or not type_:
                continue

            rows[(element.upper(), type_.upper())] = {
                str(column).strip(): str(row[column]).strip()
                for column in dataframe.columns
            }

        self._lists[name] = rows

    def _read_file(
        self,
        path: Path,
    ) -> pd.DataFrame:
        if path.suffix.lower() == ".csv":
            return pd.read_csv(path, dtype=str).fillna("")

        return pd.read_excel(path, dtype=str).fillna("")

    def matches(
        self,
        name: str,
        element: str,
        type_: str,
    ) -> bool:
        return (
            str(element).strip().upper(),
            str(type_).strip().upper(),
        ) in self._lists.get(name, {})

    def get(
        self,
        name: str,
        element: str,
        type_: str,
    ) -> dict[str, str] | None:
        return self._lists.get(name, {}).get(
            (
                str(element).strip().upper(),
                str(type_).strip().upper(),
            )
        )
