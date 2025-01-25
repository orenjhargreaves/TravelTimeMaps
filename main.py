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

    # Travel distance setting
    radius_km = st.slider(
        "Maximum Travel Distance (km)",
        1,
        50,  # Increased from 20 to 50
        5,
        step=1,
        help="Maximum radius to analyze around the starting point"
    )

    point_density = st.slider(
        "Point Density",
        16,
        128,  # Increased from 64 to 128
        32,
        step=16,
        help="Number of points per circle (higher values give more detailed results)"
    )

    # Transportation mode
    mode = st.selectbox(
        "Transportation Mode",
        ["Driving", "Walking", "Cycling"],  # Updated labels
        index=0,
        format_func=lambda x: x  # Ensures proper case display
    ).lower()  # Convert to lowercase for API

    # Calculate button
    calculate = st.button("Calculate Contours")

# Main content area
try:
    if calculate:
        with st.spinner("Calculating travel times..."):
            # Initialize calculator and visualizer with new parameters
            calculator = TravelTimeCalculator(
                location=location,
                max_time=60,
                time_step=5,
                mode=mode,
                radius_km=radius_km,
                point_density=point_density
            )
            visualizer = MapVisualizer()

            # Calculate travel times
            travel_times = calculator.calculate_travel_times()

            # Store in session state
            st.session_state.calculator = calculator
            st.session_state.visualizer = visualizer

            # Create visualization
            fig = visualizer.create_contour_map(
                travel_times,
                calculator.center_location,
                60  # Fixed maximum time display
            )

            # Display the map
            st.plotly_chart(fig, use_container_width=True)

    elif st.session_state.calculator and st.session_state.visualizer:
        # Display previously calculated map
        fig = st.session_state.visualizer.create_contour_map(
            st.session_state.calculator.last_result,
            st.session_state.calculator.center_location,
            60  # Fixed maximum time display
        )
        st.plotly_chart(fig, use_container_width=True)

    else:
        st.info("Enter a location and click 'Calculate Contours' to begin")

except Exception as e:
    st.error(f"An error occurred: {str(e)}")