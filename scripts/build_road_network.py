from src.road_network import (
    DEFAULT_DEM_PATH,
    DEFAULT_GRAPH_PATH,
    build_asheville_graph,
)


def main():
    #Build the Asheville road graph using the real USGS elevation raster.
    graph = build_asheville_graph(
        dem_path=DEFAULT_DEM_PATH,
        graph_path=DEFAULT_GRAPH_PATH,
    )

    #Print a final summary for easy verification.
    print()
    print("EcoRoute road-network build complete.")
    print(f"Nodes: {graph.number_of_nodes()}")
    print(f"Edges: {graph.number_of_edges()}")
    print(f"Saved graph: {DEFAULT_GRAPH_PATH}")


if __name__ == "__main__":
    main()