"""EcoRoute dashboard: local data review and prepared-route comparison."""
import hashlib
import json
from pathlib import Path
import networkx as nx
import altair as alt
import pandas as pd
import pydeck as pdk
import streamlit as st
from src.dashboard import (
    comparison_rows, file_digest, load_prepared_graph, load_gis_preview, read_preview, route_paths, load_evaluation_summary,
)
from src.locations import location_labels, snap_coordinate
from src.geocoding import search_address, normalize_address, AddressLookupError
from src.map_view import route_deck, overview_deck, grade_color
from src.ui_text import route_tradeoff
from src.planner_presentation import elevation_profile
from src.branding import logo_markup
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
    st.caption("Numbered street addresses in the Fairview study area.")
    with st.form("address_search"):
        start = st.text_input("Starting address", placeholder="1 Taylor Road, Fairview, NC 28730", key="address_start", persist_state="session")
        end = st.text_input("Ending address", placeholder="Number, street, city, state or ZIP", key="address_end", persist_state="session")
        submitted = st.form_submit_button("Find addresses", icon=":material/search:",width="stretch")
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
            return None, None
    matches = st.session_state.get("address_matches")
    if matches is None:
        st.info("Find both addresses, then confirm the matches.")
        return None, None
    if not matches[0] or not matches[1]:
        missing = "starting" if not matches[0] else "ending"
        st.warning(f"No match for the {missing} address. Check the building number, street, city and ZIP code. Business names alone are not supported.")
        return None, None
    a = st.selectbox("Confirm starting address", range(len(matches[0])), index=None,
                        format_func=lambda i: matches[0][i].label, key="address_origin", persist_state="session")
    b = st.selectbox("Confirm ending address", range(len(matches[1])), index=None,
                         format_func=lambda i: matches[1][i].label, key="address_destination", persist_state="session")
    st.caption("Confirm both matches. Lookup: U.S. Census Bureau; approximate locations. Addresses are sent only when you search.")
    origin = destination = None
    for choice, candidates, label in ((a,matches[0],"Start"),(b,matches[1],"Finish")):
        if choice is None:
            continue
        match = candidates[choice]
        try:
            node, gap = snap_coordinate(graph,match.latitude,match.longitude)
            st.caption(f"{label}: {match.label}. Connected to a saved road point {gap:.0f} m away; that connection is excluded from totals.")
            if label == "Start":
                origin = node
            else:
                destination = node
        except ValueError as exc:
            st.error(f"This address cannot connect to the saved Fairview network: {exc}")
    return origin,destination


def choose_locations(graph):
    nodes = list(graph.nodes)
    labels = location_labels(graph)
    if "location_mode" not in st.session_state:
        st.session_state["location_mode"] = "Addresses"
    if "origin" not in st.session_state:
        st.session_state["origin"] = nodes[0]
    if "destination" not in st.session_state:
        st.session_state["destination"] = nodes[min(1,len(nodes)-1)]
    origin = destination = None
    with st.expander("Other ways to choose locations"):
        mode = st.segmented_control("Choose locations using", ["Addresses", "Road names", "Coordinates"],
                                    key="location_mode", persist_state="session") or "Addresses"
        if mode == "Road names":
            origin = st.selectbox("Starting road location", nodes, index=None, key="origin", format_func=labels.get, persist_state="session")
            destination = st.selectbox("Ending road location", nodes, index=None, key="destination", format_func=labels.get, persist_state="session")
            st.caption("Type a road name to search. Coordinates distinguish points on the same road.")
        elif mode == "Coordinates":
            first, second = st.columns(2)
            lat1 = first.number_input("Starting latitude", min_value=-90.0, max_value=90.0,
                value=float(graph.nodes[nodes[0]]["y"]), format="%.6f", key="start_lat", persist_state="session")
            lon1 = first.number_input("Starting longitude", min_value=-180.0, max_value=180.0,
                value=float(graph.nodes[nodes[0]]["x"]), format="%.6f", key="start_lon", persist_state="session")
            lat2 = second.number_input("Ending latitude", min_value=-90.0, max_value=90.0,
                value=float(graph.nodes[nodes[min(1,len(nodes)-1)]]["y"]), format="%.6f", key="end_lat", persist_state="session")
            lon2 = second.number_input("Ending longitude", min_value=-180.0, max_value=180.0,
                value=float(graph.nodes[nodes[min(1,len(nodes)-1)]]["x"]), format="%.6f", key="end_lon", persist_state="session")
            st.caption("Connects to saved road points within 300 m. The connection distance is excluded from route totals.")
            for label, lat, lon in (("Start",lat1,lon1),("Finish",lat2,lon2)):
                try:
                    node, gap = snap_coordinate(graph,lat,lon)
                    st.caption(f"{label}: {labels[node]} ({gap:.0f} m from the entered point).")
                    if label == "Start":
                        origin = node
                    else:
                        destination = node
                except ValueError as exc:
                    st.error(str(exc))
    if mode == "Addresses":
        origin, destination = address_locations(graph)
    return origin, destination


