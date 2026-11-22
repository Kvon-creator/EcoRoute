"""CP3 helpers: all route choices are scored by the same direct simulator."""
from math import fsum, isfinite
import networkx as nx
import numpy as np


def routing_index(graph, costs):
    """Collapse parallel edges by objective, retaining exact original IDs."""
    result = nx.DiGraph()
    result.add_nodes_from(graph)
    for edge, cost in costs.items():
        if not isfinite(float(cost)) or cost < 0:
            raise ValueError('Route costs must be finite and nonnegative.')
        u, v, _ = edge
        if not result.has_edge(u, v) or cost < result[u][v]['weight']:
            result.add_edge(u, v, weight=float(cost), edge_id=edge)
    return result


def select_paths(index, pairs):
    """Reuse each source's Dijkstra search; retain failures as None."""
    cached = {}
    routes = []
    for u, v in pairs:
        if u not in index or v not in index:
            routes.append(None)
            continue
        if u not in cached:
            cached[u] = nx.single_source_dijkstra_path(index, u, weight='weight')
        path = cached[u].get(v)
        routes.append(None if path is None else tuple(index[a][b]['edge_id'] for a,b in zip(path,path[1:])))
    return routes


def route_cost(path, costs):
    return None if path is None else fsum(costs[edge] for edge in path)


def decision_metrics(shortest, direct, learned, costs):
    """Regret is excess simulator fuel over its own optimal route, in percent."""
    a, b, c = (route_cost(path, costs) for path in (shortest,direct,learned))
    if any(x is None for x in (a,b,c)):
        return dict(status='error', error='No route for one or more objectives')
    return dict(status='ok', error='', shortest_simulator_liters=a,
                direct_simulator_liters=b, learned_simulator_liters=c,
                direct_savings_percent=(a-b)/a*100 if a else None,
                learned_savings_percent=(a-c)/a*100 if a else None,
                learned_regret_percent=(c-b)/b*100 if b else None,
                learned_matches_direct=learned==direct,
                direct_matches_shortest=direct==shortest,
                learned_matches_shortest=learned==shortest)


def route_characteristics(graph, path):
    if path is None:
        return {}
    attrs=[graph[u][v][k] for u,v,k in path]
    length=fsum(float(d['length']) for d in attrs)
    return dict(distance_km=length/1000,
                ascent_m=fsum(max(0,float(d['grade']))*float(d['length']) for d in attrs),
                descent_m=fsum(max(0,-float(d['grade']))*float(d['length']) for d in attrs),
                max_absolute_grade=max((abs(float(d['grade'])) for d in attrs),default=0),
                steep_distance_fraction=fsum(float(d['length']) for d in attrs if abs(float(d['grade']))>=0.10)/length if length else 0,
                mean_speed_kph=fsum(float(d['length'])*float(d.get('speed_kph',30)) for d in attrs)/length if length else 0)


def summarize_decisions(rows):
    ok=[r for r in rows if r['status']=='ok']
    result=dict(pairs=len(rows), successful=len(ok), failed=len(rows)-len(ok))
    for key in ('direct_savings_percent','learned_savings_percent','learned_regret_percent'):
        values=[r[key] for r in ok if r.get(key) is not None]
        result['mean_'+key]=float(np.mean(values)) if values else None
        result['max_'+key]=float(max(values)) if values else None
    for key in ('learned_matches_direct','direct_matches_shortest','learned_matches_shortest'):
        result[key]=sum(r[key] for r in ok)
    result['learned_worse_than_shortest']=sum(r['learned_savings_percent'] < -1e-8 for r in ok if r['learned_savings_percent'] is not None)
    result['direct_savings_at_least_1_percent']=sum(r['direct_savings_percent'] >= 1 for r in ok if r['direct_savings_percent'] is not None)
    return result
