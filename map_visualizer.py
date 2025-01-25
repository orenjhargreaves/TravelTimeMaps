import plotly.graph_objects as go
import plotly.figure_factory as ff
import pandas as pd
import numpy as np
from typing import Tuple
from scipy.interpolate import griddata

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

        # Add base scatter points (small and semi-transparent)
        fig.add_trace(go.Scattermapbox(
            lat=data['lat'],
            lon=data['lng'],
            mode='markers',
            marker=dict(
                size=5,
                color=data['duration'],
                colorscale=self.colorscale,
                opacity=0.3
            ),
            text=data['duration'].apply(lambda x: f'{x:.1f} minutes'),
            hoverinfo='text',
            showlegend=False
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

        # Add contour overlay
        fig.add_trace(go.Contourmapbox(
            lat=data['lat'],
            lon=data['lng'],
            z=data['duration'],
            colorscale=self.colorscale,
            contours=dict(
                start=0,
                end=max_time,
                size=5,  # 5-minute intervals
                showlabels=True,
                labelfont=dict(size=12)
            ),
            colorbar=dict(
                title='Travel Time (minutes)',
                thickness=15,
                len=0.9,
                tickfont=dict(size=12)
            ),
            name='Travel Time Contours'
        ))

        # Update layout with mapbox
        fig.update_layout(
            title='Travel Time Contours',
            mapbox=dict(
                style='carto-positron',
                center=dict(lat=center[0], lon=center[1]),
                zoom=11
            ),
            height=800,
            showlegend=True,
            margin=dict(l=0, r=0, t=30, b=0)
        )

        return fig