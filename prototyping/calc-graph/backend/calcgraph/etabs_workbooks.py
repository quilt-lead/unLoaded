"""Read ETABS exported XLSX tables without evaluating formulas or external links."""
import io
import posixpath
import uuid
import zipfile
from xml.etree import ElementTree as ET

import ifcopenshell.guid

NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
REL = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'


def read_tables(content):
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        if sum(i.file_size for i in z.infolist()) > 100_000_000:
            raise ValueError('Workbook uncompressed size exceeds 100 MB')
        strings = []
        if 'xl/sharedStrings.xml' in z.namelist():
            strings = [''.join(s.itertext()) for s in ET.fromstring(z.read('xl/sharedStrings.xml'))]
        rels = {r.attrib['Id']: r.attrib['Target'] for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        tables = {}
        for sheet in ET.fromstring(z.read('xl/workbook.xml')).findall('m:sheets/m:sheet', NS):
            name = sheet.attrib['name']
            if name not in {'Program Control', 'Frame Assigns - Summary', 'Stl Frm Sum - AISC 360-10',
                            'Beam Object Connectivity', 'Column Object Connectivity', 'Brace Object Connectivity'}:
                continue
            target = rels[sheet.attrib[REL]]
            path = target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/' + target)
            rows = {}
            for row in ET.fromstring(z.read(path)).findall('m:sheetData/m:row', NS):
                values = {}
                for cell in row.findall('m:c', NS):
                    col = ''.join(c for c in cell.attrib['r'] if c.isalpha())
                    kind = cell.attrib.get('t')
                    v = cell.find('m:v', NS)
                    val = v.text if v is not None else None
                    if kind == 's' and val is not None: val = strings[int(val)]
                    elif kind == 'inlineStr': val = ''.join(cell.find('m:is', NS).itertext())
                    elif val is not None and kind not in ('str', 'e'):
                        try: val = float(val); val = int(val) if val.is_integer() else val
                        except ValueError: pass
                    values[col] = val
                rows[int(row.attrib['r'])] = values
            headers = rows.get(2, {})
            tables[name] = [dict({header: values.get(col) for col, header in headers.items() if header}, _row=n)
                            for n, values in rows.items() if n >= 4 and any(v is not None for v in values.values())]
        return tables


def build_import(building, results, elements):
    model = read_tables(building)
    design = read_tables(results)
    rows = design.get('Stl Frm Sum - AISC 360-10')
    if not rows or not model.get('Frame Assigns - Summary'):
        raise ValueError('Required ETABS frame summary and steel design summary tables are missing')
    by_id = {e['global_id']: e for e in elements}
    connectivity = {}
    for name in ('Beam Object Connectivity', 'Column Object Connectivity', 'Brace Object Connectivity'):
        for row in model.get(name, []):
            key = str(row['Unique Name'])
            if key in connectivity: raise ValueError('Duplicate frame unique name in connectivity')
            connectivity[key] = (name, row)
    assignments = {}
    for row in model['Frame Assigns - Summary']:
        key = str(row['UniqueName'])
        if key in assignments: raise ValueError('Duplicate frame unique name in assignment summary')
        assignments[key] = row
    linked, unmatched, seen = [], [], set()
    for row in rows:
        key = str(row['UniqueName'])
        if key in seen: raise ValueError('Duplicate steel result unique name')
        seen.add(key)
        pair = connectivity.get(key)
        assignment = assignments.get(key)
        reason = None
        if not pair or not assignment: reason = 'Missing model connectivity or assignment'
        else:
            sheet, conn = pair
            gid = ifcopenshell.guid.compress(uuid.UUID(conn['GUID']).hex)
            element = by_id.get(gid)
            if not element: reason = 'Connectivity GUID absent from this IFC revision'
            elif str(row['Story']) != str(conn['Story']) or str(row['Story']) != str(assignment['Story']):
                reason = 'Story differs between exported tables'
            elif str(row['Label']) != str(assignment['Label']): reason = 'Label differs between exported tables'
            elif element['cat'] != row['Design Type']: reason = 'IFC and ETABS member types differ'
            if not reason:
                notes = []
                if element.get('profile') and element['profile'] != row['Design Section']:
                    notes.append('IFC profile differs from the ETABS design section')
                if element.get('storey') and element['storey'] != row['Story']:
                    notes.append('IFC storey name differs from the ETABS story')
                linked.append({'member_id': gid, 'result': row, 'assignment': assignment,
                               'connectivity_sheet': sheet, 'connectivity_row': conn['_row'],
                               'match': 'Exact IFC GlobalId / ETABS connectivity GUID, unique name, story and label',
                               'notes': notes})
        if reason: unmatched.append({'unique_name': key, 'row': row['_row'], 'reason': reason})
    return {'members': linked, 'unmatched': unmatched, 'result_rows': len(rows),
            'program': design.get('Program Control', []),
            'result_sheet': 'Stl Frm Sum - AISC 360-10'}
