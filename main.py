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
        50,
        15,  
        step=1,
        help="Maximum radius to analyze around the starting point"
    )

    point_density = st.slider(
        "Point Density",
        16,
        1024, 
        128, 
        step=16,
        help="Number of points per circle (higher values give more detailed results)"
    )

    # Transportation mode mapping
    mode_mapping = {
        "Cycling": "bicycling",  
        "Driving": "driving",
        "Walking": "walking"
    }

    # Transportation mode
    display_mode = st.selectbox(
        "Transportation Mode",
        list(mode_mapping.keys()),
        index=0,  
        format_func=lambda x: x
    )
    mode = mode_mapping[display_mode]

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
                60,  
                show_raw_data=False  
            )

            # Display the map
            st.plotly_chart(fig, use_container_width=True)

    elif st.session_state.calculator and st.session_state.visualizer:
        # Display previously calculated map
        fig = st.session_state.visualizer.create_contour_map(
            st.session_state.calculator.last_result,
            st.session_state.calculator.center_location,
            60,  
            show_raw_data=False  
        )
        st.plotly_chart(fig, use_container_width=True)

    else:
        st.info("Enter a location and click 'Calculate Contours' to begin")

    # Visualization mode toggle (moved below the map)
    show_raw_data = st.checkbox(
        "Show Raw Data Points",
        value=False,
        help="Toggle between contour map and raw data points"
    )

    # Update visualization if toggle changes
    if st.session_state.calculator and st.session_state.visualizer and show_raw_data is not None:
        fig = st.session_state.visualizer.create_contour_map(
            st.session_state.calculator.last_result,
            st.session_state.calculator.center_location,
            60,
            show_raw_data=show_raw_data
        )
        st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.error(f"An error occurred: {str(e)}")