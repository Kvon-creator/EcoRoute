"""User-submitted US street-address lookup, with no API key or autocomplete."""
from dataclasses import dataclass
from functools import lru_cache
import json
from math import isfinite
import re
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ENDPOINT = 'https://geocoding.geo.census.gov/geocoder/locations/onelineaddress'
_lock = threading.Lock()
_last_request = 0.0


class AddressLookupError(ValueError):
    pass


@dataclass(frozen=True)
class AddressMatch:
    label: str
    latitude: float
    longitude: float


def normalize_address(address):
    query = ' '.join(address.split())
    if len(query) > 240 or not re.match(r'^\d+[A-Za-z\-\d]*\s+\S+', query):
        raise AddressLookupError('Enter a house/building number and street, followed by the city and state or ZIP code.')
    if not re.search(r'\b(?:NC|North Carolina|\d{5})\b', query, re.IGNORECASE):
        query += ', Fairview, NC 28730'
    return query.casefold()


def parse_matches(payload):
    try:
        matches = payload['result']['addressMatches']
        if not isinstance(matches, list):
            raise TypeError
        results = []
        for match in matches[:5]:
            lat = float(match['coordinates']['y'])
            lon = float(match['coordinates']['x'])
            label = str(match['matchedAddress']).strip()
            if label and isfinite(lat) and isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180:
                item = AddressMatch(label, lat, lon)
                if item not in results:
                    results.append(item)
        return tuple(results)
    except (KeyError, TypeError, ValueError) as exc:
        raise AddressLookupError('The address service returned an unreadable response. Try again or use road names/coordinates.') from exc


@lru_cache(maxsize=256)
def _lookup(query):
    global _last_request
    params = urlencode(dict(address=query, benchmark='Public_AR_Current', format='json'))
    request = Request(ENDPOINT + '?' + params, headers={
        'User-Agent': 'EcoRoute/0.3 (+https://github.com/Kvon-creator/EcoRoute)',
        'Accept': 'application/json'})
    # Serialize across this app process; avoid repeated requests during reruns.
    with _lock:
        time.sleep(max(0, 1.05 - (time.monotonic() - _last_request)))
        _last_request = time.monotonic()
        try:
            with urlopen(request, timeout=20) as response:
                payload = json.loads(response.read())
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
            raise AddressLookupError('Address search is unavailable right now. Try again, or choose road names/coordinates.') from exc
    return parse_matches(payload)


def search_address(address):
    """Only call after an explicit search submission, never on each keystroke."""
    return _lookup(normalize_address(address))
