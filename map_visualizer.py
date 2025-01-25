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

        # Create heatmap using scattermapbox
        heatmap_points = []
        for i in range(grid_size):
            for j in range(grid_size):
                if not np.isnan(zi[i, j]):
                    heatmap_points.append({
                        'lat': yi[i],
                        'lon': xi[j],
                        'duration': zi[i, j]
                    })

        # Convert to DataFrame for easier handling
        heatmap_df = pd.DataFrame(heatmap_points)

        # Add heatmap layer
        fig.add_scattermapbox(
            lat=heatmap_df['lat'],
            lon=heatmap_df['lon'],
            mode='markers',
            marker=dict(
                size=8,  # Reduced size for better blending
                color=heatmap_df['duration'],
                colorscale=self.colorscale,
                opacity=0.8,  # Increased opacity
                showscale=True,
                cmin=0,  # Set minimum value
                cmax=max_time,  # Set maximum value
                colorbar=dict(
                    title='Travel Time (minutes)',
                    thickness=15,
                    len=0.9,
                    tickfont=dict(size=12),
                    tickmode='array',
                    tickvals=list(range(0, max_time + 1, 5)),
                    ticktext=[f'{i}min' for i in range(0, max_time + 1, 5)]
                )
            ),
            hovertemplate='%{marker.color:.1f} minutes<extra></extra>',
            showlegend=False
        )

        # Add data points (optimized for performance)
        if show_raw_data:
            # Subsample points if there are too many
            max_points = 200
            if len(data) > max_points:
                data = data.sample(n=max_points)

            fig.add_scattermapbox(
                lat=data['lat'],
                lon=data['lng'],
                mode='markers+text',
                marker=dict(
                    size=8,
                    color=data['duration'],
                    colorscale=self.colorscale,
                    opacity=1.0,
                    showscale=False
                ),
                text=data['duration'].apply(lambda x: f'{x:.1f}min'),
                textposition="top center",
                hovertemplate='<b>Travel Time:</b> %{text}<extra></extra>',
                showlegend=False
            )

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

        # Update layout with proper mapbox configuration
        fig.update_layout(
            mapbox=dict(
                style='carto-positron',
                center=dict(lat=center[0], lon=center[1]),
                zoom=11,
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

    def _get_color_for_value(self, value: float, max_value: float) -> str:
        """Get color for a specific value using the colorscale."""
        ratio = value / max_value
        if ratio <= 0:
            return 'rgb(0,255,0)'
        elif ratio >= 1:
            return 'rgb(255,0,0)'
        else:
            if ratio <= 0.5:
                # Interpolate between green and yellow
                g = 255
                r = int(510 * ratio)  # 0->255 as ratio goes 0->0.5
                return f'rgb({r},{g},0)'
            else:
                # Interpolate between yellow and red
                r = 255
                g = int(510 * (1 - ratio))  # 255->0 as ratio goes 0.5->1
                return f'rgb({r},{g},0)'