"""Isolated synthetic fixtures; never project data or engineering acceptance."""
import uuid
from pathlib import Path
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from calcgraph import revstore, pipeline
from calcgraph.review_api import router_for

@pytest.fixture
def review(tmp_path):
    store = revstore.open_store(str(tmp_path / 'store'))
    store.ensure_project()
    source = Path(__file__).resolve().parents[2] / 'data/synthetic'
    if not (source / 'model_rev1.ifc').exists(): pytest.skip('Generate synthetic fixture first')
    a = pipeline.ingest_model(store, 1, str(source/'model_rev1.ifc'))
    b = pipeline.ingest_model(store, 1, str(source/'model_rev2.ifc'))
    pdf = pipeline.ingest_calcs(store, 1, str(source/'calc_package.pdf'))
    common = {e['global_id'] for e in store.elements(b) if e['cat']=='Beam'}
    gid = next(e['global_id'] for e in store.elements(a) if e['global_id'] in common)
    app = FastAPI(); app.include_router(router_for(store))
    yield TestClient(app),store,a,b,pdf,gid,source
    store.db.close()

def test_replay_and_scope(review):
    client,store,a,b,pdf,gid,_ = review
    r = client.get(f'/api/review/1/snapshot?model_revision={a}')
    assert r.status_code == 200
    assert r.json()['model_rev']['id'] == a
    assert r.json()['calc_rev'] is None and r.json()['links'] == []
    assert store.project(1)['head_model_rev'] == b
    assert client.get(f'/api/review/2/snapshot?model_revision={a}').status_code == 404
    assert client.get(f'/api/review/1/diff?before={pdf}&after={b}').status_code == 404
    assert client.get(f'/api/review/1/diff?before={a}&after={b}').json()['removed']

def test_check_persistence_and_validation(review):
    client,store,a,b,pdf,gid,_ = review
    value = dict(request_id=str(uuid.uuid4()),before_revision=a,after_revision=b,member_id=gid,
                 before_span_m=10,after_span_m=12,factored_kn_m=2,source='Synthetic unit-test inputs',confirmed=True)
    first=client.post('/api/review/1/beam',json=value)
    assert first.status_code == 201, first.text
    assert first.json()['before']['moment_kn_m'] == 25
    assert first.json()['after']['moment_kn_m'] == 36
    assert first.json()['after']['reaction_kn'] == 12
    assert first.json()['after']['deflection_mm'] is None
    assert client.post('/api/review/1/beam',json=value).json() == first.json()
    assert len(client.get('/api/review/1/records').json()) == 1
    assert client.post('/api/review/1/beam',json={**value,'after_span_m':13}).status_code == 409
    assert client.post('/api/review/1/beam',json={**value,'confirmed':False}).status_code == 422
    assert client.post('/api/review/1/beam',json={**value,'service_kn_m':1}).status_code == 422
    service={**value,'request_id':str(uuid.uuid4()),'service_kn_m':1,'elastic_gpa':200,'inertia_cm4':10000}
    result=client.post('/api/review/1/beam',json=service).json()
    assert result['before']['deflection_mm'] == pytest.approx(6.5104166667)
    assert store.project(1)['head_model_rev'] == b

def test_pdf_association_and_integrity(review):
    client,store,a,b,pdf,gid,source = review
    content=(source/'calc_package.pdf').read_bytes()
    r=client.post('/api/review/1/attachments',data={'model_revision':a,'member_id':gid,'note':'Synthetic fixture evidence'},files={'file':('fixture.pdf',content,'application/pdf')})
    assert r.status_code == 201,r.text
    record=r.json();assert client.get(record['url']).content == content
    assert client.get(record['url'].replace('/1/','/2/')).status_code == 404
    assert client.post('/api/review/1/attachments',data={'model_revision':a,'note':'bad fixture'},files={'file':('bad.pdf',b'not a pdf')}).status_code == 422
    (Path(store.root)/'review'/(record['sha256']+'.pdf')).write_bytes(b'corrupted isolated fixture')
    assert client.get(record['url']).status_code == 409
