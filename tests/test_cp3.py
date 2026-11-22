import networkx as nx
import pytest
from src.cp3_evaluation import routing_index, select_paths, decision_metrics, summarize_decisions
from src.locations import snap_coordinate, location_labels
from src.fuel_costs import directly_simulated_graph


def toy():
    g=nx.MultiDiGraph()
    g.add_node(1,x=-82.40,y=35.53)
    g.add_node(2,x=-82.39,y=35.53)
    g.add_node(3,x=-82.395,y=35.535)
    g.add_edge(1,2,key=0,length=100,grade=0,highway='residential',name='Main Road',fuel_liters=999)
    g.add_edge(1,2,key=1,length=120,grade=0,highway='residential',name='Main Road',fuel_liters=999)
    g.add_edge(1,3,key=0,length=70,grade=0,highway='residential',fuel_liters=999)
    g.add_edge(3,2,key=0,length=70,grade=0,highway='residential',fuel_liters=999)
    return g


def test_regret_uses_shared_simulator_not_model_scores():
    a=((1,2,0),)
    b=((1,3,0),(3,2,0))
    actual={(1,2,0):2.0,(1,3,0):0.5,(3,2,0):0.5}
    result=decision_metrics(a,b,a,actual)
    assert result['learned_regret_percent']==100
    assert result['direct_savings_percent']==50
    assert result['learned_savings_percent']==0


def test_index_retains_parallel_edge_identity_and_failures():
    g=toy()
    index=routing_index(g,{(1,2,0):3,(1,2,1):1,(1,3,0):1,(3,2,0):1})
    paths=select_paths(index,[(1,2),(2,1),(1,1),(99,1)])
    assert paths==[((1,2,1),),None,(),None]
    failed=decision_metrics(paths[1],paths[1],paths[1],{})
    assert failed['status']=='error'


def test_negative_savings_and_zero_savings_remain_in_summary():
    a=((1,2,0),)
    b=((1,3,0),(3,2,0))
    costs={(1,2,0):1,(1,3,0):1,(3,2,0):1}
    rows=[decision_metrics(a,a,a,costs),decision_metrics(a,a,b,costs),{'status':'error'}]
    summary=summarize_decisions(rows)
    assert summary['pairs']==3
    assert summary['failed']==1
    assert summary['mean_learned_savings_percent']==-50
    assert summary['learned_worse_than_shortest']==1


def test_snap_exact_and_nearby_location():
    g=toy()
    assert snap_coordinate(g,35.53,-82.40)==(1,0)
    node,distance=snap_coordinate(g,35.5301,-82.3999)
    assert node==1 and 0<distance<20
    assert 'Main Road' in location_labels(g)[1]


@pytest.mark.parametrize('lat,lon',[(0,0),(35.53,float('nan')),(35.534,-82.3901)])
def test_outside_nonfinite_and_distant_points_are_rejected(lat,lon):
    with pytest.raises(ValueError):
        snap_coordinate(toy(),lat,lon)


def test_direct_costs_do_not_mutate_saved_ml_graph_and_scale_by_length():
    g=toy()
    result=directly_simulated_graph(g)
    assert g[1][2][0]['fuel_liters']==999
    assert result[1][2][1]['fuel_liters']/result[1][2][0]['fuel_liters']==pytest.approx(1.2)


def test_routing_cost_index_rejects_invalid_weights():
    with pytest.raises(ValueError):
        routing_index(toy(),{(1,2,0):float('nan')})
