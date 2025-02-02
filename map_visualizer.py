
import plotly.graph_objects as go
from typing import Dict, List, Tuple

class MapVisualizer:
    def __init__(self):
        self.mode_colors = {
            "Cycling": (0, 255, 0),  # Green
            "Walking": (255, 0, 0),  # Red
            "Driving": (0, 0, 255),  # Blue
            "Transit": (255, 165, 0),  # Orange
            "Approximate Transit": (255, 69, 0)  # Red-Orange
        }

    def _get_color(self, mode: str, time: int, max_time: int, base_opacity: float = 0.6) -> str:
        """Calculate color based on mode and time proportion with hue transition"""
        # Base colors for each mode (start and end colors)
        mode_color_ranges = {
            "Cycling": ((144, 238, 144), (34, 139, 34)),    # Light green to dark green
            "Walking": ((255, 182, 193), (139, 0, 0)),      # Light red to dark red
            "Driving": ((135, 206, 235), (0, 0, 139)),      # Light blue to dark blue
            "Transit": ((255, 218, 185), (210, 105, 30)),   # Light orange to dark orange
            "Approximate Transit": ((255, 192, 203), (178, 34, 34))  # Light pink to dark red
        }

        if mode not in mode_color_ranges:
            return f'rgba(128,128,128,{base_opacity})'

        start_color, end_color = mode_color_ranges[mode]
        progress = time / max_time

        # Interpolate between colors
        r = int(start_color[0] + (end_color[0] - start_color[0]) * progress)
        g = int(start_color[1] + (end_color[1] - start_color[1]) * progress)
        b = int(start_color[2] + (end_color[2] - start_color[2]) * progress)
        
        opacity = base_opacity + (0.4 * (1 - progress))
        
        return f'rgba({r},{g},{b},{opacity})'

    def create_multi_mode_map(self, results: List[Tuple[str, Dict, int]], center: Tuple[float, float], washed_out: bool = False) -> go.Figure:
        """Create a map with multiple transport mode contours."""
        if not results:
            raise ValueError("No isochrone data available for visualization")

        fig = go.Figure()

        # Add contour lines for each mode from largest to smallest time
        for mode, data, max_time in results:
            if not data.get("features"):
                continue

            # Sort features by contour time (descending)
            features = sorted(data["features"], 
                           key=lambda x: x["properties"]["contour"],
                           reverse=True)

            # Create a separate trace for the colorbar
            offset = 0.15 * results.index((mode, data, max_time))
            fig.add_scattermapbox(
                lat=[None],
                lon=[None],
                mode='markers',
                marker=dict(
                    size=0,
                    colorscale=[[i/(len(features)-1), 
                               self._get_color(mode, f["properties"]["contour"], max_time)] 
                              for i, f in enumerate(features)],
                    showscale=True,
                    cmin=0,
                    cmax=max_time,
                    colorbar=dict(
                        title=dict(
                            text=f"{mode}",
                            side="top"
                        ),
                        x=1.02 + offset,  # Stack horizontally
                        y=0.15,  # Lower base position
                        yanchor='bottom',  # Anchor at bottom
                        len=(0.75 * max_time/60),  # Scale length proportionally to max time
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
                color = self._get_color(mode, time, max_time)

                fig.add_scattermapbox(
                    lat=[coord[1] for coord in coordinates],
                    lon=[coord[0] for coord in coordinates],
                    mode='lines',
                    line=dict(
                        width=3,
                        color=color
                    ),
                    name=f'{mode} - {time} min',
                    hoverinfo='text',
                    hovertext=f'{mode}: {time} min',
                    showlegend=False
                )

        # Add center point (without legend)
        fig.add_scattermapbox(
            lat=[center[0]],
            lon=[center[1]],
            mode='markers',
            marker=dict(size=15, color='purple', symbol='star'),
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
