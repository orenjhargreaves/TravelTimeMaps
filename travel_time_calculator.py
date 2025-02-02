import os
import requests
from typing import Dict, List, Tuple

class TravelTimeCalculator:
    def __init__(self, location: str, max_time: int, time_step: int, mode: str, radius_km: float = 5, point_spacing_meters: float = 500):
        """Initialize the calculator with location and parameters."""
        self.api_key = os.environ.get('MAPBOX_ACCESS_TOKEN')
        if not self.api_key:
            raise ValueError("Mapbox access token not found in environment variables")

        self.location = location
        self.max_time = max_time
        self.time_step = time_step
        self.mode = self._convert_mode(mode)
        self.last_result = None
        self.center_location = self._geocode_location()

    def _convert_mode(self, mode: str) -> str:
        """Convert Google Maps mode to Mapbox profile."""
        mode_mapping = {
            "driving": "driving-traffic",
            "walking": "walking",
            "bicycling": "cycling"
        }
        return mode_mapping.get(mode, "driving-traffic")

    def _geocode_location(self) -> Tuple[float, float]:
        """Convert location string to coordinates using Mapbox Geocoding API."""
        url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{self.location}.json"
        params = {
            "access_token": self.api_key,
            "limit": 1
        }

        response = requests.get(url, params=params)
        if response.status_code != 200:
            raise ValueError(f"Error geocoding location: {response.text}")

        data = response.json()
        if not data["features"]:
            raise ValueError(f"Location not found: {self.location}")

        lng, lat = data["features"][0]["center"]
        return (lat, lng)

    def calculate_travel_times(self, progress_callback=None) -> Dict:
        """Calculate isochrones using Mapbox Isochrone API."""
        if progress_callback:
            progress_callback("Calculating isochrones...", 0.3)

        contours_minutes = list(range(0, self.max_time + self.time_step, self.time_step))
        url = f"https://api.mapbox.com/isochrone/v1/mapbox/{self.mode}/{self.center_location[1]},{self.center_location[0]}"

        params = {
            "contours_minutes": ",".join(map(str, contours_minutes)),
            "polygons": "true",
            "access_token": self.api_key,
            "generalize": 0
        }

        response = requests.get(url, params=params)
        if response.status_code != 200:
            raise ValueError(f"Error calculating isochrones: {response.text}")

        if progress_callback:
            progress_callback("Completed!", 1.0)

        self.last_result = response.json()
        return self.last_result