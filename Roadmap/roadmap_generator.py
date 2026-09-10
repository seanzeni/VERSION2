"""Generate a self-contained interactive swimlane roadmap from JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = PROJECT_DIR / "templates" / "roadmap_template.html"
CSS_PATH = PROJECT_DIR / "static" / "roadmap.css"
JS_PATH = PROJECT_DIR / "static" / "roadmap.js"


def validate(data: dict) -> None:
    required = {"title", "start_year", "end_year", "lanes", "entries"}
    missing = required - data.keys()
    if missing:
        raise ValueError(f"Missing required JSON keys: {', '.join(sorted(missing))}")
    if data["end_year"] < data["start_year"]:
        raise ValueError("end_year must be greater than or equal to start_year")
    lane_ids = {lane["id"] for lane in data["lanes"]}
    for index, entry in enumerate(data["entries"], start=1):
        if entry.get("lane") not in lane_ids:
            raise ValueError(f"Entry {index} references unknown lane: {entry.get('lane')}")
        if "point" not in entry and not {"start", "end"} <= entry.keys():
            raise ValueError(f"Entry {index} needs either point or both start and end")


def generate(source: Path, destination: Path) -> None:
    data = json.loads(source.read_text(encoding="utf-8"))
    validate(data)
    replacements = {
        "__TITLE__": str(data["title"]),
        "__CSS__": CSS_PATH.read_text(encoding="utf-8"),
        "__DATA__": json.dumps(data, ensure_ascii=False).replace("</", "<\\/"),
        "__JAVASCRIPT__": JS_PATH.read_text(encoding="utf-8"),
    }
    html = TEMPLATE_PATH.read_text(encoding="utf-8")
    for placeholder, content in replacements.items():
        html = html.replace(placeholder, content)
    destination.write_text(html, encoding="utf-8")
    print(f"Created {destination.resolve()}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate an interactive swimlane roadmap from JSON.")
    parser.add_argument("source", nargs="?", type=Path, default=PROJECT_DIR / "roadmap_data.json")
    parser.add_argument("destination", nargs="?", type=Path, default=PROJECT_DIR / "roadmap.html")
    args = parser.parse_args()
    generate(args.source.resolve(), args.destination.resolve())


if __name__ == "__main__":
    main()
