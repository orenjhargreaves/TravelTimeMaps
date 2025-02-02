import plotly.graph_objects as go
import pandas as pd
import numpy as np
from typing import Tuple
from scipy.interpolate import griddata
from scipy.ndimage import gaussian_filter
import shapely.geometry as geometry
import shapely.ops

class MapVisualizer:
    def __init__(self):
        self.colorscale = [
            [0, 'rgb(0,255,0)'],     # Green for shortest times
            [0.5, 'rgb(255,255,0)'], # Yellow for medium times
            [1, 'rgb(255,0,0)']      # Red for longest times
        ]
        self.opacity = 0.5

    def create_contour_map(self,
                           data: pd.DataFrame,
                           center: Tuple[float, float],
                           max_time: int,
                           show_raw_data: bool = False) -> go.Figure:
        if data is None or data.empty:
            raise ValueError("No travel time data available for visualization")
        if not all(col in data.columns for col in ['lat', 'lng', 'duration']):
            raise ValueError("Data must contain 'lat', 'lng', and 'duration' columns")

        fig = go.Figure()

        grid_size = 10000
        lat_min, lat_max = data['lat'].min(), data['lat'].max()
        lng_min, lng_max = data['lng'].min(), data['lng'].max()

        lat_pad = (lat_max - lat_min) * 0.1
        lng_pad = (lng_max - lng_min) * 0.1
        lat_min -= lat_pad
        lat_max += lat_pad
        lng_min -= lng_pad
        lng_max += lng_pad

        xi = np.linspace(lng_min, lng_max, grid_size)
        yi = np.linspace(lat_min, lat_max, grid_size)
        xi_mg, yi_mg = np.meshgrid(xi, yi)

        points = np.column_stack((data['lng'], data['lat']))
        values = data['duration'].values
        zi = griddata(points, values, (xi_mg, yi_mg), method='cubic')
        zi = gaussian_filter(zi, sigma=1.0)

        # Create colorbar trace
        time_intervals = list(range(0, max_time + 5, 5))
        fig.add_scattermapbox(
            lat=[None], lon=[None],
            mode='markers',
            marker=dict(
                size=0,
                colorscale=self.colorscale,
                showscale=True,
                cmin=0,
                cmax=max_time,
                colorbar=dict(
                    title='Travel Time (minutes)',
                    tickmode='array',
                    tickvals=time_intervals,
                    ticktext=[f'{i}min' for i in time_intervals],
                    thickness=15,
                    len=0.9,
                    x=1.02
                )
            ),
            showlegend=False
        )

        # Build polygons from smallest to largest
        inner_poly = geometry.MultiPolygon()
        polygons_to_draw = []

        for i in range(len(time_intervals) - 1):
            lower = time_intervals[i]
            upper = time_intervals[i + 1]

            mask = (zi >= lower) & (zi < upper)
            if not np.any(mask):
                continue

            coords = []
            for y in range(grid_size):
                for x in range(grid_size):
                    if mask[y, x]:
                        coords.append((xi[x], yi[y]))

            if coords:
                try:
                    poly = geometry.MultiPoint(coords).convex_hull
                    if poly.is_valid and not poly.is_empty:
                        poly = poly.difference(inner_poly)
                        if not poly.is_empty:

                            # Choose fill color
                            color_val = lower / max_time
                            if color_val <= 0:
                                color = f'rgba(0,255,0,{self.opacity})'
                            elif color_val >= 1:
                                color = f'rgba(255,0,0,{self.opacity})'
                            else:
                                if color_val <= 0.5:
                                    g = 255
                                    r = int(510 * color_val)
                                    color = f'rgba({r},{g},0,{self.opacity})'
                                else:
                                    r = 255
                                    g = int(510 * (1 - color_val))
                                    color = f'rgba({r},{g},0,{self.opacity})'

                            if poly.geom_type == 'Polygon':
                                subpolygons = [poly]
                            else:
                                subpolygons = list(poly.geoms)

                            for subpoly in subpolygons:
                                if not subpoly.is_empty:
                                    polygons_to_draw.append((subpoly, lower, upper, color))

                            inner_poly = inner_poly.union(poly)
                except Exception as e:
                    print(f"Error creating polygon for {lower}-{upper}: {e}")
                    continue

        ###################################################################
        # ### NEW: SPLIT ALONG CENTER LINE so the polygon is forcibly cut
        #           into a north half and south half. This ensures the
        #           "central line" is always visible and never fully enclosed.
        ###################################################################
        center_lat = center[0]
        # A horizontal line from (lng_min, center_lat) to (lng_max, center_lat)
        split_line = geometry.LineString([(lng_min, center_lat),
                                          (lng_max, center_lat)])

        # We will store two lists, one for sub-polygons that are above the split
        # and one for those that are below, so we can control draw order.
        polygons_north = []
        polygons_south = []

        for subpoly, lower, upper, color in polygons_to_draw:
            # Split each subpolygon with the center line
            splitted_geom = shapely.ops.split(subpoly, split_line)
            # splitted is a GeometryCollection with 1 or 2 polygons (or more if it intersects multiple times)

            # If it's a geometrycollection, iterate .geoms
            if splitted_geom.geom_type == 'GeometryCollection':
                splitted_pieces = splitted_geom.geoms
            else:
                # It's a single geometry; just wrap in a list
                splitted_pieces = [splitted_geom]

            for piece in splitted_pieces:
                if piece.is_empty:
                    continue
            
            # Check each piece's centroid to see if it's north or south
            for piece in splitted_pieces:
                if piece.is_empty:
                    continue
                if piece.centroid.y > center_lat:
                    polygons_north.append((piece, lower, upper, color))
                else:
                    polygons_south.append((piece, lower, upper, color))

        # Now we decide an order: if you want to plot the north half first,
        # then the south half, do it as follows:
        # (You could also do the opposite if you prefer.)
        # STILL we want the largest intervals to be at the bottom if you want a
        # "concentric ring" look. So we reverse each group by time as well.

        # Sort by 'lower' time ascending, then reverse if you want the largest drawn first
        polygons_north.sort(key=lambda x: x[1])  # sort by 'lower' ascending
        polygons_south.sort(key=lambda x: x[1])

        # Plot the north group from largest to smallest
        for piece, lower, upper, color in reversed(polygons_north):
            ext_coords = list(piece.exterior.coords)
            fig.add_scattermapbox(
                lat=[p[1] for p in ext_coords],
                lon=[p[0] for p in ext_coords],
                mode='lines',
                fill='toself',
                fillcolor=color,
                line=dict(width=0),
                showlegend=False,
                hoverinfo='text',
                hovertext=f'{lower}-{upper} min',
                name=f'{lower}-{upper} min'
            )
            # Interiors as holes
            for interior in piece.interiors:
                int_coords = list(interior.coords)
                fig.add_scattermapbox(
                    lat=[p[1] for p in int_coords],
                    lon=[p[0] for p in int_coords],
                    mode='lines',
                    fill='toself',
                    fillcolor='rgba(0,0,0,0)',  # transparent
                    line=dict(width=0),
                    showlegend=False,
                    hoverinfo='skip',
                )

        # Now plot the south group from largest to smallest
        for piece, lower, upper, color in reversed(polygons_south):
            ext_coords = list(piece.exterior.coords)
            fig.add_scattermapbox(
                lat=[p[1] for p in ext_coords],
                lon=[p[0] for p in ext_coords],
                mode='lines',
                fill='toself',
                fillcolor=color,
                line=dict(width=0),
                showlegend=False,
                hoverinfo='text',
                hovertext=f'{lower}-{upper} min',
                name=f'{lower}-{upper} min'
            )
            # Interiors as holes
            for interior in piece.interiors:
                int_coords = list(interior.coords)
                fig.add_scattermapbox(
                    lat=[p[1] for p in int_coords],
                    lon=[p[0] for p in int_coords],
                    mode='lines',
                    fill='toself',
                    fillcolor='rgba(0,0,0,0)',
                    line=dict(width=0),
                    showlegend=False,
                    hoverinfo='skip',
                )

        # Add center point
        fig.add_scattermapbox(
            lat=[center[0]],
            lon=[center[1]],
            mode='markers',
            marker=dict(size=15, color='blue', symbol='star'),
            name='Starting Point',
            showlegend=False
        )

        # Optionally add raw data
        if show_raw_data:
            fig.add_scattermapbox(
                lat=data['lat'],
                lon=data['lng'],
                mode='markers',
                marker=dict(
                    size=5,
                    color=data['duration'],
                    colorscale=self.colorscale,
                    showscale=False
                ),
                text=data['duration'].apply(lambda x: f'{x:.1f} min'),
                hoverinfo='text',
                showlegend=False
            )

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
