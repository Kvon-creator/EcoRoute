"""EcoRoute dashboard: local data review and prepared-route comparison."""

import json
from pathlib import Path

import networkx as nx
import pandas as pd
import pydeck as pdk
import streamlit as st

from src.dashboard import (
    comparison_rows, file_digest, load_prepared_graph, load_gis_preview, read_preview, route_paths, load_evaluation_summary,
)
from src.locations import location_labels, snap_coordinate
from src.geocoding import search_address, normalize_address, AddressLookupError
from src.map_view import route_deck, grade_color
from src.fuel_costs import directly_simulated_graph
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
    for feature in features["features"]:
        feature["properties"]["color"] = grade_color(feature["properties"]["grade_percent"] / 100)
    st.caption("Road slopes: teal below 5%, amber 5-10%, purple 10% or steeper.")
    st.pydeck_chart(pdk.Deck(
        layers=[pdk.Layer("GeoJsonLayer", data=features, stroked=True, filled=False,
                          get_line_color="properties.color", get_line_width=3,
                          line_width_units=pdk.types.String("pixels"),
                          line_width_min_pixels=1, line_width_max_pixels=4,
                          pickable=True)],
        map_provider="carto", map_style="road",
        initial_view_state=pdk.ViewState(latitude=FAIRVIEW_CENTER[0], longitude=FAIRVIEW_CENTER[1], zoom=12),
        tooltip={"text": "Length: {length} m\nSigned grade: {grade_percent}%"},
    ), key="fairview-gis-map", alt="Fairview driving network with road lengths and signed slopes")
    st.caption("Roads: OpenStreetMap contributors. Elevations: USGS. Hover over a road for length and slope; map tiles require internet.")


@st.cache_data
def cached_preview(path: str, size: int, modified_ns: int):
    return read_preview(Path(path))



@st.cache_resource(max_entries=4)
def cached_direct_graph(path: str, metadata_path: str, graph_hash: str, metadata_hash: str):
    graph, _ = load_prepared_graph(Path(path), Path(metadata_path))
    return directly_simulated_graph(graph)



def address_locations(graph):
    st.caption("Enter numbered street addresses. Search sends them to the U.S. Census geocoder; internet is required. Locations are approximate, not verified building entrances.")
    with st.form("address_search"):
        first, second = st.columns(2)
        start = first.text_input("Starting address", placeholder="1 Taylor Road, Fairview, NC 28730", key="address_start")
        end = second.text_input("Ending address", placeholder="Number, street, city, state or ZIP", key="address_end")
        submitted = st.form_submit_button("Find addresses", icon=":material/search:")
    if submitted:
        st.session_state.pop("address_matches", None)
        st.session_state.pop("address_origin", None)
        st.session_state.pop("address_destination", None)
        try:
            # Validate both fields before making either network request.
            normalize_address(start)
            normalize_address(end)
            with st.spinner("Finding address matches..."):
                matches = (search_address(start), search_address(end))
            st.session_state["address_matches"] = matches
            st.session_state["address_queries"] = (start,end)
        except AddressLookupError as exc:
            st.error(str(exc))
            return None
    matches = st.session_state.get("address_matches")
    if matches is None:
        st.info("Enter the starting and ending addresses, then choose Find addresses.")
        return None
    if not matches[0] or not matches[1]:
        missing = "starting" if not matches[0] else "ending"
        st.warning(f"No match for the {missing} address. Check the building number, street, city and ZIP code. Business names alone are not supported.")
        return None
    first, second = st.columns(2)
    a = first.selectbox("Confirm starting address", range(len(matches[0])), index=None,
                        format_func=lambda i: matches[0][i].label, key="address_origin")
    b = second.selectbox("Confirm ending address", range(len(matches[1])), index=None,
                         format_func=lambda i: matches[1][i].label, key="address_destination")
    st.caption("Address matches: U.S. Census Bureau, MAF/TIGER address ranges. Confirm both matches before calculating.")
    if a is None or b is None:
        return None
    try:
        start_match, end_match = matches[0][a], matches[1][b]
        origin, gap1 = snap_coordinate(graph, start_match.latitude, start_match.longitude)
        destination, gap2 = snap_coordinate(graph, end_match.latitude, end_match.longitude)
    except ValueError as exc:
        st.error(f"This address cannot connect to the saved Fairview network: {exc}")
        return None
    st.caption(f"A: {start_match.label} | B: {end_match.label}. Connected to saved road points {gap1:.0f} m and {gap2:.0f} m away. These connections are not included in the distance or fuel totals.")
    return origin,destination


