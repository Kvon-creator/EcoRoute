"""Offline road labels and bounded coordinate snapping for the saved map."""
from math import isfinite
import numpy as np


def location_labels(graph):
    labels={}
    for node, attrs in graph.nodes(data=True):
        names=set()
        for _,_,d in list(graph.in_edges(node,data=True))+list(graph.out_edges(node,data=True)):
            value=d.get('name',[])
            names.update(str(v) for v in (value if isinstance(value,list) else [value]) if v)
        road=' / '.join(sorted(names)[:2]) or 'Unnamed road'
        labels[node]=f"{road} ({float(attrs['y']):.5f}, {float(attrs['x']):.5f}) [point {node}]"
    return labels


def snap_coordinate(graph, latitude, longitude, max_distance_m=300):
    """Nearest existing node, not nearest edge; reject distant/beyond-map points."""
    if not (isfinite(latitude) and isfinite(longitude) and -90<=latitude<=90 and -180<=longitude<=180):
        raise ValueError('Enter valid latitude and longitude values.')
    nodes=list(graph.nodes)
    if not nodes:
        raise ValueError('The saved road map is empty.')
    coords=np.array([[float(graph.nodes[n]['y']),float(graph.nodes[n]['x'])] for n in nodes])
    if not (coords[:,0].min()<=latitude<=coords[:,0].max() and coords[:,1].min()<=longitude<=coords[:,1].max()):
        raise ValueError('This location is outside the saved Fairview road area.')
    lat,lon=np.radians([latitude,longitude])
    arr=np.radians(coords)
    hav=np.sin((arr[:,0]-lat)/2)**2+np.cos(lat)*np.cos(arr[:,0])*np.sin((arr[:,1]-lon)/2)**2
    distances=6371008.8*2*np.arcsin(np.sqrt(np.clip(hav,0,1)))
    nearest=int(distances.argmin())
    if distances[nearest]>max_distance_m:
        raise ValueError(f'No saved road point is within {max_distance_m:.0f} m. Choose a point closer to a road junction.')
    return nodes[nearest],float(distances[nearest])
