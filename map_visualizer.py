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
        
        Args:
            data: DataFrame with lat, lng, and duration columns
            center: Tuple of (latitude, longitude) for the starting point
            max_time: Maximum travel time in minutes
        
        Returns:
            Plotly Figure object
        """
        # Create the base map
        fig = go.Figure()
        
        # Add the contour layer
        fig.add_trace(go.Contourcarpet(
            a=data['lat'],
            b=data['lng'],
            z=data['duration'],
            colorscale=self.colorscale,
            contours=dict(
                start=0,
                end=max_time,
                size=15,  # Contour lines every 15 minutes
                showlabels=True,
                labelfont=dict(size=12, color='white')
            ),
            colorbar=dict(
                title='Travel Time (minutes)',
                thickness=15,
                len=0.9,
                tickfont=dict(size=12)
            )
        ))
        
        # Add the center point marker
        fig.add_trace(go.Scattergeo(
            lon=[center[1]],
            lat=[center[0]],
            mode='markers',
            marker=dict(
                size=10,
                color='blue',
                symbol='star'
            ),
            name='Starting Point'
        ))
        
        # Configure the map layout
        fig.update_layout(
            title='Travel Time Contours',
            mapbox=dict(
                style='carto-positron',
                center=dict(lat=center[0], lon=center[1]),
                zoom=11
            ),
            height=800,
            showlegend=True
        )
        
        return fig
