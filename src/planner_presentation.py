"""Visual summaries derived only from actual saved route attributes."""
from math import isfinite


def elevation_profile(graph, route, label):
    if not route.nodes:
        return []
    distance = 0.0
    rows = []
    try:
        first = float(graph.nodes[route.nodes[0]]['elevation'])
        if not isfinite(first):
            return []
        rows.append({'Distance (km)':0.0,'Elevation (m)':first,'Route':label})
        for u,v,key in route.edges:
            distance += float(graph[u][v][key]['length'])/1000
            elevation = float(graph.nodes[v]['elevation'])
            if not isfinite(elevation):
                return []
            rows.append({'Distance (km)':distance,'Elevation (m)':elevation,'Route':label})
    except (KeyError,TypeError,ValueError):
        return []
    return rows
