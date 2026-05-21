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

    def analyse_rgb(self, contours) -> Optional[dict]:
        """
        Returns per-grid-cell travel times for all visible modes.
        Used for additive RGB colour mixing in the map view.

        Keys: lats, lons, mode_times (n_modes × n_points ndarray), contours, grid_size.
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
        mode_times = np.stack([
            self._rasterise_contour(c, flat_lons, flat_lats) for c in visible
        ])

        return {
            "lats":       flat_lats,
            "lons":       flat_lons,
            "mode_times": mode_times,
            "contours":   visible,
            "grid_size":  self.grid_size,
        }

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

    def analyse_vector(self, contours, simplify_tol: float = 0.0003) -> Optional[dict]:
        """
        Computes fastest-mode regions using polygon set operations on the actual
        isochrone shapes. Returns smooth, organic polygons rather than grid cells.

        For each time band t and each mode, computes the area that mode newly
        enters at band t AND no other mode reached strictly before band t.
        Ties (both modes enter at the same band) go to the first mode in the list.

        Returns dict with keys:
          bands    : list of (contour_obj, time_float, shapely_polygon)
          contours : visible Contour list
        or None if fewer than 2 visible contours.
        """
        from shapely.ops import unary_union

        visible = [
            c for c in contours
            if getattr(c, "visible", True)
            and c.features
            and c.features.get("features")
        ]
        if len(visible) < 2:
            return None

        # Build per-mode per-time unioned+simplified cumulative polygons
        # mode_isos[ci] = {t: shapely_polygon}
        mode_isos: dict[int, dict] = {}
        for ci, contour in enumerate(visible):
            by_time: dict[int, list] = {}
            for feat in contour.features["features"]:
                t = feat["properties"]["contour"]
                by_time.setdefault(t, []).append(shape(feat["geometry"]))
            bands: dict[int, any] = {}
            for t, polys in by_time.items():
                unified = unary_union(polys)
                if not unified.is_valid:
                    unified = unified.buffer(0)
                bands[t] = unified.simplify(simplify_tol)
            mode_isos[ci] = bands

        all_times = sorted({t for isos in mode_isos.values() for t in isos})

        def prev_band(ci: int, t: int):
            candidates = [s for s in mode_isos[ci] if s < t]
            return max(candidates) if candidates else None

        results = []  # list of (contour_obj, time_float, shapely_polygon)

        for t in all_times:
            claimed_this_band = None

            for ci, contour in enumerate(visible):
                if t not in mode_isos[ci]:
                    continue

                # Area newly entered by this mode at band t
                pt = prev_band(ci, t)
                ring = (mode_isos[ci][t].difference(mode_isos[ci][pt])
                        if pt is not None else mode_isos[ci][t])

                if ring.is_empty:
                    continue

                # Remove areas where other modes reached strictly BEFORE this band
                for other_ci in range(len(visible)):
                    if other_ci == ci:
                        continue
                    opt = prev_band(other_ci, t)
                    if opt is not None:
                        try:
                            ring = ring.difference(mode_isos[other_ci][opt])
                        except Exception:
                            ring = ring.buffer(0).difference(mode_isos[other_ci][opt].buffer(0))
                    if ring.is_empty:
                        break

                if ring.is_empty:
                    continue

                # Remove tie areas already claimed by earlier modes at this same band
                if claimed_this_band is not None:
                    try:
                        ring = ring.difference(claimed_this_band)
                    except Exception:
                        ring = ring.buffer(0).difference(claimed_this_band.buffer(0))

                if ring.is_empty:
                    continue

                results.append((contour, float(t), ring))
                claimed_this_band = (ring if claimed_this_band is None
                                     else claimed_this_band.union(ring))

        return {"bands": results, "contours": visible}