def demo_trip():
    st.session_state["location_mode"] = "Road names"
    st.session_state["origin"] = 6596571591
    st.session_state["destination"] = 4067941648
    st.session_state["demo_requested"] = True


def render_comparison(graph, metadata):
    planner, map_area = st.columns([1,2.25],gap="large",vertical_alignment="top")
    with planner:
        with st.container(border=True):
            st.subheader("Your trip",icon=":material/directions:")
            if {6596571591,4067941648}.issubset(graph.nodes):
                st.button("Try a Fairview demo",on_click=demo_trip,icon=":material/play_arrow:",width="stretch")
            origin, destination = choose_locations(graph)
            method = "Saved ML predictions"
            with st.expander("Model and calculation details"):
                st.caption(f"Saved model: {metadata['model_id']} | Vehicle: {metadata['vehicle_profile']} | Source: {metadata['prediction_source']}")
                if metadata["prediction_source"] == "simulation-trained" and all("grade" in d for _,_,d in graph.edges(data=True)):
                    method = st.segmented_control("Fuel calculation",["Direct simulation","Saved ML predictions"],
                        default="Direct simulation",key="fuel_method", persist_state="session") or "Direct simulation"
                    st.caption("Direct simulation avoids approximation error and was faster for this formula in CP3.")
                st.json(metadata)
            ready = origin is not None and destination is not None
            request_key = (origin,destination,method,metadata["graph_sha256"],metadata["model_id"])
            if st.button("Calculate routes",type="primary",disabled=not ready,width="stretch",icon=":material/route:"):
                st.session_state["route_request"] = request_key
            if st.session_state.pop("demo_requested",False) and ready:
                st.session_state["route_request"] = request_key
    result = None
    if ready and st.session_state.get("route_request") == request_key:
        try:
            routing_graph = graph if method != "Direct simulation" else cached_direct_graph(str(GRAPH),str(METADATA),file_digest(GRAPH),file_digest(METADATA))
            result = compare_routes(routing_graph,origin,destination)
        except nx.NetworkXNoPath:
            planner.error("No driving route connects these points in this direction. Choose another pair.")
        except (ValueError,TypeError,KeyError,nx.NodeNotFound) as exc:
            planner.error(f"Route comparison unavailable: {exc}")
    with planner:
        if result is not None:
            first, second = st.columns(2)
            first.metric("Predicted fuel saved",f"{result.fuel_saved_liters:.4f} L",border=True)
            second.metric("Predicted savings","N/A" if result.fuel_saved_percent is None else f"{result.fuel_saved_percent:.2f}%",border=True)
            st.success(route_tradeoff(result),icon=":material/eco:")
            if metadata["prediction_source"] == "simulation-trained":
                st.warning("Fuel estimates are simulated, not measured.")
        else:
            with st.container(border=True):
                st.markdown("### Choose your start and finish")
                st.caption("Choose two locations to compare distance with simulated fuel use.")
                st.markdown(":orange-badge[Shortest distance] :violet-badge[Lower fuel]")
        with st.expander("Map appearance"):
            style = st.segmented_control("Map background",["Color streets","Dark contrast"],default="Color streets",key="map_background", persist_state="session")
            line_opacity = st.slider("Line opacity (%)",min_value=20,max_value=100,value=65,step=5,key="line_opacity",
                help="Lower values reveal more of the map; road labels stay visible.", persist_state="session")
    with map_toolbar_area:
        toolbar, fit = st.columns([3,1],vertical_alignment="bottom")
        with toolbar:
            visible = st.segmented_control("Show routes",["Both","Shortest only","Lower fuel only"],
                default="Both",key="route_visibility",disabled=result is None, persist_state="session") or "Both"
        if fit.button("Fit both routes",disabled=result is None,key="fit_routes",icon=":material/fit_screen:"):
            st.session_state["map_fit_epoch"] = st.session_state.get("map_fit_epoch",0)+1
    with map_area:
        style_name = "dark" if style == "Dark contrast" else "road"
        if result is None:
            deck = overview_deck(graph,origin,destination,style=style_name,line_opacity=line_opacity/100)
        else:
            deck = route_deck(graph,result,origin,destination,style=style_name,line_opacity=line_opacity/100,
                show_routes={"Both":"both","Shortest only":"shortest","Lower fuel only":"fuel"}[visible])
        scene = (request_key,result is not None,st.session_state.get("map_fit_epoch",0))
        key = "route-map-"+hashlib.sha256(repr(scene).encode()).hexdigest()[:16]
        st.pydeck_chart(deck,key=key,height=620,on_select="rerun",
            alt="Fairview street map with A/B markers and orange shortest, purple lower-fuel and teal shared route sections")
        st.markdown(":orange-badge[Shortest] :violet-badge[Lower fuel] :green-badge[Shared] **A** Start | **B** Finish")
        st.caption("OpenStreetMap contributors | CARTO basemap | Markers connect to saved road points; building entrances and access distances are not included.")
        if result is not None:
            cards = st.columns(2)
            for card, label, route, badge in ((cards[0],"Shortest distance",result.shortest,"orange"),(cards[1],"Lower simulated fuel",result.lowest_fuel,"violet")):
                with card.container(border=True):
                    st.markdown(f":{badge}-badge[{label}]")
                    st.markdown(f"### {route.distance_m/1000:.2f} km")
                    st.caption(f"{route.fuel_liters:.3f} L simulated fuel")
            profile = elevation_profile(graph,result.shortest,"Shortest")+elevation_profile(graph,result.lowest_fuel,"Lower fuel")
            if profile:
                st.markdown("#### Hills along the trip")
                chart = alt.Chart(pd.DataFrame(profile)).mark_line(strokeWidth=2.5).encode(
                    x=alt.X("Distance (km):Q"),y=alt.Y("Elevation (m):Q",scale=alt.Scale(zero=False)),
                    color=alt.Color("Route:N",scale=alt.Scale(domain=["Shortest","Lower fuel"],range=["#ea580c","#6d28d9"]),legend=alt.Legend(orient="bottom")),
                    tooltip=["Route:N","Distance (km):Q","Elevation (m):Q"]).properties(height=140)
                st.altair_chart(chart,width="stretch",alt="Distance versus saved endpoint elevation for both routes")
                st.caption("Sampled road-end elevations, connected for comparison; not a detailed survey of every hill.")
            with st.expander("Full route numbers"):
                rows = comparison_rows(result)
                st.dataframe(pd.DataFrame(rows),hide_index=True,alt="Distance and simulated fuel for both routes")
                st.bar_chart(pd.DataFrame(rows),x="Route",y="Predicted fuel (L)")


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
        with st.expander("Detailed model and routing comparisons"):
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
        with st.expander("Detailed sensitivity results"):
            st.dataframe(pd.read_csv(folder / "sensitivity_summary.csv"), hide_index=True,
                         alt="Sensitivity results for 27 weight, speed and efficiency combinations")
        with st.expander("The two different Checkpoint 2 trips"):
            st.dataframe(pd.read_csv(folder / "cp2_different_route_profiles.csv"), hide_index=True,
                         alt="Distance, climb, slope and simulator fuel for the two original trips")
        st.download_button("Download all sensitivity route results", (folder / "sensitivity_routes.csv").read_bytes(),
                           file_name="cp3_sensitivity_routes.csv", mime="text/csv")
    except (OSError, ValueError, KeyError) as exc:
        st.error(f"Could not read saved CP3 evaluation: {exc}")


BRAND_ASSETS = ROOT / "assets" / "branding"
app_icon = BRAND_ASSETS / "ecoroute-icon.png"
st.set_page_config(page_title="EcoRoute | Route planner", page_icon=str(app_icon) if app_icon.is_file() else ":material/route:", layout="wide")
brand, location = st.columns([3,1],vertical_alignment="center")
with brand:
    logo = BRAND_ASSETS / "ecoroute-light.png"
    if logo.is_file():
        st.html(logo_markup(logo), width="content")
    else:
        st.title("EcoRoute",anchor=False)
    st.caption("Compare distance and simulated fuel, side by side.")
with location:
    st.badge("Fairview, NC",icon=":material/location_on:",color="green")
    st.caption(f"Study area: {STUDY_AREA_LABEL}")
workspace_nav, map_toolbar_area = st.columns([1,2.25],gap="large",vertical_alignment="top")
with workspace_nav:
    screen = st.segmented_control("Workspace",["Plan a route","Evaluation evidence","Current data"],default="Plan a route",key="workspace", persist_state="session") or "Plan a route"
if screen == "Plan a route":
    render_routes()
elif screen == "Evaluation evidence":
    render_evaluation()
else:
    render_data()
