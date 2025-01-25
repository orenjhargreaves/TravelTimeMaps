import plotly.graph_objects as go
import pandas as pd
import numpy as np
from typing import Tuple
from scipy.interpolate import griddata
from scipy.ndimage import gaussian_filter
import shapely.geometry as geometry

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

        # Smooth the interpolated data
        zi = gaussian_filter(zi, sigma=1.0)

        # Create time intervals
        time_intervals = list(range(0, max_time + 5, 5))  # 5-minute intervals

        # Create filled contours for each time interval
        for i in range(len(time_intervals) - 1, -1, -1):  # Reverse order to layer properly
            lower = time_intervals[i]
            upper = time_intervals[i + 1] if i < len(time_intervals) - 1 else max_time

            # Create mask for current time interval
            mask = (zi >= lower) & (zi < upper)
            if not np.any(mask):
                continue

            # Find contour paths
            coords = []
            for y in range(grid_size):
                for x in range(grid_size):
                    if mask[y, x]:
                        coords.append((xi[x], yi[y]))

            if coords:
                try:
                    # Create polygon
                    poly = geometry.MultiPoint(coords).convex_hull
                    if poly.is_valid and not poly.is_empty:
                        # Extract coordinates
                        path_coords = list(poly.exterior.coords)

                        # Calculate color based on time interval
                        color_val = lower / max_time
                        if color_val <= 0:
                            color = 'rgb(0,255,0)'
                        elif color_val >= 1:
                            color = 'rgb(255,0,0)'
                        else:
                            if color_val <= 0.5:
                                g = 255
                                r = int(510 * color_val)
                                color = f'rgb({r},{g},0)'
                            else:
                                r = 255
                                g = int(510 * (1 - color_val))
                                color = f'rgb({r},{g},0)'

                        # Add filled path
                        fig.add_scattermapbox(
                            lat=[p[1] for p in path_coords],
                            lon=[p[0] for p in path_coords],
                            mode='lines',
                            fill='toself',
                            fillcolor=color,
                            line=dict(width=0),
                            opacity=0.5,
                            showlegend=False,
                            hoverinfo='skip',
                            name=f'{lower}-{upper} min'
                        )

                except Exception as e:
                    print(f"Error creating polygon for time interval {lower}-{upper}: {str(e)}")
                    continue

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
            fig.add_scattermapbox(
                lat=data['lat'],
                lon=data['lng'],
                mode='markers',
                marker=dict(
                    size=5,
                    color=data['duration'],
                    colorscale=self.colorscale,
                    showscale=True,
                    colorbar=dict(
                        title='Travel Time (minutes)',
                        tickmode='array',
                        tickvals=time_intervals,
                        ticktext=[f'{i}min' for i in time_intervals]
                    )
                ),
                text=data['duration'].apply(lambda x: f'{x:.1f} min'),
                hoverinfo='text',
                showlegend=False
            )

        # Update layout
        fig.update_layout(
            mapbox=dict(
                style='carto-positron',
                center=dict(lat=center[0], lon=center[1]),
                zoom=11
            ),
            height=800,
            showlegend=False,
            margin=dict(l=0, r=0, t=30, b=0)
        )

        return fig