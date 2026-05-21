from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

import json
import streamlit as st
from travel_time_calculator import TravelTimeCalculator
from map_visualizer import MapVisualizer
from fastest_mode_analyser import FastestModeAnalyser
from contour import Contour

st.set_page_config(page_title="Travel Time Contour Map", layout="wide")

# ── Session state defaults ────────────────────────────────────────────────────
if "contours" not in st.session_state:
    st.session_state.contours = []
if "location" not in st.session_state:
    st.session_state.location = "SW9 6JX"
if "default_loaded" not in st.session_state:
    st.session_state.default_loaded = False
if "fastest_cache" not in st.session_state:
    st.session_state.fastest_cache = {}
if "rgb_cache" not in st.session_state:
    st.session_state.rgb_cache = {}

# ── Pre-load demo contours on first run ───────────────────────────────────────
if not st.session_state.default_loaded:
    st.session_state.default_loaded = True
    # hidden_by_default: Transit loads hidden so Approx Transit is the active comparison target
    hidden_by_default = {"demo_transit.json"}
    for fname in ("demo_approximate_transit.json", "demo_cycling.json", "demo_driving.json", "demo_transit.json"):
        path = Path(__file__).parent / fname
        if path.exists():
            data = json.loads(path.read_text())
            c = Contour(
                mode=data["mode"],
                location=data["location"],
                max_time=data["max_time"],
                interval=data["interval"],
            )
            c.set_results(data["features"], tuple(data["center_location"]))
            if fname in hidden_by_default:
                c.visible = False
            st.session_state.contours.append(c)
    if st.session_state.contours:
        st.rerun()

_MAP_STYLES = {
    "Clean":    "carto-positron",
    "Detailed": "open-street-map",
    "Dark":     "carto-darkmatter",
}

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Map")
    map_style_label = st.selectbox("Base map", list(_MAP_STYLES.keys()), key="map_style_label")
    map_style = _MAP_STYLES[map_style_label]
    opacity = st.slider("Opacity", min_value=0.1, max_value=1.0, value=0.65, step=0.05, key="opacity")

    st.divider()
    st.header("Contours")

    available_modes = {
        "Cycling":             ("bicycling",           False),
        "Driving":             ("driving",             False),
        "Walking":             ("walking",             False),
        "Transit":             ("transit",             True),
        "Approximate Transit": ("approximated_transit", True),
        "Bus":                 ("bus",                 True),
    }

    mode_descriptions = {
        "Cycling":             "Travel times by bicycle.",
        "Driving":             "Travel times by car, using live traffic data.",
        "Walking":             "Travel times on foot.",
        "Transit":             "Public transport using real scheduled timetables. Most accurate but slower to compute.",
        "Approximate Transit": "Public transport using a generalised speed model instead of live timetables. Faster to compute but less precise.",
        "Bus":                 "Distance a bus vehicle can travel (routing, not passenger journey time). Rarely what you want.",
    }

    if "contour_info" not in st.session_state:
        st.session_state.contour_info = []

    tabs = ["New"] + [f"{c.mode} {i+1}" for i, c in enumerate(st.session_state.contours)]
    current_tab = st.tabs(tabs)

    with current_tab[0]:
        st.text_input("Starting Location", value=st.session_state.location, key="new_location")
        selected_mode = st.selectbox("Transportation Mode", list(available_modes.keys()), key="new_mode")
        st.caption(mode_descriptions[selected_mode])
        max_time = st.slider("Maximum Travel Time", 5, 60, 30, step=5, key="new_max_time")
        interval = st.slider("Time Interval", 1, 15, 5, step=1, key="new_interval")

        if st.button("Create Contour"):
            api_mode, use_geoapify = available_modes[selected_mode]
            calculator = TravelTimeCalculator(
                location=st.session_state.new_location,
                max_time=max_time,
                mode=api_mode,
                interval=interval,
                use_geoapify=use_geoapify,
            )
            new_contour = Contour(
                mode=selected_mode,
                location=st.session_state.new_location,
                max_time=max_time,
                interval=interval,
            )
            new_contour.set_results(calculator.calculate_travel_times(), calculator.center_location)
            st.session_state.contours.append(new_contour)
            st.rerun()

    for idx, tab in enumerate(current_tab[1:]):
        with tab:
            contour = st.session_state.contours[idx]
            st.markdown("### Contour Information")
            st.text(f"Location: {contour.location}")
            st.text(f"Mode: {contour.mode}")
            st.text(f"Maximum Time: {contour.max_time} minutes")
            st.text(f"Time Interval: {contour.interval} minutes")

            new_name = st.text_input("Legend label", value=contour.name, key=f"name_{idx}")
            if new_name != contour.name:
                contour.name = new_name
                st.rerun()

            col_a, col_b = st.columns(2)
            with col_a:
                new_start = st.color_picker("Colour (short)", value=contour.start_color_hex, key=f"start_{idx}")
            with col_b:
                new_end = st.color_picker("Colour (long)", value=contour.end_color_hex, key=f"end_{idx}")
            if new_start != contour.start_color_hex or new_end != contour.end_color_hex:
                contour.start_color_hex = new_start
                contour.end_color_hex = new_end
                st.rerun()

            band_style = st.selectbox(
                "Time band labels",
                options=["None", "Numbers", "Width"],
                index=["None", "Numbers", "Width"].index(getattr(contour, "band_style", "None")),
                key=f"band_style_{idx}",
                help="Numbers: numbered badge at each ring's peak. Width: line thickness increases with travel time.",
            )
            if band_style != getattr(contour, "band_style", "None"):
                contour.band_style = band_style
                st.rerun()

            valid_intervals = [
                i for i in range(contour.interval, contour.max_time + 1, contour.interval)
            ]
            current_di = getattr(contour, "display_interval", contour.interval)
            new_di = st.selectbox(
                "Show every N min",
                options=valid_intervals,
                index=valid_intervals.index(current_di) if current_di in valid_intervals else 0,
                key=f"disp_{idx}",
                help="Thin out displayed rings without re-fetching data.",
            )
            if new_di != current_di:
                contour.display_interval = new_di
                st.rerun()

            visible = st.checkbox("Show on map", value=contour.visible, key=f"visible_{idx}")
            if visible != contour.visible:
                contour.visible = visible
                st.rerun()

            if st.button("Delete Contour", key=f"delete_{idx}"):
                st.session_state.contours.pop(idx)
                st.rerun()

