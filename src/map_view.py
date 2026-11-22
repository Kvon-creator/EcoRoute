"""Readable route maps with distinct shared sections and labeled endpoints."""
import pydeck as pdk
from src.dashboard import route_paths
from src.routing import RouteResult

SHORTEST = [234, 88, 12]
FUEL = [109, 40, 217]
SHARED = [13, 148, 136]



def road_context_layers(graph, style='road', line_opacity=0.65):
    """Draw actual saved roads above the pale basemap, below route highlights."""
    edges = tuple(graph.edges(keys=True))
    paths = route_paths(graph, RouteResult(nodes=(), edges=edges, distance_m=0, fuel_liters=0))
    roads = []
    representatives = {}
    for edge, path in zip(edges, paths):
        attrs = graph[edge[0]][edge[1]][edge[2]]
        names = attrs.get('name', 'Unnamed road')
        name = ' / '.join(names) if isinstance(names, list) else str(names)
        roads.append(dict(path=path, route='Road: ' + name))
        length = float(attrs['length'])
        if name != 'Unnamed road' and (name not in representatives or length > representatives[name]['priority']):
            geometry = attrs.get('geometry')
            if geometry is not None and geometry.geom_type == 'LineString':
                middle = geometry.interpolate(0.5, normalized=True)
                position = [float(middle.x), float(middle.y)]
            else:
                position = [(path[0][0]+path[-1][0])/2, (path[0][1]+path[-1][1])/2]
            representatives[name] = dict(position=position, name=name, priority=length)
    dark = style == 'dark'
    outline = [15,23,42,255] if dark else [255,255,255,255]
    road_color = [203,213,225,240] if dark else [100,116,139,235]
    border = pdk.Layer('PathLayer', roads, id='road-borders', get_path='path', opacity=line_opacity,
                       get_color=outline, get_width=5, width_units=pdk.types.String('pixels'),
                       width_min_pixels=5, width_max_pixels=5)
    fill = pdk.Layer('PathLayer', roads, id='visible-roads', get_path='path', opacity=line_opacity,
                     get_color=road_color, get_width=3, width_units=pdk.types.String('pixels'),
                     width_min_pixels=3, width_max_pixels=3, pickable=True)
    labels = pdk.Layer('TextLayer', list(representatives.values()), id='road-names',
                       get_position='position', get_text='name', get_size=13,
                       get_color=[248,250,252] if dark else [15,23,42],
                       font_weight='bold', font_settings={'sdf': True}, outline_width=3,
                       outline_color=[15,23,42,255] if dark else [255,255,255,255],
                       get_pixel_offset=[0,-10],
                       extensions=[{'@@type':'CollisionFilterExtension'}],
                       collision_enabled=True, get_collision_priority='priority')
    return [border,fill,labels]


def endpoint_layers(graph, origin=None, destination=None):
    markers = [dict(position=[float(graph.nodes[n]['x']),float(graph.nodes[n]['y'])],
                    route=label, text=text, color=color)
               for n,label,text,color in ((origin,'A - Start','A',[22,130,60]),(destination,'B - Finish','B',[190,24,60])) if n is not None]
    pins = pdk.Layer('ScatterplotLayer', markers, id='endpoints', get_position='position',
                     get_fill_color='color', get_radius=12, radius_units=pdk.types.String('pixels'),
                     stroked=True, get_line_color=[255,255,255], get_line_width=2,
                     line_width_units=pdk.types.String('pixels'), pickable=True)
    letters = pdk.Layer('TextLayer', markers, id='endpoint-letters', get_position='position', get_text='text',
                        get_size=15, get_color=[255,255,255], get_text_anchor=pdk.types.String('middle'),
                        get_alignment_baseline=pdk.types.String('center'), pickable=True)
    return markers, pins, letters


def fitted_view(coords):
    xs, ys = [p[0] for p in coords], [p[1] for p in coords]
    if max(xs)-min(xs) < 1e-9 and max(ys)-min(ys) < 1e-9:
        return pdk.ViewState(longitude=xs[0],latitude=ys[0],zoom=15)
    view = pdk.data_utils.compute_view(coords,view_proportion=1)
    view.longitude, view.latitude = (min(xs)+max(xs))/2, (min(ys)+max(ys))/2
    view.zoom = min(view.zoom,15)
    return view


def overview_deck(graph, origin=None, destination=None, style='road', line_opacity=0.65):
    markers,pins,letters = endpoint_layers(graph,origin,destination)
    coords = [[float(d['x']),float(d['y'])] for _,d in graph.nodes(data=True)]
    layers = road_context_layers(graph,style,line_opacity)
    if markers:
        layers += [pins,letters]
    return pdk.Deck(layers=layers,map_provider='carto',map_style=style,
        initial_view_state=fitted_view(coords),tooltip={'text':'{route}'})


def route_deck(graph, comparison, origin, destination, style='road', line_opacity=0.65, show_routes='both'):
    shortest, fuel = comparison.shortest, comparison.lowest_fuel
    common = set(shortest.edges) & set(fuel.edges) if show_routes == 'both' else set()
    segments = []
    selected = ((shortest,SHORTEST,'Shortest route'),) if show_routes == 'shortest' else ((fuel,FUEL,'Lower-fuel route'),) if show_routes == 'fuel' else ((shortest,SHORTEST,'Shortest route'),(fuel,FUEL,'Lower-fuel route'))
    for route, color, label in selected:
        for edge, path in zip(route.edges, route_paths(graph, route)):
            if edge not in common:
                segments.append(dict(path=path, color=color, route=label))
    for edge in shortest.edges:
        if edge in common:
            one = RouteResult(nodes=(), edges=(edge,), distance_m=0, fuel_liters=0)
            segments.append(dict(path=route_paths(graph, one)[0], color=SHARED, route='Shared by both routes'))
    # White casing separates colored routes from the road background.
    casing = pdk.Layer('PathLayer', segments, id='route-outline', get_path='path', opacity=line_opacity,
                       get_color=[255,255,255,245], get_width=9,
                       width_units=pdk.types.String('pixels'), width_min_pixels=9, width_max_pixels=9)
    routes = pdk.Layer('PathLayer', segments, id='route-colors', get_path='path', opacity=line_opacity, get_color='color',
                       get_width=5, width_units=pdk.types.String('pixels'),
                       width_min_pixels=5, width_max_pixels=5, pickable=True)
    markers,pins,letters = endpoint_layers(graph,origin,destination)
    coords = [point for path in route_paths(graph,shortest)+route_paths(graph,fuel) for point in path] + [m['position'] for m in markers]
    view = fitted_view(coords)
    road_border, road_fill, road_names = road_context_layers(graph, style, line_opacity)
    return pdk.Deck(layers=[road_border,road_fill,casing,routes,road_names,pins,letters], map_provider='carto',map_style=style,
                    initial_view_state=view, tooltip={'text':'{route}'})


def grade_color(grade):
    value = abs(float(grade))
    return [14,116,144] if value < .05 else [217,119,6] if value < .10 else [147,51,234]
