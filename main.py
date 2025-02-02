import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from travel_time_calculator import TravelTimeCalculator
from map_visualizer import MapVisualizer

# Page configuration
st.set_page_config(page_title="Travel Time Contour Map", layout="wide")

# Initialize session state
if 'calculator' not in st.session_state:
    st.session_state.calculator = None
if 'visualizer' not in st.session_state:
    st.session_state.visualizer = None
if 'stored_results' not in st.session_state:
    st.session_state.stored_results = []
if 'center_location' not in st.session_state:
    st.session_state.center_location = None
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

    # Create a mapping of modes to their occurrence number
    mode_counts = {}
    mode_indices = []
    for mode, _, _ in st.session_state.stored_results:
        mode_counts[mode] = mode_counts.get(mode, 0) + 1
        mode_indices.append(mode_counts[mode])

    # Create tabs for new contour and existing contours
    tabs = ["New"] + [f"{result[0]} {idx}" for result, idx in zip(st.session_state.stored_results, mode_indices)]
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

            results = calculator.calculate_travel_times()
            st.session_state.center_location = calculator.center_location
            st.session_state.stored_results.append((selected_mode, results, max_time))
            st.rerun()

    # Display existing contour information in tabs
    for idx, tab in enumerate(current_tab[1:], 0):
        with tab:
            stored_result = st.session_state.stored_results[idx]
            st.markdown("### Contour Information")
            st.text(f"Location: {st.session_state.location}")
            st.text(f"Mode: {stored_result[0]}")
            st.text(f"Maximum Time: {stored_result[2]} minutes")
            st.text(f"Time Interval: {interval} minutes")

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
                key=f"color_{idx}"
            )
            
            # Store the color selection in session state
            if f"color_choice_{idx}" not in st.session_state:
                st.session_state[f"color_choice_{idx}"] = selected_color

            if selected_color != st.session_state[f"color_choice_{idx}"]:
                st.session_state[f"color_choice_{idx}"] = selected_color
                st.rerun()

            if st.button("Delete Contour", key=f"delete_{idx}"):
                st.session_state.stored_results.pop(idx)
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

    if st.session_state.stored_results:
        current_fig = visualizer.create_multi_mode_map(
            st.session_state.stored_results,
            st.session_state.center_location,
            washed_out=(map_style == "Washed out")
        )
        map_container.plotly_chart(current_fig, use_container_width=True)
    else:
        map_container.info("Create a contour to begin")

except Exception as e:
    st.error(f"An error occurred: {str(e)}")