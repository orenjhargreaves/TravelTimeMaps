import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from travel_time_calculator import TravelTimeCalculator
from map_visualizer import MapVisualizer
import googlemaps

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
if 'show_raw_data' not in st.session_state:
    st.session_state.show_raw_data = False

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

    # Maximum travel time setting
    max_time = st.slider(
        "Maximum Travel Time (minutes)",
        5,
        60,
        30,  # Default to 30 minutes
        step=5,
        help="Maximum travel time from the starting point"
    )

    # API selection
    use_geoapify = st.checkbox("Use Geoapify API (includes public transport)", False)
    
    # Transportation mode mapping
    if use_geoapify:
        mode_mapping = {
            "Public Transport": "public_transport",
            "Cycling": "bicycling",
            "Driving": "driving",
            "Walking": "walking"
        }
    else:
        mode_mapping = {
            "Cycling": "bicycling",  # Default mode first
            "Driving": "driving",
            "Walking": "walking"
        }

    # Transportation mode
    display_mode = st.selectbox(
        "Transportation Mode",
        list(mode_mapping.keys()),
        index=0,  # Default to Cycling
        format_func=lambda x: x
    )
    mode = mode_mapping[display_mode]

    # Calculate button
    calculate = st.button("Calculate Contours")

# Create placeholders for the interface elements
map_placeholder = st.empty()
progress_container = st.container()
with progress_container:
    progress_bar = st.progress(0)
    progress_text = st.empty()

# Create container for the toggle button
toggle_container = st.container()

# Main content area
try:
    if calculate:
        # Initialize calculator and visualizer with new parameters
        calculator = TravelTimeCalculator(
            location=location,
            max_time=max_time,
            mode=mode,
            use_geoapify=use_geoapify
        )
        visualizer = MapVisualizer()

        # Add progress update function
        def update_progress(message, percentage=None):
            if percentage is not None:
                progress_bar.progress(percentage)
            progress_text.text(message)

        # Calculate travel times
        travel_times = calculator.calculate_travel_times(progress_callback=update_progress)

        # Store in session state
        st.session_state.calculator = calculator
        st.session_state.visualizer = visualizer

        # Create visualization
        fig = visualizer.create_contour_map(
            travel_times,
            calculator.center_location,
            60,
            show_raw_data=st.session_state.show_raw_data
        )

        # Display the map in the placeholder
        map_placeholder.plotly_chart(fig, use_container_width=True, key="map_new")
        # Clear progress indicators after completion
        progress_text.empty()
        progress_bar.empty()

    elif st.session_state.calculator and st.session_state.visualizer:
        # Update visualization with current toggle state
        fig = st.session_state.visualizer.create_contour_map(
            st.session_state.calculator.last_result,
            st.session_state.calculator.center_location,
            60,
            show_raw_data=st.session_state.show_raw_data
        )
        # Display in placeholder with unique key
        map_placeholder.plotly_chart(fig, use_container_width=True, key="map_existing")

    # Show toggle only when map is displayed
    if st.session_state.calculator and st.session_state.visualizer:
        with toggle_container:
            # Toggle for raw data points
            show_raw_data = st.checkbox(
                "Show Raw Data Points",
                value=st.session_state.show_raw_data,
                help="Toggle between contour map and raw data points"
            )

            # Update session state if toggle changes
            if show_raw_data != st.session_state.show_raw_data:
                st.session_state.show_raw_data = show_raw_data
                st.rerun()

    else:
        # Show empty map container
        map_placeholder.empty()
        st.info("Enter a location and click 'Calculate Contours' to begin")

except Exception as e:
    st.error(f"An error occurred: {str(e)}")