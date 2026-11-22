"""Reproduce CP3 model, routing, sensitivity, GIS, and count evidence offline."""
import argparse
import csv
import itertools
import json
from pathlib import Path
from time import perf_counter
import sys
import platform

import joblib
import networkx as nx
import numpy as np
import sklearn
from sklearn.compose import TransformedTargetRegressor
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.simulate_fuel import PARAMETERS, SEED, simulated_rate, assumed_speed, digest, write_csv, write_json
from src.dashboard import load_prepared_graph
from src.cp3_evaluation import (routing_index, select_paths, decision_metrics,
                               route_cost, route_characteristics, summarize_decisions)


def cases(seed, n):
    rng=np.random.default_rng(seed)
    return np.column_stack([rng.uniform(15,90,n),rng.uniform(-0.25,0.25,n)])


def error_metrics(y, prediction):
    return dict(mae_liters_per_km=float(mean_absolute_error(y,prediction)),
                rmse_liters_per_km=float(np.sqrt(mean_squared_error(y,prediction))))


def timed_prediction(predict, x):
    predict(x)
    samples=[]
    for _ in range(21):
        start=perf_counter()
        predict(x)
        samples.append((perf_counter()-start)*1000)
    return float(np.median(samples))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--pairs',type=int,default=200)
    args=parser.parse_args()
    if args.pairs < 20:
        parser.error('Keep at least the original 20 CP2 pairs.')
    root=args.root.resolve()
    out=root/'data/processed/cp3'
    out.mkdir(parents=True,exist_ok=True)
    graph,metadata=load_prepared_graph(root/'data/processed/fairview.graphml',root/'data/processed/fuel_metadata.json')
    model_path=root/metadata['model_path']
    if digest(model_path)!=metadata['model_sha256']:
        raise ValueError('Model checksum does not match prepared predictions.')
    bundle=joblib.load(model_path)
    edges=sorted(graph.edges(keys=True,data=True),key=lambda e:e[:3])
    ids=[(u,v,k) for u,v,k,_ in edges]
    x=np.array([[assumed_speed(d.get('highway','unknown')),float(d['grade'])] for *_,d in edges])
    lengths=np.array([float(d['length']) for *_,d in edges])
    for *_,d in edges:
        d['speed_kph']=assumed_speed(d.get('highway','unknown'))
    # Reproduce CP2 training exactly. New selection/test examples are disjoint streams.
    train=cases(SEED,8000)
    validation=cases(2365,2000)
    test=cases(3365,2000)
    train_y=simulated_rate(train)
    alternatives={
        'constant_mean':DummyRegressor(),
        'linear_log':TransformedTargetRegressor(regressor=make_pipeline(StandardScaler(),Ridge(alpha=1.0)),func=np.log,inverse_func=np.exp),
        'random_forest_log':TransformedTargetRegressor(regressor=RandomForestRegressor(n_estimators=120,max_depth=16,min_samples_leaf=2,random_state=SEED,n_jobs=1),func=np.log,inverse_func=np.exp),
        'existing_hgb':bundle['model']}
    for name,model in alternatives.items():
        if name!='existing_hgb':
            model.fit(train,train_y)
    validation_rmse={name:error_metrics(simulated_rate(validation),model.predict(validation))['rmse_liters_per_km'] for name,model in alternatives.items()}
    selected=min(validation_rmse,key=validation_rmse.get)
    all_predictors={**{name:model.predict for name,model in alternatives.items()},'direct_simulator':simulated_rate}
    model_rows=[]
    for name,predict in all_predictors.items():
        metrics=error_metrics(simulated_rate(test),predict(test))
        model_rows.append(dict(method=name,validation_rmse_liters_per_km=validation_rmse.get(name,0.0),
            **metrics,median_prediction_ms_1652_edges=timed_prediction(predict,x),
            selected_ml_on_validation=name==selected))
    write_csv(out/'model_comparison.csv',model_rows)
    print('Model comparison complete; validation-selected ML:',selected,flush=True)
    with (root/'data/processed/simulation_evaluation_pairs.csv').open(newline='') as f:
        original=[(int(r['origin']),int(r['destination'])) for r in csv.DictReader(f)]
    if len(original)!=20 or len(set(original))!=20:
        raise ValueError('Expected the unchanged 20 unique CP2 route pairs.')
    pairs=list(original)
    rng=np.random.default_rng(20261122)
    nodes=sorted(graph.nodes)
    if args.pairs>len(nodes)*(len(nodes)-1):
        raise ValueError('Requested more unique pairs than the graph permits.')
    while len(pairs)<args.pairs:
        pair=tuple(int(v) for v in rng.choice(nodes,2,replace=False))
        if pair not in pairs:
            pairs.append(pair)
    write_csv(out/'evaluation_pairs.csv',[dict(pair_id=i,origin=u,destination=v,cohort='cp2_original' if i<20 else 'cp3_new') for i,(u,v) in enumerate(pairs)])
    paths={}
    lengths_map=dict(zip(ids,lengths))
    paths['shortest']=select_paths(routing_index(graph,lengths_map),pairs)
    nominal_costs=dict(zip(ids,simulated_rate(x)*lengths/1000))
    paths['direct_simulator']=select_paths(routing_index(graph,nominal_costs),pairs)
    nominal_rows=[]
    for name,model in alternatives.items():
        predicted=model.predict(x)*lengths/1000
        if not np.isfinite(predicted).all() or np.any(predicted<0):
            raise ValueError('Invalid model costs.')
        paths[name]=select_paths(routing_index(graph,dict(zip(ids,predicted))),pairs)
        for i,(u,v) in enumerate(pairs):
            row=dict(pair_id=i,origin=u,destination=v,cohort='cp2_original' if i<20 else 'cp3_new',method=name)
            row.update(decision_metrics(paths['shortest'][i],paths['direct_simulator'][i],paths[name][i],nominal_costs))
            for label,path in [('shortest',paths['shortest'][i]),('direct',paths['direct_simulator'][i]),('learned',paths[name][i])]:
                row.update({label+'_'+k:v for k,v in route_characteristics(graph,path).items()})
            nominal_rows.append(row)
    write_csv(out/'nominal_routes.csv',nominal_rows)
    nominal_summaries={name:summarize_decisions([r for r in nominal_rows if r['method']==name]) for name in alternatives}
    # Explicitly preserve the original dashboard decisions, not a retrained replacement.
    costs_stored={edge:float(graph[edge[0]][edge[1]][edge[2]]['fuel_liters']) for edge in ids}
    stored_paths=select_paths(routing_index(graph,costs_stored),pairs)
    if stored_paths!=paths['existing_hgb']:
        raise ValueError('Stored graph decisions differ from the loaded CP2 model.')
    cp2_rows=[r for r in nominal_rows if r['method']=='existing_hgb' and r['pair_id']<20]
    case_rows=[]
    case_json=[]
    for row in cp2_rows:
        if row['learned_matches_shortest']:
            continue
        i=row['pair_id']
        details=dict(pair_id=i,origin=row['origin'],destination=row['destination'],routes={})
        for label in ('shortest','direct_simulator','existing_hgb'):
            path=paths[label][i]
            profile=route_characteristics(graph,path)
            profile['simulator_liters']=route_cost(path,nominal_costs)
            case_rows.append(dict(pair_id=i,origin=row['origin'],destination=row['destination'],route=label,**profile))
            details['routes'][label]=dict(**profile,edge_ids=path)
        case_json.append(details)
    write_csv(out/'cp2_different_route_profiles.csv',case_rows)
    write_json(out/'cp2_different_route_details.json',case_json)
    # Full factorial: direct re-optimization under each assumption combination.
    # Frozen deployed HGB paths are stress-tested, not passed off as mass-aware.
    sensitivity=[]
    for mass,speed_factor,efficiency in itertools.product([2000,3000,4000],[0.8,1.0,1.2],[0.20,0.25,0.30]):
        sx=x.copy()
        raw_speed=x[:,0]*speed_factor
        sx[:,0]=np.clip(raw_speed,15,90)
        parameters=dict(PARAMETERS,mass_kg=mass,drivetrain_efficiency=efficiency)
        costs=dict(zip(ids,simulated_rate(sx,parameters)*lengths/1000))
        direct=select_paths(routing_index(graph,costs),pairs)
        for i,(u,v) in enumerate(pairs):
            row=dict(mass_kg=mass,speed_factor=speed_factor,efficiency=efficiency,
                     clipped_speed_edges=int(np.sum(raw_speed!=sx[:,0])),pair_id=i,origin=u,destination=v,
                     direct_route_changed_from_nominal=direct[i]!=paths['direct_simulator'][i])
            row.update(decision_metrics(paths['shortest'][i],direct[i],paths['existing_hgb'][i],costs))
            sensitivity.append(row)
        print(f'Sensitivity {mass} kg / speed {speed_factor} / efficiency {efficiency}: done',flush=True)
    write_csv(out/'sensitivity_routes.csv',sensitivity)
    scenario_summaries=[]
    for mass,speed_factor,efficiency in itertools.product([2000,3000,4000],[0.8,1.0,1.2],[0.20,0.25,0.30]):
        rows=[r for r in sensitivity if (r['mass_kg'],r['speed_factor'],r['efficiency'])==(mass,speed_factor,efficiency)]
        scenario_summaries.append(dict(mass_kg=mass,speed_factor=speed_factor,efficiency=efficiency,
            direct_route_changes=sum(r['direct_route_changed_from_nominal'] for r in rows),
            clipped_speed_edges=rows[0]['clipped_speed_edges'],**summarize_decisions(rows)))
    write_csv(out/'sensitivity_summary.csv',scenario_summaries)
    # Cohort characteristics describe associations, not causal proof.
    cohorts=[]
    existing=[r for r in nominal_rows if r['method']=='existing_hgb']
    for cohort,rows in [('same_route',[r for r in existing if r.get('learned_matches_shortest')]),
                        ('different_route',[r for r in existing if r['status']=='ok' and not r['learned_matches_shortest']])]:
        cohorts.append(dict(cohort=cohort,pairs=len(rows),**{key:float(np.mean([r[key] for r in rows])) if rows else None for key in ['shortest_distance_km','shortest_ascent_m','shortest_steep_distance_fraction','learned_savings_percent']}))
    write_csv(out/'route_cohorts.csv',cohorts)
    steep=[]
    for u,v,k,d in edges:
        if abs(float(d['grade']))>=0.15:
            steep.append(dict(u=u,v=v,key=k,name=str(d.get('name','unnamed')),length_m=float(d['length']),grade=float(d['grade']),maxspeed_tag=str(d.get('maxspeed','missing'))))
    steep.sort(key=lambda r:abs(r['grade']),reverse=True)
    write_csv(out/'steep_roads_review.csv',steep)
    gis=dict(nodes=len(graph),directed_edges=len(edges),strong_components=nx.number_strongly_connected_components(graph),
        edges_with_maxspeed_tags=sum('maxspeed' in d for *_,d in edges),
        edges_with_assumed_speed=len(edges),edges_at_least_15_percent_grade=len(steep),
        grades_match_endpoint_elevations=all(np.isclose(float(d['grade']), (float(graph.nodes[v]['elevation'])-float(graph.nodes[u]['elevation']))/float(d['length'])) for u,v,k,d in edges),
        source_gis_graph_sha256=metadata['source_gis_graph_sha256'],
        scope='Automated consistency review, not independent field validation. Posted-speed parsing, turn restrictions and steep-road plausibility still need manual review.')
    speed_rows=[]
    for u,v,k,d in edges:
        raw=d.get('maxspeed')
        if raw is not None:
            posted=float(raw.removesuffix(' mph'))*1.609344 if isinstance(raw,str) and raw.endswith(' mph') else None
            speed_rows.append(dict(u=u,v=v,key=k,road=str(d.get('name','unnamed')),source_tag=str(raw),posted_limit_kph=posted,
                assumed_speed_kph=float(d['speed_kph']),note='Posted limit is not observed driving speed; simulation assumption unchanged.'))
    if speed_rows:
        write_csv(out/'posted_speed_review.csv',speed_rows)
    gis['unparsed_posted_speed_tags']=sum(row['posted_limit_kph'] is None for row in speed_rows)
    write_json(out/'gis_review.json',gis)
    counts=dict(cp2_training_cases=8000,cp2_heldout_prediction_cases=2000,cp2_route_pairs=20,
        cp3_validation_cases=2000,cp3_new_test_cases=2000,cp3_total_route_pairs=len(pairs),cp3_new_route_pairs=len(pairs)-20,
        sensitivity_scenarios=len(scenario_summaries),sensitivity_route_comparisons=len(sensitivity),
        clarification='Different units: synthetic speed/grade examples are not route pairs. User confirmed video intended the same counts as script/report; exact video wording/timestamp not independently verified.')
    write_json(out/'evaluation_counts.json',counts)
    write_json(out/'summary.json',dict(counts=counts,selected_ml_on_validation=selected,
        model_comparison=model_rows,nominal_routes=nominal_summaries,
        cp2_original_routes=summarize_decisions(cp2_rows),gis=gis,
        graph_sha256=metadata['graph_sha256'],model_sha256=metadata['model_sha256'],
        pairs_sha256=digest(out/'evaluation_pairs.csv'),seed_new_pairs=20261122,
        python=platform.python_version(),sklearn=sklearn.__version__,numpy=np.__version__,
        protocol='All methods scored with the direct simulator. Pair set frozen independent of savings. Model selected by new validation RMSE; new test set not used for selection. Sensitivity reoptimizes direct routes and scores frozen nominal HGB deployment paths. No real-world validation.'))
    print(json.dumps(dict(selected_ml=selected,nominal=nominal_summaries,counts=counts),indent=2))


if __name__=='__main__':
    main()
