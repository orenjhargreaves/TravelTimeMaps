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
    st.session_state.location = "Buckingham Palace, London"

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

            if st.button("Delete Contour", key=f"delete_{idx}"):
                st.session_state.contours.pop(idx)
                st.rerun()

# Create placeholders for the interface elements
map_col1, map_col2 = st.columns([4, 1])

with map_col1:
    map_container = st.empty()

with map_col2:
    map_style = st.radio("Map Style", ["Standard", "Washed out"],
                         horizontal=True)

# Initialize visualization
try:
    visualizer = MapVisualizer()

    if st.session_state.contours:
        current_fig = visualizer.create_multi_mode_map(
            st.session_state.contours,
            washed_out=(map_style == "Washed out")
        )
        map_container.plotly_chart(current_fig, use_container_width=True)
    else:
        map_container.info("Create a contour to begin")

except Exception as e:
    st.error(f"An error occurred: {str(e)}")