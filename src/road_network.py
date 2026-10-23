from pathlib import Path

import networkx as nx
import numpy as np
import osmnx as ox
import rasterio
from pyproj import Transformer


from src.study_area import FAIRVIEW_CENTER, DEFAULT_DISTANCE_METERS, DEFAULT_GRAPH_PATH

#Real USGS elevation raster for the Fairview area.
DEFAULT_DEM_PATH = Path(
    "data/USGS/raw/USGS_13_n36w083_20171114.tif"
)

def download_fairview_graph(
    center=FAIRVIEW_CENTER,
    distance_m=DEFAULT_DISTANCE_METERS,
):
    """
    Download a drivable Fairview road network from OpenStreetMap.

    Returns a directed NetworkX MultiDiGraph.
    """

    #Download drivable roads while preserving road direction.
    graph = ox.graph_from_point(
        center,
        dist=distance_m,
        dist_type="bbox",
        network_type="drive",
        simplify=True,
    )

    #EcoRoute routing expects a directed MultiDiGraph.
    if not isinstance(graph, nx.MultiDiGraph):
        raise TypeError(
            "Expected a directed NetworkX MultiDiGraph."
        )

    return graph


def add_node_elevations(
    graph,
    dem_path=DEFAULT_DEM_PATH,
):
    """
    Add USGS elevation values to each graph node.
    """

    dem_path = Path(dem_path)

    #Stop if the real elevation file is unavailable.
    if not dem_path.exists():
        raise FileNotFoundError(
            f"USGS elevation raster not found: {dem_path}"
        )

    with rasterio.open(dem_path) as dataset:

        #The raster must identify its coordinate system.
        if dataset.crs is None:
            raise ValueError(
                "Elevation raster does not contain a CRS."
            )

        #OSMnx stores coordinates in longitude/latitude.
        #Convert them to the DEM coordinate system before sampling.
        transformer = Transformer.from_crs(
            "EPSG:4326",
            dataset.crs,
            always_xy=True,
        )

        node_ids = []
        coordinates = []

        for node_id, data in graph.nodes(data=True):

            #Every road node needs longitude and latitude.
            if "x" not in data or "y" not in data:
                raise ValueError(
                    f"Node {node_id} is missing x/y coordinates."
                )

            lon = float(data["x"])
            lat = float(data["y"])
            if not (np.isfinite(lon) and np.isfinite(lat)):
                raise ValueError(f"Node {node_id} has nonfinite coordinates.")

            raster_x, raster_y = transformer.transform(
                lon,
                lat,
            )
            if not (
                dataset.bounds.left <= raster_x < dataset.bounds.right
                and dataset.bounds.bottom < raster_y <= dataset.bounds.top
            ):
                raise ValueError(f"Elevation raster does not cover node {node_id}.")

            node_ids.append(node_id)
            coordinates.append(
                (raster_x, raster_y)
            )

        #Sample the USGS raster at every road-node location.
        samples = list(
            dataset.sample(coordinates, masked=True)
        )

        elevations = {}
        for node_id, sample in zip(
            node_ids,
            samples,
        ):
            if np.ma.is_masked(sample[0]):
                raise ValueError(f"Missing elevation for node {node_id}.")
            elevation = float(sample[0])

            #Reject missing values instead of inventing elevation data.
            if (
                dataset.nodata is not None
                and np.isclose(
                    elevation,
                    dataset.nodata,
                )
            ):
                raise ValueError(
                    f"Missing elevation for node {node_id}."
                )

            if not np.isfinite(elevation):
                raise ValueError(
                    f"Invalid elevation for node {node_id}."
                )

            elevations[node_id] = elevation

        #Only mutate the graph after every sample has passed validation.
        nx.set_node_attributes(graph, elevations, "elevation")

    return graph


