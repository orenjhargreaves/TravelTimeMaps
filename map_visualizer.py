
import plotly.graph_objects as go
from typing import Dict, Tuple

class MapVisualizer:
    def __init__(self):
        self.opacity = 1.0

    def _get_color(self, time: int, max_time: int) -> str:
        """Calculate color based on time proportion"""
        color_val = time / max_time
        if color_val <= 0:
            return 'rgb(0,255,0)'  # Green
        elif color_val >= 1:
            return 'rgb(255,0,0)'  # Red
        else:
            if color_val <= 0.5:
                g = 255
                r = int(510 * color_val)
            else:
                r = 255
                g = int(510 * (1 - color_val))
            return f'rgb({r},{g},0)'

    def create_contour_map(self, data: Dict, center: Tuple[float, float], max_time: int, show_raw_data: bool = False) -> go.Figure:
        if not data or "features" not in data:
            raise ValueError("No isochrone data available for visualization")

        fig = go.Figure()

        # Add colorbar
        time_intervals = [feature["properties"]["contour"] for feature in data["features"]]
        colorscale = [[i/(len(time_intervals)-1), self._get_color(t, max_time)] for i, t in enumerate(time_intervals)]
        
        fig.add_scattermapbox(
            lat=[None], lon=[None],
            mode='markers',
            marker=dict(
                size=0,
                colorscale=colorscale,
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

        # Plot contour lines from largest to smallest
        for feature in reversed(data["features"]):
            time = feature["properties"]["contour"]
            coordinates = feature["geometry"]["coordinates"][0]
            color = self._get_color(time, max_time)

            # Add contour line
            fig.add_scattermapbox(
                lat=[coord[1] for coord in coordinates],
                lon=[coord[0] for coord in coordinates],
                mode='lines',
                line=dict(
                    width=3,
                    color=color
                ),
                showlegend=False,
                hoverinfo='text',
                hovertext=f'{time} min',
                name=f'{time} min'
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
