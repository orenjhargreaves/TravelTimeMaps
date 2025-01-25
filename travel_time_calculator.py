import googlemaps
import numpy as np
import pandas as pd
from typing import Tuple, List, Dict
import os
import json
import math
import hashlib
from functools import lru_cache
import threading
from queue import Queue
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

class TravelTimeCalculator:
    def __init__(self, location: str, max_time: int, time_step: int, mode: str, radius_km: float = 5, point_spacing_meters: float = 500):
        """Initialize the calculator with location and parameters."""
        api_key = os.environ.get('GOOGLE_MAPS_API_KEY')
        if not api_key:
            raise ValueError("Google Maps API key not found in environment variables")

        self.gmaps = googlemaps.Client(key=api_key)
        self.location = location
        self.max_time = max_time
        self.time_step = time_step
        self.mode = mode
        self.radius_km = radius_km
        self.point_spacing_meters = point_spacing_meters
        self.center_location = self._geocode_location()
        self.last_result = None
        self._cache_lock = threading.Lock()
        self._cache = {}
        self.progress_callback = None

    def calculate_travel_times(self, progress_callback=None) -> pd.DataFrame:
        """Calculate travel times to grid points using batch processing."""
        self.progress_callback = progress_callback

        if not self.center_location:
            raise ValueError("Center location not set. Please check the provided address.")

        if self.progress_callback:
            self.progress_callback("Verifying API access...")
        self._verify_api_access()

        if self.progress_callback:
            self.progress_callback("Generating sampling points...")
        points = self._generate_radial_points()

        if self.progress_callback:
            self.progress_callback(f"Generated {len(points)} points for analysis. Starting calculations...")

        results = self._process_batch(points)

        if not results:
            raise ValueError(
                "No valid travel times could be calculated. This might be because:\n"
                "1. The API key doesn't have access to the Directions API\n"
                "2. The selected mode of transport is not available in this area\n"
                "3. The destination points are not reachable\n"
                "Please check your API key configuration and input parameters."
            )

        if self.progress_callback:
            self.progress_callback(f"Completed! Successfully calculated {len(results)} travel times.")

        df = pd.DataFrame(results)
        self.last_result = df
        return df

    def _process_batch(self, points: List[Tuple[float, float]], batch_size: int = 25) -> List[Dict]:
        """Process a batch of points and return their travel time data."""
        results = []

        # Process points in batches with enhanced progress bar
        total_batches = (len(points) + batch_size - 1) // batch_size
        progress_bar = tqdm(
            range(0, len(points), batch_size),
            desc="Calculating travel times",
            total=total_batches,
            unit="batch",
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} batches [{elapsed}<{remaining}, {rate_fmt}{postfix}]"
        )

        for i in progress_bar:
            batch = points[i:i + batch_size]
            batch_results = []

            # Create batch request
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = []
                for dest_lat, dest_lng in batch:
                    futures.append(
                        executor.submit(
                            self._get_cached_directions,
                            self.center_location[0],
                            self.center_location[1],
                            dest_lat,
                            dest_lng,
                            self.mode
                        )
                    )

                # Collect results as they complete
                for future, (dest_lat, dest_lng) in zip(futures, batch):
                    try:
                        directions = future.result()
                        if directions and directions[0].get('legs'):
                            leg = directions[0]['legs'][0]
                            duration = leg['duration']['value'] / 60
                            actual_end_location = leg['end_location']

                            batch_results.append({
                                'lat': actual_end_location['lat'],
                                'lng': actual_end_location['lng'],
                                'duration': duration
                            })
                    except Exception as e:
                        print(f"Error calculating travel time to ({dest_lat}, {dest_lng}): {str(e)}")

            results.extend(batch_results)
            # Update progress bar with detailed status
            progress_info = {
                "points_processed": len(results),
                "success_rate": f"{(len(results) / (i + len(batch)) * 100):.1f}%"
            }
            progress_bar.set_postfix(progress_info)

            # Update Streamlit progress
            if self.progress_callback:
                remaining_batches = total_batches - (i // batch_size) - 1
                eta_seconds = progress_bar.format_dict.get('rate', 0)
                if eta_seconds > 0:
                    eta_minutes = (remaining_batches / eta_seconds) / 60
                    self.progress_callback(
                        f"Processing points: {progress_info['points_processed']} complete "
                        f"({progress_info['success_rate']} success rate). "
                        f"Estimated time remaining: {eta_minutes:.1f} minutes"
                    )

        return results

    def _get_cached_directions(self, origin_lat: float, origin_lng: float, dest_lat: float, dest_lng: float, mode: str) -> Dict:
        """Thread-safe cached wrapper for directions API calls."""
        cache_key = self._cache_key(origin_lat, origin_lng, dest_lat, dest_lng, mode)

        with self._cache_lock:
            if cache_key in self._cache:
                return self._cache[cache_key]

        try:
            result = self.gmaps.directions(
                (origin_lat, origin_lng),
                (dest_lat, dest_lng),
                mode=mode
            )

            with self._cache_lock:
                self._cache[cache_key] = result

            return result
        except Exception as e:
            print(f"Error getting directions: {str(e)}")
            return None

    def _geocode_location(self) -> Tuple[float, float]:
        """Convert location string to coordinates."""
        try:
            print(f"Geocoding location: {self.location}")
            geocode_result = self.gmaps.geocode(self.location)

            if not geocode_result:
                raise ValueError(f"Location not found: {self.location}")

            lat = geocode_result[0]['geometry']['location']['lat']
            lng = geocode_result[0]['geometry']['location']['lng']
            print(f"Successfully geocoded to: {lat}, {lng}")
            return (lat, lng)
        except Exception as e:
            if 'REQUEST_DENIED' in str(e):
                raise ValueError(
                    "Access to Google Maps API was denied. Please ensure you have:\n"
                    "1. Enabled the Geocoding API in your Google Cloud Console\n"
                    "2. Enabled the Directions API in your Google Cloud Console\n"
                    "3. Properly configured your API key with access to these services"
                )
            raise ValueError(f"Error geocoding location '{self.location}': {str(e)}")

    def _verify_api_access(self):
        """Verify API access with a test request"""
        try:
            test_directions = self._get_cached_directions(
                self.center_location[0],
                self.center_location[1],
                self.center_location[0],
                self.center_location[1],
                self.mode
            )

            if not test_directions:
                raise ValueError("Could not get directions data from Google Maps API")
            print("API access verification successful")
        except Exception as e:
            if 'REQUEST_DENIED' in str(e):
                raise ValueError(
                    "Access to Google Maps API was denied. Please ensure you have:\n"
                    "1. Enabled the Directions API in your Google Cloud Console\n"
                    "2. Properly configured your API key with access to these services\n"
                    "3. Enabled billing for your Google Cloud project"
                )
            raise
    def _generate_radial_points(self) -> List[Tuple[float, float]]:
        """Generate points with specified spacing around the center location."""
        lat, lng = self.center_location
        points = [(lat, lng)]  # Include center point

        # Constants for coordinate conversion
        earth_radius = 6371000  # Earth's radius in meters
        lat_rad = math.radians(lat)

        # Calculate number of circles based on radius and point spacing
        meters_per_degree_lat = 111320  # Approximate meters per degree of latitude
        meters_per_degree_lng = 111320 * math.cos(lat_rad)  # Adjust for latitude

        # Calculate the number of circles needed to cover the radius
        num_circles = int(self.radius_km * 1000 / self.point_spacing_meters)

        for circle_idx in range(num_circles):
            # Calculate radius for this circle
            radius_meters = (circle_idx + 1) * self.point_spacing_meters
            radius_km = radius_meters / 1000

            if radius_km > self.radius_km:
                break

            # Calculate number of points needed for this circle to maintain spacing
            circle_circumference = 2 * math.pi * radius_meters
            num_points = max(8, int(circle_circumference / self.point_spacing_meters))

            # Generate points around the circle
            for point_idx in range(num_points):
                angle = (point_idx * 2 * math.pi) / num_points

                # Add small random variation to prevent grid artifacts
                radius_jitter = radius_meters * (1 + 0.1 * (np.random.random() - 0.5))
                angle_jitter = angle + 0.1 * (np.random.random() - 0.5)

                # Convert to lat/lng
                dlat = (radius_jitter * math.cos(angle_jitter)) / meters_per_degree_lat
                dlng = (radius_jitter * math.sin(angle_jitter)) / meters_per_degree_lng

                points.append((lat + dlat, lng + dlng))

        return points
    def _cache_key(self, origin_lat: float, origin_lng: float, dest_lat: float, dest_lng: float, mode: str) -> str:
        """Generate a unique cache key for the request."""
        key_parts = f"{origin_lat:.6f},{origin_lng:.6f}-{dest_lat:.6f},{dest_lng:.6f}-{mode}"
        return hashlib.md5(key_parts.encode()).hexdigest()