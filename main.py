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
        "New York, NY",
        help="Enter an address or landmark"
    )
    
    # Time range settings
    max_time = st.slider(
        "Maximum Travel Time (minutes)",
        15,
        120,
        60,
        step=15
    )
    
    time_step = st.slider(
        "Time Interval (minutes)",
        5,
        30,
        15,
        step=5
    )
    
    # Transportation mode
    mode = st.selectbox(
        "Transportation Mode",
        ["driving", "walking", "bicycling", "transit"],
        index=0
    )
    
    # Calculate button
    calculate = st.button("Calculate Contours")

# Main content area
try:
    if calculate:
        with st.spinner("Calculating travel times..."):
            # Initialize calculator and visualizer
            calculator = TravelTimeCalculator(location, max_time, time_step, mode)
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
                max_time
            )
            
            # Display the map
            st.plotly_chart(fig, use_container_width=True)
            
    elif st.session_state.calculator and st.session_state.visualizer:
        # Display previously calculated map
        fig = st.session_state.visualizer.create_contour_map(
            st.session_state.calculator.last_result,
            st.session_state.calculator.center_location,
            max_time
        )
        st.plotly_chart(fig, use_container_width=True)
    
    else:
        st.info("Enter a location and click 'Calculate Contours' to begin")

except Exception as e:
    st.error(f"An error occurred: {str(e)}")
