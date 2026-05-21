from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

import os
import streamlit as st

# On Streamlit Community Cloud, API keys come from st.secrets rather than .env.
# Push them into os.environ so travel_time_calculator.py can read them unchanged.
for _key in ("MAPBOX_ACCESS_TOKEN", "GEOAPIFY_API_KEY"):
    if _key not in os.environ:
        try:
            os.environ[_key] = st.secrets[_key]
        except (KeyError, FileNotFoundError):
            pass

import json
from travel_time_calculator import TravelTimeCalculator
from map_visualizer import MapVisualizer
from fastest_mode_analyser import FastestModeAnalyser
from contour import Contour

st.set_page_config(page_title="Travel Time Contour Map", layout="wide")

# ── Session state defaults ────────────────────────────────────────────────────
if "contours" not in st.session_state:
    st.session_state.contours = []
if "default_loaded" not in st.session_state:
    st.session_state.default_loaded = False
if "fastest_cache" not in st.session_state:
    st.session_state.fastest_cache = {}
if "rgb_cache" not in st.session_state:
    st.session_state.rgb_cache = {}
if "contour_raster_cache" not in st.session_state:
    st.session_state.contour_raster_cache = {}
if "imported_file_ids" not in st.session_state:
    st.session_state.imported_file_ids = set()

# ── Pre-load demo contours on first run ───────────────────────────────────────
if not st.session_state.default_loaded:
    st.session_state.default_loaded = True
    # Approximate Transit hidden by default; Transit (exact timetables) is the recommended mode
    hidden_by_default = {"demo_approximate_transit.json"}
    for fname in ("demo_transit.json", "demo_cycling.json", "demo_driving.json", "demo_approximate_transit.json"):
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

_AVAILABLE_MODES = {
    "Cycling":             ("bicycling",            False),
    "Driving":             ("driving",              False),
    "Walking":             ("walking",              False),
    "Transit":             ("transit",              True),
    "Approximate Transit": ("approximated_transit", True),
    "Bus":                 ("bus",                  True),
}

