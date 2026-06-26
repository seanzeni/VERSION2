from __future__ import annotations
from pathlib import Path
from app.core.models import Element
from app.services.exporter import Exporter
from app.reports.report_utils import make_writable

def make_element(name: str, selected: bool=True, visible: bool=True) -> Element:
    return Element(release="REL1", project="ABC", element=name, type="OCOB", selected=selected, visible=visible, source_row={"Element":name,"Type":"OCOB","Project":"ABC","DSN ID":"DSN1","Release":"REL1","Subsys":"SUB1","System":"SYSTEM99","Act Rgn":"DV","Application":"APP"})

def test_exporter_sorts_element_name_only() -> None:
    """Verifies exporter sorts element name only."""
    assert [e.element for e in Exporter({}, Path('.')).sort_elements([make_element('ZZZ'), make_element('AAA')])] == ['AAA','ZZZ']

def test_build_lines_excludes_hidden_and_unselected() -> None:
    """Verifies build lines excludes hidden and unselected."""
    lines=Exporter({}, Path('.')).build_lines([make_element('AAA'), make_element('BBB', selected=False), make_element('CCC', visible=False)], 'PROD')
    assert len(lines)==1
    assert lines[0][0:8].strip() == 'AAA'

def test_export_writes_file(tmp_path: Path) -> None:
    """Verifies export writes file."""
    output_path=tmp_path/'out.txt'
    result=Exporter({}, tmp_path).export([make_element('AAA')], 'PROD', 'REL1', output_path)
    assert result == output_path
    assert output_path.exists()
    assert output_path.read_text(encoding='utf-8')
    make_writable(output_path)

def test_export_default_path_uses_settings_output_folder(tmp_path: Path) -> None:
    """Verifies export default path uses settings output folder."""
    result = Exporter({"files": {"default_output_folder": "Reports"}}, tmp_path).export([make_element('AAA')], 'PROD', 'REL1')
    assert result.parent.parent.name == 'REL1'
    assert result.parent.parent.parent == tmp_path / 'Reports'
    assert result.name.startswith('REL1_export_')
    make_writable(result)
