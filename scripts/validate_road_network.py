from src.road_network import DEFAULT_GRAPH_PATH, load_graph, validate_graph

import networkx as nx


REVIEW_GRADE_THRESHOLD = 0.20
TOP_ROADS_TO_SHOW = 10


def is_oneway(value):
    #Handle common OSMnx one-way values.
    if isinstance(value, bool):
        return value

    if isinstance(value, (list, tuple)):
        return any(is_oneway(item) for item in value)

    return str(value).strip().lower() in {
        "true",
        "1",
        "yes",
        "y",
        "t",
    }


def get_road_name(value):
    #Keep road names readable in the terminal.
    if value is None:
        return "Unnamed road"

    if isinstance(value, list):
        return ", ".join(str(item) for item in value)

    return str(value)


def collect_edge_data(graph):
    #Collect grade and elevation information for each directed road edge.
    roads = []

    for u, v, key, data in graph.edges(keys=True, data=True):
        length = float(data["length"])
        grade = float(data["grade"])
        grade_abs = float(data["grade_abs"])

        elevation_u = float(graph.nodes[u]["elevation"])
        elevation_v = float(graph.nodes[v]["elevation"])

        roads.append(
            {
                "u": u,
                "v": v,
                "key": key,
                "name": get_road_name(data.get("name")),
                "length": length,
                "grade": grade,
                "grade_abs": grade_abs,
                "elevation_change": elevation_v - elevation_u,
            }
        )

    return roads


def main():
    print("Loading prepared Asheville road network...")

    graph = load_graph(DEFAULT_GRAPH_PATH)

    #Confirm required road-network fields are still valid.
    validate_graph(graph)

    roads = collect_edge_data(graph)

    #Check overall connectivity of the directed road network.
    weak_components = list(nx.weakly_connected_components(graph))
    strong_components = list(nx.strongly_connected_components(graph))

    largest_weak = max(
        (len(component) for component in weak_components),
        default=0,
    )

    largest_strong = max(
        (len(component) for component in strong_components),
        default=0,
    )

    #Count roads identified as one-way by OpenStreetMap.
    oneway_edges = sum(
        1
        for _, _, _, data in graph.edges(keys=True, data=True)
        if is_oneway(data.get("oneway", False))
    )

    #Find unusually steep roads that should be reviewed.
    steep_roads = [
        road
        for road in roads
        if road["grade_abs"] >= REVIEW_GRADE_THRESHOLD
    ]

    steepest_roads = sorted(
        roads,
        key=lambda road: road["grade_abs"],
        reverse=True,
    )[:TOP_ROADS_TO_SHOW]

    print()
    print("EcoRoute road-network validation")
    print("--------------------------------")
    print(f"Nodes: {graph.number_of_nodes()}")
    print(f"Directed edges: {graph.number_of_edges()}")
    print(f"Weakly connected components: {len(weak_components)}")
    print(f"Largest weak component: {largest_weak} nodes")
    print(f"Strongly connected components: {len(strong_components)}")
    print(f"Largest strong component: {largest_strong} nodes")
    print(f"OSM one-way edges: {oneway_edges}")
    print(
        "Edges at or above "
        f"{REVIEW_GRADE_THRESHOLD * 100:.0f}% absolute grade: "
        f"{len(steep_roads)}"
    )

    print()
    print("Top 10 steepest directed road edges")
    print("-----------------------------------")

    for index, road in enumerate(steepest_roads, start=1):
        direction = "uphill" if road["grade"] > 0 else "downhill"

        print(
            f"{index}. {road['name']} | "
            f"{road['grade'] * 100:.2f}% {direction} | "
            f"{road['length']:.1f} m | "
            f"elevation change {road['elevation_change']:.1f} m"
        )

    print()
    print("Validation complete.")
    print("Steep-road results are review candidates, not automatic errors.")


if __name__ == "__main__":
    main()