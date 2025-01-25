import plotly.graph_objects as go
import pandas as pd
import numpy as np
from typing import Tuple
from scipy.interpolate import griddata
from scipy.ndimage import gaussian_filter
import shapely.geometry as geometry
from shapely.ops import unary_union
import geopandas as gpd

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

        # Create contour regions for each time interval
        time_intervals = list(range(0, max_time + 5, 5))  # 5-minute intervals
        contours = []

        for i in range(len(time_intervals) - 1):
            lower = time_intervals[i]
            upper = time_intervals[i + 1]

            # Create mask for current time interval
            mask = (zi >= lower) & (zi < upper)

            if not np.any(mask):
                continue

            # Create coordinates for the contour
            coords = []
            for y in range(grid_size):
                for x in range(grid_size):
                    if mask[y, x]: # Corrected condition here
                        # Swap x,y to lng,lat for geojson format
                        coords.append((xi[x], yi[y]))

            if coords:
                try:
                    # Create polygon for the time interval
                    poly = geometry.MultiPoint(coords).convex_hull
                    if poly.is_valid and not poly.is_empty:
                        # Extract coordinates in the correct format for geojson
                        coord_list = [[[lng, lat] for lat, lng in poly.exterior.coords]]
                        contours.append({
                            'type': 'Feature',
                            'geometry': {
                                'type': 'Polygon',
                                'coordinates': coord_list
                            },
                            'properties': {
                                'time': lower
                            }
                        })
                except Exception as e:
                    print(f"Error creating polygon for time interval {lower}-{upper}: {str(e)}")
                    continue

        if not contours:
            raise ValueError("No valid contours could be created from the data")

        # Create a FeatureCollection
        geojson_data = {
            'type': 'FeatureCollection',
            'features': contours
        }

        # Add choropleth layer
        fig.add_choroplethmapbox(
            geojson=geojson_data,
            locations=[f.get('properties', {}).get('time') for f in contours],
            z=[f.get('properties', {}).get('time') for f in contours],
            featureidkey='properties.time',
            colorscale=self.colorscale,
            zmin=0,
            zmax=max_time,
            showscale=True,
            colorbar=dict(
                title='Travel Time (minutes)',
                thickness=15,
                len=0.9,
                tickfont=dict(size=12),
                tickmode='array',
                tickvals=time_intervals,
                ticktext=[f'{i}min' for i in time_intervals]
            ),
            hovertemplate='%{z} minutes<extra></extra>',
            marker=dict(opacity=0.7),
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