_MODE_DESCRIPTIONS = {
    "Transit":             "Real scheduled timetables. Most accurate.",
    "Approximate Transit": "Generalised speed model. Faster to compute, less precise.",
    "Cycling":             "Travel times by bicycle.",
    "Driving":             "Travel times by car, using live traffic data.",
    "Walking":             "Travel times on foot.",
    "Bus":                 "Bus vehicle routing (not passenger journey time).",
}

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Map")
    map_style_label = st.selectbox("Base map", list(_MAP_STYLES.keys()), key="map_style_label")
    map_style = _MAP_STYLES[map_style_label]
    opacity   = st.slider("Opacity", min_value=0.1, max_value=1.0, value=0.65, step=0.05, key="opacity")
    pin_color = st.color_picker("Pin colour", value="#E63946", key="pin_color")

    st.divider()
    st.header("Contours")

    contour_display = st.radio(
        "Style",
        ["Filled", "Outlines"],
        horizontal=True,
        key="contour_display",
        help="Filled: solid colour bands. Outlines: isochrone ring lines only.",
    )

    st.divider()

    # ── Export / import layers ────────────────────────────────────────────────
    st.subheader("Save / load layers")

    exportable = [
        c for c in st.session_state.contours
        if c.features and c.features.get("features")
    ]
    if exportable:
        export_data = json.dumps([
            {
                "mode":            c.mode,
                "location":        c.location,
                "max_time":        c.max_time,
                "interval":        c.interval,
                "name":            c.name,
                "start_color_hex": c.start_color_hex,
                "end_color_hex":   c.end_color_hex,
                "visible":         c.visible,
                "display_interval": c.display_interval,
                "band_style":      c.band_style,
                "time_penalty":    getattr(c, 'time_penalty', 0),
                "features":        c.features,
                "center_location": list(c.center_location),
            }
            for c in exportable
        ], indent=2)
        st.download_button(
            "Export layers",
            data=export_data,
            file_name="travel_time_layers.json",
            mime="application/json",
            use_container_width=True,
        )

    uploaded = st.file_uploader("Import layers", type="json", label_visibility="collapsed")
    if uploaded is not None and uploaded.file_id not in st.session_state.imported_file_ids:
        try:
            items = json.loads(uploaded.read())
            loaded = 0
            for item in items:
                c = Contour(
                    mode=item["mode"],
                    location=item["location"],
                    max_time=item["max_time"],
                    interval=item["interval"],
                )
                c.set_results(item["features"], tuple(item["center_location"]))
                c.name             = item.get("name", item["mode"])
                c.start_color_hex  = item.get("start_color_hex", c.start_color_hex)
                c.end_color_hex    = item.get("end_color_hex",   c.end_color_hex)
                c.visible          = item.get("visible", True)
                c.display_interval = item.get("display_interval", item["interval"])
                c.band_style       = item.get("band_style", "None")
                c.time_penalty     = item.get("time_penalty", 0)
                st.session_state.contours.append(c)
                loaded += 1
            st.session_state.imported_file_ids.add(uploaded.file_id)
            st.success(f"Loaded {loaded} layer(s).")
            st.rerun()
        except Exception as e:
            st.error(f"Import failed: {e}")

    st.divider()

    # ── New contour creation form ─────────────────────────────────────────────
    st.subheader("New contour")

    new_location = st.text_input("Address or postcode", value="SW9 6JX", key="new_location")

    col_time, col_int = st.columns(2)
    with col_time:
        max_time = st.slider("Max time (min)", 5, 60, 30, step=5, key="new_max_time")
    with col_int:
        interval = st.slider("Interval (min)", 1, 15, 5, step=1, key="new_interval")

    st.caption("Select modes")
    mode_cols = st.columns(3)
    mode_list = list(_AVAILABLE_MODES.keys())
    # Transit checked by default; all others unchecked
    default_checked = {"Transit"}
    mode_selected = {}
    for i, mode in enumerate(mode_list):
        with mode_cols[i % 3]:
            mode_selected[mode] = st.checkbox(
                mode,
                value=(mode in default_checked),
                key=f"mode_cb_{mode}",
                help=_MODE_DESCRIPTIONS.get(mode, ""),
            )

    if st.button("Create", type="primary", use_container_width=True):
        chosen = [m for m, checked in mode_selected.items() if checked]
        if not chosen:
            st.warning("Select at least one mode.")
        else:
            with st.spinner(f"Fetching travel times for {len(chosen)} mode(s)…"):
                for mode_name in chosen:
                    api_mode, use_geoapify = _AVAILABLE_MODES[mode_name]
                    try:
                        calculator = TravelTimeCalculator(
                            location=new_location,
                            max_time=max_time,
                            mode=api_mode,
                            interval=interval,
                            use_geoapify=use_geoapify,
                        )
                        new_contour = Contour(
                            mode=mode_name,
                            location=new_location,
                            max_time=max_time,
                            interval=interval,
                        )
                        new_contour.set_results(
                            calculator.calculate_travel_times(),
                            calculator.center_location,
                        )
                        st.session_state.contours.append(new_contour)
                    except Exception as e:
                        st.error(f"{mode_name}: {e}")
            st.rerun()

    # ── Existing contour list ─────────────────────────────────────────────────
    if st.session_state.contours:
        st.divider()
        st.subheader("Layers")

    for idx, contour in enumerate(st.session_state.contours):
        eye = "👁" if contour.visible else "🚫"
        # Top-level sidebar columns are allowed; only nested columns are forbidden.
        col_btn, col_exp = st.columns([1, 6])

        with col_btn:
            if st.button(eye, key=f"toggle_{idx}", use_container_width=True, help="Show/hide"):
                contour.visible = not contour.visible
                st.rerun()

        with col_exp:
            # No st.columns inside here (would be nested) — widgets stack vertically.
            with st.expander(contour.name, expanded=False):
                new_name = st.text_input("Label", value=contour.name, key=f"name_{idx}")
                if new_name != contour.name:
                    contour.name = new_name
                    st.rerun()

                new_start = st.color_picker("Near colour", value=contour.start_color_hex, key=f"start_{idx}")
                new_end   = st.color_picker("Far colour",  value=contour.end_color_hex,   key=f"end_{idx}")
                if new_start != contour.start_color_hex or new_end != contour.end_color_hex:
                    contour.start_color_hex = new_start
                    contour.end_color_hex   = new_end
                    st.rerun()

                if contour_display == "Outlines":
                    band_style = st.selectbox(
                        "Band style",
                        options=["None", "Numbers", "Width"],
                        index=["None", "Numbers", "Width"].index(getattr(contour, "band_style", "None")),
                        key=f"band_style_{idx}",
                        help="Numbers: time badge at each ring. Width: line thickness scales with time.",
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
                    help="Thin out rings without re-fetching data.",
                )
                if new_di != current_di:
                    contour.display_interval = new_di
                    st.rerun()

                new_penalty = st.slider(
                    "Time overhead (min)",
                    min_value=0, max_value=30,
                    value=getattr(contour, 'time_penalty', 0),
                    step=1,
                    key=f"penalty_{idx}",
                    help="Fixed cost added to all travel times (e.g. walking to car, carrying bike downstairs).",
                )
                if new_penalty != getattr(contour, 'time_penalty', 0):
                    contour.time_penalty = new_penalty
                    st.rerun()

                if st.button("Delete", key=f"delete_{idx}", use_container_width=True):
                    st.session_state.contours.pop(idx)
                    st.rerun()

