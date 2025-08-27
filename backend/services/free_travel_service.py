"""Free travel service using OpenStreetMap and open APIs."""
import logging
import json
import asyncio
import time
from typing import Dict, Any, Optional, Tuple
import httpx
import re

logger = logging.getLogger(__name__)

class FreeTravelService:
    """Service for fetching travel information using completely free APIs."""
    
    def __init__(self):
        """Initialize the free travel service."""
        logger.info("Initializing FreeTravelService (100% Free)")
        
        self.http_client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": "RecruitIQ Travel Assistant/1.0",
                "Accept": "application/json"
            }
        )
        
        # Free API endpoints
        self.osrm_base_url = "http://router.project-osrm.org"
        self.nominatim_base_url = "https://nominatim.openstreetmap.org"
        
        # Flight time estimates for major routes
        self.flight_estimates = {
            ("boston", "new york"): {"duration": "1 hour 30 minutes", "distance": "200 miles"},
            ("new york", "boston"): {"duration": "1 hour 30 minutes", "distance": "200 miles"},
            ("los angeles", "new york"): {"duration": "5 hours 30 minutes", "distance": "2,450 miles"},
            ("new york", "los angeles"): {"duration": "6 hours", "distance": "2,450 miles"},
            ("san francisco", "new york"): {"duration": "5 hours 45 minutes", "distance": "2,570 miles"},
            ("new york", "san francisco"): {"duration": "6 hours 15 minutes", "distance": "2,570 miles"},
            ("chicago", "new york"): {"duration": "2 hours 30 minutes", "distance": "790 miles"},
            ("new york", "chicago"): {"duration": "2 hours 45 minutes", "distance": "790 miles"},
        }
        
        logger.info("FreeTravelService initialized with free APIs")
    
    def _detect_transport_mode(self, query: str) -> str:
        """Detect transportation mode from the query."""
        query_lower = query.lower()
        
        if any(word in query_lower for word in ["fly", "flight", "plane", "air"]):
            return "flying"
        elif any(word in query_lower for word in ["train", "bus", "public transport", "transit"]):
            return "transit"
        elif any(word in query_lower for word in ["walk", "walking", "foot"]):
            return "walking"
        elif any(word in query_lower for word in ["bike", "bicycle", "cycling"]):
            return "cycling"
        else:
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
            "nyc": "New York",
            "ny": "New York", 
            "boston": "Boston",
            "sf": "San Francisco",
            "la": "Los Angeles",
            "chicago": "Chicago",
            "dc": "Washington",
            "philly": "Philadelphia"
        }
        
        location_lower = location.lower().strip()
        return city_mappings.get(location_lower, location.strip())
    
    def _get_location_key(self, location: str) -> str:
        """Convert location to a standardized key for lookups."""
        return location.lower().replace(" city", "").replace(", ny", "").replace(", ca", "").replace(", ma", "").replace(", il", "").replace(", dc", "").strip()
    
    async def _geocode_location(self, location: str) -> Optional[Tuple[float, float]]:
        """Geocode a location using Nominatim (free)."""
        for attempt in range(3):
            try:
                url = f"{self.nominatim_base_url}/search"
                params = {
                    "q": location,
                    "format": "json",
                    "limit": 1,
                    "addressdetails": 1
                }
                
                response = await self.http_client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                
                if data and len(data) > 0:
                    result = data[0]
                    lat = float(result["lat"])
                    lon = float(result["lon"])
                    return (lat, lon)
                    
            except Exception as e:
                logger.error(f"Error geocoding {location} (attempt {attempt + 1}): {e}")
                if attempt < 2:
                    await asyncio.sleep(1 * (attempt + 1))
                
        return None
    
    async def _get_osrm_route(self, origin_coords: Tuple[float, float], dest_coords: Tuple[float, float], profile: str = "driving") -> Optional[Dict[str, Any]]:
        """Get route from OSRM (free)."""
        for attempt in range(3):
            try:
                osrm_profile = profile if profile in ["driving", "walking", "cycling"] else "driving"
                
                origin_lat, origin_lon = origin_coords
                dest_lat, dest_lon = dest_coords
                
                url = f"{self.osrm_base_url}/route/v1/{osrm_profile}/{origin_lon},{origin_lat};{dest_lon},{dest_lat}"
                params = {
                    "overview": "false",
                    "alternatives": "false",
                    "steps": "false"
                }
                
                response = await self.http_client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                
                if data.get("code") == "Ok" and data.get("routes"):
                    route = data["routes"][0]
                    
                    # Convert from meters and seconds
                    distance_miles = route["distance"] * 0.000621371
                    duration_minutes = route["duration"] / 60
                    
                    duration_text = self._format_duration(duration_minutes)
                    distance_text = f"{distance_miles:.1f} miles"
                    
                    return {
                        "duration": duration_text,
                        "distance": distance_text,
                        "mode": profile,
                        "source": "OpenStreetMap (OSRM)"
                    }
                    
            except Exception as e:
                logger.error(f"Error getting OSRM route (attempt {attempt + 1}): {e}")
                if attempt < 2:
                    await asyncio.sleep(1 * (attempt + 1))
                
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
    
    async def _get_flight_info(self, origin: str, destination: str) -> Optional[Dict[str, Any]]:
        """Get flight information from static estimates."""
        origin_key = self._get_location_key(origin)
        dest_key = self._get_location_key(destination)
        
        key = (origin_key, dest_key)
        if key in self.flight_estimates:
            info = self.flight_estimates[key]
            return {
                "duration": info["duration"],
                "distance": info["distance"],
                "mode": "flying",
                "source": "Flight Time Estimates",
                "start_address": origin,
                "end_address": destination
            }
        
        return None
    
    async def get_travel_info(self, origin: str, destination: str, mode: str = None, query: str = "") -> Dict[str, Any]:
        """Get comprehensive travel information using free APIs."""
        clean_origin = self._clean_location(origin)
        clean_destination = self._clean_location(destination)
        
        if not mode:
            mode = self._detect_transport_mode(query)
        
        logger.info(f"Getting free travel info: {clean_origin} -> {clean_destination} via {mode}")
        
        results = []
        
        if mode == "flying":
            flight_info = await self._get_flight_info(clean_origin, clean_destination)
            if flight_info:
                results.append(flight_info)
        
        else:
            try:
                origin_coords = await self._geocode_location(clean_origin)
                dest_coords = await self._geocode_location(clean_destination)
                
                if origin_coords and dest_coords:
                    osrm_mode = "cycling" if mode == "bicycling" else mode
                    
                    route_info = await self._get_osrm_route(origin_coords, dest_coords, osrm_mode)
                    if route_info:
                        route_info["start_address"] = clean_origin
                        route_info["end_address"] = clean_destination
                        results.append(route_info)
                
            except Exception as e:
                logger.error(f"Error getting route info: {e}")
        
        if not results:
            flight_info = await self._get_flight_info(clean_origin, clean_destination)
            if flight_info:
                results.append(flight_info)
                results.append({
                    "note": f"Showing flight information as {mode} data was unavailable",
                    "requested_mode": mode
                })
        
        return {
            "origin": clean_origin,
            "destination": clean_destination,
            "mode": mode,
            "results": results,
            "has_results": len(results) > 0
        }
    
    def format_travel_response(self, travel_data: Dict[str, Any], query: str) -> str:
        """Format travel information into a natural language response."""
        if not travel_data.get("has_results"):
            return f"I couldn't find travel information between {travel_data.get('origin', 'the origin')} and {travel_data.get('destination', 'the destination')}. This might be because the locations are not well-covered by free mapping services."
        
        origin = travel_data.get("origin", "")
        destination = travel_data.get("destination", "")
        results = travel_data.get("results", [])
        
        if results:
            primary_result = results[0]
            mode = primary_result.get("mode", travel_data.get("mode", ""))
            
            response = f"**🆓 Free Travel Info: {origin} to {destination}**\n\n"
            
            if mode == "flying":
                response += f"✈️ **By Air**: {primary_result.get('duration', 'Unknown time')}"
            elif mode == "driving":
                response += f"🚗 **By Car**: {primary_result.get('duration', 'Unknown time')}"
            elif mode == "walking":
                response += f"🚶 **Walking**: {primary_result.get('duration', 'Unknown time')}"
            elif mode == "cycling":
                response += f"🚴 **Cycling**: {primary_result.get('duration', 'Unknown time')}"
            
            if primary_result.get('distance'):
                response += f" ({primary_result['distance']})"
            
            if len(results) > 1 and isinstance(results[1], dict) and "note" in results[1]:
                response += f"\n\n*Note: {results[1]['note']}*"
            
            response += f"\n\n*Source: {primary_result.get('source', 'Free Travel Service')}*"
            response += f"\n*📍 Using free OpenStreetMap data - no API costs!*"
            
            return response
        
        return "I found some travel information, but couldn't format it properly. Please try rephrasing your question."

def get_free_travel_service() -> FreeTravelService:
    """Get or create free travel service instance."""
    if not hasattr(get_free_travel_service, '_instance'):
        get_free_travel_service._instance = FreeTravelService()
    return get_free_travel_service._instance 