import pytest
import networkx as nx
from src.routing import compare_routes
from src.planner_presentation import elevation_profile


def test_profile_uses_exact_edge_lengths_and_endpoint_elevations():
    g=nx.MultiDiGraph()
    g.add_node(1,elevation=600)
    g.add_node(2,elevation=620)
    g.add_node(3,elevation=610)
    g.add_edge(1,2,key=0,length=100,fuel_liters=.1)
    g.add_edge(2,3,key=0,length=200,fuel_liters=.1)
    rows=elevation_profile(g,compare_routes(g,1,3).shortest,'Shortest')
    assert [r['Distance (km)'] for r in rows]==pytest.approx([0,.1,.3])
    assert [r['Elevation (m)'] for r in rows]==[600,620,610]
    del g.nodes[2]['elevation']
    assert elevation_profile(g,compare_routes(g,1,3).shortest,'Shortest')==[]
