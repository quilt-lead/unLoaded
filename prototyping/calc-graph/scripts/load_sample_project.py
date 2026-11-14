"""Load the approved, renamed engineering sample into a running local server."""
import argparse
import json
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import uuid


def post(base, route, fields, files):
    boundary = uuid.uuid4().hex
    parts = []
    for name, value in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    for name, path in files.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{path.name}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode())
        parts.extend((path.read_bytes(), b'\r\n'))
    parts.append(f'--{boundary}--\r\n'.encode())
    request = Request(base + route, data=b''.join(parts), headers={'Content-Type': f'multipart/form-data; boundary={boundary}'})
    with urlopen(request, timeout=120) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8000')
    args = parser.parse_args()
    base = args.url.rstrip('/')
    if urlparse(base).hostname not in ('127.0.0.1', 'localhost', '::1'):
        parser.error('This loader accepts local servers only')
    sample = Path(__file__).resolve().parents[1] / 'data/sample-project'
    with urlopen(base + '/api/projects/1/state', timeout=15) as response:
        state = json.load(response)
    if state.get('model_rev') or state.get('calc_rev'):
        parser.error('Use an empty CALCGRAPH_STORE so this sample is not mixed with another project')
    model = post(base, '/api/projects/1/model', {'label': 'Sample engineering model'}, {'file': sample / 'architecture.ifc'})
    packet = post(base, '/api/review/1/etabs', {'model_revision': model['revision']},
                  {'building': sample / 'Bldg_Export.xlsx', 'results': sample / 'Design_results.xlsx'})
    print(f"Loaded IFC revision {model['revision']}: {len(packet['members'])}/{packet['result_rows']} ETABS rows linked; {len(packet['unmatched'])} unmatched.")
    print(base + '/ifc')


if __name__ == '__main__':
    main()
