"""Behavioral checks for the address-first comparison flow."""
import json
from streamlit.testing.v1 import AppTest
from test_dashboard import prepared, copy_app


def calculate(app):
    next(b for b in app.button if b.label=='Calculate routes').click().run()
    assert not app.exception
    return app


def test_initial_map_and_address_first_without_network(prepared,monkeypatch):
    def unexpected(*args):
        raise AssertionError('Geocoding must wait for a submitted search')
    monkeypatch.setattr('src.geocoding.search_address',unexpected)
    _,path,_=prepared
    app=AppTest.from_file(str(copy_app(path.parents[2]))).run(timeout=30)
    assert not app.exception
    assert app.segmented_control(key='location_mode').value=='Addresses'
    assert len(app.get('deck_gl_json_chart'))==1
    assert next(b for b in app.button if b.label=='Calculate routes').disabled
    assert not app.metric


def test_visibility_fit_and_location_changes_keep_correct_results(prepared):
    _,path,_=prepared
    app=AppTest.from_file(str(copy_app(path.parents[2]))).run(timeout=30)
    app.segmented_control(key='location_mode').set_value('Road names').run()
    calculate(app)
    assert any('60.0% less simulated fuel for an extra 60 metres' in v.value for v in list(app.markdown)+list(app.success))
    assert sum('Fuel estimates are simulated, not measured.' in v.value for v in app.warning)==1
    app.segmented_control(key='route_visibility').set_value('Shortest only').run()
    spec=json.loads(app.get('deck_gl_json_chart')[0].proto.json)
    data=next(l['data'] for l in spec['layers'] if l['id']=='route-colors')
    assert {d['route'] for d in data}=={'Shortest route'}
    before=app.get('deck_gl_json_chart')[0].proto.id
    next(b for b in app.button if b.label=='Fit both routes').click().run()
    assert app.session_state['map_fit_epoch']==1
    assert app.get('deck_gl_json_chart')[0].proto.id!=before
    assert app.metric[0].value=='0.3000 L'
    app.segmented_control(key='route_visibility').set_value('Lower fuel only').run()
    spec=json.loads(app.get('deck_gl_json_chart')[0].proto.json)
    data=next(l['data'] for l in spec['layers'] if l['id']=='route-colors')
    assert {d['route'] for d in data}=={'Lower-fuel route'}
    app.selectbox(key='destination').select(3).run()
    assert not app.metric
    spec=json.loads(app.get('deck_gl_json_chart')[0].proto.json)
    assert not any(l['id']=='route-colors' for l in spec['layers'])


def test_one_confirmed_address_previews_one_marker(prepared,monkeypatch):
    from src.geocoding import AddressMatch
    monkeypatch.setattr('src.geocoding.search_address',lambda q:(AddressMatch(q,35.59,-82.55 if q.startswith('1 ') else -82.54),))
    _,path,_=prepared
    app=AppTest.from_file(str(copy_app(path.parents[2]))).run(timeout=30)
    app.text_input(key='address_start').set_value('1 Test Road, Fairview, NC')
    app.text_input(key='address_end').set_value('2 Test Road, Fairview, NC')
    app.form_submit_button[0].click().run()
    app.selectbox(key='address_origin').set_value(0).run()
    assert not app.exception
    spec=json.loads(app.get('deck_gl_json_chart')[0].proto.json)
    pins=next(l['data'] for l in spec['layers'] if l['id']=='endpoints')
    assert len(pins)==1 and pins[0]['text']=='A'
    assert next(b for b in app.button if b.label=='Calculate routes').disabled


def test_workspace_switch_preserves_trip_and_results(prepared):
    _,path,_=prepared
    app=AppTest.from_file(str(copy_app(path.parents[2]))).run(timeout=30)
    app.segmented_control(key='location_mode').set_value('Road names').run()
    calculate(app)
    app.segmented_control(key='workspace').set_value('Current data').run()
    assert not app.exception
    app.segmented_control(key='workspace').set_value('Plan a route').run()
    assert not app.exception and not app.error
    assert app.selectbox(key='origin').value==1
    assert app.selectbox(key='destination').value==2
    assert app.metric[0].value=='0.3000 L'
