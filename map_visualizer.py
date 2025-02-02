import plotly.graph_objects as go
from typing import Dict, Tuple

class MapVisualizer:
    def __init__(self):
        self.colorscale = [
            [0, 'rgb(0,255,0)'],     # Green for shortest times
            [0.5, 'rgb(255,255,0)'], # Yellow for medium times
            [1, 'rgb(255,0,0)']      # Red for longest times
        ]
        self.opacity = 0.5

    def create_contour_map(self, data: Dict, center: Tuple[float, float], max_time: int, show_raw_data: bool = False) -> go.Figure:
        if not data or "features" not in data:
            raise ValueError("No isochrone data available for visualization")

        fig = go.Figure()

        # Add colorbar
        time_intervals = [feature["properties"]["contour"] for feature in data["features"]]
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

        # Plot isochrones from largest to smallest
        for feature in reversed(data["features"]):
            time = feature["properties"]["contour"]
            coordinates = feature["geometry"]["coordinates"][0]

            # Calculate color based on time
            color_val = time / max_time
            if color_val <= 0:
                color = f'rgba(0,255,0,{self.opacity})'
            elif color_val >= 1:
                color = f'rgba(255,0,0,{self.opacity})'
            else:
                if color_val <= 0.5:
                    g = 255
                    r = int(510 * color_val)
                else:
                    r = 255
                    g = int(510 * (1 - color_val))
                color = f'rgba({r},{g},0,{self.opacity})'

            # Add polygon
            fig.add_scattermapbox(
                lat=[coord[1] for coord in coordinates],
                lon=[coord[0] for coord in coordinates],
                mode='lines',
                fill='toself',
                fillcolor=color,
                line=dict(width=0),
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