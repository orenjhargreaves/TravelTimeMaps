import plotly.graph_objects as go
import pandas as pd
import numpy as np
from typing import Tuple

class MapVisualizer:
    def __init__(self):
        """Initialize the map visualizer with default settings."""
        self.colorscale = [
            [0, 'rgb(0,255,0)'],      # Green for shortest times
            [0.5, 'rgb(255,255,0)'],   # Yellow for medium times
            [1, 'rgb(255,0,0)']        # Red for longest times
        ]

    def create_contour_map(
        self,
        data: pd.DataFrame,
        center: Tuple[float, float],
        max_time: int
    ) -> go.Figure:
        """
        Create a contour map visualization using Plotly.
        """
        # Validate input data
        if data is None or data.empty:
            raise ValueError("No travel time data available for visualization")

        if not all(col in data.columns for col in ['lat', 'lng', 'duration']):
            raise ValueError("Data must contain 'lat', 'lng', and 'duration' columns")

        # Create base figure
        fig = go.Figure()

        # Add contour scatter points
        fig.add_trace(go.Scattermapbox(
            lat=data['lat'].values,  # Explicitly convert to numpy array
            lon=data['lng'].values,  # Explicitly convert to numpy array
            mode='markers',
            marker=dict(
                size=10,
                color=data['duration'].values,  # Explicitly convert to numpy array
                colorscale=self.colorscale,
                showscale=True,
                colorbar=dict(
                    title='Travel Time (minutes)',
                    thickness=15,
                    len=0.9
                ),
                cmin=0,
                cmax=max_time
            ),
            text=data['duration'].apply(lambda x: f'{x:.1f} minutes'),
            hoverinfo='text'
        ))

        # Add center point
        fig.add_trace(go.Scattermapbox(
            lat=[center[0]],
            lon=[center[1]],
            mode='markers',
            marker=dict(
                size=15,
                color='blue',
                symbol='star'
            ),
            name='Starting Point'
        ))

        # Update layout with mapbox
        fig.update_layout(
            title='Travel Time Contours',
            mapbox=dict(
                style='carto-positron',  # Use Carto basemap (no API key needed)
                center=dict(lat=center[0], lon=center[1]),
                zoom=11
            ),
            height=800,
            showlegend=True,
            margin=dict(l=0, r=0, t=30, b=0)
        )

        return fig