def render_comparison(graph, metadata):
    st.caption(
        f"Saved ML model: {metadata['model_id']} | Vehicle: {metadata['vehicle_profile']} | "
        f"Source: {metadata['prediction_source']}. Costs were prepared offline."
    )
    if metadata["prediction_source"] == "simulation-trained":
        st.warning("These predictions come from a simulation-trained model.")
    nodes = list(graph.nodes)
    labels = location_labels(graph)
    mode = st.segmented_control("Choose locations using", ["Addresses", "Road names", "Coordinates"],
                                default="Road names", key="location_mode") or "Road names"
    if mode == "Addresses":
        locations = address_locations(graph)
        if locations is None:
            return
        origin, destination = locations
    elif mode == "Coordinates":
        first, second = st.columns(2)
        lat1 = first.number_input("Starting latitude", min_value=-90.0, max_value=90.0,
                                  value=float(graph.nodes[nodes[0]]["y"]), format="%.6f", key="start_lat")
        lon1 = first.number_input("Starting longitude", min_value=-180.0, max_value=180.0,
                                  value=float(graph.nodes[nodes[0]]["x"]), format="%.6f", key="start_lon")
        lat2 = second.number_input("Ending latitude", min_value=-90.0, max_value=90.0,
                                   value=float(graph.nodes[nodes[min(1,len(nodes)-1)]]["y"]), format="%.6f", key="end_lat")
        lon2 = second.number_input("Ending longitude", min_value=-180.0, max_value=180.0,
                                   value=float(graph.nodes[nodes[min(1,len(nodes)-1)]]["x"]), format="%.6f", key="end_lon")
        st.caption("Coordinates connect to the nearest saved road point, within 300 m. Travel between your entered point and that road point is not included.")
        try:
            origin, gap1 = snap_coordinate(graph, lat1, lon1)
            destination, gap2 = snap_coordinate(graph, lat2, lon2)
        except ValueError as exc:
            st.error(str(exc))
            return
        st.caption(f"Start: {labels[origin]} ({gap1:.0f} m away). End: {labels[destination]} ({gap2:.0f} m away).")
    else:
        origin = st.selectbox("Starting road location", nodes, key="origin", format_func=labels.get)
        destination = st.selectbox("Ending road location", nodes, index=min(1, len(nodes)-1), key="destination", format_func=labels.get)
        st.caption("Type a road name to search. Coordinates distinguish different points on the same road.")
    method = "Saved ML predictions"
    if metadata["prediction_source"] == "simulation-trained" and all("grade" in d for _, _, d in graph.edges(data=True)):
        method = st.segmented_control("Fuel calculation", ["Direct simulation", "Saved ML predictions"],
                                      default="Direct simulation", key="fuel_method") or "Direct simulation"
        st.caption("Direct simulation is recommended for this proof of concept: it avoids approximation errors and was faster in our CP3 comparison. Both options use assumed vehicle settings, not real fuel measurements.")
        if method == "Direct simulation":
            try:
                graph = cached_direct_graph(str(GRAPH), str(METADATA), file_digest(GRAPH), file_digest(METADATA))
            except (ValueError, TypeError, KeyError) as exc:
                st.error(f"Direct simulation unavailable: {exc}")
                return
        st.caption(f"Displayed fuel estimates use: {method}.")
    request_key = (origin, destination, method, metadata["graph_sha256"], metadata["model_id"])
    if st.button("Calculate routes", type="primary"):
        st.session_state["route_request"] = request_key
    if st.session_state.get("route_request") != request_key:
        st.info("Select endpoints, then calculate to compare predicted route costs.")
        return
    try:
        result = compare_routes(graph, origin, destination)
        rows = comparison_rows(result)
    except nx.NetworkXNoPath:
        st.error("No driving route connects these nodes in this direction. Choose another pair.")
        return
    except (ValueError, TypeError, nx.NodeNotFound) as exc:
        st.error(f"Route comparison unavailable: {exc}")
        return
    st.markdown(":orange-badge[Shortest route] :violet-badge[Lower-fuel route] :green-badge[Shared sections]  **A** Start / **B** Finish")
    st.caption("Orange follows the shortest route, purple the lower-fuel route, and teal marks sections used by both.")
    style = st.segmented_control("Map background", ["Color streets", "Dark contrast"], default="Color streets", key="map_background")
    st.pydeck_chart(route_deck(graph, result, origin, destination,
                             style="dark" if style == "Dark contrast" else "road"),
                    key="route-map", height=550,
                    alt="Street map with orange shortest-route sections, purple lower-fuel sections, teal shared sections, and A/B endpoints")
    st.caption("Roads: OpenStreetMap contributors. Basemap: CARTO. Map fits both routes; tiles require internet. Markers show the connected road points, not building entrances.")
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