# ── Main content ──────────────────────────────────────────────────────────────
st.title("Travel Time Contour Map")

tab_map, tab_fastest = st.tabs(["Contour Map", "Fastest Mode"])

# ── Tab 1: Contour map ────────────────────────────────────────────────────────
with tab_map:
    try:
        visualizer  = MapVisualizer()
        vis_map     = [
            c for c in st.session_state.contours
            if getattr(c, "visible", True) and c.features and c.features.get("features")
        ]
        any_visible = bool(vis_map)

        if vis_map:
            if contour_display == "Filled":
                # Rasterise to a PIL image so every pixel has exactly one colour —
                # no polygon stacking, opacity is perfectly uniform.
                #
                # Cache only the slow PIP rasterization step, keyed by contour data.
                # Colorization (colours, opacity, pin colour) always runs fresh so
                # visual setting changes take effect immediately.
                raster_key = tuple(
                    (c.mode, c.location, c.max_time, c.interval) for c in vis_map
                )
                if raster_key not in st.session_state.contour_raster_cache:
                    with st.spinner("Computing contour fill…"):
                        raster = MapVisualizer.rasterise_contours(vis_map)
                        st.session_state.contour_raster_cache[raster_key] = raster
                else:
                    raster = st.session_state.contour_raster_cache[raster_key]

                fig = visualizer.create_contour_image_map(
                    st.session_state.contours,
                    map_style=map_style,
                    opacity=opacity,
                    pin_color=pin_color,
                    raster=raster,
                )
                st.plotly_chart(fig, use_container_width=True, key="chart_contour_filled")
            else:
                # Outlines mode: per-contour ring lines.
                fig = visualizer.create_multi_mode_map(
                    st.session_state.contours,
                    map_style=map_style,
                    opacity=opacity,
                    pin_color=pin_color,
                    display_mode="Outlines",
                )
                st.plotly_chart(fig, use_container_width=True, key="chart_contour_outline")

        elif st.session_state.contours:
            st.info("All contours are hidden. Toggle visibility in the Layers panel.")
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
            # Reuse the raster cache from the Contour tab (same computation).
            # The PIL image approach assigns each pixel independently via argmin —
            # no polygon subtraction, so no geometry artefacts.
            if cache_key not in st.session_state.contour_raster_cache:
                with st.spinner("Computing fastest-mode regions…"):
                    raster = MapVisualizer.rasterise_contours(visible_contours)
                    st.session_state.contour_raster_cache[cache_key] = raster
            else:
                raster = st.session_state.contour_raster_cache[cache_key]

            try:
                visualizer = MapVisualizer()
                fig = visualizer.create_contour_image_map(
                    visible_contours,
                    map_style=map_style, opacity=opacity, pin_color=pin_color,
                    raster=raster,
                )
                st.plotly_chart(fig, use_container_width=True, key="chart_fastest_gradient")
                st.caption("Colour = fastest mode. Darker shade = longer travel time within that mode's zone.")
            except Exception as e:
                st.error(f"Render error: {e}")

        else:  # RGB mix
            if cache_key not in st.session_state.rgb_cache:
                with st.spinner("Computing RGB mode map…"):
                    analyser = FastestModeAnalyser(grid_size=250)
                    result   = analyser.analyse_rgb(visible_contours)
                    st.session_state.rgb_cache[cache_key] = result
            else:
                result = st.session_state.rgb_cache[cache_key]

            if result is None:
                st.info("Not enough data to compute. Ensure at least two contours have results.")
            else:
                try:
                    visualizer = MapVisualizer()
                    fig = visualizer.create_rgb_mode_map(
                        result, map_style=map_style, opacity=opacity, pin_color=pin_color
                    )
                    st.plotly_chart(fig, use_container_width=True, key="chart_fastest_rgb")
                    st.caption(
                        "Each mode is assigned a primary colour (red, green, blue…). "
                        "Brightness = speed. Mixed colours indicate areas where multiple modes perform similarly."
                    )
                except Exception as e:
                    st.error(f"Render error: {e}")
