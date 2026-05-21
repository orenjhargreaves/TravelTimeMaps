import base64
import colorsys
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

    def _get_color(self, contour, time: int, base_opacity: float = 0.6, vary_opacity: bool = True) -> str:
        start_color = self._hex_to_rgb(getattr(contour, 'start_color_hex', '#AAAAAA'))
        end_color   = self._hex_to_rgb(getattr(contour, 'end_color_hex',   '#333333'))

        progress = time / contour.max_time
        r = int(start_color[0] + (end_color[0] - start_color[0]) * progress)
        g = int(start_color[1] + (end_color[1] - start_color[1]) * progress)
        b = int(start_color[2] + (end_color[2] - start_color[2]) * progress)
        opacity = base_opacity + (0.4 * (1 - progress)) if vary_opacity else base_opacity

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

    def _rgb_legend_items(self, contours, base_hex: list):
        """Legend for RGB mix mode: solid colour swatch per mode plus a brightness note."""
        n_rows = len(contours) + 2  # modes + "brighter = faster" note + pin row
        box_h = _PAD_Y * 2 + n_rows * _ROW_H
        box_y0 = _BOX_Y1 - box_h

        images, annotations = [], []
        swatch_x = _BOX_X0 + _PAD_X
        label_x  = swatch_x + _SWATCH_W + _GAP

        for i, (contour, hex_c) in enumerate(zip(contours, base_hex)):
            swatch_top = _BOX_Y1 - _PAD_Y - i * _ROW_H
            swatch_mid = swatch_top - _SWATCH_H / 2
            images.append(dict(
                source=self._gradient_svg(hex_c, hex_c),
                xref="paper", yref="paper",
                x=swatch_x, y=swatch_top,
                sizex=_SWATCH_W, sizey=_SWATCH_H,
                xanchor="left", yanchor="top", layer="above",
            ))
            annotations.append(dict(
                text=contour.name, x=label_x, y=swatch_mid,
                xref="paper", yref="paper",
                xanchor="left", yanchor="middle",
                showarrow=False, font=dict(size=12, color="#222222"),
            ))

        note_top = _BOX_Y1 - _PAD_Y - len(contours) * _ROW_H
        note_mid = note_top - _SWATCH_H / 2
        annotations.append(dict(
            text="Brighter = faster",
            x=swatch_x, y=note_mid,
            xref="paper", yref="paper",
            xanchor="left", yanchor="middle",
            showarrow=False, font=dict(size=10, color="#666666"),
        ))

        pin_top = _BOX_Y1 - _PAD_Y - (len(contours) + 1) * _ROW_H
        pin_mid = pin_top - _SWATCH_H / 2
        annotations.append(dict(
            text='<b style="color:#E63946;">●</b> Origin',
            x=swatch_x, y=pin_mid,
            xref="paper", yref="paper",
            xanchor="left", yanchor="middle",
            showarrow=False, font=dict(size=12, color="#222222"),
        ))

        shapes = [dict(
            type="rect", xref="paper", yref="paper",
            x0=_BOX_X0, y0=box_y0, x1=_BOX_X1, y1=_BOX_Y1,
            fillcolor="rgba(255,255,255,0.88)",
            line=dict(color="rgba(0,0,0,0.18)", width=1),
            layer="above",
        )]

        return images, annotations, shapes

    def create_multi_mode_map(self, contours: List["Contour"], map_style: str = "carto-positron", opacity: float = 0.65) -> go.Figure:
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
            display_interval = getattr(contour, 'display_interval', contour.interval)

            for feature in features:
                time = feature["properties"]["contour"]
                if time % display_interval != 0:
                    continue
                coordinates = feature["geometry"]["coordinates"][0]
                color = self._get_color(contour, time, base_opacity=opacity)

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
                style=map_style,
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
    def _geom_to_latlon(geom) -> tuple[list, list]:
        """Convert a Shapely Polygon or MultiPolygon to lat/lon lists with None separators."""
        polys = list(geom.geoms) if hasattr(geom, "geoms") else [geom]
        lats: list = []
        lons: list = []
        for poly in polys:
            if poly.is_empty:
                continue
            coords = list(poly.exterior.coords)
            lons += [c[0] for c in coords] + [None]
            lats += [c[1] for c in coords] + [None]
        return lats, lons

    def create_fastest_mode_map(self, result: dict, map_style: str = "open-street-map", opacity: float = 0.65) -> go.Figure:
        """
        Render a fastest-mode map using actual isochrone polygon shapes.

        Each mode's winning area is divided into time-band rings. Rings are
        rendered outer-first (lighter) so inner rings (darker, nearer origin)
        appear on top. Colours use the same gradient as the contour map.

        `result` is the dict returned by FastestModeAnalyser.analyse_vector().
        """
        bands    = result["bands"]      # [(contour, t, shapely_poly), ...]
        contours = result["contours"]

        fig = go.Figure()

        # Render outer bands first so inner (darker, nearer) bands overlay them
        for contour, t, poly in sorted(bands, key=lambda x: x[1], reverse=True):
            lats, lons = self._geom_to_latlon(poly)
            color = self._get_color(contour, t, base_opacity=opacity, vary_opacity=False)
            fig.add_scattermapbox(
                lat=lats,
                lon=lons,
                mode="lines",
                fill="toself",
                fillcolor=color,
                line=dict(width=0.3, color=color),
                showlegend=False,
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
                    showlegend=False,
                    hoverinfo="text",
                    hovertext=contour.location,
                )

        single_origin = len(seen) == 1
        images, annotations, shapes = self._legend_items(contours, single_origin)

        center = contours[0].center_location
        fig.update_layout(
            mapbox=dict(
                style=map_style,
                center=dict(lat=center[0], lon=center[1]),
                zoom=11,
            ),
            height=_MAP_H,
            margin=dict(l=0, r=20, t=10, b=0),
            showlegend=False,
            images=images,
            annotations=annotations,
            shapes=shapes,
        )
        return fig

    def create_rgb_mode_map(self, result: dict, map_style: str = "carto-positron", opacity: float = 0.65) -> go.Figure:
        """
        Render a fastest-mode map using additive RGB colour mixing.

        Each mode is assigned an evenly-spaced hue (red, green, blue for three modes).
        Each grid cell's colour is the additive mix of all modes' contributions, where
        each mode's channel intensity = its speed (1 - travel_time / max_time).
        Bright primary = one mode dominant; white = all equally fast; black = unreachable.

        Grid cells are rendered as tiled filled rectangles (same fill='toself' approach as
        the gradient view) rather than scatter markers, so there are no gaps.
        Colours are quantized to ~8 levels per channel to keep the trace count manageable.
        """
        mode_times = result["mode_times"]   # (n_modes, n_points)
        flat_lats  = result["lats"]
        flat_lons  = result["lons"]
        contours   = result["contours"]
        grid_size  = result["grid_size"]
        n_modes    = len(contours)

        # Evenly-spaced hues at full saturation and brightness
        base_rgb = [
            tuple(int(x * 255) for x in colorsys.hsv_to_rgb(i / n_modes, 1.0, 1.0))
            for i in range(n_modes)
        ]
        base_hex = [f'#{r:02x}{g:02x}{b:02x}' for r, g, b in base_rgb]

        R = np.zeros(len(flat_lats))
        G = np.zeros(len(flat_lats))
        B = np.zeros(len(flat_lats))

        for ci, contour in enumerate(contours):
            INF   = float(contour.max_time + 1)
            times = mode_times[ci]
            speed = np.where(times < INF, 1.0 - times / contour.max_time, 0.0)
            speed = np.clip(speed, 0.0, 1.0)
            r_m, g_m, b_m = base_rgb[ci]
            R += speed * r_m / 255.0
            G += speed * g_m / 255.0
            B += speed * b_m / 255.0

        R = np.clip(R, 0, 1)
        G = np.clip(G, 0, 1)
        B = np.clip(B, 0, 1)

        # Quantize to ~8 levels per channel so each unique colour becomes one trace
        quant = 32
        ri = np.clip(((R * 255 + quant / 2) // quant).astype(int) * quant, 0, 255)
        gi = np.clip(((G * 255 + quant / 2) // quant).astype(int) * quant, 0, 255)
        bi = np.clip(((B * 255 + quant / 2) // quant).astype(int) * quant, 0, 255)
        color_key = ri * 65536 + gi * 256 + bi

        mask = color_key > 0

        # Cell half-extents from the regular linspace grid
        lh  = (flat_lons.max() - flat_lons.min()) / (grid_size - 1) / 2
        lth = (flat_lats.max() - flat_lats.min()) / (grid_size - 1) / 2

        fig = go.Figure()

        for ck in np.unique(color_key[mask]):
            sel   = mask & (color_key == ck)
            clons = flat_lons[sel]
            clats = flat_lats[sel]
            n     = len(clons)
            r_v   = int(ck >> 16) & 0xFF
            g_v   = int(ck >> 8)  & 0xFF
            b_v   = int(ck)       & 0xFF
            fill  = f'rgba({r_v},{g_v},{b_v},{opacity})'

            # Build rectangle coords vectorised: SW SE NE NW close NaN per cell
            lons_out = np.full(n * 6, np.nan)
            lats_out = np.full(n * 6, np.nan)
            lons_out[0::6] = clons - lh;  lats_out[0::6] = clats - lth  # SW
            lons_out[1::6] = clons + lh;  lats_out[1::6] = clats - lth  # SE
            lons_out[2::6] = clons + lh;  lats_out[2::6] = clats + lth  # NE
            lons_out[3::6] = clons - lh;  lats_out[3::6] = clats + lth  # NW
            lons_out[4::6] = clons - lh;  lats_out[4::6] = clats - lth  # close

            fig.add_scattermapbox(
                lat=lats_out.tolist(),
                lon=lons_out.tolist(),
                mode="lines",
                fill="toself",
                fillcolor=fill,
                line=dict(width=0, color=fill),
                showlegend=False,
                hoverinfo="skip",
            )

        seen: set = set()
        for contour in contours:
            if contour.location not in seen:
                seen.add(contour.location)
                clat, clon = contour.center_location
                fig.add_scattermapbox(
                    lat=[clat], lon=[clon],
                    mode="markers",
                    marker=dict(size=14, color="#E63946"),
                    showlegend=False,
                    hoverinfo="text",
                    hovertext=contour.location,
                )

        images, annotations, shapes = self._rgb_legend_items(contours, base_hex)

        center = contours[0].center_location
        fig.update_layout(
            mapbox=dict(
                style=map_style,
                center=dict(lat=center[0], lon=center[1]),
                zoom=11,
            ),
            height=_MAP_H,
            margin=dict(l=0, r=20, t=10, b=0),
            showlegend=False,
            images=images,
            annotations=annotations,
            shapes=shapes,
        )
        return fig
