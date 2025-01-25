import plotly.graph_objects as go
import plotly.figure_factory as ff
import pandas as pd
import numpy as np
from typing import Tuple
from scipy.interpolate import griddata
import matplotlib.pyplot as plt
import math

class MapVisualizer:
    def __init__(self):
        """Initialize the map visualizer with default settings."""
        self.colorscale = [
            [0, 'rgb(0,255,0)'],      # Green for shortest times
            [0.5, 'rgb(255,255,0)'],   # Yellow for medium times
            [1, 'rgb(255,0,0)']        # Red for longest times
        ]

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

        # Create a fine grid for interpolation
        grid_size = 100
        lat_min, lat_max = data['lat'].min(), data['lat'].max()
        lng_min, lng_max = data['lng'].min(), data['lng'].max()

        # Add padding to avoid edge effects
        lat_pad = (lat_max - lat_min) * 0.1
        lng_pad = (lng_max - lng_min) * 0.1
        lat_min -= lat_pad
        lat_max += lat_pad
        lng_min -= lng_pad
        lng_max += lng_pad

        lat_grid = np.linspace(lat_min, lat_max, grid_size)
        lng_grid = np.linspace(lng_min, lng_max, grid_size)
        lat_mesh, lng_mesh = np.meshgrid(lat_grid, lng_grid)

        # Interpolate the data using linear interpolation to prevent unrealistic islands
        grid_z = griddata(
            (data['lat'], data['lng']), 
            data['duration'],
            (lat_mesh, lng_mesh),
            method='linear',  # Changed from cubic to linear
            fill_value=max_time
        )

        # Create base figure
        fig = go.Figure()

        # Add contour lines using scattermapbox
        contour_levels = np.arange(0, max_time + 1, 5)  # 5-minute intervals

        # Create contour plot
        contours = plt.contour(lng_grid, lat_grid, grid_z, levels=contour_levels)
        plt.close()  # Close the matplotlib figure

        # Extract and plot each contour level
        for i, segs in enumerate(contours.allsegs):
            level = contours.levels[i]
            level_color = self._get_color_for_value(level, max_time)

            for segment in segs:
                if len(segment) > 1:  # Only add if we have a valid line
                    # Add contour line
                    fig.add_trace(go.Scattermapbox(
                        lon=segment[:, 0],
                        lat=segment[:, 1],
                        mode='lines',
                        line=dict(
                            width=2,
                            color=level_color
                        ),
                        hovertemplate=f'{int(level)} minutes<extra></extra>',
                        showlegend=False
                    ))

                    # Add text labels along the contour (visible when zoomed)
                    # Place labels at regular intervals along the contour
                    num_labels = max(1, len(segment) // 50)  # Adjust density of labels
                    label_indices = np.linspace(0, len(segment)-1, num_labels, dtype=int)

                    for idx in label_indices:
                        # Calculate label offset perpendicular to the contour
                        if idx > 0:  # Skip first point if we can't calculate direction
                            # Calculate direction vector of the contour
                            dx = segment[idx, 0] - segment[idx-1, 0]
                            dy = segment[idx, 1] - segment[idx-1, 1]
                            # Normalize and rotate 90 degrees for perpendicular offset
                            length = math.sqrt(dx*dx + dy*dy)
                            if length > 0:
                                # Offset by 0.0003 degrees (roughly 30 meters)
                                offset_x = -dy/length * 0.0003
                                offset_y = dx/length * 0.0003
                                # Calculate angle for text rotation
                                angle = math.degrees(math.atan2(dy, dx))

                                fig.add_trace(go.Scattermapbox(
                                    lon=[segment[idx, 0] + offset_x],
                                    lat=[segment[idx, 1] + offset_y],
                                    mode='text',
                                    text=[f'{int(level)}min'],
                                    textfont=dict(
                                        size=12,
                                        color=level_color
                                    ),
                                    textangle=angle,  # Rotate text to follow contour
                                    showlegend=False,
                                    hoverinfo='none'
                                ))

        # Add data points (small and semi-transparent)
        fig.add_trace(go.Scattermapbox(
            lat=data['lat'],
            lon=data['lng'],
            mode='markers',
            marker=dict(
                size=4,
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
            name='Starting Point',
            showlegend=False
        ))

        # Create a colorbar trace
        fig.add_trace(go.Scattermapbox(
            lat=[None],
            lon=[None],
            mode='markers',
            marker=dict(
                colorscale=self.colorscale,
                showscale=True,
                cmin=0,
                cmax=max_time,
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
            showlegend=False
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
            showlegend=False,
            margin=dict(l=0, r=0, t=30, b=0)
        )

        return fig