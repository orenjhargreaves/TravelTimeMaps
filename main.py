from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from travel_time_calculator import TravelTimeCalculator
from map_visualizer import MapVisualizer

# Page configuration
st.set_page_config(page_title="Travel Time Contour Map", layout="wide")

from contour import Contour

# Initialize session state
if 'contours' not in st.session_state:
    st.session_state.contours = []
if 'location' not in st.session_state:
    st.session_state.location = "SW9 6JX"
if 'default_loaded' not in st.session_state:
    st.session_state.default_loaded = False

# Pre-fill from saved file on first load (no API call needed)
if not st.session_state.default_loaded:
    st.session_state.default_loaded = True
    _default_path = Path(__file__).parent / "default_contour.json"
    if _default_path.exists():
        import json
        _data = json.loads(_default_path.read_text())
        _c = Contour(mode=_data["mode"], location=_data["location"],
                     max_time=_data["max_time"], interval=_data["interval"])
        _c.set_results(_data["features"], tuple(_data["center_location"]))
        st.session_state.contours.append(_c)
        st.rerun()

# Main title
st.title("Travel Time Contour Map")

# Sidebar controls
with st.sidebar:
    st.header("Contours")

    # Transportation mode mapping
    available_modes = {
        "Cycling": ("bicycling", False),
        "Driving": ("driving", False),
        "Walking": ("walking", False),
        "Transit": ("transit", True),
        "Approximate Transit": ("approximated_transit", True),
        "Bus": ("bus", True)
    }

    mode_descriptions = {
        "Cycling":            "Travel times by bicycle.",
        "Driving":            "Travel times by car, using live traffic data.",
        "Walking":            "Travel times on foot.",
        "Transit":            "Public transport using real scheduled timetables. Most accurate but slower to compute.",
        "Approximate Transit": "Public transport using a generalised speed model instead of live timetables. Faster to compute but less precise.",
        "Bus":                "Distance a bus vehicle can travel (routing, not passenger journey time). Rarely what you want.",
    }

    # Mode counts are no longer needed since we use the contour list directly

    # Store contour information when created
    if "contour_info" not in st.session_state:
        st.session_state.contour_info = []

    # Create tabs for new contour and existing contours
    tabs = ["New"] + [f"{contour.mode} {i+1}" for i, contour in enumerate(st.session_state.contours)]
    current_tab = st.tabs(tabs)

    with current_tab[0]:
        # New contour controls
        st.text_input("Starting Location", 
                     value=st.session_state.location,
                     key="new_location")

        selected_mode = st.selectbox("Transportation Mode",
                                   list(available_modes.keys()),
                                   key="new_mode")

        st.caption(mode_descriptions[selected_mode])

        max_time = st.slider("Maximum Travel Time",
                           5, 60, 30,
                           step=5,
                           key="new_max_time")

        interval = st.slider("Time Interval",
                          1, 15, 5,
                          step=1,
                          key="new_interval")

        if st.button("Create Contour"):
            mode_settings = {
                "max_time": max_time,
                "interval": interval,
                "api_mode": available_modes[selected_mode]
            }

            api_mode, use_geoapify = available_modes[selected_mode]
            calculator = TravelTimeCalculator(
                location=st.session_state.new_location,
                max_time=max_time,
                mode=api_mode,
                interval=interval,
                use_geoapify=use_geoapify
            )

            new_contour = Contour(
                mode=selected_mode,
                location=st.session_state.new_location,
                max_time=max_time,
                interval=interval
            )
            results = calculator.calculate_travel_times()
            new_contour.set_results(results, calculator.center_location)
            st.session_state.contours.append(new_contour)
            st.rerun()

    # Display existing contour information in tabs
    for idx, tab in enumerate(current_tab[1:], 0):
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

            # Color selection
            color_options = {
                "Default": None,
                "Blue": ((135, 206, 235), (0, 0, 139)),
                "Green": ((144, 238, 144), (34, 139, 34)),
                "Red": ((255, 182, 193), (139, 0, 0)),
                "Orange": ((255, 218, 185), (210, 105, 30)),
                "Purple": ((230, 190, 255), (128, 0, 128))
            }
            
            selected_color = st.selectbox(
                "Contour Color",
                options=list(color_options.keys()),
                key=f"color_{idx}",
                index=list(color_options.keys()).index(contour.color)
            )
            
            if selected_color != contour.color:
                contour.update_color(selected_color)
                st.rerun()

            band_style = st.selectbox(
                "Time band labels",
                options=["None", "Numbers", "Width + dash"],
                index=["None", "Numbers", "Width + dash"].index(getattr(contour, 'band_style', 'None')),
                key=f"band_style_{idx}",
                help="Numbers: small label at each ring's peak. Width + dash: line thickness and dash pattern vary by time."
            )
            if band_style != getattr(contour, 'band_style', 'None'):
                contour.band_style = band_style
                st.rerun()

            visible = st.checkbox("Show on map", value=contour.visible, key=f"visible_{idx}")
            if visible != contour.visible:
                contour.visible = visible
                st.rerun()

            if st.button("Delete Contour", key=f"delete_{idx}"):
                st.session_state.contours.pop(idx)
                st.rerun()

# Create placeholders for the interface elements
map_col1, map_col2 = st.columns([4, 1])

with map_col1:
    map_container = st.empty()


# Initialize visualization
try:
    visualizer = MapVisualizer()

    any_visible = any(getattr(c, 'visible', True) for c in st.session_state.contours)
    if st.session_state.contours and any_visible:
        current_fig = visualizer.create_multi_mode_map(
            st.session_state.contours)
        map_container.plotly_chart(current_fig, use_container_width=True)
    elif st.session_state.contours:
        map_container.info("All contours are hidden. Use 'Show on map' in the contour tabs to reveal them.")
    else:
        map_container.info("Create a contour to begin")

except Exception as e:
    st.error(f"An error occurred: {str(e)}")