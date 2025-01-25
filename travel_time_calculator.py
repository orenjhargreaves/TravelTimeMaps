import googlemaps
import numpy as np
import pandas as pd
from typing import Tuple, List, Dict
import os
import json
import math

class TravelTimeCalculator:
    def __init__(self, location: str, max_time: int, time_step: int, mode: str):
        """Initialize the calculator with location and parameters."""
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
            print(f"Geocoding location: {self.location}")
            geocode_result = self.gmaps.geocode(self.location)
            print(f"Geocoding response: {json.dumps(geocode_result, indent=2)}")

            if not geocode_result:
                raise ValueError(f"Location not found: {self.location}")

            lat = geocode_result[0]['geometry']['location']['lat']
            lng = geocode_result[0]['geometry']['location']['lng']
            print(f"Successfully geocoded to: {lat}, {lng}")
            return (lat, lng)
        except Exception as e:
            if 'REQUEST_DENIED' in str(e):
                print(f"Full error response: {str(e)}")
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
            print(f"Verifying API access with mode: {self.mode}")
            test_directions = self.gmaps.directions(
                self.center_location,
                self.center_location,  # Same point for test
                mode=self.mode
            )
            print(f"Test directions response: {json.dumps(test_directions, indent=2)}")

            if not test_directions:
                raise ValueError("Could not get directions data from Google Maps API")
            print("API access verification successful")
        except Exception as e:
            print(f"API verification failed. Full error: {str(e)}")
            if 'REQUEST_DENIED' in str(e):
                raise ValueError(
                    "Access to Google Maps API was denied. Please ensure you have:\n"
                    "1. Enabled the Directions API in your Google Cloud Console\n"
                    "2. Properly configured your API key with access to these services\n"
                    "3. Enabled billing for your Google Cloud project"
                )
            raise

    def _generate_radial_points(self, radius_km: float = 5) -> List[Tuple[float, float]]:
        """Generate points in concentric circles around the center location."""
        lat, lng = self.center_location
        points = [(lat, lng)]  # Include center point

        # Constants for coordinate conversion
        km_per_lat = 111.0  # Approximate km per degree latitude
        km_per_lng = 111.0 * math.cos(math.radians(lat))  # Adjust for latitude

        # Generate concentric circles with increasing radius
        num_circles = 8
        points_per_circle = 32  # Must be divisible by 4 for even distribution

        for radius_idx in range(num_circles):
            radius = (radius_idx + 1) * (radius_km / num_circles)

            # Generate points around the circle
            for angle_idx in range(points_per_circle):
                angle = (angle_idx * 2 * math.pi) / points_per_circle

                # Convert polar coordinates to lat/lng
                dlat = (radius * math.cos(angle)) / km_per_lat
                dlng = (radius * math.sin(angle)) / km_per_lng

                points.append((lat + dlat, lng + dlng))

        return points

    def calculate_travel_times(self) -> pd.DataFrame:
        """Calculate travel times to grid points."""
        if not self.center_location:
            raise ValueError("Center location not set. Please check the provided address.")

        # Verify API access before making multiple requests
        self._verify_api_access()

        points = self._generate_radial_points()
        results = []
        error_count = 0

        # Calculate travel times for each point
        for dest_lat, dest_lng in points:
            try:
                print(f"Requesting directions to: ({dest_lat}, {dest_lng})")
                directions = self.gmaps.directions(
                    self.center_location,
                    (dest_lat, dest_lng),
                    mode=self.mode
                )
                print(f"Received directions response: {json.dumps(directions, indent=2)}")

                if directions and directions[0].get('legs'):
                    # Extract duration in minutes
                    duration = directions[0]['legs'][0]['duration']['value'] / 60
                    results.append({
                        'lat': dest_lat,
                        'lng': dest_lng,
                        'duration': duration
                    })
                    print(f"Successfully calculated duration: {duration} minutes")
                else:
                    print(f"No valid route found for destination: ({dest_lat}, {dest_lng})")
                    error_count += 1

            except Exception as e:
                error_count += 1
                print(f"Error calculating travel time to ({dest_lat}, {dest_lng}). Full error: {str(e)}")
                if 'REQUEST_DENIED' in str(e):
                    raise ValueError(
                        "Access to Google Maps API was denied. Please ensure you have:\n"
                        "1. Enabled the Directions API in your Google Cloud Console\n"
                        "2. Properly configured your API key with access to these services\n"
                        "3. Enabled billing for your Google Cloud project"
                    )
                continue

        # Create DataFrame with results
        if not results:
            print(f"No successful results out of {len(points)} attempts. Error count: {error_count}")
            raise ValueError(
                "No valid travel times could be calculated. This might be because:\n"
                "1. The API key doesn't have access to the Directions API\n"
                "2. The selected mode of transport is not available in this area\n"
                "3. The destination points are not reachable\n"
                "Please check your API key configuration and input parameters."
            )

        print(f"Successfully calculated {len(results)} travel times out of {len(points)} attempts")
        df = pd.DataFrame(results)
        self.last_result = df
        return df