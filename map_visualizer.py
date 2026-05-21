import base64
import numpy as np
import plotly.graph_objects as go
from typing import List

_MAP_H = 800      # figure height in px
_MAP_W = 900      # effective map width assumption (px); used only for paper-coord scaling

# Paper-coordinate measurements
_SWATCH_W = 60 / _MAP_W    # ~0.067
_SWATCH_H = 14 / _MAP_H    # 0.0175
_PAD_X    = 10 / _MAP_W    # left/right padding inside box
_PAD_Y    = 10 / _MAP_H    # top/bottom padding inside box
_ROW_H    = 30 / _MAP_H    # vertical step per legend row
_GAP      = 8  / _MAP_W    # gap between swatch and label

# Legend box left edge and top edge (paper coords)
_BOX_X0 = 0.01
_BOX_Y1 = 0.99
_BOX_X1 = _BOX_X0 + _PAD_X + _SWATCH_W + _GAP + 0.10  # 0.10 for label text


class MapVisualizer:
    def __init__(self):
        pass

    @staticmethod
    def _hex_to_rgb(hex_color: str) -> tuple:
        h = hex_color.lstrip('#')
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

    def _get_color(self, contour, time: int, base_opacity: float = 0.6) -> str:
        start_color = self._hex_to_rgb(getattr(contour, 'start_color_hex', '#AAAAAA'))
        end_color   = self._hex_to_rgb(getattr(contour, 'end_color_hex',   '#333333'))

        progress = time / contour.max_time
        r = int(start_color[0] + (end_color[0] - start_color[0]) * progress)
        g = int(start_color[1] + (end_color[1] - start_color[1]) * progress)
        b = int(start_color[2] + (end_color[2] - start_color[2]) * progress)
        opacity = base_opacity + (0.4 * (1 - progress))

        return f'rgba({r},{g},{b},{opacity})'

    @staticmethod
    def _gradient_svg(start_hex: str, end_hex: str, w: int = 60, h: int = 14) -> str:
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">'
            '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="0">'
            f'<stop offset="0%" stop-color="{start_hex}"/>'
            f'<stop offset="100%" stop-color="{end_hex}"/>'
            '</linearGradient></defs>'
            f'<rect width="{w}" height="{h}" fill="url(#g)" rx="2"/>'
            '</svg>'
        )
        return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()

    def _legend_items(self, visible, single_origin):
        """Return (images, annotations, shapes) for the custom gradient legend."""
        n_rows = len(visible) + 1  # contours + pin row
        box_h = _PAD_Y * 2 + n_rows * _ROW_H
        box_y0 = _BOX_Y1 - box_h

        images = []
        annotations = []

        swatch_x = _BOX_X0 + _PAD_X
        label_x  = swatch_x + _SWATCH_W + _GAP

        for i, contour in enumerate(visible):
            # Top of swatch in paper coords (yanchor='top')
            swatch_top = _BOX_Y1 - _PAD_Y - i * _ROW_H
            swatch_mid = swatch_top - _SWATCH_H / 2

            images.append(dict(
                source=self._gradient_svg(contour.start_color_hex, contour.end_color_hex),
                xref="paper", yref="paper",
                x=swatch_x,
                y=swatch_top,
                sizex=_SWATCH_W,
                sizey=_SWATCH_H,
                xanchor="left",
                yanchor="top",
                layer="above",
            ))

            annotations.append(dict(
                text=contour.name,
                x=label_x,
                y=swatch_mid,
                xref="paper", yref="paper",
                xanchor="left", yanchor="middle",
                showarrow=False,
                font=dict(size=12, color="#222222"),
            ))

        # Pin row
        pin_row_top = _BOX_Y1 - _PAD_Y - len(visible) * _ROW_H
        pin_mid = pin_row_top - _SWATCH_H / 2
        pin_label = "Origin" if single_origin else "Origins"

        annotations.append(dict(
            text=f'<b style="color:#E63946;">●</b> {pin_label}',
            x=swatch_x,
            y=pin_mid,
            xref="paper", yref="paper",
            xanchor="left", yanchor="middle",
            showarrow=False,
            font=dict(size=12, color="#222222"),
        ))

        shapes = [dict(
            type="rect",
            xref="paper", yref="paper",
            x0=_BOX_X0, y0=box_y0,
            x1=_BOX_X1, y1=_BOX_Y1,
            fillcolor="rgba(255,255,255,0.88)",
            line=dict(color="rgba(0,0,0,0.18)", width=1),
            layer="above",
        )]

        return images, annotations, shapes

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

        # ── Contour line traces ───────────────────────────────────────────────
        for contour in visible:
            features = sorted(contour.features["features"],
                              key=lambda x: x["properties"]["contour"],
                              reverse=True)

            group_id = f"{contour.mode}_{contour.location}"
            band_style = getattr(contour, 'band_style', 'None')
            times_sorted = sorted(set(f["properties"]["contour"] for f in contour.features["features"]))
            n_times = len(times_sorted)
            labelled_times = set()

            for feature in features:
                time = feature["properties"]["contour"]
                coordinates = feature["geometry"]["coordinates"][0]
                color = self._get_color(contour, time)

                if band_style == "Width":
                    rank = times_sorted.index(time) if time in times_sorted else 0
                    line_width = 1.5 + (rank / max(n_times - 1, 1)) * 3.5
                else:
                    line_width = 3

                fig.add_scattermapbox(
                    lat=[coord[1] for coord in coordinates],
                    lon=[coord[0] for coord in coordinates],
                    mode='lines',
                    line=dict(width=line_width, color=color),
                    legendgroup=group_id,
                    showlegend=False,
                    hoverinfo='text',
                    hovertext=f'{contour.name}: {time} min',
                )

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
                        legendgroup=group_id,
                        showlegend=False,
                        hoverinfo='text',
                        hovertext=f'{time} min',
                    )

        # ── Origin pin(s) ─────────────────────────────────────────────────────
        seen_locations = set()
        for contour in visible:
            if contour.location not in seen_locations:
                seen_locations.add(contour.location)
                clat, clon = contour.center_location
                fig.add_scattermapbox(
                    lat=[clat],
                    lon=[clon],
                    mode='markers',
                    marker=dict(size=14, color='#E63946'),
                    showlegend=False,
                    hoverinfo='text',
                    hovertext=contour.location,
                )

        single_origin = len(seen_locations) == 1
        title_text = visible[0].location if single_origin else ""
        top_margin = 50 if single_origin else 30

        images, annotations, shapes = self._legend_items(visible, single_origin)

        fig.update_layout(
            mapbox=dict(
                style='open-street-map',
                center=dict(lat=center[0], lon=center[1]),
                zoom=11,
            ),
            height=_MAP_H,
            margin=dict(l=0, r=20, t=top_margin, b=0),
            title=dict(
                text=title_text,
                x=0.5,
                xanchor='center',
                font=dict(size=15),
            ),
            showlegend=False,
            images=images,
            annotations=annotations,
            shapes=shapes,
        )

        return fig

    # ── Fastest-mode map ─────────────────────────────────────────────────────

    @staticmethod
    def _mid_color(contour, opacity: float = 0.6) -> str:
        """Blend start and end hex colours at 50% and return an rgba string."""
        sr, sg, sb = MapVisualizer._hex_to_rgb(contour.start_color_hex)
        er, eg, eb = MapVisualizer._hex_to_rgb(contour.end_color_hex)
        return f"rgba({(sr+er)//2},{(sg+eg)//2},{(sb+eb)//2},{opacity})"

    def create_fastest_mode_map(self, result: dict) -> go.Figure:
        """
        Render a rasterised map where each grid cell is filled with the colour
        of the transport mode that reaches it fastest.

        Cells are rendered as geo-referenced filled rectangles (Scattermapbox
        fill='toself'), so they scale correctly when the map is zoomed.
        """
        contours = result["contours"]
        lats     = result["lats"]
        lons     = result["lons"]
        win_idx  = result["winning_idx"]
        bad      = result["unreachable"]
        g        = result["grid_size"]

        # Cell half-extents from the meshgrid layout
        half_lon = (lons[1] - lons[0]) / 2
        half_lat = (lats[g] - lats[0]) / 2

        fig = go.Figure()

        for ci, contour in enumerate(contours):
            mask = (win_idx == ci) & ~bad
            if not mask.any():
                continue

            fill_color = self._mid_color(contour, opacity=0.55)

            # Build one closed rectangle per cell, separated by None.
            # fill='toself' fills each segment independently.
            cell_lats: list = []
            cell_lons: list = []
            for lat, lon in zip(lats[mask], lons[mask]):
                lo, hi_lo = lon - half_lon, lat - half_lat
                hi_lon, hi = lon + half_lon, lat + half_lat
                cell_lats += [hi_lo, hi_lo, hi,    hi,    hi_lo, None]
                cell_lons += [lo,    hi_lon, hi_lon, lo,   lo,    None]

            fig.add_scattermapbox(
                lat=cell_lats,
                lon=cell_lons,
                mode="lines",
                fill="toself",
                fillcolor=fill_color,
                line=dict(width=0, color=fill_color),
                name=contour.name,
                showlegend=True,
                hoverinfo="skip",
            )

        # Origin pin(s)
        seen: set = set()
        for contour in contours:
            if contour.location not in seen:
                seen.add(contour.location)
                clat, clon = contour.center_location
                fig.add_scattermapbox(
                    lat=[clat], lon=[clon],
                    mode="markers",
                    marker=dict(size=14, color="#E63946"),
                    name="Origin",
                    showlegend=True,
                    hoverinfo="text",
                    hovertext=contour.location,
                )

        center = contours[0].center_location
        fig.update_layout(
            mapbox=dict(
                style="open-street-map",
                center=dict(lat=center[0], lon=center[1]),
                zoom=11,
            ),
            height=_MAP_H,
            margin=dict(l=0, r=20, t=10, b=0),
            showlegend=True,
            legend=dict(
                yanchor="top", y=0.99,
                xanchor="left", x=0.01,
                bgcolor="rgba(255,255,255,0.88)",
                bordercolor="rgba(0,0,0,0.18)",
                borderwidth=1,
                font=dict(size=12),
            ),
        )
        return fig
