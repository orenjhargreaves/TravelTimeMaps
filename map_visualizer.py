import plotly.graph_objects as go
import streamlit as st
import numpy as np
from typing import List

class MapVisualizer:
    def __init__(self):
        self.mode_colors = {
            "Cycling": ((144, 238, 144), (34, 139, 34)),    # Light green to dark green
            "Walking": ((255, 182, 193), (139, 0, 0)),      # Light red to dark red
            "Driving": ((135, 206, 235), (0, 0, 139)),      # Light blue to dark blue
            "Transit": ((255, 218, 185), (210, 105, 30)),   # Light orange to dark orange
            "Approximate Transit": ((255, 192, 203), (178, 34, 34)),  # Light pink to dark red
            "Bus": ((255, 218, 185), (210, 105, 30))        # Light orange to dark orange
        }

    def _get_color(self, contour, time: int, base_opacity: float = 0.6) -> str:
        """Calculate color based on mode and time proportion with hue transition"""
        color_options = {
            "Blue": ((135, 206, 235), (0, 0, 139)),
            "Green": ((144, 238, 144), (34, 139, 34)),
            "Red": ((255, 182, 193), (139, 0, 0)),
            "Orange": ((255, 218, 185), (210, 105, 30)),
            "Purple": ((230, 190, 255), (128, 0, 128))
        }

        if contour.color != "Default" and contour.color in color_options:
            start_color, end_color = color_options[contour.color]
        else:
            # Use default mode colors
            start_color, end_color = self.mode_colors.get(contour.mode, ((128, 128, 128), (64, 64, 64)))

        progress = time / contour.max_time

        # Interpolate between colors
        r = int(start_color[0] + (end_color[0] - start_color[0]) * progress)
        g = int(start_color[1] + (end_color[1] - start_color[1]) * progress)
        b = int(start_color[2] + (end_color[2] - start_color[2]) * progress)

        opacity = base_opacity + (0.4 * (1 - progress))

        return f'rgba({r},{g},{b},{opacity})'

    def create_multi_mode_map(self, contours: List["Contour"]) -> go.Figure:
        """Create a map with multiple transport mode contours."""
        visible = [
            c for c in contours
            if getattr(c, 'visible', True) and c.features and c.features.get("features")
        ]

        if not visible:
            raise ValueError("No visible contours to display")

        center = visible[0].center_location
        fig = go.Figure()

        # Collect all unique times across visible contours for width/dash scaling
        for contour in visible:
            features = sorted(contour.features["features"],
                           key=lambda x: x["properties"]["contour"],
                           reverse=True)

            group_id = f"{contour.mode}_{contour.location}"
            legend_added = False
            band_style = getattr(contour, 'band_style', 'None')

            # For width+dash, gather unique times for this contour
            times_sorted = sorted(set(f["properties"]["contour"] for f in contour.features["features"]))
            n_times = len(times_sorted)
            dash_cycle = ["solid", "dot", "dash", "longdash", "dashdot", "longdashdot"]

            # Track which times have had a number label placed (one label per time value)
            labelled_times = set()

            for feature in features:
                time = feature["properties"]["contour"]
                coordinates = feature["geometry"]["coordinates"][0]
                color = self._get_color(contour, time)

                if band_style == "Width + dash":
                    rank = times_sorted.index(time) if time in times_sorted else 0
                    line_width = 1.5 + (rank / max(n_times - 1, 1)) * 3.5
                    dash = dash_cycle[rank % len(dash_cycle)]
                else:
                    line_width = 3
                    dash = "solid"

                show_in_legend = not legend_added
                if show_in_legend:
                    legend_added = True

                fig.add_scattermapbox(
                    lat=[coord[1] for coord in coordinates],
                    lon=[coord[0] for coord in coordinates],
                    mode='lines',
                    line=dict(width=line_width, color=color, dash=dash),
                    name=getattr(contour, 'name', contour.mode),
                    legendgroup=group_id,
                    showlegend=show_in_legend,
                    hoverinfo='text',
                    hovertext=f'{contour.mode}: {time} min',
                )

                # Numbers method: one label per time value at the northernmost point
                if band_style == "Numbers" and time not in labelled_times:
                    labelled_times.add(time)
                    north_idx = max(range(len(coordinates)), key=lambda i: coordinates[i][1])
                    label_lon, label_lat = coordinates[north_idx]
                    fig.add_scattermapbox(
                        lat=[label_lat],
                        lon=[label_lon],
                        mode='markers+text',
                        marker=dict(size=16, color=color, opacity=0.9),
                        text=[str(time)],
                        textfont=dict(size=9, color='white'),
                        textposition='middle center',
                        name=getattr(contour, 'name', contour.mode),
                        legendgroup=group_id,
                        showlegend=False,
                        hoverinfo='text',
                        hovertext=f'{time} min',
                    )

        # One pin per unique origin
        seen_locations = set()
        for contour in visible:
            if contour.location not in seen_locations:
                seen_locations.add(contour.location)
                clat, clon = contour.center_location
                fig.add_scattermapbox(
                    lat=[clat],
                    lon=[clon],
                    mode='markers',
                    marker=dict(size=18, symbol='marker', color='#E63946'),
                    showlegend=False,
                    hoverinfo='text',
                    hovertext=contour.location,
                )

        single_origin = len(seen_locations) == 1
        title_text = visible[0].location if single_origin else ""
        top_margin = 50 if single_origin else 30

        fig.update_layout(
            mapbox=dict(
                style='carto-positron',
                center=dict(lat=center[0], lon=center[1]),
                zoom=11,
                domain={'x': [0, 1], 'y': [0, 1]}
            ),
            height=800,
            margin=dict(l=0, r=0, t=top_margin, b=0),
            title=dict(
                text=title_text,
                x=0.5,
                xanchor='center',
                font=dict(size=15),
            ),
            showlegend=True,
            legend=dict(
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=0.01,
                bgcolor="rgba(255,255,255,0.85)",
                bordercolor="rgba(0,0,0,0.2)",
                borderwidth=1,
                font=dict(size=13),
            ),
            bargap=0,
            bargroupgap=0.2
        )

        return fig