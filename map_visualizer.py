import plotly.graph_objects as go
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
        max_time: int,
        show_raw_data: bool = False
    ) -> go.Figure:
        """Create a visualization using Plotly."""
        if data is None or data.empty:
            raise ValueError("No travel time data available for visualization")

        if not all(col in data.columns for col in ['lat', 'lng', 'duration']):
            raise ValueError("Data must contain 'lat', 'lng', and 'duration' columns")

        # Create the base figure
        fig = go.Figure()

        # Create optimized grid for interpolation
        grid_size = 100  # Increased for smoother visualization
        lat_min, lat_max = data['lat'].min(), data['lat'].max()
        lng_min, lng_max = data['lng'].min(), data['lng'].max()

        # Add padding to the boundaries
        lat_pad = (lat_max - lat_min) * 0.1
        lng_pad = (lng_max - lng_min) * 0.1
        lat_min -= lat_pad
        lat_max += lat_pad
        lng_min -= lng_pad
        lng_max += lng_pad

        # Create grid
        xi = np.linspace(lng_min, lng_max, grid_size)
        yi = np.linspace(lat_min, lat_max, grid_size)
        xi_mg, yi_mg = np.meshgrid(xi, yi)

        # Interpolate with higher resolution
        points = np.column_stack((data['lng'], data['lat']))
        values = data['duration'].values
        zi = griddata(points, values, (xi_mg, yi_mg), method='cubic')

        # Add contours on top of the map
        fig.add_trace(go.Contour(
            z=zi,
            x=xi,
            y=yi,
            colorscale=self.colorscale,
            opacity=0.7,
            zmin=0,
            zmax=max_time,
            showscale=True,
            contours=dict(
                start=0,
                end=max_time,
                size=5,  # 5-minute intervals
                coloring='fill'
            ),
            colorbar=dict(
                title='Travel Time (minutes)',
                thickness=15,
                len=0.9,
                tickfont=dict(size=12),
                tickmode='array',
                tickvals=list(range(0, max_time + 1, 5)),
                ticktext=[f'{i}min' for i in range(0, max_time + 1, 5)]
            ),
            hovertemplate='%{z:.1f} minutes<extra></extra>'
        ))

        # Add center point
        fig.add_scattermapbox(
            lat=[center[0]],
            lon=[center[1]],
            mode='markers',
            marker=dict(
                size=15,
                color='blue',
                symbol='star'
            ),
            name='Starting Point',
            showlegend=False
        )

        # Add data points if requested
        if show_raw_data:
            # Subsample points if there are too many
            max_points = 200
            if len(data) > max_points:
                data = data.sample(n=max_points)

            fig.add_scattermapbox(
                lat=data['lat'],
                lon=data['lng'],
                mode='markers',
                marker=dict(
                    size=8,
                    color=data['duration'],
                    colorscale=self.colorscale,
                    showscale=False
                ),
                text=data['duration'].apply(lambda x: f'{x:.1f}min'),
                hovertemplate='<b>Travel Time:</b> %{text}<extra></extra>',
                showlegend=False
            )

        # Update layout with proper configuration
        fig.update_layout(
            mapbox=dict(
                style='carto-positron',
                center=dict(lat=center[0], lon=center[1]),
                zoom=11
            ),
            dragmode='zoom',
            modebar=dict(
                orientation='v',
                bgcolor='white',
                color='black',
                activecolor='blue'
            ),
            modebar_add=['zoom', 'pan', 'reset-view'],
            height=800,
            showlegend=False,
            margin=dict(l=0, r=0, t=30, b=0),
            paper_bgcolor='white',
            plot_bgcolor='white'
        )

        return fig