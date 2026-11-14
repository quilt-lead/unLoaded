"""Isolated synthetic checks for identifier joins, never engineering observations."""
import pytest
import ifcopenshell.guid
from calcgraph import etabs_workbooks as mod


@pytest.fixture
def tables(monkeypatch):
    guid = '00000000-0000-0000-0000-000000000001'
    model = {'Frame Assigns - Summary': [{'UniqueName': 2, 'Story': 'Roof', 'Label': 'B1'}],
             'Beam Object Connectivity': [{'Unique Name': 2, 'Story': 'Roof', 'GUID': guid, '_row': 4}]}
    results = {'Stl Frm Sum - AISC 360-10': [{'UniqueName': '2', 'Story': 'Roof', 'Label': 'B1', 'Design Type': 'Beam', 'Design Section': 'TEST', 'PMM Ratio': 0, '_row': 4}]}
    monkeypatch.setattr(mod, 'read_tables', lambda b: model if b == b'model' else results)
    elements = [{'global_id': ifcopenshell.guid.compress(guid.replace('-', '')), 'cat': 'Beam', 'profile': 'TEST', 'storey': 'Roof'}]
    return model, results, elements


def test_exact_guid_join_preserves_zero(tables):
    result = mod.build_import(b'model', b'results', tables[2])
    assert len(result['members']) == 1
    assert result['members'][0]['result']['PMM Ratio'] == 0


def test_wrong_ifc_not_linked_by_label(tables):
    tables[2][0]['global_id'] = 'unrelated'
    result = mod.build_import(b'model', b'results', tables[2])
    assert not result['members']
    assert len(result['unmatched']) == 1


def test_story_mismatch_rejected(tables):
    tables[1]['Stl Frm Sum - AISC 360-10'][0]['Story'] = 'Other'
    assert not mod.build_import(b'model', b'results', tables[2])['members']


def test_duplicate_results_rejected(tables):
    rows = tables[1]['Stl Frm Sum - AISC 360-10']
    rows.append(dict(rows[0]))
    with pytest.raises(ValueError, match='Duplicate'):
        mod.build_import(b'model', b'results', tables[2])
