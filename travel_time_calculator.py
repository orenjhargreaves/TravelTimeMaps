
import os
import requests
from typing import Dict, List, Tuple

class TravelTimeCalculator:
    def __init__(self, location: str, max_time: int, mode: str, use_geoapify: bool = False):
        """Initialize the calculator with location and parameters."""
        if use_geoapify:
            self.api_key = os.environ.get('GEOAPIFY_API_KEY')
            if not self.api_key:
                raise ValueError("Geoapify API key not found in environment variables")
        else:
            self.api_key = os.environ.get('MAPBOX_ACCESS_TOKEN')
            if not self.api_key:
                raise ValueError("Mapbox access token not found in environment variables")
        
        self.use_geoapify = use_geoapify

        self.location = location
        self.max_time = max_time
        self.mode = self._convert_mode(mode)
        self.last_result = None
        self.center_location = self._geocode_location()

    def _convert_mode(self, mode: str) -> str:
        """Convert mode to API-specific format."""
        if self.use_geoapify:
            mode_mapping = {
                "driving": "drive",
                "walking": "walk",
                "bicycling": "bicycle",
                "public_transport": "public_transport"
            }
            return mode_mapping.get(mode, "drive")
        else:
            mode_mapping = {
                "driving": "driving-traffic",
                "walking": "walking",
                "bicycling": "cycling"
            }
            return mode_mapping.get(mode, "driving-traffic")

    def _geocode_location(self) -> Tuple[float, float]:
        """Convert location string to coordinates using selected API."""
        if self.use_geoapify:
            url = "https://api.geoapify.com/v1/geocode/search"
            params = {
                "text": self.location,
                "apiKey": self.api_key,
                "limit": 1
            }
        else:
            url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{self.location}.json"
            params = {
                "access_token": self.api_key,
                "limit": 1
            }

        response = requests.get(url, params=params)
        if response.status_code != 200:
            raise ValueError(f"Error geocoding location: {response.text}")

        data = response.json()
        if self.use_geoapify:
            if not data.get("features"):
                raise ValueError(f"Location not found: {self.location}")
            feature = data["features"][0]
            return (feature["properties"]["lat"], feature["properties"]["lon"])
        else:
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
        """Calculate isochrones using selected API."""
        if progress_callback:
            progress_callback("Calculating isochrones...", 0.3)

        contours_minutes = self._calculate_contour_intervals()
        
        if self.use_geoapify:
            # For Geoapify, we need to make separate requests for each contour
            features = []
            for minutes in contours_minutes:
                url = "https://api.geoapify.com/v1/isoline"
                params = {
                    "lat": self.center_location[0],
                    "lon": self.center_location[1],
                    "type": "time",
                    "mode": self.mode,
                    "range": str(minutes * 60),  # Convert to seconds
                    "apiKey": self.api_key
                }
                response = requests.get(url, params=params)
                if response.status_code != 200:
                    raise ValueError(f"Error calculating isochrones: {response.text}")
                data = response.json()
                if data["features"]:
                    # Add the contour time to properties
                    data["features"][0]["properties"]["contour"] = minutes
                    features.extend(data["features"])
            
            self.last_result = {"type": "FeatureCollection", "features": features}
            return self.last_result
        else:
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
