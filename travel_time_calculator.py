import os
import requests
from typing import Dict, List, Tuple
import math

class TravelTimeCalculator:
    def __init__(self, location: str, max_time: int, mode: str, interval: int = 5, use_geoapify: bool = False):
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
        self.interval = interval
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
            return mode_mapping.get(mode, mode)
        else:
            mode_mapping = {
                "driving": "driving-traffic",
                "walking": "walking",
                "bicycling": "cycling"
            }
            return mode_mapping.get(mode, mode)

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

    def calculate_travel_times(self, progress_callback=None) -> Dict:
        """Calculate isochrones using selected API with batched requests."""
        if progress_callback:
            progress_callback("Calculating isochrones...", 0.3)

        # Generate all time intervals
        times = list(range(self.interval, self.max_time + 1, self.interval))
        features = []

        # Batch requests in groups of 4 for both APIs
        batches = [times[i:i + 4] for i in range(0, len(times), 4)]
        total_batches = len(batches)

        if self.use_geoapify:
            for i, batch in enumerate(batches):
                # Convert minutes to seconds for Geoapify
                ranges = [str(minutes * 60) for minutes in batch]
                url = "https://api.geoapify.com/v1/isoline"
                params = {
                    "lat": self.center_location[0],
                    "lon": self.center_location[1],
                    "type": "time",
                    "mode": self.mode,
                    "range": "|".join(ranges),  # Join ranges with pipe for multiple contours
                    "apiKey": self.api_key
                }

                response = requests.get(url, params=params)
                if response.status_code != 200:
                    raise ValueError(f"Error calculating isochrones: {response.text}")

                data = response.json()
                if data.get("features"):
                    for idx, feature in enumerate(data["features"]):
                        # Ensure we're setting the correct contour time
                        feature["properties"]["contour"] = batch[idx]
                        # Convert MultiPolygon to individual Polygons if needed
                        if feature["geometry"]["type"] == "MultiPolygon":
                            for polygon in feature["geometry"]["coordinates"]:
                                new_feature = {
                                    "type": "Feature",
                                    "geometry": {
                                        "type": "Polygon",
                                        "coordinates": polygon
                                    },
                                    "properties": {
                                        "contour": batch[idx],
                                        **feature["properties"]
                                    }
                                }
                                features.append(new_feature)
                        else:
                            features.append(feature)

                if progress_callback:
                    progress_callback(f"Calculating batch {i+1}/{total_batches}", (i + 1) / total_batches)
        else:
            # For Mapbox, continue with existing batch implementation

            for i, batch in enumerate(batches):
                url = f"https://api.mapbox.com/isochrone/v1/mapbox/{self.mode}/{self.center_location[1]},{self.center_location[0]}"
                params = {
                    "contours_minutes": ",".join(map(str, batch)),
                    "polygons": "true",
                    "access_token": self.api_key,
                    "generalize": 0
                }

                response = requests.get(url, params=params)
                if response.status_code != 200:
                    raise ValueError(f"Error calculating isochrones: {response.text}")

                data = response.json()
                if data.get("features"):
                    features.extend(data["features"])

                if progress_callback:
                    progress_callback(f"Calculating batch {i+1}/{total_batches}", (i + 1) / total_batches)

        self.last_result = {"type": "FeatureCollection", "features": features}
        return self.last_result