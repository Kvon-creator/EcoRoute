"""EcoRoute dashboard: local data review and prepared-route comparison."""

import json
from pathlib import Path

import networkx as nx
import pandas as pd
import pydeck as pdk
import streamlit as st

from src.dashboard import (
    comparison_rows, file_digest, load_prepared_graph, load_gis_preview, read_preview, route_paths,
)
from src.routing import compare_routes
from src.study_area import DEFAULT_GRAPH_PATH, STUDY_AREA_LABEL, FAIRVIEW_CENTER
from src.road_network import DEFAULT_DEM_PATH


ROOT = Path(__file__).resolve().parent
GRAPH = ROOT / DEFAULT_GRAPH_PATH
METADATA = ROOT / "data/processed/fuel_metadata.json"
VED = ROOT / "data/VED/extracted/VED_171101_week.csv"
FLEET = ROOT / "data/NLR Delivery Truck Data/data_for_fleet_dna_delivery_trucks.csv"


@st.cache_resource
def cached_graph(graph_path: str, metadata_path: str, graph_hash: str, metadata_hash: str):
    # Content hashes invalidate the cache when either artifact changes.
    return load_prepared_graph(Path(graph_path), Path(metadata_path))


@st.cache_resource(max_entries=4)
def cached_gis_preview(graph_path: str, graph_hash: str):
    return load_gis_preview(Path(graph_path))


def render_gis_preview():
    try:
        graph, features = cached_gis_preview(str(GRAPH), file_digest(GRAPH))
    except Exception as exc:
        st.error(f"Cannot display the GIS graph: {exc}")
        return
    st.subheader("Fairview road network")
    st.caption("GIS preview: actual roads and sampled elevations. Fuel predictions are not available yet.")
    nodes, edges, elevation = st.columns(3)
    nodes.metric("Road nodes", f"{graph.number_of_nodes():,}")
    edges.metric("Directed road edges", f"{graph.number_of_edges():,}")
    heights = [float(attrs["elevation"]) for _, attrs in graph.nodes(data=True)]
    elevation.metric("Elevation range", f"{min(heights):.0f}-{max(heights):.0f} m")
    st.pydeck_chart(pdk.Deck(
        layers=[pdk.Layer("GeoJsonLayer", data=features, stroked=True, filled=False,
                          get_line_color=[35, 100, 220], get_line_width=3,
                          line_width_units=pdk.types.String("pixels"),
                          line_width_min_pixels=1, line_width_max_pixels=4,
                          pickable=True)],
        map_provider="carto", map_style="light",
        initial_view_state=pdk.ViewState(latitude=FAIRVIEW_CENTER[0], longitude=FAIRVIEW_CENTER[1], zoom=12),
        tooltip={"text": "Length: {length} m\nSigned grade: {grade_percent}%"},
    ), key="fairview-gis-map", alt="Fairview driving network with road lengths and signed slopes")
    st.caption("Roads: OpenStreetMap contributors. Elevations: USGS. Hover over a road for length and slope; map tiles require internet.")


@st.cache_data
def cached_preview(path: str, size: int, modified_ns: int):
    return read_preview(Path(path))


def render_comparison(graph, metadata):
    st.caption(
        f"Model: {metadata['model_id']} | Vehicle: {metadata['vehicle_profile']} | "
        f"Source: {metadata['prediction_source']}. Costs were prepared offline."
    )
    if metadata["prediction_source"] == "simulation-trained":
        st.warning("These predictions come from a simulation-trained model.")
    nodes = list(graph.nodes)
    origin = st.selectbox("Origin road node", nodes, key="origin")
    destination = st.selectbox("Destination road node", nodes, index=min(1, len(nodes)-1), key="destination")
    st.caption("Choose nodes from the prepared graph. Address search and coordinate snapping are pending.")
    if not st.button("Calculate routes", type="primary"):
        st.info("Select endpoints, then calculate to compare predicted route costs.")
        return
    try:
        result = compare_routes(graph, origin, destination)
        rows = comparison_rows(result)
        colors = ([35, 100, 220], [20, 160, 100])
        segments = []
        for route, row, color in zip((result.shortest, result.lowest_fuel), rows, colors):
            segments.extend({"path": path, "route": row["Route"], "color": color}
                            for path in route_paths(graph, route))
    except nx.NetworkXNoPath:
        st.error("No driving route connects these nodes in this direction. Choose another pair.")
        return
    except (ValueError, TypeError, nx.NodeNotFound) as exc:
        st.error(f"Route comparison unavailable: {exc}")
        return
    st.caption("Blue: shortest distance. Green: lowest predicted fuel. Overlapping routes may hide one color.")
    layer = pdk.Layer("PathLayer", segments, get_path="path", get_color="color",
                      get_width=5, width_units=pdk.types.String("pixels"),
                      width_min_pixels=2, width_max_pixels=5, pickable=True)
    marker = pdk.Layer(
        "ScatterplotLayer",
        [{"position": [graph.nodes[n]["x"], graph.nodes[n]["y"]], "route": label}
         for n, label in ((origin, "Origin"), (destination, "Destination"))],
        get_position="position", get_fill_color=[240, 155, 35],
        get_radius=8, radius_units=pdk.types.String("pixels"), pickable=True,
    )
    st.pydeck_chart(pdk.Deck(
        layers=[layer, marker], map_provider="carto", map_style="light",
        initial_view_state=pdk.ViewState(latitude=graph.nodes[origin]["y"],
                                        longitude=graph.nodes[origin]["x"], zoom=13),
        tooltip={"text": "{route}"},
    ))
    st.caption("Roads: OpenStreetMap contributors. Segments without stored geometry use their endpoints. Map tiles require internet.")
    first, second = st.columns(2)
    first.metric("Predicted fuel saved", f"{result.fuel_saved_liters:.4f} L")
    second.metric("Predicted savings", "N/A" if result.fuel_saved_percent is None
                  else f"{result.fuel_saved_percent:.2f}%")
    st.dataframe(pd.DataFrame(rows), hide_index=True)
    st.bar_chart(pd.DataFrame(rows), x="Route", y="Predicted fuel (L)")
    if result.shortest.edges == result.lowest_fuel.edges:
        st.info("Both objectives selected the same route. Zero predicted savings is a valid result.")
    st.caption("Predicted savings use the same model for both routes. They are not measured fuel savings.")


