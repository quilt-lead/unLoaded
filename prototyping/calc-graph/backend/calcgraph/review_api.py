"""Project-neutral local review history. No external database or solver required."""
import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import pymupdf
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, ConfigDict
from . import pipeline


class BeamInput(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    request_id: uuid.UUID
    before_revision: int
    after_revision: int
    member_id: str
    before_span_m: float = Field(gt=0, le=100)
    after_span_m: float = Field(gt=0, le=100)
    factored_kn_m: float = Field(gt=0, le=10000)
    service_kn_m: float | None = Field(default=None, gt=0, le=10000)
    elastic_gpa: float | None = Field(default=None, gt=0, le=1000)
    inertia_cm4: float | None = Field(default=None, gt=0, le=1e9)
    source: str = Field(min_length=3, max_length=2000)
    confirmed: bool


def beam_result(length, inputs):
    result = {'span_m': length, 'moment_kn_m': inputs.factored_kn_m * length**2 / 8,
              'reaction_kn': inputs.factored_kn_m * length / 2, 'deflection_mm': None}
    if inputs.service_kn_m is not None:
        # kN/m -> N/m, GPa -> N/m², cm⁴ -> m⁴, m -> mm.
        result['deflection_mm'] = 5 * inputs.service_kn_m * 1000 * length**4 / (384 * inputs.elastic_gpa * 1e9 * inputs.inertia_cm4 * 1e-8) * 1000
    return result


def router_for(store):
    router = APIRouter(prefix='/api/review', tags=['local review'])
    folder = Path(store.root) / 'review'

    @contextmanager
    def db():
        folder.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(folder / 'review.sqlite', timeout=20)
        try:
            with connection:
                connection.execute('CREATE TABLE IF NOT EXISTS records (id TEXT PRIMARY KEY, kind TEXT, project_id INTEGER, body TEXT)')
                yield connection
        finally:
            connection.close()

    def revision(pid, rid, kind='model'):
        try: row = store.revision(rid)
        except KeyError: raise HTTPException(404, 'Revision not found') from None
        if row['project_id'] != pid or row['kind'] != kind:
            raise HTTPException(404, 'Revision does not belong to this project or file type')
        return row

    @router.get('/{pid}/snapshot')
    def snapshot(pid: int, model_revision: int, calc_revision: int | None = None):
        revision(pid, model_revision)
        if calc_revision is not None: revision(pid, calc_revision, 'calcs')
        return pipeline.state(store, pid, model_revision, calc_revision, historical=True)

    @router.get('/{pid}/diff')
    def diff(pid: int, before: int, after: int):
        revision(pid, before); revision(pid, after)
        return store.compare_models(before, after)

    @router.get('/{pid}/records')
    def records(pid: int):
        with db() as connection:
            return [json.loads(r[0]) for r in connection.execute('SELECT body FROM records WHERE project_id=? ORDER BY rowid DESC', (pid,))]

    @router.post('/{pid}/etabs', status_code=201)
    async def import_etabs(pid: int, model_revision: int = Form(...), building: UploadFile = File(...), results: UploadFile = File(...)):
        from .etabs_workbooks import build_import
        revision(pid, model_revision)
        sources = []
        for upload in (building, results):
            content = await upload.read(20 * 1024 * 1024 + 1)
            if len(content) > 20 * 1024 * 1024: raise HTTPException(413, 'Workbook limit is 20 MB')
            sources.append((content, hashlib.sha256(content).hexdigest(), Path(upload.filename or 'export.xlsx').name))
        try:
            packet = build_import(sources[0][0], sources[1][0], store.elements(model_revision))
        except Exception as exc:
            raise HTTPException(422, 'Invalid or unsupported ETABS workbook tables: ' + type(exc).__name__) from None
        if not packet['members']: raise HTTPException(422, 'No steel result GUID matches this IFC revision')
        key = str(uuid.uuid5(uuid.NAMESPACE_URL, f'{pid}/{model_revision}/' + '/'.join(x[1] for x in sources)))
        record = dict(packet, id=key, kind='etabs_import', model_revision=model_revision,
                      created_at=datetime.now(timezone.utc).isoformat(),
                      sources=[{'name': x[2], 'sha256': x[1], 'url': f'/api/review/{pid}/etabs/{key}/source/{i}'} for i, x in enumerate(sources)])
        with db() as connection:
            prior = connection.execute('SELECT body FROM records WHERE id=?', (key,)).fetchone()
            if prior: return json.loads(prior[0])
            for content, digest, _ in sources: (folder / (digest + '.xlsx')).write_bytes(content)
            connection.execute('INSERT INTO records VALUES (?,?,?,?)', (key, 'etabs_import', pid, json.dumps(record)))
        return record

    @router.get('/{pid}/etabs/{key}/source/{index}')
    def etabs_source(pid: int, key: str, index: int):
        with db() as connection:
            row = connection.execute('SELECT body FROM records WHERE id=? AND project_id=? AND kind=?', (key, pid, 'etabs_import')).fetchone()
        if not row or index not in (0, 1): raise HTTPException(404, 'Source not found')
        source = json.loads(row[0])['sources'][index]
        path = folder / (source['sha256'] + '.xlsx')
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != source['sha256']:
            raise HTTPException(409, 'Source integrity check failed')
        return FileResponse(path, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', filename=source['name'])

    @router.post('/{pid}/beam', status_code=201)
    def calculate(pid: int, value: BeamInput):
        for rid in (value.before_revision, value.after_revision):
            revision(pid, rid)
            member = next((e for e in store.elements(rid) if e['global_id'] == value.member_id), None)
            if not member or member['cat'] != 'Beam':
                raise HTTPException(422, 'Choose a beam present in both model revisions')
        if not value.confirmed or len(value.source.strip()) < 3:
            raise HTTPException(422, 'Confirm the beam assumptions and record the input source')
        if value.service_kn_m is not None and (value.elastic_gpa is None or value.inertia_cm4 is None):
            raise HTTPException(422, 'Service deflection requires E and I from the engineer')
        inputs = value.model_dump(mode='json'); key = str(value.request_id)
        record = {'id': key, 'kind': 'beam_check', 'created_at': datetime.now(timezone.utc).isoformat(),
                  'inputs': inputs, 'member_id': value.member_id, 'model_revision': value.after_revision,
                  'engine': 'uniform-simple-beam-v1', 'engine_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  'qualification': 'Engineer-supplied effective spans; simply supported uniform load; not a model edit, global analysis or capacity check.',
                  'before': beam_result(value.before_span_m, value), 'after': beam_result(value.after_span_m, value)}
        with db() as connection:
            old = connection.execute('SELECT body FROM records WHERE id=?', (key,)).fetchone()
            if old:
                prior = json.loads(old[0])
                if prior.get('inputs') != inputs: raise HTTPException(409, 'Request ID already used with different inputs')
                return prior
            connection.execute('INSERT INTO records VALUES (?,?,?,?)', (key, 'beam_check', pid, json.dumps(record)))
        return record

    @router.post('/{pid}/attachments', status_code=201)
    async def attach(pid: int, model_revision: int = Form(...), note: str = Form(...), member_id: str = Form(''), file: UploadFile = File(...)):
        revision(pid, model_revision)
        if member_id and not any(e['global_id'] == member_id for e in store.elements(model_revision)):
            raise HTTPException(422, 'Member is not in this revision')
        if len(note.strip()) < 3: raise HTTPException(422, 'Add a source or association note')
        content = await file.read(20 * 1024 * 1024 + 1)
        if len(content) > 20 * 1024 * 1024: raise HTTPException(413, 'PDF limit is 20 MB')
        try:
            with pymupdf.open(stream=content, filetype='pdf') as document:
                if document.is_encrypted or document.page_count == 0: raise ValueError()
        except Exception: raise HTTPException(422, 'Supply a readable, unencrypted PDF') from None
        digest = hashlib.sha256(content).hexdigest(); key = str(uuid.uuid4())
        record = {'id': key, 'kind': 'attachment', 'model_revision': model_revision, 'member_id': member_id,
                  'name': Path(file.filename or 'report.pdf').name, 'note': note, 'sha256': digest,
                  'created_at': datetime.now(timezone.utc).isoformat(), 'url': f'/api/review/{pid}/attachments/{key}'}
        with db() as connection:
            (folder / (digest + '.pdf')).write_bytes(content)
            connection.execute('INSERT INTO records VALUES (?,?,?,?)', (key, 'attachment', pid, json.dumps(record)))
        return record

    @router.get('/{pid}/attachments/{key}')
    def attachment(pid: int, key: str):
        with db() as connection:
            row = connection.execute('SELECT body FROM records WHERE id=? AND project_id=? AND kind=?', (key, pid, 'attachment')).fetchone()
        if not row: raise HTTPException(404, 'Attachment not found')
        record = json.loads(row[0]); path = folder / (record['sha256'] + '.pdf')
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != record['sha256']:
            raise HTTPException(409, 'Attachment integrity check failed')
        return FileResponse(path, media_type='application/pdf', filename=record['name'])
    return router
