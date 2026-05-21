import numpy as np
import shapely
from shapely.geometry import shape
from typing import Optional

# Simplification tolerance in degrees: ~50 m at London's latitude.
# Much finer than any grid cell size we use, so accuracy is unaffected.
_SIMPLIFY_TOL = 0.0005


class FastestModeAnalyser:
    """
    Rasterises isochrone contours onto a regular lat/lon grid and, for each
    cell, identifies which transport mode reaches it fastest.

    Key optimisations:
    - shapely 2.x vectorised contains_xy (C-level GEOS)
    - Polygons simplified before PIP tests (avg vertex count 400 → ~60)
    - Unassigned-point mask: points already assigned to inner bands are
      excluded from outer band tests, shrinking each successive batch
    """

    def __init__(self, grid_size: int = 100):
        self.grid_size = grid_size

    # ── Grid construction ────────────────────────────────────────────────────

    def _make_grid(self, contours) -> tuple[np.ndarray, np.ndarray]:
        all_lons, all_lats = [], []
        for contour in contours:
            for feat in contour.features["features"]:
                gtype = feat["geometry"]["type"]
                coords = feat["geometry"]["coordinates"]
                rings = coords if gtype == "Polygon" else [r for p in coords for r in p]
                for ring in rings:
                    all_lons.extend(c[0] for c in ring)
                    all_lats.extend(c[1] for c in ring)

        lon0, lon1 = min(all_lons), max(all_lons)
        lat0, lat1 = min(all_lats), max(all_lats)
        pw, ph = (lon1 - lon0) * 0.04, (lat1 - lat0) * 0.04

        lons_1d = np.linspace(lon0 - pw, lon1 + pw, self.grid_size)
        lats_1d = np.linspace(lat0 - ph, lat1 + ph, self.grid_size)
        lon_g, lat_g = np.meshgrid(lons_1d, lats_1d)
        return lon_g.ravel(), lat_g.ravel()

    # ── Per-mode rasterisation ───────────────────────────────────────────────

    def _rasterise_contour(self, contour, flat_lons: np.ndarray, flat_lats: np.ndarray) -> np.ndarray:
        """
        Returns float array (n_points,): minimum travel time to each grid cell
        for this mode, or max_time+1 where unreachable.

        Iterates bands from innermost outward. For each band, tests only
        unassigned points against each (simplified) polygon.
        """
        n = len(flat_lons)
        INF = float(contour.max_time + 1)

        # Group features by time band, build simplified polygons once
        by_time: dict[int, list] = {}
        for feat in contour.features["features"]:
            t = feat["properties"]["contour"]
            poly = shape(feat["geometry"]).simplify(_SIMPLIFY_TOL)
            by_time.setdefault(t, []).append(poly)

        min_times = np.full(n, INF)
        unassigned = np.ones(n, dtype=bool)

        for t in sorted(by_time.keys()):
            if not unassigned.any():
                break
            # Operate only on the remaining unassigned subset
            idx = np.where(unassigned)[0]
            sub_lons = flat_lons[idx]
            sub_lats = flat_lats[idx]
            sub_in = np.zeros(len(idx), dtype=bool)

            for poly in by_time[t]:
                sub_in |= shapely.contains_xy(poly, sub_lons, sub_lats)

            hit = idx[sub_in]
            min_times[hit] = float(t)
            unassigned[hit] = False

        return min_times

    # ── Main analysis ────────────────────────────────────────────────────────

    def analyse(self, contours) -> Optional[dict]:
        """
        Returns a dict ready for rendering, or None if fewer than 2 visible
        contours with data are available.

        Keys: lats, lons, winning_idx, winning_time, margin, unreachable,
              contours, grid_size.
        """
        visible = [
            c for c in contours
            if getattr(c, "visible", True)
            and c.features
            and c.features.get("features")
        ]
        if len(visible) < 2:
            return None

        flat_lons, flat_lats = self._make_grid(visible)
        INF = float(max(c.max_time for c in visible) + 1)

        mode_times = np.stack([
            self._rasterise_contour(c, flat_lons, flat_lats) for c in visible
        ])  # shape: (n_modes, n_points)

        winning_idx  = np.argmin(mode_times, axis=0)
        winning_time = np.min(mode_times, axis=0)
        unreachable  = winning_time >= INF

        sorted_times = np.sort(mode_times, axis=0)
        margin = sorted_times[1] - sorted_times[0]
        margin[unreachable] = 0.0

        return {
            "lats":         flat_lats,
            "lons":         flat_lons,
            "winning_idx":  winning_idx,
            "winning_time": winning_time,
            "margin":       margin,
            "unreachable":  unreachable,
            "contours":     visible,
            "grid_size":    self.grid_size,
        }
