import json
from io import BytesIO
from urllib.error import URLError
import pytest
from src import geocoding as geo


def payload(lat=35.59, lon=-82.55):
    return {'result': {'addressMatches': [{'matchedAddress':'1 TEST ROAD, FAIRVIEW, NC',
                                          'coordinates':{'x':lon,'y':lat}}]}}


def test_numbered_address_normalization_and_empty_rejection():
    assert geo.normalize_address(' 1   Taylor Road ') == '1 taylor road, fairview, nc 28730'
    assert geo.normalize_address('1 Taylor Road, Fairview, NC 28730') == '1 taylor road, fairview, nc 28730'
    with pytest.raises(geo.AddressLookupError):
        geo.normalize_address('Fairview Library')


def test_empty_and_invalid_provider_results():
    assert geo.parse_matches({'result':{'addressMatches':[]}}) == ()
    assert geo.parse_matches(payload(float('nan'))) == ()
    with pytest.raises(geo.AddressLookupError):
        geo.parse_matches({'error':'offline'})


def test_lookup_is_cached_and_request_encodes_address(monkeypatch):
    geo._lookup.cache_clear()
    calls=[]
    def request(req, timeout):
        calls.append(req)
        return BytesIO(json.dumps(payload()).encode())
    monkeypatch.setattr(geo,'urlopen',request)
    monkeypatch.setattr(geo.time,'sleep',lambda _:None)
    one=geo.search_address('1 Test Road, Fairview, NC')
    two=geo.search_address('  1 TEST ROAD, Fairview, NC ')
    assert one == two and len(calls)==1
    assert 'benchmark=Public_AR_Current' in calls[0].full_url
    assert '+test+road' in calls[0].full_url
    geo._lookup.cache_clear()


def test_network_failure_is_actionable_and_not_cached(monkeypatch):
    geo._lookup.cache_clear()
    def fail(*args,**kwargs):
        raise URLError('offline')
    monkeypatch.setattr(geo,'urlopen',fail)
    monkeypatch.setattr(geo.time,'sleep',lambda _:None)
    with pytest.raises(geo.AddressLookupError,match='road names/coordinates'):
        geo.search_address('5 Test Road, Fairview, NC')
    assert geo._lookup.cache_info().currsize==0
