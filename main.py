import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from travel_time_calculator import TravelTimeCalculator
from map_visualizer import MapVisualizer

# Page configuration
st.set_page_config(
    page_title="Travel Time Contour Map",
    layout="wide"
)

# Initialize session state
if 'calculator' not in st.session_state:
    st.session_state.calculator = None
if 'visualizer' not in st.session_state:
    st.session_state.visualizer = None
if 'stored_results' not in st.session_state:
    st.session_state.stored_results = []

# Main title
st.title("Travel Time Contour Map")

# Sidebar controls
with st.sidebar:
    st.header("Settings")

    # Location input
    location = st.text_input(
        "Starting Location",
        "Buckingham Palace, London",
        help="Enter an address or landmark"
    )

    # API selection
    use_geoapify = st.checkbox("Use Geoapify API (includes public transport)", False)

    # Transportation mode mapping
    if use_geoapify:
        available_modes = {
            "Cycling": "bicycle",
            "Driving": "drive",
            "Walking": "walk",
            "Transit": "transit",
            "Approximate Transit": "approximated_transit"
        }
    else:
        available_modes = {
            "Cycling": "bicycling",
            "Driving": "driving",
            "Walking": "walking"
        }

    # Mode selection (multiple)
    selected_modes = st.multiselect(
        "Transportation Modes",
        list(available_modes.keys()),
        default=["Cycling"],
        help="Select one or more transportation modes"
    )

    # Settings for each selected mode
    mode_settings = {}
    for mode in selected_modes:
        st.subheader(f"{mode} Settings")
        max_time = st.slider(
            f"Maximum Travel Time ({mode})",
            5, 60, 30,
            step=5,
            key=f"max_time_{mode}"
        )
        interval = st.slider(
            f"Time Interval ({mode})",
            1, 15, 5,
            step=1,
            key=f"interval_{mode}"
        )
        mode_settings[mode] = {
            "max_time": max_time,
            "interval": interval,
            "api_mode": available_modes[mode]
        }

    # Calculate button
    calculate = st.button("Add Contours")

# Display existing contours and removal options
col1, col2 = st.columns([3, 1])
with col2:
    st.write("Active Contours:")
    for idx, (mode, _, max_time) in enumerate(st.session_state.stored_results):
        if st.button(f"Remove {mode} ({max_time}min)", key=f"remove_{idx}"):
            st.session_state.stored_results.pop(idx)
            st.experimental_rerun()

# Create placeholders for the interface elements
with col1:
    map_placeholder = st.empty()
    progress_container = st.container()
    with progress_container:
        progress_bar = st.progress(0)
        progress_text = st.empty()

# Main content area
try:
    visualizer = MapVisualizer()

    if calculate:
        new_results = []
        total_calculations = len(selected_modes)
        for i, mode in enumerate(selected_modes):
            settings = mode_settings[mode]
            calculator = TravelTimeCalculator(
                location=location,
                max_time=settings["max_time"],
                mode=settings["api_mode"],
                interval=settings["interval"],
                use_geoapify=use_geoapify
            )

            base_progress = i / total_calculations
            progress_step = 1 / total_calculations

            def mode_progress(message, percentage=None):
                if percentage is not None:
                    progress_bar.progress(base_progress + (percentage * progress_step))
                progress_text.text(f"{mode}: {message}")

            results = calculator.calculate_travel_times(progress_callback=mode_progress)
            new_results.append((mode, results, settings["max_time"]))

            if i == 0:
                st.session_state.center_location = calculator.center_location

        st.session_state.stored_results.extend(new_results)

        # Create visualization
        fig = visualizer.create_multi_mode_map(
            st.session_state.stored_results,
            st.session_state.center_location
        )

        # Display the map
        map_placeholder.plotly_chart(fig, use_container_width=True)

        # Clear progress indicators
        progress_text.empty()
        progress_bar.empty()

    else:
        if st.session_state.stored_results:
            fig = visualizer.create_multi_mode_map(
                st.session_state.stored_results,
                st.session_state.center_location
            )
            map_placeholder.plotly_chart(fig, use_container_width=True)
        else:
            # Show empty map container
            map_placeholder.empty()
            st.info("Enter a location and click 'Add Contours' to begin")

except Exception as e:
    st.error(f"An error occurred: {str(e)}")