from __future__ import annotations

# Purpose:
#     Load infrequently changed element/type reference workbooks once.

from pathlib import Path

import pandas as pd


class ReferenceElementService:
    REQUIRED_COLUMNS = ("Element", "Type")

    def __init__(self) -> None:
        self._lists: dict[str, set[tuple[str, str]]] = {}

    def load(
        self,
        name: str,
        file_path: str | Path,
    ) -> None:
        path = Path(file_path)
        dataframe = pd.read_excel(path, dtype=str).fillna("")
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
        self._lists[name] = {
            (
                str(row[element_column]).strip().upper(),
                str(row[type_column]).strip().upper(),
            )
            for _, row in dataframe.iterrows()
            if str(row[element_column]).strip() and str(row[type_column]).strip()
        }

    def matches(
        self,
        name: str,
        element: str,
        type_: str,
    ) -> bool:
        return (
            str(element).strip().upper(),
            str(type_).strip().upper(),
        ) in self._lists.get(name, set())

