import googlemaps
import numpy as np
import pandas as pd
from typing import Tuple, List, Dict
import os

class TravelTimeCalculator:
    def __init__(self, location: str, max_time: int, time_step: int, mode: str):
        """
        Initialize the calculator with location and parameters.

        Args:
            location: Starting location address or coordinates
            max_time: Maximum travel time in minutes
            time_step: Time interval between contours in minutes
            mode: Transportation mode (driving, walking, bicycling, transit)
        """
        api_key = os.environ.get('GOOGLE_MAPS_API_KEY')
        if not api_key:
            raise ValueError("Google Maps API key not found in environment variables")

        self.gmaps = googlemaps.Client(key=api_key)
        self.location = location
        self.max_time = max_time
        self.time_step = time_step
        self.mode = mode
        self.center_location = self._geocode_location()
        self.last_result = None

    def _geocode_location(self) -> Tuple[float, float]:
        """Convert location string to coordinates."""
        try:
            geocode_result = self.gmaps.geocode(self.location)
            if not geocode_result:
                raise ValueError("Location not found")

            lat = geocode_result[0]['geometry']['location']['lat']
            lng = geocode_result[0]['geometry']['location']['lng']
            return (lat, lng)
        except Exception as e:
            raise ValueError(f"Error geocoding location: {str(e)}")

    def _generate_grid_points(self, radius_km: float = 5) -> List[Tuple[float, float]]:
        """Generate a grid of points around the center location."""
        lat, lng = self.center_location
        points = []

        # Convert radius to degrees (approximate)
        radius_deg = radius_km / 111  # 1 degree ≈ 111 km

        # Create a grid of points
        for i in np.linspace(-radius_deg, radius_deg, 20):
            for j in np.linspace(-radius_deg, radius_deg, 20):
                points.append((lat + i, lng + j))

        return points

    def calculate_travel_times(self) -> pd.DataFrame:
        """Calculate travel times to grid points."""
        grid_points = self._generate_grid_points()
        results = []

        # Calculate travel times in batches
        for dest_lat, dest_lng in grid_points:
            try:
                # Get directions from Google Maps
                directions = self.gmaps.directions(
                    self.center_location,
                    (dest_lat, dest_lng),
                    mode=self.mode
                )

                if directions:
                    # Extract duration in minutes
                    duration = directions[0]['legs'][0]['duration']['value'] / 60
                    results.append({
                        'lat': dest_lat,
                        'lng': dest_lng,
                        'duration': duration
                    })

            except Exception as e:
                # Skip failed requests
                continue

        # Create DataFrame with results
        df = pd.DataFrame(results)
        self.last_result = df
        return df