# ── Main content ──────────────────────────────────────────────────────────────
st.title("Travel Time Contour Map")

tab_map, tab_fastest = st.tabs(["Contour Map", "Fastest Mode"])

# ── Tab 1: Contour map ────────────────────────────────────────────────────────
with tab_map:
    try:
        visualizer = MapVisualizer()
        any_visible = any(getattr(c, "visible", True) for c in st.session_state.contours)
        if st.session_state.contours and any_visible:
            fig = visualizer.create_multi_mode_map(st.session_state.contours, map_style=map_style, opacity=opacity)
            st.plotly_chart(fig, use_container_width=True)
        elif st.session_state.contours:
            st.info("All contours are hidden. Use 'Show on map' in the contour tabs to reveal them.")
        else:
            st.info("Create a contour to begin.")
    except Exception as e:
        st.error(f"An error occurred: {e}")

# ── Tab 2: Fastest mode ───────────────────────────────────────────────────────
with tab_fastest:
    visible_contours = [
        c for c in st.session_state.contours
        if getattr(c, "visible", True) and c.features and c.features.get("features")
    ]

    if len(visible_contours) < 2:
        st.info("Add at least two visible contours to compare modes.")
    else:
        colour_mode = st.radio(
            "Colour mode",
            ["Gradient", "RGB mix"],
            horizontal=True,
            help=(
                "Gradient: each mode uses its own colour, shaded light→dark with travel time. "
                "RGB mix: modes are mapped to R/G/B channels — brightness encodes speed, "
                "mixed colours show areas where multiple modes perform similarly."
            ),
        )

        cache_key = tuple(
            (c.mode, c.location, c.max_time, c.interval) for c in visible_contours
        )

        if colour_mode == "Gradient":
            if cache_key not in st.session_state.fastest_cache:
                with st.spinner("Computing fastest-mode regions…"):
                    analyser = FastestModeAnalyser()
                    result = analyser.analyse_vector(visible_contours)
                    st.session_state.fastest_cache[cache_key] = result
            else:
                result = st.session_state.fastest_cache[cache_key]

            if result is None:
                st.info("Not enough data to compute. Ensure at least two contours have results.")
            else:
                try:
                    visualizer = MapVisualizer()
                    fig = visualizer.create_fastest_mode_map(result, map_style=map_style, opacity=opacity)
                    st.plotly_chart(fig, use_container_width=True)
                    st.caption("Colour = fastest mode. Darker shade = longer travel time within that mode's zone.")
                except Exception as e:
                    st.error(f"Render error: {e}")

        else:  # RGB mix
            if cache_key not in st.session_state.rgb_cache:
                with st.spinner("Computing RGB mode map…"):
                    analyser = FastestModeAnalyser(grid_size=250)
                    result = analyser.analyse_rgb(visible_contours)
                    st.session_state.rgb_cache[cache_key] = result
            else:
                result = st.session_state.rgb_cache[cache_key]

            if result is None:
                st.info("Not enough data to compute. Ensure at least two contours have results.")
            else:
                try:
                    visualizer = MapVisualizer()
                    fig = visualizer.create_rgb_mode_map(result, map_style=map_style, opacity=opacity)
                    st.plotly_chart(fig, use_container_width=True)
                    st.caption(
                        "Each mode is assigned a primary colour (red, green, blue…). "
                        "Brightness = speed. Mixed colours indicate areas where multiple modes perform similarly."
                    )
                except Exception as e:
                    st.error(f"Render error: {e}")
