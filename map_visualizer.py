import base64
import colorsys
import io
import math

import numpy as np
import plotly.graph_objects as go
from PIL import Image
from shapely.geometry import shape
from shapely.ops import unary_union
from typing import List

_MAP_H = 800
_MAP_W = 900

_SWATCH_W = 60 / _MAP_W
_SWATCH_H = 14 / _MAP_H
_PAD_X    = 10 / _MAP_W
_PAD_Y    = 10 / _MAP_H
_ROW_H    = 30 / _MAP_H
_GAP      = 8  / _MAP_W

_BOX_X0 = 0.01
_BOX_Y1 = 0.99
_BOX_X1 = _BOX_X0 + _PAD_X + _SWATCH_W + _GAP + 0.10


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

    # ── Custom map-pin polygon ────────────────────────────────────────────────

    def _pin_polygon(self, clat: float, clon: float, h: float = 0.003) -> tuple[list, list]:
        """
        Teardrop map-pin polygon whose tip points to (clat, clon).
        Longitude is scaled by cos(lat) so the circle head looks round on the map.
        """
        lon_scale = math.cos(math.radians(clat))
        r_lat = h * 0.35                 # circle radius in lat degrees
        r_lon = r_lat / lon_scale        # circle radius in lon degrees
        cy    = clat + h * 0.60          # circle centre latitude

        # Tangent half-angle from the vertical centre→tip line
        alpha = math.asin(r_lat / (h * 0.60))

        # Arc sweeps CCW from right tangent angle (-alpha) over the top to left (π+alpha)
        angles   = np.linspace(-alpha, math.pi + alpha, 48)
        arc_lons = clon + r_lon * np.cos(angles)
        arc_lats = cy   + r_lat * np.sin(angles)

        lons = np.concatenate([[clon], arc_lons, [clon]])
        lats = np.concatenate([[clat], arc_lats, [clat]])
        return lats.tolist(), lons.tolist()

    def _add_origin_pin(
        self, fig: go.Figure,
        clat: float, clon: float,
        location: str, color: str, opacity: float,
    ) -> None:
        lats, lons = self._pin_polygon(clat, clon)
        r, g, b   = self._hex_to_rgb(color)
        fig.add_scattermapbox(
            lat=lats, lon=lons,
            mode='lines',
            fill='toself',
            fillcolor=f'rgba({r},{g},{b},{opacity})',
            line=dict(width=1, color=f'rgba({r},{g},{b},1.0)'),
            showlegend=False,
            hoverinfo='text',
            hovertext=location,
        )

    # ── Legend helpers ────────────────────────────────────────────────────────

    def _legend_items(self, visible, single_origin: bool, pin_color: str = '#E63946'):
        n_rows = len(visible) + 1
        box_h  = _PAD_Y * 2 + n_rows * _ROW_H
        box_y0 = _BOX_Y1 - box_h

        images, annotations = [], []
        swatch_x = _BOX_X0 + _PAD_X
        label_x  = swatch_x + _SWATCH_W + _GAP

        for i, contour in enumerate(visible):
            swatch_top = _BOX_Y1 - _PAD_Y - i * _ROW_H
            swatch_mid = swatch_top - _SWATCH_H / 2
            images.append(dict(
                source=self._gradient_svg(contour.start_color_hex, contour.end_color_hex),
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

        pin_row_top = _BOX_Y1 - _PAD_Y - len(visible) * _ROW_H
        pin_mid     = pin_row_top - _SWATCH_H / 2
        pin_label   = "Origin" if single_origin else "Origins"
        annotations.append(dict(
            text=f'<b style="color:{pin_color};">●</b> {pin_label}',
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

    def _rgb_legend_items(self, contours, base_hex: list, pin_color: str = '#E63946'):
        n_rows = len(contours) + 2
        box_h  = _PAD_Y * 2 + n_rows * _ROW_H
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
            text=f'<b style="color:{pin_color};">●</b> Origin',
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

    # ── Geometry helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _geom_to_latlon(geom) -> tuple[list, list]:
        """Shapely Polygon or MultiPolygon → lat/lon lists with None separators."""
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

    @staticmethod
    def _compute_rings(features: list) -> tuple[dict, list]:
        """
        Convert cumulative isochrone GeoJSON features into non-overlapping ring polygons.
        ring[t] = isochrone[t] - isochrone[t-1], so each area is covered by exactly one ring.
        This eliminates the opacity-stacking problem when filling with a semi-transparent colour.
        """
        by_time: dict = {}
        for feat in features:
            t = feat["properties"]["contour"]
            by_time.setdefault(t, []).append(shape(feat["geometry"]))

        sorted_times = sorted(by_time.keys())
        cumulative: dict = {}
        for t in sorted_times:
            poly = unary_union(by_time[t]).buffer(0)
            cumulative[t] = poly

        rings: dict = {}
        for i, t in enumerate(sorted_times):
            if i == 0:
                rings[t] = cumulative[t]
            else:
                prev_t = sorted_times[i - 1]
                try:
                    rings[t] = cumulative[t].difference(cumulative[prev_t])
                except Exception:
                    rings[t] = cumulative[t].buffer(0).difference(cumulative[prev_t].buffer(0))

        return rings, sorted_times

    # ── Public map builders ───────────────────────────────────────────────────

    def create_multi_mode_map(
        self,
        contours: List["Contour"],
        map_style: str = "carto-positron",
        opacity: float = 0.65,
        pin_color: str = '#E63946',
        display_mode: str = "Filled",
    ) -> go.Figure:
        """
        Contour map with ring rendering.

        display_mode="Filled"   — filled rings, opacity compensated for N overlapping contours
        display_mode="Outlines" — outline rings only, vary_opacity=True (inner = more opaque)
        """
        visible = [
            c for c in contours
            if getattr(c, 'visible', True) and c.features and c.features.get("features")
        ]
        if not visible:
            raise ValueError("No visible contours to display")

        # Adjust per-contour opacity so N fully-overlapping contours produce exactly `opacity`.
        # Formula: per = 1 - (1 - opacity)^(1/N)  →  compounded N times = 1 - (1-opacity) = opacity
        n_visible  = len(visible)
        per_opacity = 1.0 - (1.0 - opacity) ** (1.0 / max(1, n_visible))

        filled   = display_mode == "Filled"
        center   = visible[0].center_location
        fig      = go.Figure()

        for contour in visible:
            group_id         = f"{contour.mode}_{contour.location}"
            band_style       = getattr(contour, 'band_style', 'None')
            display_interval = getattr(contour, 'display_interval', contour.interval)
            times_sorted     = sorted(set(f["properties"]["contour"] for f in contour.features["features"]))
            n_times          = len(times_sorted)
            labelled_times: set = set()

            rings, _ = self._compute_rings(contour.features["features"])

            # Outer bands first so inner (darker) bands paint on top
            for t in sorted(rings.keys(), reverse=True):
                if t % display_interval != 0:
                    continue
                ring = rings[t]
                if ring.is_empty:
                    continue

                if filled:
                    color      = self._get_color(contour, t, base_opacity=per_opacity, vary_opacity=False)
                    line_color = color
                    fill_arg   = 'toself'
                    fill_color = color
                    line_w     = 0.5
                else:
                    color      = self._get_color(contour, t, base_opacity=per_opacity, vary_opacity=True)
                    line_color = color
                    fill_arg   = None
                    fill_color = 'rgba(0,0,0,0)'
                    if band_style == "Width":
                        rank   = times_sorted.index(t) if t in times_sorted else 0
                        line_w = 1.0 + (rank / max(n_times - 1, 1)) * 3.0
                    else:
                        line_w = 2.0

                if filled and band_style == "Width":
                    rank   = times_sorted.index(t) if t in times_sorted else 0
                    line_w = 0.5 + (rank / max(n_times - 1, 1)) * 2.0

                lats, lons = self._geom_to_latlon(ring)

                trace_kw = dict(
                    lat=lats, lon=lons,
                    mode='lines',
                    line=dict(width=line_w, color=line_color),
                    legendgroup=group_id,
                    showlegend=False,
                    hoverinfo='text',
                    hovertext=f'{contour.name}: {t} min',
                )
                if fill_arg:
                    trace_kw['fill']      = fill_arg
                    trace_kw['fillcolor'] = fill_color

                fig.add_scattermapbox(**trace_kw)

                if band_style == "Numbers" and t not in labelled_times:
                    labelled_times.add(t)
                    poly_for_label = ring.geoms[0] if hasattr(ring, 'geoms') else ring
                    if not poly_for_label.is_empty:
                        coords = list(poly_for_label.exterior.coords)
                        north  = max(coords, key=lambda c: c[1])
                        fig.add_scattermapbox(
                            lat=[north[1]], lon=[north[0]],
                            mode='markers+text',
                            marker=dict(size=16, color=color, opacity=0.9),
                            text=[str(t)],
                            textfont=dict(size=9, color='white'),
                            textposition='middle center',
                            legendgroup=group_id,
                            showlegend=False,
                            hoverinfo='text',
                            hovertext=f'{t} min',
                        )

        seen_locations: set = set()
        for contour in visible:
            if contour.location not in seen_locations:
                seen_locations.add(contour.location)
                clat, clon = contour.center_location
                self._add_origin_pin(fig, clat, clon, contour.location, pin_color, opacity)

        single_origin = len(seen_locations) == 1
        title_text    = visible[0].location if single_origin else ""
        top_margin    = 50 if single_origin else 30
        images, annotations, shapes = self._legend_items(visible, single_origin, pin_color)

        fig.update_layout(
            mapbox=dict(style=map_style, center=dict(lat=center[0], lon=center[1]), zoom=11),
            height=_MAP_H,
            margin=dict(l=0, r=20, t=top_margin, b=0),
            title=dict(text=title_text, x=0.5, xanchor='center', font=dict(size=15)),
            showlegend=False,
            images=images,
            annotations=annotations,
            shapes=shapes,
        )
        return fig

    @staticmethod
    def rasterise_contours(visible: list, grid_size: int = 300) -> dict:
        """
        Run the slow PIP rasterization step and return raw grid data.
        Cache this in session state; re-run only when contour data changes.
        Returns dict with keys: flat_lons, flat_lats, mode_times, visible, grid_size.
        """
        from fastest_mode_analyser import FastestModeAnalyser
        analyser = FastestModeAnalyser(grid_size=grid_size)
        flat_lons, flat_lats = analyser._make_grid(visible)
        mode_times = np.stack([
            analyser._rasterise_contour(c, flat_lons, flat_lats) for c in visible
        ])
        return {
            "flat_lons":  flat_lons,
            "flat_lats":  flat_lats,
            "mode_times": mode_times,
            "visible":    visible,
            "grid_size":  grid_size,
        }

    def create_contour_image_map(
        self,
        contours: List["Contour"],
        map_style: str = "carto-positron",
        opacity: float = 0.65,
        pin_color: str = '#E63946',
        raster: dict | None = None,
        grid_size: int = 300,
    ) -> go.Figure:
        """
        Filled contour map rendered as a PIL image overlay.

        Each grid point is assigned to the fastest mode and coloured by that
        mode's time-band gradient. Because the output is a single rasterised
        image, opacity is perfectly uniform — no polygon stacking is possible.

        Pass `raster` (from rasterise_contours) to skip the slow PIP step when
        only visual settings (colours, opacity, pin colour) have changed.
        """
        visible = [
            c for c in contours
            if getattr(c, 'visible', True) and c.features and c.features.get("features")
        ]
        if not visible:
            raise ValueError("No visible contours to display")

        if raster is None:
            raster = self.rasterise_contours(visible, grid_size)

        flat_lons    = raster["flat_lons"]
        flat_lats    = raster["flat_lats"]
        mode_times   = raster["mode_times"]
        grid_size    = raster["grid_size"]
        n_pts        = len(flat_lats)

        # Apply per-mode time penalty (fixed overhead e.g. walking to car).
        # Penalty shifts effective times upward; cells where effective_time > max_time
        # are treated as unreachable for that mode.
        effective_times = mode_times.copy().astype(float)
        for ci, contour in enumerate(visible):
            p   = float(getattr(contour, 'time_penalty', 0))
            INF = float(contour.max_time + 1)
            effective_times[ci] += p
            effective_times[ci, mode_times[ci] >= INF] = INF          # raw-unreachable
            effective_times[ci, effective_times[ci] > contour.max_time] = INF  # penalty pushes over limit

        winning_idx  = np.argmin(effective_times, axis=0)
        winning_time = np.min(effective_times, axis=0)

        # Smooth isolated single-pixel patches: replace each cell with the
        # majority winner in a 5×5 neighbourhood. Only applied where a point
        # is reachable (winning_time < INF for at least one mode).
        if len(visible) > 1:
            from scipy.ndimage import generic_filter
            INF_global = float(max(c.max_time for c in visible) + 1)
            reachable  = (winning_time < INF_global).reshape(grid_size, grid_size)
            idx_2d     = winning_idx.reshape(grid_size, grid_size).astype(float)
            # Mask unreachable cells as -1 so they don't bias the majority vote
            idx_masked = np.where(reachable, idx_2d, -1.0)

            def _majority(window):
                vals = window[window >= 0].astype(int)
                if len(vals) == 0:
                    return -1.0
                counts = np.bincount(vals, minlength=len(visible))
                return float(np.argmax(counts))

            smoothed = generic_filter(idx_masked, _majority, size=5, mode='nearest')
            winning_idx = np.where(
                reachable.ravel(),
                smoothed.ravel().astype(int),
                winning_idx,
            )

        R = np.zeros(n_pts)
        G = np.zeros(n_pts)
        B = np.zeros(n_pts)
        A = np.zeros(n_pts)

        for ci, contour in enumerate(visible):
            INF  = float(contour.max_time + 1)
            mask = (winning_idx == ci) & (winning_time < INF)
            if not mask.any():
                continue

            sc   = np.array(self._hex_to_rgb(contour.start_color_hex), dtype=float)
            ec   = np.array(self._hex_to_rgb(contour.end_color_hex),   dtype=float)
            # winning_time already includes penalty; normalise against max_time
            prog = np.clip(winning_time[mask] / contour.max_time, 0.0, 1.0)

            R[mask] = (sc[0] + (ec[0] - sc[0]) * prog) / 255.0
            G[mask] = (sc[1] + (ec[1] - sc[1]) * prog) / 255.0
            B[mask] = (sc[2] + (ec[2] - sc[2]) * prog) / 255.0
            A[mask] = opacity

        rgba = np.zeros((grid_size, grid_size, 4), dtype=np.uint8)
        rgba[:, :, 0] = (R.reshape(grid_size, grid_size) * 255).clip(0, 255).astype(np.uint8)
        rgba[:, :, 1] = (G.reshape(grid_size, grid_size) * 255).clip(0, 255).astype(np.uint8)
        rgba[:, :, 2] = (B.reshape(grid_size, grid_size) * 255).clip(0, 255).astype(np.uint8)
        rgba[:, :, 3] = (A.reshape(grid_size, grid_size) * 255).clip(0, 255).astype(np.uint8)
        rgba = rgba[::-1, :, :]  # row 0 = south → flip so image row 0 = north

        img = Image.fromarray(rgba, 'RGBA')
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        img_src = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

        lon_min = float(flat_lons.min())
        lon_max = float(flat_lons.max())
        lat_min = float(flat_lats.min())
        lat_max = float(flat_lats.max())

        fig = go.Figure()
        fig.add_scattermapbox(
            lat=[lat_min, lat_max], lon=[lon_min, lon_max],
            mode='markers', marker=dict(size=1, opacity=0),
            showlegend=False, hoverinfo='skip',
        )

        # Ring boundary lines overlaid on the image so individual time bands are legible.
        for contour in visible:
            display_interval = getattr(contour, 'display_interval', contour.interval)
            penalty          = int(getattr(contour, 'time_penalty', 0))
            rings, _ = self._compute_rings(contour.features["features"])
            for t in sorted(rings.keys()):
                if t % display_interval != 0:
                    continue
                effective_t = t + penalty
                if effective_t > contour.max_time:
                    continue  # penalty pushes this ring beyond the requested window
                ring = rings[t]
                if ring.is_empty:
                    continue
                lats, lons = self._geom_to_latlon(ring)
                label = f'{contour.name}: {effective_t} min'
                if penalty:
                    label += f' ({t} min travel + {penalty} min overhead)'
                fig.add_scattermapbox(
                    lat=lats, lon=lons,
                    mode='lines',
                    line=dict(width=1.0, color='rgba(255,255,255,0.55)'),
                    showlegend=False,
                    hoverinfo='text',
                    hovertext=label,
                )

        seen: set = set()
        for contour in visible:
            if contour.location not in seen:
                seen.add(contour.location)
                clat, clon = contour.center_location
                self._add_origin_pin(fig, clat, clon, contour.location, pin_color, opacity)

        single_origin = len(seen) == 1
        images, annotations, shapes = self._legend_items(visible, single_origin, pin_color)

        center = visible[0].center_location
        fig.update_layout(
            mapbox=dict(
                style=map_style,
                center=dict(lat=center[0], lon=center[1]),
                zoom=11,
                layers=[dict(
                    sourcetype="image",
                    source=img_src,
                    coordinates=[
                        [lon_min, lat_max],  # NW
                        [lon_max, lat_max],  # NE
                        [lon_max, lat_min],  # SE
                        [lon_min, lat_min],  # SW
                    ],
                )],
            ),
            height=_MAP_H,
            margin=dict(l=0, r=20, t=10, b=0),
            showlegend=False,
            images=images,
            annotations=annotations,
            shapes=shapes,
        )
        return fig

    def create_fastest_mode_map(
        self,
        result: dict,
        map_style: str = "open-street-map",
        opacity: float = 0.65,
        pin_color: str = '#E63946',
    ) -> go.Figure:
        """Fastest-mode map using actual isochrone polygon shapes."""
        bands    = result["bands"]
        contours = result["contours"]

        fig = go.Figure()

        for contour, t, poly in sorted(bands, key=lambda x: x[1], reverse=True):
            lats, lons = self._geom_to_latlon(poly)
            color = self._get_color(contour, t, base_opacity=opacity, vary_opacity=False)
            fig.add_scattermapbox(
                lat=lats, lon=lons,
                mode="lines",
                fill="toself",
                fillcolor=color,
                line=dict(width=0.3, color=color),
                showlegend=False,
                hoverinfo="skip",
            )

        seen: set = set()
        for contour in contours:
            if contour.location not in seen:
                seen.add(contour.location)
                clat, clon = contour.center_location
                self._add_origin_pin(fig, clat, clon, contour.location, pin_color, opacity)

        single_origin = len(seen) == 1
        images, annotations, shapes = self._legend_items(contours, single_origin, pin_color)

        center = contours[0].center_location
        fig.update_layout(
            mapbox=dict(style=map_style, center=dict(lat=center[0], lon=center[1]), zoom=11),
            height=_MAP_H,
            margin=dict(l=0, r=20, t=10, b=0),
            showlegend=False,
            images=images,
            annotations=annotations,
            shapes=shapes,
        )
        return fig

    def create_rgb_mode_map(
        self,
        result: dict,
        map_style: str = "carto-positron",
        opacity: float = 0.65,
        pin_color: str = '#E63946',
    ) -> go.Figure:
        """
        RGB colour-mix fastest-mode map rendered as a smooth PIL image overlay.
        Each mode is assigned an evenly-spaced hue; brightness encodes speed.
        The image is added as a georeferenced Mapbox layer — no grid artefacts.
        """
        mode_times = result["mode_times"]
        flat_lats  = result["lats"]
        flat_lons  = result["lons"]
        contours   = result["contours"]
        grid_size  = result["grid_size"]
        n_modes    = len(contours)

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
            R += speed * (r_m / 255.0)
            G += speed * (g_m / 255.0)
            B += speed * (b_m / 255.0)

        R = np.clip(R, 0, 1)
        G = np.clip(G, 0, 1)
        B = np.clip(B, 0, 1)

        # Reshape to 2D grid (row=lat index, col=lon index)
        R_2d = R.reshape(grid_size, grid_size)
        G_2d = G.reshape(grid_size, grid_size)
        B_2d = B.reshape(grid_size, grid_size)
        reach_2d = (R_2d + G_2d + B_2d) > 0

        rgba = np.zeros((grid_size, grid_size, 4), dtype=np.uint8)
        rgba[:, :, 0] = (R_2d * 255).clip(0, 255).astype(np.uint8)
        rgba[:, :, 1] = (G_2d * 255).clip(0, 255).astype(np.uint8)
        rgba[:, :, 2] = (B_2d * 255).clip(0, 255).astype(np.uint8)
        rgba[:, :, 3] = np.where(reach_2d, int(opacity * 255), 0).astype(np.uint8)

        # Row 0 of array = south (lat_min); image row 0 = north. Flip vertically.
        rgba = rgba[::-1, :, :]

        img = Image.fromarray(rgba, 'RGBA')
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        img_src = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

        lon_min = float(flat_lons.min())
        lon_max = float(flat_lons.max())
        lat_min = float(flat_lats.min())
        lat_max = float(flat_lats.max())

        fig = go.Figure()

        # Invisible bounds trace so Plotly knows the map extent
        fig.add_scattermapbox(
            lat=[lat_min, lat_max], lon=[lon_min, lon_max],
            mode='markers',
            marker=dict(size=1, opacity=0),
            showlegend=False,
            hoverinfo='skip',
        )

        seen: set = set()
        for contour in contours:
            if contour.location not in seen:
                seen.add(contour.location)
                clat, clon = contour.center_location
                self._add_origin_pin(fig, clat, clon, contour.location, pin_color, opacity)

        images, annotations, shapes = self._rgb_legend_items(contours, base_hex, pin_color)

        center = contours[0].center_location
        fig.update_layout(
            mapbox=dict(
                style=map_style,
                center=dict(lat=center[0], lon=center[1]),
                zoom=11,
                layers=[dict(
                    sourcetype="image",
                    source=img_src,
                    coordinates=[
                        [lon_min, lat_max],  # NW
                        [lon_max, lat_max],  # NE
                        [lon_max, lat_min],  # SE
                        [lon_min, lat_min],  # SW
                    ],
                )],
            ),
            height=_MAP_H,
            margin=dict(l=0, r=20, t=10, b=0),
            showlegend=False,
            images=images,
            annotations=annotations,
            shapes=shapes,
        )
        return fig
