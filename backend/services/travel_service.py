"""Travel service for real-time travel time and route information."""
import logging
import json
import os
from typing import List, Dict, Any, Optional, Tuple
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
import re
import asyncio

logger = logging.getLogger(__name__)

class TravelService:
    """Service for fetching real-time travel information using multiple APIs."""
    
    def __init__(self):
        """Initialize the travel service."""
        logger.info("Initializing TravelService")
        
        self.http_client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": "RecruitIQ Travel Assistant/1.0",
                "Accept": "application/json"
            }
        )
        
        # Get API keys from environment variables
        self.google_maps_key = os.getenv("GOOGLE_API_KEY")
        self.traveltime_key = os.getenv("TRAVELTIME_API_KEY")
        self.mapbox_token = os.getenv("MAPBOX_ACCESS_TOKEN")
        
        # Transportation mode mappings
        self.transport_modes = {
            "driving": ["drive", "driving", "car", "auto"],
            "walking": ["walk", "walking", "foot", "on foot"],
            "bicycling": ["bike", "biking", "bicycle", "cycling"],
            "transit": ["train", "bus", "public transport", "transit", "subway", "metro"],
            "flying": ["fly", "flight", "plane", "air"]
        }
        
        logger.info(f"Travel API keys available - Google: {bool(self.google_maps_key)}, TravelTime: {bool(self.traveltime_key)}, Mapbox: {bool(self.mapbox_token)}")
    
    def _detect_transport_mode(self, query: str) -> str:
        """Detect transportation mode from the query."""
        query_lower = query.lower()
        
        for mode, keywords in self.transport_modes.items():
            if any(keyword in query_lower for keyword in keywords):
                return mode
        
        # Default to driving for distance/time queries
        return "driving"
    
    def _clean_location(self, location: str) -> str:
        """Clean and normalize location names."""
        if not location:
            return ""
        
        # Remove common prefixes/suffixes
        location = re.sub(r'^(from|to|the|in|at|near)\s+', '', location.strip(), flags=re.IGNORECASE)
        location = re.sub(r'\s+(by|via|through|using)\s+.*$', '', location, flags=re.IGNORECASE)
        
        # Common city name mappings
        city_mappings = {
            "nyc": "New York City, NY",
            "ny": "New York, NY", 
            "boston": "Boston, MA",
            "sf": "San Francisco, CA",
            "la": "Los Angeles, CA",
            "chicago": "Chicago, IL",
            "dc": "Washington, DC",
            "philly": "Philadelphia, PA"
        }
        
        location_lower = location.lower().strip()
        return city_mappings.get(location_lower, location.strip())
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def _get_google_directions(self, origin: str, destination: str, mode: str) -> Optional[Dict[str, Any]]:
        """Get directions from Google Maps API using the new Routes API."""
        if not self.google_maps_key:
            logger.warning("Google Maps API key not available")
            return None
        
        try:
            # Convert mode for Google API
            google_mode = mode
            if mode == "flying":
                google_mode = "DRIVE"  # Fallback for flights
            elif mode == "driving":
                google_mode = "DRIVE"
            elif mode == "transit":
                google_mode = "TRANSIT"
            elif mode == "walking":
                google_mode = "WALK"
            elif mode == "bicycling":
                google_mode = "BICYCLE"
            else:
                google_mode = "DRIVE"
            
            # Use the new Routes API
            url = "https://routes.googleapis.com/directions/v2:computeRoutes"
            headers = {
                "Content-Type": "application/json",
                "X-Goog-Api-Key": self.google_maps_key,
                "X-Goog-FieldMask": "routes.duration,routes.distanceMeters,routes.legs"
            }
            
            payload = {
                "origin": {
                    "address": origin
                },
                "destination": {
                    "address": destination
                },
                "travelMode": google_mode,
                "routingPreference": "TRAFFIC_AWARE_OPTIMAL",
                "units": "IMPERIAL"
            }
            
            if mode == "transit":
                payload["transitPreferences"] = {
                    "allowedTravelModes": ["BUS", "SUBWAY", "TRAIN", "LIGHT_RAIL"]
                }
            
            logger.debug(f"Calling Google Routes API with payload: {payload}")
            response = await self.http_client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            logger.debug(f"Google Routes API response: {data}")
            if data.get("routes") and len(data["routes"]) > 0:
                route = data["routes"][0]
                
                # Get duration and distance
                duration_seconds = route.get("duration", "0s").rstrip('s')
                distance_meters = route.get("distanceMeters", 0)
                
                # Convert duration from seconds to readable format
                duration_minutes = int(duration_seconds) / 60 if duration_seconds.isdigit() else 0
                duration_text = self._format_duration(duration_minutes)
                
                # Convert distance from meters to miles
                distance_miles = distance_meters * 0.000621371
                distance_text = f"{distance_miles:.1f} miles"
                
                # Get leg info if available
                start_address = origin
                end_address = destination
                if route.get("legs") and len(route["legs"]) > 0:
                    leg = route["legs"][0]
                    start_address = leg.get("startLocation", {}).get("address", origin)
                    end_address = leg.get("endLocation", {}).get("address", destination)
                
                result = {
                    "duration": duration_text,
                    "duration_seconds": int(duration_seconds) if duration_seconds.isdigit() else 0,
                    "distance": distance_text,
                    "distance_meters": distance_meters,
                    "start_address": start_address,
                    "end_address": end_address,
                    "mode": mode,
                    "source": "Google Routes API"
                }
                logger.debug(f"Successfully parsed Google Routes result: {result}")
                return result
            else:
                logger.warning(f"Google Routes API returned empty routes")
                
        except Exception as e:
            logger.error(f"Error getting Google directions: {e}")
            # Fall back to legacy API as backup
            return await self._get_google_directions_legacy(origin, destination, mode)
            
        return None
    
    def _format_duration(self, minutes: float) -> str:
        """Format duration in minutes to human readable format."""
        if minutes < 60:
            return f"{int(minutes)} minutes"
        else:
            hours = int(minutes // 60)
            mins = int(minutes % 60)
            if mins == 0:
                return f"{hours} hour{'s' if hours != 1 else ''}"
            else:
                return f"{hours} hour{'s' if hours != 1 else ''} {mins} minutes"
    
    async def _get_google_directions_legacy(self, origin: str, destination: str, mode: str) -> Optional[Dict[str, Any]]:
        """Fallback to legacy Google Directions API."""
        try:
            # Convert mode for Google API
            google_mode = mode
            if mode == "flying":
                google_mode = "driving"  # Fallback for flights
            
            url = "https://maps.googleapis.com/maps/api/directions/json"
            params = {
                "origin": origin,
                "destination": destination,
                "mode": google_mode,
                "key": self.google_maps_key,
                "units": "imperial",
                "departure_time": "now"
            }
            
            if mode == "transit":
                params["transit_mode"] = "bus|subway|train|tram"
            
            logger.debug(f"Calling Google Maps legacy API with params: {params}")
            response = await self.http_client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            logger.debug(f"Google Maps legacy API response status: {data.get('status')}")
            if data.get("status") == "OK" and data.get("routes"):
                route = data["routes"][0]
                leg = route["legs"][0]
                
                result = {
                    "duration": leg["duration"]["text"],
                    "duration_seconds": leg["duration"]["value"],
                    "distance": leg["distance"]["text"],
                    "distance_meters": leg["distance"]["value"],
                    "start_address": leg["start_address"],
                    "end_address": leg["end_address"],
                    "mode": mode,
                    "source": "Google Maps (Legacy)"
                }
                logger.debug(f"Successfully parsed Google Maps legacy result: {result}")
                return result
            else:
                logger.warning(f"Google Maps legacy API returned status: {data.get('status')}, error_message: {data.get('error_message', 'No error message')}")
                
        except Exception as e:
            logger.error(f"Error getting Google legacy directions: {e}")
            
        return None
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    async def _get_flight_info(self, origin: str, destination: str) -> Optional[Dict[str, Any]]:
        """Get flight information using a flight API or estimate."""
        try:
            # For major city pairs, provide typical flight times
            flight_estimates = {
                ("boston", "new york"): {"duration": "1 hour 30 minutes", "distance": "200 miles"},
                ("new york", "boston"): {"duration": "1 hour 30 minutes", "distance": "200 miles"},
                ("boston, ma", "new york city, ny"): {"duration": "1 hour 30 minutes", "distance": "200 miles"},
                ("new york city, ny", "boston, ma"): {"duration": "1 hour 30 minutes", "distance": "200 miles"},
                ("los angeles", "new york"): {"duration": "5 hours 30 minutes", "distance": "2,450 miles"},
                ("new york", "los angeles"): {"duration": "6 hours", "distance": "2,450 miles"},
                ("san francisco", "los angeles"): {"duration": "1 hour 30 minutes", "distance": "350 miles"},
                ("los angeles", "san francisco"): {"duration": "1 hour 30 minutes", "distance": "350 miles"},
                ("san francisco", "new york"): {"duration": "5 hours 45 minutes", "distance": "2,570 miles"},
                ("new york", "san francisco"): {"duration": "6 hours 15 minutes", "distance": "2,570 miles"},
                ("chicago", "new york"): {"duration": "2 hours 30 minutes", "distance": "790 miles"},
                ("new york", "chicago"): {"duration": "2 hours 45 minutes", "distance": "790 miles"},
            }
            
            # Normalize location names for better matching
            def normalize_location(loc):
                return loc.lower().strip().replace(" city", "").replace(", ny", "").replace(", ca", "").replace(", ma", "").replace(", il", "").replace(",", "").strip()
            
            origin_key = normalize_location(origin)
            dest_key = normalize_location(destination)
            
            logger.debug(f"Checking flight estimates for: {origin_key} -> {dest_key}")
            
            # Try exact match first
            key = (origin_key, dest_key)
            if key in flight_estimates:
                info = flight_estimates[key]
                result = {
                    "duration": info["duration"],
                    "distance": info["distance"],
                    "mode": "flying",
                    "source": "Flight Estimates",
                    "start_address": origin,
                    "end_address": destination
                }
                logger.debug(f"Found flight estimate: {result}")
                return result
                
            # Try partial matches for common variations
            for (est_origin, est_dest), info in flight_estimates.items():
                if (origin_key in est_origin or est_origin in origin_key) and \
                   (dest_key in est_dest or est_dest in dest_key):
                    result = {
                        "duration": info["duration"],
                        "distance": info["distance"],
                        "mode": "flying",
                        "source": "Flight Estimates",
                        "start_address": origin,
                        "end_address": destination
                    }
                    logger.debug(f"Found partial flight estimate match: {result}")
                    return result
                    
            logger.debug(f"No flight estimate found for {origin_key} -> {dest_key}")
                
        except Exception as e:
            logger.error(f"Error getting flight info: {e}")
            
        return None
    
    async def get_travel_info(self, origin: str, destination: str, mode: str = None, query: str = "") -> Dict[str, Any]:
        """Get comprehensive travel information."""
        # Clean locations
        clean_origin = self._clean_location(origin)
        clean_destination = self._clean_location(destination)
        
        # Detect mode if not specified
        if not mode:
            mode = self._detect_transport_mode(query)
        
        logger.info(f"Getting travel info: {clean_origin} -> {clean_destination} via {mode}")
        
        results = []
        
        # Get information based on mode
        if mode == "flying":
            flight_info = await self._get_flight_info(clean_origin, clean_destination)
            if flight_info:
                results.append(flight_info)
        
        # Always try to get driving directions as a backup/comparison
        if mode != "flying":
            directions = await self._get_google_directions(clean_origin, clean_destination, mode)
            if directions:
                results.append(directions)
        
        # If primary mode failed, try driving as fallback
        if not results and mode != "driving":
            driving_directions = await self._get_google_directions(clean_origin, clean_destination, "driving")
            if driving_directions:
                results.append(driving_directions)
                results.append({
                    "note": f"Showing driving directions as {mode} information was unavailable",
                    "requested_mode": mode
                })
        
        return {
            "origin": clean_origin,
            "destination": clean_destination,
            "mode": mode,
            "results": results,
            "has_results": len(results) > 0
        }
    
    async def get_transportation_options(self, origin: str, destination: str) -> Dict[str, Any]:
        """Get multiple transportation options for a route."""
        clean_origin = self._clean_location(origin)
        clean_destination = self._clean_location(destination)
        
        logger.info(f"Getting transportation options: {clean_origin} -> {clean_destination}")
        
        # Try multiple modes
        modes_to_try = ["driving", "transit", "flying"]
        results = []
        
        # Execute API calls in parallel for faster response
        tasks = []
        
        for mode in modes_to_try:
            if mode == "flying":
                tasks.append(self._get_flight_info(clean_origin, clean_destination))
            else:
                tasks.append(self._get_google_directions(clean_origin, clean_destination, mode))
        
        # Wait for all tasks to complete
        api_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(api_results):
            if result and not isinstance(result, Exception):
                result["transportation_mode"] = modes_to_try[i]
                results.append(result)
        
        return {
            "origin": clean_origin,
            "destination": clean_destination,
            "options": results,
            "has_options": len(results) > 0
        }
    
    def format_travel_response(self, travel_data: Dict[str, Any], query: str) -> str:
        """Format travel information into a natural language response."""
        if not travel_data.get("has_results") and not travel_data.get("has_options"):
            return f"I couldn't find travel information between {travel_data.get('origin', 'the origin')} and {travel_data.get('destination', 'the destination')}. Please check the location names and try again."
        
        origin = travel_data.get("origin", "")
        destination = travel_data.get("destination", "")
        
        # Handle single route results
        if "results" in travel_data:
            results = travel_data["results"]
            if results:
                primary_result = results[0]
                mode = primary_result.get("mode", travel_data.get("mode", ""))
                
                response = f"**Travel from {origin} to {destination}**\n\n"
                
                if mode == "flying":
                    response += f"✈️ **By Air**: {primary_result.get('duration', 'Unknown time')}"
                    if primary_result.get('distance'):
                        response += f" ({primary_result['distance']})"
                elif mode == "driving":
                    response += f"🚗 **By Car**: {primary_result.get('duration', 'Unknown time')}"
                    if primary_result.get('distance'):
                        response += f" ({primary_result['distance']})"
                elif mode == "transit":
                    response += f"🚊 **By Public Transit**: {primary_result.get('duration', 'Unknown time')}"
                    if primary_result.get('distance'):
                        response += f" ({primary_result['distance']})"
                elif mode == "walking":
                    response += f"🚶 **Walking**: {primary_result.get('duration', 'Unknown time')}"
                    if primary_result.get('distance'):
                        response += f" ({primary_result['distance']})"
                
                # Add any notes
                if len(results) > 1 and isinstance(results[1], dict) and "note" in results[1]:
                    response += f"\n\n*Note: {results[1]['note']}*"
                
                response += f"\n\n*Source: {primary_result.get('source', 'Travel Service')}*"
                
                return response
        
        # Handle multiple transportation options
        if "options" in travel_data:
            options = travel_data["options"]
            if options:
                response = f"**Travel Options from {origin} to {destination}**\n\n"
                
                for option in options:
                    mode = option.get("transportation_mode", option.get("mode", ""))
                    if mode == "flying":
                        response += f"✈️ **By Air**: {option.get('duration', 'Unknown time')}"
                    elif mode == "driving":
                        response += f"🚗 **By Car**: {option.get('duration', 'Unknown time')}"
                    elif mode == "transit":
                        response += f"🚊 **By Public Transit**: {option.get('duration', 'Unknown time')}"
                    
                    if option.get('distance'):
                        response += f" ({option['distance']})"
                    response += "\n"
                
                response += f"\n*Travel times are estimates and may vary based on current conditions.*"
                return response
        
        return "I found some travel information, but couldn't format it properly. Please try rephrasing your question."

# Service registry function
def get_travel_service() -> TravelService:
    """Get or create travel service instance."""
    if not hasattr(get_travel_service, '_instance'):
        get_travel_service._instance = TravelService()
    return get_travel_service._instance 