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

# Main title
st.title("Travel Time Contour Map")

# Sidebar controls
with st.sidebar:
    st.header("Settings")

    # Tabs for contours
    st.markdown("### Contours")
    if 'mode_settings' not in st.session_state:
        st.session_state.mode_settings = {}
    
    if 'active_tabs' not in st.session_state:
        st.session_state.active_tabs = []
        
    if 'selected_tab' not in st.session_state:
        st.session_state.selected_tab = 0
    if 'location' not in st.session_state:
        st.session_state.location = "Buckingham Palace, London"
    
    stored_tabs = st.session_state.active_tabs
    tabs = stored_tabs + ["+ New"]
    current_tab = st.tabs(tabs)

    mode_settings = {}
    
    # Transportation mode mapping
    available_modes = {
        "Cycling": ("bicycling", False),  # (mode, use_geoapify)
            "Driving": ("driving", False),
            "Walking": ("walking", False),
            "Transit": ("transit", True),
            "Approximate Transit": ("approximated_transit", True),
            "Bus": ("bus", True)
        }

    if st.session_state.selected_tab == len(tabs) - 1:
        # New tab content
        st.session_state.location = st.text_input("Starting Location",
                                 st.session_state.location,
                                 help="Enter an address or landmark")

        # Single mode selection
        selected_mode = st.selectbox("Transportation Mode",
                                     list(available_modes.keys()),
                                     help="Select a transportation mode")

        # Settings for selected mode
        st.subheader(f"{selected_mode} Settings")
        max_time = st.slider(f"Maximum Travel Time ({selected_mode})",
                             5,
                             60,
                             30,
                             step=5,
                             key=f"max_time_{selected_mode}")
        interval = st.slider(f"Time Interval ({selected_mode})",
                             1,
                             15,
                             5,
                             step=1,
                             key=f"interval_{selected_mode}")
        mode_settings[selected_mode] = {
            "max_time": max_time,
            "interval": interval,
            "api_mode": available_modes[selected_mode]
        }
    else:
        # Display stored contour information
        stored_result = st.session_state.stored_results[st.session_state.selected_tab]
        st.markdown("### Contour Information")
        st.text(f"Location: {st.session_state.location}")
        st.text(f"Mode: {stored_result[0]}")
        st.text(f"Maximum Time: {stored_result[2]} minutes")
        selected_mode = stored_result[0]

    # Add/Delete button based on tab
    if st.session_state.selected_tab == len(tabs) - 1:  # New tab
        st.session_state.calculate = st.button("Add Contour")
    else:
        if st.button("Delete Contour", key=f"delete_{st.session_state.selected_tab}"):
            st.session_state.stored_results.pop(st.session_state.selected_tab)
            st.session_state.active_tabs.pop(st.session_state.selected_tab)
            st.session_state.selected_tab = min(st.session_state.selected_tab, len(st.session_state.active_tabs))
            st.experimental_rerun()

# Create placeholders for the interface elements
map_placeholder = st.empty()

# Map container
map_col1, map_col2 = st.columns([4, 1])
with map_col1:
    map_container = map_placeholder.container()

with map_col2:
    map_style = st.radio("Map Style", ["Standard", "Washed out"],
                         horizontal=True)

# Initialize mode settings in session state
if 'mode_settings' not in st.session_state:
    st.session_state.mode_settings = {}
    for idx, (mode, _, max_time) in enumerate(st.session_state.stored_results):
        with st.expander(f"{mode} ({max_time}min)"):
            if st.button(f"Remove {mode}", key=f"remove_{idx}"):
                st.session_state.stored_results.pop(idx)
                st.experimental_rerun()

# Create progress container
progress_container = st.container()
with progress_container:
    progress_bar = st.progress(0)
    progress_text = st.empty()

# Main content area
try:
    visualizer = MapVisualizer()

    if getattr(st.session_state, 'calculate', False):
        new_results = []
        total_calculations = 1  # Only one mode at a time
        mode = selected_mode
        settings = mode_settings[mode]
        api_mode, use_geoapify = available_modes[mode]
        calculator = TravelTimeCalculator(location=st.session_state.location,
                                        max_time=settings["max_time"],
                                        mode=api_mode,
                                        interval=settings["interval"],
                                        use_geoapify=use_geoapify)

        base_progress = 0  # Since we only have one calculation
        progress_step = 1

        def mode_progress(message, percentage=None):
            if percentage is not None:
                progress_bar.progress(base_progress +
                                    (percentage * progress_step))
            progress_text.text(f"{mode}: {message}")

        results = calculator.calculate_travel_times(
            progress_callback=mode_progress)
        new_results.append((mode, results, settings["max_time"]))
        st.session_state.center_location = calculator.center_location

        # Store the new mode settings
        st.session_state.mode_settings[mode] = {
            "max_time": settings["max_time"],
            "interval": settings["interval"],
            "api_mode": api_mode
        }
        # Update active tabs
        new_tab_name = f"{mode} ({settings['max_time']}min)"
        if new_tab_name not in st.session_state.active_tabs:
            st.session_state.active_tabs.insert(0, new_tab_name)  # Insert at beginning
        
        # Add new results to list
        st.session_state.stored_results = st.session_state.stored_results + new_results
        # Update selected tab to the newly added contour
        st.session_state.selected_tab = len(st.session_state.stored_results) - 1
        
        # Create visualization
        st.session_state.current_fig = visualizer.create_multi_mode_map(
            st.session_state.stored_results,
            st.session_state.center_location,
            washed_out=(map_style == "Washed out"))

        # Display the map
        map_placeholder.plotly_chart(st.session_state.current_fig, use_container_width=True)

        # Clear progress indicators
        progress_text.empty()
        progress_bar.empty()

    else:
        if st.session_state.stored_results:
            st.session_state.current_fig = visualizer.create_multi_mode_map(
                st.session_state.stored_results,
                st.session_state.center_location,
                washed_out=(map_style == "Washed out"))
            map_placeholder.plotly_chart(st.session_state.current_fig, use_container_width=True)
        else:
            # Show empty map container
            map_placeholder.empty()
            st.info("Enter a location and click 'Add Contours' to begin")

except Exception as e:
    st.error(f"An error occurred: {str(e)}")
