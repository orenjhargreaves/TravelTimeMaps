import plotly.graph_objects as go
import streamlit as st
from typing import Dict, List, Tuple

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
        # Get custom color if set in session state
        color_index = next((i for i, c in enumerate(st.session_state.contours) if c == contour), 0)
        custom_color_key = f"color_{color_index}"

        if custom_color_key in st.session_state and st.session_state[custom_color_key] != "Default":
            color_options = {
                "Blue": ((135, 206, 235), (0, 0, 139)),
                "Green": ((144, 238, 144), (34, 139, 34)),
                "Red": ((255, 182, 193), (139, 0, 0)),
                "Orange": ((255, 218, 185), (210, 105, 30)),
                "Purple": ((230, 190, 255), (128, 0, 128))
            }
            start_color, end_color = color_options[st.session_state[custom_color_key]]
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

    def create_multi_mode_map(self, contours: List["Contour"], washed_out: bool = False) -> go.Figure:
        """Create a map with multiple transport mode contours."""
        if not contours:
            raise ValueError("No contours available for visualization")

        center = contours[0].center_location
        fig = go.Figure()

        for contour in contours:
            if not contour.features or not contour.features.get("features"):
                continue

            features = sorted(contour.features["features"], 
                           key=lambda x: x["properties"]["contour"],
                           reverse=True)

            # Create colorbar trace
            offset = 0.15 * contours.index(contour)
            fig.add_scattermapbox(
                lat=[None],
                lon=[None],
                mode='markers',
                marker=dict(
                    size=0,
                    colorscale=[[i/(len(features)-1), 
                               self._get_color(contour, f["properties"]["contour"])] 
                              for i, f in enumerate(features)],
                    showscale=True,
                    cmin=0,
                    cmax=contour.max_time,
                    colorbar=dict(
                        title=dict(
                            text=f"{contour.mode}",
                            side="top"
                        ),
                        x=1.02 + offset,
                        y=0,
                        yanchor='bottom',
                        len=0.06 + 0.75 * (contour.max_time / 60),
                        thickness=20,
                        orientation='v',
                        bgcolor='rgba(255,255,255,0.9)',
                        tickmode='array',
                        tickvals=[f["properties"]["contour"] for f in features],
                        ticktext=[f'{i}min' for i in [f["properties"]["contour"] for f in features]],
                        tickfont=dict(size=10),
                        titlefont=dict(size=12)
                    )
                ),
                showlegend=False
            )

            # Add contour lines
            for feature in features:
                time = feature["properties"]["contour"]
                coordinates = feature["geometry"]["coordinates"][0]
                color = self._get_color(contour, time)

                fig.add_scattermapbox(
                    lat=[coord[1] for coord in coordinates],
                    lon=[coord[0] for coord in coordinates],
                    mode='lines',
                    line=dict(
                        width=3,
                        color=color
                    ),
                    name=f'{contour.mode} - {time} min',
                    hoverinfo='text',
                    hovertext=f'{contour.mode}: {time} min',
                    showlegend=False
                )

        # Add center point
        fig.add_scattermapbox(
            lat=[center[0]],
            lon=[center[1]],
            mode='markers',
            marker=dict(size=15, color='purple'),
            showlegend=False
        )

        fig.update_layout(
            mapbox=dict(
                style='carto-positron' if not washed_out else 'carto-light',
                center=dict(lat=center[0], lon=center[1]),
                zoom=11
            ),
            height=800,
            margin=dict(l=0, r=0, t=30, b=0),
            showlegend=False
        )

        return fig