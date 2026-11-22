"""Readable route maps with distinct shared sections and labeled endpoints."""
import pydeck as pdk
from src.dashboard import route_paths
from src.routing import RouteResult

SHORTEST = [234, 88, 12]
FUEL = [109, 40, 217]
SHARED = [13, 148, 136]


def route_deck(graph, comparison, origin, destination, style='road'):
    shortest, fuel = comparison.shortest, comparison.lowest_fuel
    common = set(shortest.edges) & set(fuel.edges)
    segments = []
    for route, color, label in ((shortest, SHORTEST, 'Shortest route'), (fuel, FUEL, 'Lower-fuel route')):
        for edge, path in zip(route.edges, route_paths(graph, route)):
            if edge not in common:
                segments.append(dict(path=path, color=color, route=label))
    for edge in shortest.edges:
        if edge in common:
            one = RouteResult(nodes=(), edges=(edge,), distance_m=0, fuel_liters=0)
            segments.append(dict(path=route_paths(graph, one)[0], color=SHARED, route='Shared by both routes'))
    # White casing separates colored routes from the road background.
    casing = pdk.Layer('PathLayer', segments, id='route-outline', get_path='path',
                       get_color=[255,255,255,245], get_width=9,
                       width_units=pdk.types.String('pixels'), width_min_pixels=9, width_max_pixels=9)
    routes = pdk.Layer('PathLayer', segments, id='route-colors', get_path='path', get_color='color',
                       get_width=5, width_units=pdk.types.String('pixels'),
                       width_min_pixels=5, width_max_pixels=5, pickable=True)
    markers = [dict(position=[float(graph.nodes[n]['x']),float(graph.nodes[n]['y'])],
                    route=label, text=text, color=color)
               for n,label,text,color in ((origin,'A - Start','A',[22,130,60]),(destination,'B - Finish','B',[190,24,60]))]
    pins = pdk.Layer('ScatterplotLayer', markers, id='endpoints', get_position='position',
                     get_fill_color='color', get_radius=12, radius_units=pdk.types.String('pixels'),
                     stroked=True, get_line_color=[255,255,255], get_line_width=2,
                     line_width_units=pdk.types.String('pixels'), pickable=True)
    letters = pdk.Layer('TextLayer', markers, id='endpoint-letters', get_position='position', get_text='text',
                        get_size=15, get_color=[255,255,255], get_text_anchor=pdk.types.String('middle'),
                        get_alignment_baseline=pdk.types.String('center'), pickable=True)
    coords = [point for segment in segments for point in segment['path']] + [m['position'] for m in markers]
    view = pdk.data_utils.compute_view(coords, view_proportion=0.75)
    view.zoom = min(view.zoom, 15)
    return pdk.Deck(layers=[casing,routes,pins,letters], map_provider='carto',map_style=style,
                    initial_view_state=view, tooltip={'text':'{route}'})


def grade_color(grade):
    value = abs(float(grade))
    return [14,116,144] if value < .05 else [217,119,6] if value < .10 else [147,51,234]
