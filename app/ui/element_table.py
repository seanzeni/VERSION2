from __future__ import annotations

# Purpose:
#     Display inventory elements in a searchable/sortable table.
#
# Used By:
#     MainWindow
#
# Responsibilities:
#     - Display visible elements.
#     - Support display-only search.
#     - Support display-only column sorting.
#     - Allow selectable elements to be selected/unselected.
#     - Notify MainWindow when selection changes.
#
# Notes:
#     Search and column sorting do not affect exports or reports.
#     Exports and reports use their own stable sorting rules.

from typing import Callable

import customtkinter as ctk
import tkinter as tk
from tkinter import ttk

from app.core.models import Element


class ElementTable(ctk.CTkFrame):
    COLUMNS = (
        "selected",
        "element",
        "type",
        "project",
        "severity",
        "reason",
    )

    HEADINGS = {
        "selected": "Selected",
        "element": "Element",
        "type": "Type",
        "project": "Project",
        "severity": "Severity",
        "reason": "Reason",
    }

    def __init__(
        self,
        parent,
        theme_manager,
        on_selection_changed: Callable[[], None],
    ) -> None:
        super().__init__(
            parent,
            corner_radius=8,
        )

        self.theme_manager = theme_manager
        self.on_selection_changed = on_selection_changed

        self.elements: list[Element] = []
        self.displayed_elements: list[Element] = []

        self.search_text: str = ""
        self.sort_column: str | None = None
        self.sort_descending: bool = False
        self.tooltip: tk.Toplevel | None = None
        self.tooltip_target: tuple[str, str] | None = None

        self._build_ui()

    def _build_ui(
        self,
    ) -> None:
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self,
            text="Elements",
            font=ctk.CTkFont(
                size=14,
                weight="bold",
            ),
        ).grid(
            row=0,
            column=0,
            sticky="w",
            padx=8,
            pady=(8, 4),
        )

        frame = ctk.CTkFrame(
            self,
            fg_color="transparent",
        )
        frame.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=8,
            pady=(0, 8),
        )
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        y_scroll = ttk.Scrollbar(
            frame,
            orient="vertical",
        )
        y_scroll.grid(
            row=0,
            column=1,
            sticky="ns",
        )

        x_scroll = ttk.Scrollbar(
            frame,
            orient="horizontal",
        )
        x_scroll.grid(
            row=1,
            column=0,
            sticky="ew",
        )

        self.tree = ttk.Treeview(
            frame,
            columns=self.COLUMNS,
            show="headings",
            selectmode="none",
            yscrollcommand=y_scroll.set,
            xscrollcommand=x_scroll.set,
        )
        self.tree.grid(
            row=0,
            column=0,
            sticky="nsew",
        )

        y_scroll.configure(
            command=self.tree.yview,
        )
        x_scroll.configure(
            command=self.tree.xview,
        )

        for column in self.COLUMNS:
            self.tree.heading(
                column,
                text=self.HEADINGS[column],
                command=lambda col=column: self.set_sort_column(col),
            )

        self.tree.column(
            "selected",
            width=80,
            anchor="center",
            stretch=False,
        )
        self.tree.column(
            "element",
            width=130,
            anchor="w",
        )
        self.tree.column(
            "type",
            width=90,
            anchor="w",
        )
        self.tree.column(
            "project",
            width=110,
            anchor="w",
        )
        self.tree.column(
            "severity",
            width=90,
            anchor="w",
        )
        self.tree.column(
            "reason",
            width=650,
            anchor="w",
            stretch=True,
        )

        self.tree.tag_configure(
            "error",
            background="#663333",
            foreground="#FFFFFF",
        )
        self.tree.tag_configure(
            "warning",
            background="#665533",
            foreground="#FFFFFF",
        )
        self.tree.tag_configure(
            "info",
            background="#334466",
            foreground="#FFFFFF",
        )

        self.tree.bind(
            "<Button-1>",
            self._on_click,
        )
        self.tree.bind(
            "<Motion>",
            self._on_motion,
        )
        self.tree.bind(
            "<Leave>",
            self._hide_tooltip,
        )

    def load_elements(
        self,
        elements: list[Element],
    ) -> None:
        self.elements = [element for element in elements if element.visible]

        self.refresh()

    def set_search_text(
        self,
        search_text: str,
    ) -> None:
        self.search_text = str(search_text or "").strip().upper()

        self.refresh()

    def set_sort_column(
        self,
        column_name: str,
    ) -> None:
        if self.sort_column == column_name:
            self.sort_descending = not self.sort_descending
        else:
            self.sort_column = column_name
            self.sort_descending = False

        self.refresh()

    def refresh(
        self,
    ) -> None:
        self.tree.delete(
            *self.tree.get_children(),
        )
        self._hide_tooltip()

        filtered = self._apply_search(self.elements)

        self.displayed_elements = self._apply_sort(filtered)

        for index, element in enumerate(self.displayed_elements):
            tag = element.color

            self.tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    "â˜‘" if element.selected else "â˜",
                    element.element,
                    element.type,
                    element.project,
                    element.severity.value,
                    element.display_reason,
                ),
                tags=(tag,) if tag else (),
            )

    def select_all(
        self,
    ) -> None:
        for element in self.elements:
            if element.visible and element.selectable:
                element.selected = True

        self.refresh()
        self.on_selection_changed()

    def _on_motion(
        self,
        event,
    ) -> None:
        row_id = self.tree.identify_row(
            event.y,
        )
        column_id = self.tree.identify_column(
            event.x,
        )

        if column_id != "#6" or not row_id:
            self._hide_tooltip()
            return

        element = self.displayed_elements[int(row_id)]
        reason = element.display_reason.strip()

        if not reason:
            self._hide_tooltip()
            return

        target = (row_id, column_id)
        if self.tooltip_target == target:
            self._position_tooltip(event)
            return

        self._show_tooltip(
            event=event,
            text=reason,
            target=target,
        )

    def _show_tooltip(
        self,
        event,
        text: str,
        target: tuple[str, str],
    ) -> None:
        self._hide_tooltip()

        tooltip = tk.Toplevel(self.tree)
        tooltip.wm_overrideredirect(True)
        tooltip.configure(
            background="#111827",
        )

        label = tk.Label(
            tooltip,
            text=text,
            justify="left",
            wraplength=620,
            background="#111827",
            foreground="#F9FAFB",
            relief="solid",
            borderwidth=1,
            padx=10,
            pady=8,
            font=("Segoe UI", 9),
        )
        label.pack()

        self.tooltip = tooltip
        self.tooltip_target = target
        self._position_tooltip(event)

    def _position_tooltip(
        self,
        event,
    ) -> None:
        if self.tooltip is None:
            return

        self.tooltip.wm_geometry(
            f"+{event.x_root + 16}+{event.y_root + 12}"
        )

    def _hide_tooltip(
        self,
        _event=None,
    ) -> None:
        if self.tooltip is not None:
            self.tooltip.destroy()
            self.tooltip = None

        self.tooltip_target = None

    def clear_all(
        self,
    ) -> None:
        for element in self.elements:
            if element.visible:
                element.selected = False

        self.refresh()
        self.on_selection_changed()

    def _apply_search(
        self,
        elements: list[Element],
    ) -> list[Element]:
        if not self.search_text:
            return list(elements)

        return [
            element
            for element in elements
            if self.search_text in element.element.upper()
            or self.search_text in element.type.upper()
            or self.search_text in element.project.upper()
        ]

    def _apply_sort(
        self,
        elements: list[Element],
    ) -> list[Element]:
        if self.sort_column is None:
            return sorted(
                elements,
                key=lambda element: element.display_sort_key,
            )

        return sorted(
            elements,
            key=lambda element: self._sort_value(
                element=element,
                column_name=self.sort_column,
            ),
            reverse=self.sort_descending,
        )

    def _sort_value(
        self,
        element: Element,
        column_name: str,
    ) -> str:
        if column_name == "selected":
            return "1" if element.selected else "0"

        if column_name == "element":
            return element.element.upper()

        if column_name == "type":
            return element.type.upper()

        if column_name == "project":
            return element.project.upper()

        if column_name == "severity":
            return element.severity.value

        if column_name == "reason":
            return element.display_reason.upper()

        return ""

    def _on_click(
        self,
        event,
    ) -> None:
        row_id = self.tree.identify_row(
            event.y,
        )

        column_id = self.tree.identify_column(
            event.x,
        )

        if not row_id:
            return

        if column_id != "#1":
            return

        element = self.displayed_elements[int(row_id)]

        if not element.selectable:
            return

        element.selected = not element.selected

        self.refresh()
        self.on_selection_changed()
