
import os
import requests
from typing import Dict, List, Tuple

class TravelTimeCalculator:
    def __init__(self, location: str, max_time: int, mode: str):
        """Initialize the calculator with location and parameters."""
        self.api_key = os.environ.get('MAPBOX_ACCESS_TOKEN')
        if not self.api_key:
            raise ValueError("Mapbox access token not found in environment variables")

        self.location = location
        self.max_time = max_time
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

    def _calculate_contour_intervals(self) -> List[int]:
        """Calculate round number contour intervals based on max time."""
        if self.max_time <= 20:
            # For max times up to 20 minutes, use quarters
            step = self.max_time // 4
            return [step, step * 2, step * 3, self.max_time]
        elif self.max_time <= 30:
            # For max times up to 30 minutes
            return [5, 10, 20, 30]
        elif self.max_time <= 45:
            # For max times up to 45 minutes
            return [10, 20, 30, 45]
        else:
            # For max times up to 60 minutes
            return [15, 30, 45, 60]

    def calculate_travel_times(self, progress_callback=None) -> Dict:
        """Calculate isochrones using Mapbox Isochrone API."""
        if progress_callback:
            progress_callback("Calculating isochrones...", 0.3)

        contours_minutes = self._calculate_contour_intervals()
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