def render_routes():
    if not GRAPH.is_file() or not METADATA.is_file():
        if GRAPH.is_file():
            render_gis_preview()
            st.info("The Fairview graph is ready. Fuel comparison is waiting for model predictions and fuel metadata.")
        else:
            st.info("Fairview comparison is waiting for a prepared road graph with fuel predictions.")
        for path in (GRAPH, METADATA):
            st.write(f"{'Found' if path.is_file() else 'Missing'}: `{path.relative_to(ROOT).as_posix()}`")
        waiting_for = "Fuel predictions required" if GRAPH.is_file() else "Road graph required"
        st.selectbox("Origin road node", [], disabled=True, placeholder=waiting_for)
        st.selectbox("Destination road node", [], disabled=True, placeholder=waiting_for)
        st.button("Calculate routes", disabled=True)
        st.caption("No route or savings values are generated from the current source-data files.")
        return
    try:
        graph, metadata = cached_graph(str(GRAPH), str(METADATA), file_digest(GRAPH), file_digest(METADATA))
    except Exception as exc:
        # Artifact errors should leave source-data review available in the other tab.
        st.error(f"Cannot load the prepared route data: {exc}")
        return
    render_comparison(graph, metadata)


def render_data():
    st.write("Review the source files already downloaded for EcoRoute.")
    summary = ROOT / "data/VED/sample_inspection.json"
    if summary.is_file():
        try:
            audit = json.loads(summary.read_text(encoding="utf-8"))
            columns = st.columns(3)
            columns[0].metric("Rows in saved first-week audit", f"{audit['rows']:,}")
            columns[1].metric("Finite fuel-rate readings", f"{audit['finite_value_counts']['Fuel Rate[L/hr]']:,}")
            columns[2].metric("Zero fuel-rate readings", f"{audit['finite_value_counts'].get('zero_fuel_rates', 0):,}")
            st.caption("Saved inspection of the first VED week, not all downloaded weeks. Missing fuel readings are not zero.")
        except (ValueError, TypeError, KeyError) as exc:
            st.warning(f"Saved VED inspection could not be read: {exc}")
    st.warning("VED records come from Ann Arbor, Michigan. They are a training-data candidate, not Fairview measurements or predictions.")
    available = {label: path for label, path in (("VED first week", VED), ("Fleet DNA summaries", FLEET)) if path.is_file()}
    if available:
        selected = st.selectbox("Source dataset", list(available))
        path = available[selected]
        try:
            stat = path.stat()
            frame = cached_preview(str(path), stat.st_size, stat.st_mtime_ns)
            st.caption(f"First {len(frame):,} rows only: {path.relative_to(ROOT).as_posix()}. Showing up to 100 rows below.")
            st.dataframe(frame.head(100), hide_index=True)
            fuel = "Fuel Rate[L/hr]"
            if fuel in frame.columns:
                rates = pd.to_numeric(frame[fuel], errors="coerce").replace([float("inf"), -float("inf")], float("nan"))
                counts = pd.DataFrame({"Reading": ["Missing or nonfinite", "Zero", "Positive", "Negative"],
                                       "Rows": [int(rates.isna().sum()), int((rates == 0).sum()),
                                                int((rates > 0).sum()), int((rates < 0).sum())]})
                st.bar_chart(counts, x="Reading", y="Rows")
                st.caption("Counts cover this preview only. Liters/hour is a rate, not segment liters.")
            else:
                st.info("This summary CSV has no fuel-rate target or explicit latitude/longitude columns.")
        except (OSError, ValueError, pd.errors.ParserError) as exc:
            st.error(f"Could not read source data: {exc}")
    else:
        st.info("No local preview CSV is available.")
    raster = ROOT / DEFAULT_DEM_PATH
    if raster.is_file():
        with raster.open("rb") as stream:
            pointer = stream.read(100).startswith(b"version https://git-lfs.github.com/spec/v1")
        st.info("The configured elevation file is a Git LFS pointer; raster bytes are missing."
                if pointer else "The configured USGS elevation raster is present locally.")
    if GRAPH.is_file():
        st.caption("The prepared Fairview graph is available in the Route comparison tab.")
    else:
        st.caption("The saved OpenStreetMap reference is a download link, not a routable graph.")


st.set_page_config(page_title="EcoRoute", layout="wide")
st.title("EcoRoute")
st.caption(f"Study area: {STUDY_AREA_LABEL}")
st.write("Compare shortest-distance and predicted lowest-fuel driving routes.")
routes_tab, data_tab = st.tabs(["Route comparison", "Current data"])
with routes_tab:
    render_routes()
with data_tab:
    render_data()
