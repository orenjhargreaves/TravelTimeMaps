import plotly.graph_objects as go
import pandas as pd
import numpy as np
from typing import Tuple
from scipy.interpolate import griddata
import matplotlib.pyplot as plt
from matplotlib.tri import Triangulation, LinearTriInterpolator

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

        fig = go.Figure()

        # Create high-resolution grid for smooth interpolation
        grid_size = 200  # Increased for better resolution
        lat_min, lat_max = data['lat'].min(), data['lat'].max()
        lng_min, lng_max = data['lng'].min(), data['lng'].max()

        # Add padding to the boundaries
        lat_pad = (lat_max - lat_min) * 0.1
        lng_pad = (lng_max - lng_min) * 0.1
        lat_min -= lat_pad
        lat_max += lat_pad
        lng_min -= lng_pad
        lng_max += lng_pad

        # Create triangulation for better interpolation
        triang = Triangulation(data['lng'], data['lat'])
        interpolator = LinearTriInterpolator(triang, data['duration'])

        # Create dense grid
        xi = np.linspace(lng_min, lng_max, grid_size)
        yi = np.linspace(lat_min, lat_max, grid_size)
        xi_mg, yi_mg = np.meshgrid(xi, yi)

        # Interpolate values
        zi = interpolator(xi_mg, yi_mg)

        # Create mask for points too far from data
        mask = np.zeros_like(zi, dtype=bool)
        for i in range(len(data)):
            x, y = data.iloc[i][['lng', 'lat']]
            distances = np.sqrt((xi_mg - x)**2 + (yi_mg - y)**2)
            mask |= distances < 0.01  # Adjust this value to control the interpolation extent

        # Apply mask
        zi = np.ma.masked_array(zi, ~mask)

        # Add contour fill
        fig.add_trace(go.Contour(
            x=xi,
            y=yi,
            z=zi,
            colorscale=self.colorscale,
            opacity=0.4,
            showscale=True,
            contours=dict(
                start=0,
                end=max_time,
                size=5,
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

        # Add contour lines with better visibility
        contour_levels = np.arange(0, max_time + 1, 5)
        contours = plt.contour(xi_mg, yi_mg, zi, levels=contour_levels)
        plt.close()

        for collection, level in zip(contours.collections, contour_levels):
            paths = collection.get_paths()
            for path in paths:
                vertices = path.vertices
                if len(vertices) > 1:
                    fig.add_trace(go.Scattermapbox(
                        lon=vertices[:, 0],
                        lat=vertices[:, 1],
                        mode='lines',
                        line=dict(
                            width=2,
                            color=self._get_color_for_value(level, max_time)
                        ),
                        hovertemplate=f'{int(level)} minutes<extra></extra>',
                        showlegend=False
                    ))

        # Add data points with conditional visibility
        marker_size = 8 if show_raw_data else 4
        opacity = 1.0 if show_raw_data else 0.3

        fig.add_trace(go.Scattermapbox(
            lat=data['lat'],
            lon=data['lng'],
            mode='markers+text' if show_raw_data else 'markers',
            marker=dict(
                size=marker_size,
                color=data['duration'],
                colorscale=self.colorscale,
                opacity=opacity,
                showscale=False
            ),
            text=data['duration'].apply(lambda x: f'{x:.1f}min') if show_raw_data else None,
            textposition="top center" if show_raw_data else None,
            hovertemplate='<b>Travel Time:</b> %{text}<extra></extra>' if show_raw_data else None,
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

        fig.update_layout(
            mapbox=dict(
                style='carto-positron',
                center=dict(lat=center[0], lon=center[1]),
                zoom=11
            ),
            dragmode='zoom',
            modebar=dict(
                orientation='v',
                bgcolor='white'
            ),
            height=800,
            showlegend=False,
            margin=dict(l=0, r=0, t=30, b=0)
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