def add_edge_grades(graph):
    """
    Calculate signed road grade for every directed edge.
    """

    for u, v, key, data in graph.edges(
        keys=True,
        data=True,
    ):

        #Road length is required to calculate slope.
        if "length" not in data:
            raise ValueError(
                f"Edge {(u, v, key)} is missing length."
            )

        length = float(data["length"])

        #Reject invalid road lengths before calculating grade.
        if (
            not np.isfinite(length)
            or length <= 0
        ):
            raise ValueError(
                f"Edge {(u, v, key)} has invalid length."
            )

        #Both endpoints must have real elevation values.
        if "elevation" not in graph.nodes[u]:
            raise ValueError(
                f"Node {u} is missing elevation."
            )

        if "elevation" not in graph.nodes[v]:
            raise ValueError(
                f"Node {v} is missing elevation."
            )

        elevation_u = float(
            graph.nodes[u]["elevation"]
        )

        elevation_v = float(
            graph.nodes[v]["elevation"]
        )
        if not (np.isfinite(elevation_u) and np.isfinite(elevation_v)):
            raise ValueError(f"Edge {(u, v, key)} has nonfinite endpoint elevations.")

        #Positive grade means uphill; negative grade means downhill.
        grade = (
            elevation_v - elevation_u
        ) / length

        data["grade"] = float(grade)

        #Absolute grade is useful when only steepness matters.
        data["grade_abs"] = float(
            abs(grade)
        )

    return graph


def validate_graph(graph):
    """
    Check that the prepared graph contains required GIS fields.
    """

    #The routing component requires a directed MultiDiGraph.
    if not isinstance(graph, nx.MultiDiGraph):
        raise TypeError(
            "EcoRoute requires a directed MultiDiGraph."
        )

    if graph.number_of_nodes() == 0 or graph.number_of_edges() == 0:
        raise ValueError("Prepared graph must contain road nodes and edges.")

    for node_id, data in graph.nodes(
        data=True
    ):

        #Each node needs location and elevation data.
        for attribute in (
            "x",
            "y",
            "elevation",
        ):
            if attribute not in data:
                raise ValueError(
                    f"Node {node_id} missing {attribute}."
                )
            if not np.isfinite(float(data[attribute])):
                raise ValueError(f"Node {node_id} has invalid {attribute}.")

    for u, v, key, data in graph.edges(
        keys=True,
        data=True,
    ):

        #Each edge needs distance and slope information.
        for attribute in (
            "length",
            "grade",
            "grade_abs",
        ):
            if attribute not in data:
                raise ValueError(
                    f"Edge {(u, v, key)} "
                    f"missing {attribute}."
                )

        length = float(data["length"])

        if (
            not np.isfinite(length)
            or length <= 0
        ):
            raise ValueError(
                f"Invalid edge length on "
                f"{(u, v, key)}."
            )
        grade, grade_abs = float(data["grade"]), float(data["grade_abs"])
        if not (np.isfinite(grade) and np.isfinite(grade_abs)):
            raise ValueError(f"Invalid edge grade on {(u, v, key)}.")
        if not np.isclose(abs(grade), grade_abs):
            raise ValueError(f"Inconsistent signed/absolute grades on {(u, v, key)}.")

    return True


def save_graph(
    graph,
    graph_path=DEFAULT_GRAPH_PATH,
):
    """
    Save the prepared Fairview graph as GraphML.
    """

    graph_path = Path(graph_path)

    #Create the processed-data folder if it does not exist.
    graph_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    #GraphML preserves the road network for later project stages.
    ox.io.save_graphml(
        graph,
        filepath=graph_path,
    )

    return graph_path


def load_graph(
    graph_path=DEFAULT_GRAPH_PATH,
):
    """
    Load a previously prepared Fairview GraphML file.
    """

    graph_path = Path(graph_path)

    if not graph_path.exists():
        raise FileNotFoundError(
            f"Prepared graph not found: {graph_path}"
        )

    return ox.io.load_graphml(
        graph_path
    )


def build_fairview_graph(
    dem_path=DEFAULT_DEM_PATH,
    graph_path=DEFAULT_GRAPH_PATH,
    distance_m=DEFAULT_DISTANCE_METERS,
):
    """
    Run the complete EcoRoute GIS preparation pipeline.
    """

    print(
        "Downloading Fairview road network..."
    )

    graph = download_fairview_graph(
        distance_m=distance_m
    )

    print(
        f"Downloaded {graph.number_of_nodes()} nodes "
        f"and {graph.number_of_edges()} directed edges."
    )

    print(
        "Adding USGS node elevations..."
    )

    graph = add_node_elevations(
        graph,
        dem_path=dem_path,
    )

    print(
        "Calculating signed road grades..."
    )

    graph = add_edge_grades(
        graph
    )

    print(
        "Validating graph..."
    )

    validate_graph(
        graph
    )

    print(
        "Saving prepared Fairview graph..."
    )

    output_path = save_graph(
        graph,
        graph_path=graph_path,
    )

    print(
        f"Prepared Fairview graph saved to "
        f"{output_path}"
    )

    #Fuel predictions are added later by the ML component.
    return graph
