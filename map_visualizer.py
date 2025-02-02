
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
        """Calculate color based on mode and time proportion with opacity"""
        if mode not in self.mode_colors:
            r, g, b = 128, 128, 128  # Default gray for unknown modes
        else:
            r, g, b = self.mode_colors[mode]

        # Calculate opacity based on time (shorter time = more opaque)
        opacity = base_opacity + (0.4 * (1 - time / max_time))
        
        return f'rgba({r},{g},{b},{opacity})'

    def create_multi_mode_map(self, results: List[Tuple[str, Dict, int]], center: Tuple[float, float]) -> go.Figure:
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
                        title=f'{mode} Time (minutes)',
                        tickmode='array',
                        tickvals=[f["properties"]["contour"] for f in features],
                        ticktext=[f'{i}min' for i in [f["properties"]["contour"] for f in features]],
                        thickness=15,
                        len=0.9,
                        x=1.02 + (0.05 * results.index((mode, data, max_time)))
                    )
                ),
                name=mode,
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
                    showlegend=True
                )

        # Add center point
        fig.add_scattermapbox(
            lat=[center[0]],
            lon=[center[1]],
            mode='markers',
            marker=dict(size=15, color='purple', symbol='star'),
            name='Starting Point',
            showlegend=True
        )

        fig.update_layout(
            mapbox=dict(
                style='carto-positron',
                center=dict(lat=center[0], lon=center[1]),
                zoom=11
            ),
            height=800,
            margin=dict(l=0, r=0, t=30, b=0),
            legend=dict(
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=0.01
            )
        )

        return fig