def render_evaluation():
    folder = ROOT / "data/processed/cp3"
    report = folder / "summary.json"
    if not report.is_file():
        st.info("CP3 evaluation has not been generated in this checkout. Run python -m scripts.evaluate_cp3.")
        return
    try:
        try:
            summary = load_evaluation_summary(folder, GRAPH, METADATA)
        except (OSError, ValueError, KeyError) as exc:
            st.warning(f"Saved evaluation needs attention: {exc}")
            return
        st.subheader("What we tested")
        counts = summary["counts"]
        st.write(f"Checkpoint 2 used {counts['cp2_training_cases']:,} training cases, {counts['cp2_heldout_prediction_cases']:,} held-out prediction cases, and {counts['cp2_route_pairs']} route pairs. CP3 evaluates {counts['cp3_total_route_pairs']} route pairs in {counts['sensitivity_scenarios']} assumption combinations.")
        st.warning("All fuel results are simulated. Agreement with the simulator does not establish real vehicle accuracy.")
        st.write("All route choices are scored using the same direct calculation. Regret means extra simulated fuel above the route chosen directly by the simulator.")
        methods = {"constant_mean": "One average estimate", "linear_log": "Simple linear model",
                   "random_forest_log": "Random forest", "existing_hgb": "Saved ML model",
                   "direct_simulator": "Direct simulation"}
        nominal = summary["nominal_routes"]["existing_hgb"]
        totals = st.columns(3)
        totals[0].metric("Test trips", str(nominal["pairs"]))
        totals[1].metric("Direct routes different from shortest", str(nominal["successful"] - nominal["direct_matches_shortest"]))
        totals[2].metric("Average direct simulated savings", f"{nominal['mean_direct_savings_percent']:.2f}%")
        st.caption("These CP3 trip results use direct simulation to score every route, including those chosen by ML. They use a larger sample than Checkpoint 2.")
        model_frame = pd.read_csv(folder / "model_comparison.csv")
        model_frame["method"] = model_frame["method"].replace(methods)
        model_frame = model_frame.rename(columns={"method": "Method", "rmse_liters_per_km": "Prediction error (RMSE, L/km)",
            "mae_liters_per_km": "Average absolute error (L/km)", "median_prediction_ms_1652_edges": "Time for road estimates (ms)",
            "validation_rmse_liters_per_km": "Model-selection error (L/km)", "selected_ml_on_validation": "Selected ML candidate"})
        st.dataframe(model_frame, hide_index=True, alt="Alternative model accuracy and prediction time compared with direct simulation")
        st.caption("Validation chooses the ML candidate. Separate test cases measure its error. Timings are machine-specific median warm batch times; no training or model-loading time included.")
        routing_frame = pd.DataFrame([{"Method": methods.get(k,k), "Trips": v["pairs"],
            "Matches direct route": v["learned_matches_direct"], "Average simulated savings (%)": v["mean_learned_savings_percent"],
            "Average extra fuel vs direct (%)": v["mean_learned_regret_percent"], "Worse than shortest": v["learned_worse_than_shortest"]}
            for k,v in summary["nominal_routes"].items()])
        st.dataframe(routing_frame, hide_index=True, alt="Routing decisions scored by direct simulation for each model")
        st.subheader("Changing assumptions")
        st.write("The direct calculation chooses new routes for each weight, speed, and efficiency setting. We also score the original saved ML routes under those new conditions; that model has not learned weight or efficiency changes.")
        st.dataframe(pd.read_csv(folder / "sensitivity_summary.csv"), hide_index=True,
                     alt="Sensitivity results for 27 weight, speed and efficiency combinations")
        with st.expander("The two different Checkpoint 2 trips"):
            st.dataframe(pd.read_csv(folder / "cp2_different_route_profiles.csv"), hide_index=True,
                         alt="Distance, climb, slope and simulator fuel for the two original trips")
        st.download_button("Download all sensitivity route results", (folder / "sensitivity_routes.csv").read_bytes(),
                           file_name="cp3_sensitivity_routes.csv", mime="text/csv")
    except (OSError, ValueError, KeyError) as exc:
        st.error(f"Could not read saved CP3 evaluation: {exc}")


st.set_page_config(page_title="EcoRoute", layout="wide")
st.title("EcoRoute")
st.caption(f"Study area: {STUDY_AREA_LABEL}")
st.write("Compare shortest-distance and predicted lowest-fuel driving routes.")
routes_tab, data_tab, evaluation_tab = st.tabs(["Route comparison", "Current data", "Evaluation evidence"])
with routes_tab:
    render_routes()
with data_tab:
    render_data()

with evaluation_tab:
    render_evaluation()
