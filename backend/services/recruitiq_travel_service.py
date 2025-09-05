"""RecruitIQ Travel Service - Specialized travel service for recruiting scenarios."""
import logging
import os
import json
import asyncio
import time
import re
from typing import Dict, Any, Optional, Tuple, List, Union
from ..utils.config import get_settings
import httpx
import math
from datetime import datetime, timedelta
import threading

logger = logging.getLogger(__name__)

class RecruitIQTravelService:
    """Service for fetching and analyzing travel information specifically for recruiting scenarios."""
    
    def __init__(self):
        """Initialize the RecruitIQ travel service."""
        logger.info("Initializing RecruitIQTravelService for recruiting-focused travel intelligence")
        
        # Load configured API keys from settings (if available)
        settings = None
        try:
            settings = get_settings()
        except Exception:
            settings = None

        # Distinguish between OpenRouter (LLM) API key and OpenRouteService (routing) API key.
        # OPENROUTER_API_KEY is used elsewhere for LLMs; the routing service expects a separate
        # OPENROUTESERVICE_API_KEY environment variable. Prefer the dedicated routing key.
        self.openroute_llm_key = ''
        if settings is not None:
            try:
                self.openroute_llm_key = getattr(settings, 'openrouter_api_key', '') or ''
            except Exception:
                self.openroute_llm_key = ''

        # Check for dedicated routing key in Settings (preferred) and fallback to environment
        self.openrouteservice_api_key = ''
        if settings is not None:
            try:
                self.openrouteservice_api_key = getattr(settings, 'openrouteservice_api_key', '') or ''
            except Exception:
                self.openrouteservice_api_key = os.getenv('OPENROUTESERVICE_API_KEY', '')
        else:
            self.openrouteservice_api_key = os.getenv('OPENROUTESERVICE_API_KEY', '')

        if not self.openrouteservice_api_key and self.openroute_llm_key:
            # If only the LLM key is present, log a helpful hint — it will not work for routing
            logger.info("OpenRouteService routing key not found in OPENROUTESERVICE_API_KEY. "
                        "Found OPENROUTER_API_KEY which is likely an LLM key and won't work for routing APIs.")
        
        # Log API key status for debugging (without exposing the actual key)
        if self.openrouteservice_api_key:
            logger.info(f"OpenRouteService API key configured (length: {len(self.openrouteservice_api_key)})")
        else:
            logger.warning("OpenRouteService API key not configured - routing features will be limited")

        # Prepare default headers and include authorization header (routing key) if present
        default_headers = {
            "User-Agent": "RecruitIQ Travel Assistant/1.0",
            "Accept": "application/json"
        }

        if self.openrouteservice_api_key:
            # OpenRouteService expects the API key in the Authorization header
            # Format: "Authorization: <api_key>" (no "Bearer" prefix)
            default_headers["Authorization"] = self.openrouteservice_api_key

        self.http_client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers=default_headers
        )
        
        # Free API endpoints
        self.openroute_base_url = "https://api.openrouteservice.org"
        self.nominatim_base_url = "https://nominatim.openstreetmap.org"
        self.openmeteo_base_url = "https://api.open-meteo.com/v1"
        self.kiwi_base_url = "https://api.tequila.kiwi.com/v2"
        
        # Cache for API responses to reduce calls
        self.geocode_cache = {}
        self.directions_cache = {}
        self.weather_cache = {}
        self.flights_cache = {}
        
        # Recruiting-specific travel patterns
        self.recruiting_travel_patterns = {
            "interview_travel": [
                r"(interview|interviews|interviewing).*?(travel|commute|get to|arrive)",
                r"(how|best way).*?(get to|reach).*?(interview|office|headquarters)",
                r"(travel|transportation).*?(options|arrangements).*?(interview|candidate)"
            ],
            "relocation": [
                r"(relocation|relocate|moving).*?(for|to).*?(job|position|offer|role)",
                r"(commute|travel|distance).*?(new job|new role|new position)",
                r"(moving|move|relocate).*?(family|spouse|partner).*?(job|position|offer)"
            ],
            "office_visit": [
                r"(visit|visiting).*?(office|headquarters|location|site)",
                r"(travel|trip).*?(office|headquarters|location|site)",
                r"(directions|navigate).*?(office|headquarters|location)"
            ],
            "candidate_travel": [
                r"(candidate|applicant|interviewee).*?(travel|transportation|arrival)",
                r"(arrange|book|schedule).*?(travel|flight|transportation).*?(candidate|applicant)",
                r"(reimburse|cover|pay for).*?(travel|transportation).*?(expenses|costs)"
            ]
        }
        
        logger.info("RecruitIQTravelService initialized with recruiting-specific patterns")

        # Start a non-blocking startup check for routing API authentication.
        try:
            threading.Thread(target=self._run_startup_check, daemon=True).start()
        except Exception as e:
            logger.debug(f"Could not start routing startup check thread: {e}")
    
    # Intent Classification Methods
    
    def classify_recruiting_intent(self, query: str) -> Dict[str, Any]:
        """
        Classify the recruiting-related travel intent from a user query.
        
        Args:
            query: The user's query text
            
        Returns:
            Dict containing intent classification results
        """
        # First try pattern-based classification
        pattern_results = self._classify_with_patterns(query)
        
        if pattern_results.get('matched', False):
            logger.info(f"Classified recruiting travel intent using patterns: {pattern_results['intent_type']}")
            return pattern_results
        
        # Extract potential locations using regex
        locations = self._extract_locations(query)
        
        result = {
            'query': query,
            'matched': bool(pattern_results.get('matched', False) or locations),
            'intent_type': pattern_results.get('intent_type', 'general_travel'),
            'origin': locations.get('origin', ''),
            'destination': locations.get('destination', ''),
            'confidence': pattern_results.get('confidence', 0.6) if pattern_results.get('matched', False) else 0.4,
            'travel_mode': self._detect_travel_mode(query),
            'is_recruiting_related': self._is_recruiting_related(query)
        }
        
        return result
    
    def _extract_locations(self, query: str) -> Dict[str, str]:
        """
        Extract origin and destination locations from a query.
        
        Args:
            query: The user's query text
            
        Returns:
            Dict containing origin and destination if found
        """
        # Common patterns for location extraction
        patterns = [
            # "from X to Y"
            r'from\s+(?P<origin>[A-Za-z\s,]+)\s+to\s+(?P<destination>[A-Za-z\s,]+)',
            # "X to Y"
            r'(?P<origin>[A-Za-z\s,]+)\s+to\s+(?P<destination>[A-Za-z\s,]+)',
            # "between X and Y"
            r'between\s+(?P<origin>[A-Za-z\s,]+)\s+and\s+(?P<destination>[A-Za-z\s,]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                return {
                    'origin': match.group('origin').strip(),
                    'destination': match.group('destination').strip()
                }
        
        return {'origin': '', 'destination': ''}
    
    def _detect_travel_mode(self, query: str) -> str:
        """
        Detect the travel mode from the query.
        
        Args:
            query: The user's query text
            
        Returns:
            Detected travel mode
        """
        query_lower = query.lower()
        
        if any(word in query_lower for word in ['fly', 'flight', 'plane', 'air', 'airport']):
            return 'flying'
        elif any(word in query_lower for word in ['train', 'rail', 'amtrak', 'subway', 'metro']):
            return 'transit'
        elif any(word in query_lower for word in ['bus', 'public transport', 'transit']):
            return 'transit'
        elif any(word in query_lower for word in ['walk', 'walking', 'foot']):
            return 'walking'
        elif any(word in query_lower for word in ['bike', 'bicycle', 'cycling']):
            return 'cycling'
        else:
            return 'driving'
    
    def _is_recruiting_related(self, query: str) -> bool:
        """
        Determine if the query is related to recruiting.
        
        Args:
            query: The user's query text
            
        Returns:
            Boolean indicating if query is recruiting-related
        """
        recruiting_terms = [
            'interview', 'candidate', 'applicant', 'job', 'position', 'offer', 
            'role', 'hiring', 'recruit', 'talent', 'hr', 'human resources',
            'onsite', 'on-site', 'relocation', 'relocate', 'office visit',
            'headquarters', 'hq', 'company', 'employer'
        ]
        
        query_lower = query.lower()
        return any(term in query_lower for term in recruiting_terms)
    
    def _classify_with_patterns(self, query: str) -> Dict[str, Any]:
        """
        Use pattern matching to classify recruiting travel intents.
        
        Args:
            query: The user's query text
            
        Returns:
            Dict containing pattern matching results
        """
        query_lower = query.lower()
        result = {
            'matched': False,
            'intent_type': '',
            'confidence': 0.0,
            'pattern_matched': ''
        }
        
        # Check each intent type and its patterns
        for intent_type, patterns in self.recruiting_travel_patterns.items():
            for pattern in patterns:
                match = re.search(pattern, query_lower, re.IGNORECASE)
                if match:
                    result['matched'] = True
                    result['intent_type'] = intent_type
                    result['confidence'] = 0.8  # High confidence for pattern matches
                    result['pattern_matched'] = pattern
                    
                    # Extract any captured groups
                    if match.groupdict():
                        for key, value in match.groupdict().items():
                            result[key] = value
                    
                    return result
        
        # Check for general travel patterns if no recruiting-specific patterns matched
        general_travel_patterns = [
            r'(travel|trip|commute|journey|drive|fly).*?(to|from|between)',
            r'(how|what).*?(get|travel|commute).*?(to|from)',
            r'(directions|route|path|way).*?(to|from|between)',
            r'(distance|time|duration|long).*?(travel|trip|commute|journey|drive|fly)'
        ]
        
        for pattern in general_travel_patterns:
            if re.search(pattern, query_lower, re.IGNORECASE):
                result['matched'] = True
                result['intent_type'] = 'general_travel'
                result['confidence'] = 0.6  # Medium confidence
                result['pattern_matched'] = pattern
                return result
        
        return result
    
    # Travel Data Gathering Methods
    
    async def gather_recruiting_travel_data(self, origin: str, destination: str, 
                                           intent_type: str, travel_date: Optional[str] = None, query: str = "") -> Dict[str, Any]:
        """
        Gather comprehensive travel data for recruiting scenarios.
        
        Args:
            origin: Origin location
            destination: Destination location
            intent_type: Type of recruiting intent (interview_travel, relocation, etc.)
            travel_date: Optional date of travel
            
        Returns:
            Dict containing comprehensive travel data
        """
        logger.info(f"Gathering recruiting travel data for {intent_type} from {origin} to {destination}")
        
        # Initialize result structure
        result = {
            "origin": origin,
            "destination": destination,
            "intent_type": intent_type,
            "travel_date": travel_date,
            "timestamp": datetime.now().isoformat(),
            "travel_mode": self._detect_travel_mode(query or f"from {origin} to {destination}")
        }
        
        try:
            # Step 1: Geocode origin and destination
            logger.info("Geocoding origin and destination locations")
            origin_coords = await self._geocode_nominatim(origin)
            dest_coords = await self._geocode_nominatim(destination)
            
            if origin_coords and dest_coords:
                result["origin_coords"] = origin_coords
                result["destination_coords"] = dest_coords
                
                # Step 2: Get enhanced weather at destination
                logger.info("Fetching weather conditions at destination")
                weather_data = await self._get_enhanced_weather_conditions(dest_coords[0], dest_coords[1], travel_date)
                if weather_data:
                    result["weather"] = weather_data
                
                # Step 3: Get directions based on travel mode
                travel_mode = result["travel_mode"]
                
                if travel_mode == "flying":
                    # If flying, get flight options
                    logger.info("Fetching flight options")
                    
                    # Determine if we're using city codes or location names
                    origin_code = origin if len(origin.strip()) <= 3 else None
                    dest_code = destination if len(destination.strip()) <= 3 else None
                    
                    flight_data = await self._get_kiwi_flights(origin_code or origin, dest_code or destination, 
                                                          date_from=travel_date)
                    if flight_data:
                        result["flights"] = flight_data
                    
                    # Also get ground transportation at destination for the last mile
                    # Simulate a typical airport to destination route
                    if dest_coords:
                        # Create approximate airport coordinates (slightly offset from destination)
                        airport_lat = dest_coords[0] + 0.05  # Rough approximation
                        airport_lon = dest_coords[1] + 0.05
                        airport_coords = (airport_lat, airport_lon)
                        
                        # Get directions from simulated airport to final destination
                        logger.info("Fetching ground directions from airport to destination")
                        directions = await self._get_openroute_directions(
                            airport_coords, dest_coords, "driving-car")
                        if directions:
                            result["airport_to_destination"] = directions
                else:
                    # For non-flying modes, get direct route
                    logger.info(f"Fetching {travel_mode} directions")
                    profile = "driving-car"
                    
                    # Map travel mode to OpenRoute profile
                    if travel_mode == "walking":
                        profile = "foot-walking"
                    elif travel_mode == "cycling":
                        profile = "cycling-regular"
                    elif travel_mode == "transit":
                        # Check if this is a train schedule request
                        query_lower = query.lower() if query else f"from {origin} to {destination}".lower()
                        if any(word in query_lower for word in ['train', 'schedule', 'amtrak', 'rail']):
                            # Get train schedule information
                            logger.info("Fetching train schedule information")
                            train_data = await self._get_train_schedule_info(origin, destination)
                            if train_data:
                                result["train_schedule"] = train_data
                        else:
                            # OpenRoute doesn't support transit directly, use driving as approximation
                            profile = "driving-car"
                        
                    if profile != "transit":  # Only get directions if not handling train schedules
                        directions = await self._get_openroute_directions(origin_coords, dest_coords, profile)
                        if directions:
                            result["directions"] = directions
                
            # Step 4: Generate comprehensive cost analysis
            logger.info("Generating comprehensive cost analysis")
            cost_analysis = await self._generate_cost_analysis(result, intent_type)
            if cost_analysis:
                result["cost_analysis"] = cost_analysis
            
            # Step 5: Get local area intelligence
            logger.info("Gathering local area intelligence")
            local_area = await self._get_local_area_intelligence(destination, dest_coords)
            if local_area:
                result["local_area"] = local_area
            
            # Step 6: Generate transportation comparison
            logger.info("Generating transportation comparison")
            transport_comparison = await self._generate_transportation_comparison(result)
            if transport_comparison:
                result["transportation_comparison"] = transport_comparison
            
            # Step 7: Get recruiting-specific advice
            logger.info("Generating recruiting-specific travel advice")
            advice = await self._get_recruiting_specific_advice(origin, destination, intent_type, result)
            if advice:
                result["recruiting_advice"] = advice
            
            # Add overall assessment
            result["assessment"] = self._generate_travel_assessment(result, intent_type)
            
            return result
            
        except Exception as e:
            logger.error(f"Error gathering recruiting travel data: {e}")
            # Return partial result if we have any data
            if len(result) > 4:  # More than just the input parameters
                return result
            else:
                return {"error": str(e), "origin": origin, "destination": destination}
    
    def _generate_travel_assessment(self, travel_data: Dict[str, Any], intent_type: str) -> Dict[str, Any]:
        """
        Generate overall assessment of travel options for recruiting context.
        
        Args:
            travel_data: Collected travel data
            intent_type: Type of recruiting intent
            
        Returns:
            Dict containing assessment metrics
        """
        assessment = {
            "overall_convenience": "medium",  # Default
            "recommended_buffer_time": 30,  # Default 30 minutes
            "stress_level": "moderate",      # Default
            "special_considerations": []
        }
        
        # Assess convenience based on travel mode and duration
        travel_mode = travel_data.get("travel_mode", "unknown")
        
        if "directions" in travel_data:
            duration_seconds = travel_data["directions"].get("duration", 0)
            duration_mins = duration_seconds / 60
            
            # Set buffer time based on duration
            if duration_mins < 30:
                assessment["recommended_buffer_time"] = 15
                assessment["overall_convenience"] = "high"
                assessment["stress_level"] = "low"
            elif duration_mins < 60:
                assessment["recommended_buffer_time"] = 30
                assessment["overall_convenience"] = "medium"
                assessment["stress_level"] = "moderate"
            else:
                assessment["recommended_buffer_time"] = 45
                assessment["overall_convenience"] = "low"
                assessment["stress_level"] = "high"
                assessment["special_considerations"].append(
                    "Long commute may impact candidate experience")
        
        # Consider weather impact
        if "weather" in travel_data:
            weather_data = travel_data["weather"]
            weather_impact = self._assess_weather_impact(weather_data)
            
            if weather_impact == "severe":
                assessment["special_considerations"].append(
                    "Weather conditions may significantly impact travel")
                assessment["recommended_buffer_time"] += 15  # Add 15 minutes buffer
                assessment["stress_level"] = "high"
            elif weather_impact == "moderate":
                assessment["special_considerations"].append(
                    "Weather conditions may cause slight delays")
                assessment["recommended_buffer_time"] += 10  # Add 10 minutes buffer
        
        # Add special considerations based on intent type
        if intent_type == "interview_travel":
            assessment["special_considerations"].append(
                "Candidate comfort and punctuality are priorities")
        elif intent_type == "relocation":
            assessment["special_considerations"].append(
                "Consider typical commute patterns at different times/days")
        elif intent_type == "candidate_travel":
            assessment["special_considerations"].append(
                "Ensure clear communication of travel reimbursement policies")
        
        return assessment
    
    async def _geocode_nominatim(self, location: str) -> Optional[Tuple[float, float]]:
        """
        Geocode a location using Nominatim (free OpenStreetMap service).
        
        Args:
            location: Location name or address
            
        Returns:
            Tuple of (latitude, longitude) if successful, None otherwise
        """
        # Check cache first
        if location in self.geocode_cache:
            logger.info(f"Using cached geocode data for {location}")
            return self.geocode_cache[location]
        
        # Normalize location string
        location = location.strip()
        if not location:
            return None
        
        try:
            # Build the request URL
            url = f"{self.nominatim_base_url}/search"
            
            # Prepare parameters
            params = {
                "q": location,
                "format": "json",
                "limit": 1,  # Only need the top result
                "addressdetails": 0  # Don't need detailed address information
            }
            
            # Add recruiting-specific context to improve geocoding
            if any(term in location.lower() for term in ['office', 'hq', 'headquarters', 'campus']):
                # If it's likely a business location, use appropriate settings
                params.update({"featuretype": "building"})
            
            # Respect Nominatim usage policy with a small delay
            await asyncio.sleep(1.0)  
            
            # Make the request
            logger.info(f"Geocoding location: {location}")
            response = await self.http_client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            # Process the response
            if data and len(data) > 0:
                lat = float(data[0].get('lat'))
                lon = float(data[0].get('lon'))
                
                # Cache the result
                self.geocode_cache[location] = (lat, lon)
                
                logger.info(f"Geocoded {location} to coordinates: {lat}, {lon}")
                return (lat, lon)
            else:
                logger.warning(f"Could not geocode location: {location}")
                return None
                
        except Exception as e:
            logger.error(f"Error geocoding location {location}: {e}")
            return None
    
    async def _get_openroute_directions(self, origin_coords: Tuple[float, float], 
                                       dest_coords: Tuple[float, float], 
                                       profile: str = "driving-car") -> Optional[Dict[str, Any]]:
        """
        Get directions from OpenRouteService (free).
        
        Args:
            origin_coords: Origin coordinates (lat, lon)
            dest_coords: Destination coordinates (lat, lon)
            profile: Transportation profile
            
        Returns:
            Dict containing directions data if successful, None otherwise
        """
        # Check cache first
        cache_key = f"{origin_coords},{dest_coords},{profile}"
        if cache_key in self.directions_cache:
            logger.info(f"Using cached directions data for {cache_key}")
            return self.directions_cache[cache_key]
        
        try:
            # OpenRouteService expects [lon, lat] format, not [lat, lon]
            # So we need to reverse the coordinates
            coords = [
                [origin_coords[1], origin_coords[0]],  # [lon, lat] for origin
                [dest_coords[1], dest_coords[0]]        # [lon, lat] for destination
            ]
            
            # Validate transportation profile
            valid_profiles = [
                "driving-car", "driving-hgv", "cycling-regular", 
                "cycling-road", "cycling-mountain", "cycling-electric",
                "foot-walking", "foot-hiking", "wheelchair"
            ]
            
            if profile not in valid_profiles:
                profile = "driving-car"  # Default to car if invalid profile
            
            # Build the request URL
            url = f"{self.openroute_base_url}/v2/directions/{profile}/json"
            
            # Prepare the request body
            data = {
                "coordinates": coords,
                "instructions": True,
                "units": "mi",  # Use miles for US context
                "language": "en"
            }
            
            # Add recruiting context parameters 
            if profile == "driving-car":
                # For driving, optimize for reliability (less time variance)
                data["preference"] = "recommended"
            elif "foot" in profile:
                # For walking, optimize for shortest path if it's to an interview
                data["preference"] = "shortest"
            
            # Make the request
            logger.info(f"Fetching directions from {origin_coords} to {dest_coords} via {profile}")
            request_headers = {}
            # Prefer the dedicated routing key, fallback to llm-style key only if necessary
            if getattr(self, 'openrouteservice_api_key', ''):
                request_headers['Authorization'] = getattr(self, 'openrouteservice_api_key')
            elif getattr(self, 'openroute_llm_key', ''):
                request_headers['Authorization'] = getattr(self, 'openroute_llm_key')

            response = await self.http_client.post(url, json=data, headers=request_headers)
            
            # Handle API access issues gracefully
            if response.status_code in (401, 403):
                error_msg = "OpenRouteService API access denied"
                try:
                    error_data = response.json()
                    if "Access to this API has been disallowed" in str(error_data):
                        error_msg = "OpenRouteService API access has been disallowed - check API key permissions"
                except:
                    pass
                logger.warning(f"{error_msg}. Falling back to distance estimation.")
                return self._estimate_driving_option(origin_coords, dest_coords)
            
            response.raise_for_status()
            
            route_data = response.json()
            
            # Process the response
            if "routes" in route_data and route_data["routes"]:
                route = route_data["routes"][0]  # Get the first (best) route
                
                # Extract useful information
                result = {
                    "distance": route.get("summary", {}).get("distance", 0),  # In miles
                    "duration": route.get("summary", {}).get("duration", 0),  # In seconds
                    "formatted_duration": self._format_duration(route.get("summary", {}).get("duration", 0) / 60),
                    "bounds": route.get("bbox", []),
                    "steps": []
                }
                
                # Extract navigation steps if available
                if "segments" in route:
                    for segment in route["segments"]:
                        for step in segment.get("steps", []):
                            instruction = {
                                "instruction": step.get("instruction", ""),
                                "distance": step.get("distance", 0),
                                "duration": step.get("duration", 0),
                                "name": step.get("name", "")
                            }
                            result["steps"].append(instruction)
                
                # Add recruiting-specific assessments
                result["recruiting_assessment"] = {
                    "is_convenient": result["duration"] < 3600,  # Less than 1 hour
                    "travel_impact": "low" if result["duration"] < 1800 else 
                                    "moderate" if result["duration"] < 3600 else "high",
                    "recommended_departure_buffer": 15 if result["duration"] < 1200 else 
                                                 30 if result["duration"] < 2400 else 45  # In minutes
                }
                
                # Cache the result
                self.directions_cache[cache_key] = result
                
                return result
            else:
                logger.warning("No routes found in the response")
                return None
                
        except httpx.HTTPStatusError as e:
            status = None
            try:
                status = e.response.status_code
            except Exception:
                status = None

            # If auth failed (401/403) and we have a key, try a single retry using 'Bearer <key>'
            if status in (401, 403) and getattr(self, 'openrouteservice_api_key', ''):
                try:
                    masked = 'set' if self.openrouteservice_api_key else 'not-set'
                    logger.warning(f"OpenRouteService returned {status}. Attempting one retry using 'Bearer' auth if key is present (key {masked}).")
                    # Try with Bearer prefix
                    bearer_headers = {'Authorization': f"Bearer {self.openrouteservice_api_key}"}
                    response2 = await self.http_client.post(url, json=data, headers=bearer_headers)
                    response2.raise_for_status()
                    route_data = response2.json()
                    if "routes" in route_data and route_data["routes"]:
                        route = route_data["routes"][0]
                        # reuse the same processing as above
                        result = {
                            "distance": route.get("summary", {}).get("distance", 0),
                            "duration": route.get("summary", {}).get("duration", 0),
                            "formatted_duration": self._format_duration(route.get("summary", {}).get("duration", 0) / 60),
                            "bounds": route.get("bbox", []),
                            "steps": []
                        }
                        if "segments" in route:
                            for segment in route["segments"]:
                                for step in segment.get("steps", []):
                                    instruction = {
                                        "instruction": step.get("instruction", ""),
                                        "distance": step.get("distance", 0),
                                        "duration": step.get("duration", 0),
                                        "name": step.get("name", "")
                                    }
                                    result["steps"].append(instruction)

                        result["recruiting_assessment"] = {
                            "is_convenient": result["duration"] < 3600,
                            "travel_impact": "low" if result["duration"] < 1800 else 
                                            "moderate" if result["duration"] < 3600 else "high",
                            "recommended_departure_buffer": 15 if result["duration"] < 1200 else 
                                                         30 if result["duration"] < 2400 else 45
                        }

                        # Cache and return
                        self.directions_cache[cache_key] = result
                        return result
                except Exception as ex:
                    logger.error(f"Retry with 'Bearer' auth failed: {ex}")

            logger.error(f"Error fetching directions: {e}")
            return None
        except Exception as e:
            logger.error(f"Error fetching directions: {e}")
            return None
    
    async def _get_kiwi_flights(self, origin: str, destination: str, 
                               date_from: Optional[str] = None, 
                               date_to: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get flight options estimation from Kiwi.
        
        Args:
            origin: Origin location
            destination: Destination location
            date_from: Optional start date range
            date_to: Optional end date range
            
        Returns:
            Dict containing flight options if successful, None otherwise
        """
        # Check cache first
        cache_key = f"{origin},{destination},{date_from},{date_to}"
        if cache_key in self.flights_cache:
            logger.info(f"Using cached flight data for {cache_key}")
            return self.flights_cache[cache_key]
        
        try:
            # If no dates provided, set default search range (next 3-30 days)
            if not date_from:
                date_from = (datetime.now() + timedelta(days=3)).strftime("%d/%m/%Y")
            if not date_to:
                date_to = (datetime.now() + timedelta(days=30)).strftime("%d/%m/%Y")
            
            # Convert date formats if needed
            if "-" in date_from and not "/" in date_from:
                # Convert YYYY-MM-DD to DD/MM/YYYY
                date_parts = date_from.split("-")
                if len(date_parts) == 3:
                    date_from = f"{date_parts[2]}/{date_parts[1]}/{date_parts[0]}"
            
            if "-" in date_to and not "/" in date_to:
                # Convert YYYY-MM-DD to DD/MM/YYYY
                date_parts = date_to.split("-")
                if len(date_parts) == 3:
                    date_to = f"{date_parts[2]}/{date_parts[1]}/{date_parts[0]}"
            
            # Build the request URL
            url = f"{self.kiwi_base_url}/search"
            
            # Prepare headers - for Kiwi API, API key goes in header
            headers = {
                "apikey": "YOUR_API_KEY_HERE",  # Placeholder - should be configured securely
                "Content-Type": "application/json"
            }
            
            # Prepare parameters
            params = {
                "fly_from": origin,
                "fly_to": destination,
                "date_from": date_from,
                "date_to": date_to,
                "nights_in_dst_from": 1,
                "nights_in_dst_to": 5,
                "one_for_city": 1,
                "max_stopovers": 1,  # Prefer direct flights or max 1 stopover
                "curr": "USD",
                "sort": "duration",  # Sort by duration for recruiting travel context
                "limit": 5  # Limit to 5 options
            }
            
            # Make the request
            logger.info(f"Fetching flight data from {origin} to {destination}")
            # For demo purposes, simulate a response
            # In a real implementation, use: response = await self.http_client.get(url, headers=headers, params=params)
            # response.raise_for_status()
            # data = response.json()
            
            # Simulate flight data for demo purposes without requiring an actual API key
            simulated_data = self._simulate_flight_data(origin, destination, date_from, date_to)
            
            # Cache the result
            self.flights_cache[cache_key] = simulated_data
            
            return simulated_data
            
        except Exception as e:
            logger.error(f"Error fetching flight data: {e}")
            return None
    
    def _simulate_flight_data(self, origin: str, destination: str, date_from: str, date_to: str) -> Dict[str, Any]:
        """
        Helper to simulate flight data for demo purposes.
        
        Args:
            origin: Origin location code
            destination: Destination location code
            date_from: Start date range
            date_to: End date range
            
        Returns:
            Simulated flight data
        """
        # Generate random flight times within the date range
        try:
            # Parse dates
            if "/" in date_from:
                day, month, year = map(int, date_from.split("/"))
                start_date = datetime(year, month, day)
            else:
                start_date = datetime.now() + timedelta(days=3)
                
            flight_date = start_date + timedelta(days=1)  # Flight one day after start date
            
            # Generate flight duration based on location pairs (simplified)
            flight_hours = 2  # Default duration
            
            # Simulate different durations based on location pairs
            us_airports = ['JFK', 'LAX', 'ORD', 'SFO', 'ATL', 'DFW', 'MIA', 'BOS', 'SEA', 'DEN']
            if origin.upper() in us_airports and destination.upper() in us_airports:
                # Domestic US flight
                origin_idx = us_airports.index(origin.upper()) if origin.upper() in us_airports else 0
                dest_idx = us_airports.index(destination.upper()) if destination.upper() in us_airports else 0
                flight_hours = abs(origin_idx - dest_idx) / 2 + 1.5  # Rough estimate
            else:
                # International flight
                flight_hours = 8
            
            # Create simulated flight options
            flight_options = []
            
            for i in range(3):  # Generate 3 flight options
                departure_time = flight_date.replace(hour=8+i*4)  # Flights at 8am, 12pm, 4pm
                arrival_time = departure_time + timedelta(hours=flight_hours)
                
                flight = {
                    "id": f"simulated_flight_{i}",
                    "flyFrom": origin.upper(),
                    "flyTo": destination.upper(),
                    "cityFrom": origin.upper(),
                    "cityTo": destination.upper(),
                    "departure": departure_time.isoformat(),
                    "arrival": arrival_time.isoformat(),
                    "flight_duration": self._format_duration(flight_hours * 60),
                    "price": 200 + i * 75,  # Simulate different price points
                    "availability": {"seats": 5 + i * 3},
                    "airlines": ["AA", "UA", "DL"][i % 3],
                    "direct": i < 2,  # First two options are direct flights
                    "bags_price": {"1": 30, "2": 60},
                    "booking_token": f"simulated_token_{i}"
                }
                
                flight_options.append(flight)
            
            # Create the response structure
            result = {
                "search_params": {
                    "fly_from": origin,
                    "fly_to": destination,
                    "date_from": date_from,
                    "date_to": date_to
                },
                "flights": flight_options,
                "recruiting_assessment": {
                    "recommended_option": 0,  # Index of best option for recruiting
                    "convenience_factor": "high" if flight_hours < 3 else "medium" if flight_hours < 6 else "low",
                    "recommended_arrival_buffer": 3 if flight_hours < 3 else 6,  # Hours before interview
                    "suggested_booking_window": "2-3 weeks in advance for best rates"
                }
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error simulating flight data: {e}")
            return {"flights": [], "error": "Failed to generate flight options"}
    
    async def _get_enhanced_weather_conditions(self, lat: float, lon: float, 
                                             date: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get enhanced weather information with detailed forecasts and travel impact assessment.
        
        Args:
            lat: Latitude
            lon: Longitude
            date: Optional date for forecast
            
        Returns:
            Dict containing enhanced weather data if successful, None otherwise
        """
        # Get basic weather data first
        basic_weather = await self._get_weather_conditions(lat, lon, date)
        if not basic_weather:
            return None
        
        # Enhance with additional information
        enhanced_weather = basic_weather.copy()
        
        # Add travel impact assessment
        enhanced_weather["travel_impact"] = self._assess_weather_impact(enhanced_weather)
        
        # Add packing recommendations
        enhanced_weather["packing_recommendations"] = self._generate_packing_recommendations(enhanced_weather)
        
        # Add weather summary for quick reference
        current = enhanced_weather.get("current", {})
        if current:
            temp = current.get('temperature', 'N/A')
            desc = current.get('weather_description', 'Unknown')
            enhanced_weather["summary"] = f"{desc}, {temp}°C"
        
        return enhanced_weather

    async def _generate_cost_analysis(self, travel_data: Dict[str, Any], intent_type: str) -> Dict[str, Any]:
        """
        Generate comprehensive cost analysis for travel.
        
        Args:
            travel_data: Travel data containing routes, schedules, etc.
            intent_type: Type of travel intent (interview, relocation, etc.)
            
        Returns:
            Dict containing detailed cost breakdown
        """
        cost_analysis = {
            "transportation_costs": {},
            "additional_costs": {},
            "total_estimate": None
        }
        
        # Analyze transportation costs
        if travel_data.get("directions"):
            directions = travel_data["directions"]
            distance = directions.get("distance", 0)
            if distance:
                # Estimate gas costs (assuming 25 mpg, $3.50/gallon)
                gas_cost = (distance / 25) * 3.50
                cost_analysis["transportation_costs"]["driving"] = {
                    "cost": f"${gas_cost:.2f}",
                    "notes": "Gas only, excludes tolls and parking"
                }
        
        if travel_data.get("train_schedule"):
            train_info = travel_data["train_schedule"]
            if train_info.get("booking_info", {}).get("pricing"):
                cost_analysis["transportation_costs"]["train"] = train_info["booking_info"]["pricing"]
        
        if travel_data.get("flights"):
            flights = travel_data["flights"]
            if flights.get("best_option"):
                best = flights["best_option"]
                cost_analysis["transportation_costs"]["flight"] = {
                    "cost": best.get("price", "Varies"),
                    "notes": "One-way fare"
                }
        
        # Add additional costs based on intent type
        if intent_type == "interview_travel":
            cost_analysis["additional_costs"] = {
                "parking": "$10-25/day",
                "meals": "$15-40/day",
                "incidentals": "$10-20"
            }
        elif intent_type == "relocation":
            cost_analysis["additional_costs"] = {
                "moving_truck": "$50-150/day",
                "hotel_overnight": "$80-200/night",
                "meals": "$30-60/day"
            }
        else:
            cost_analysis["additional_costs"] = {
                "parking": "$5-20/day",
                "meals": "$10-30/day"
            }
        
        # Calculate total estimate
        total_cost = 0
        for mode, cost_info in cost_analysis["transportation_costs"].items():
            if isinstance(cost_info, dict) and cost_info.get("cost"):
                cost_str = cost_info["cost"]
                if cost_str.startswith("$"):
                    try:
                        total_cost += float(cost_str[1:])
                    except ValueError:
                        pass
        
        if total_cost > 0:
            cost_analysis["total_estimate"] = f"${total_cost:.2f} (transportation only)"
        
        return cost_analysis

    async def _get_local_area_intelligence(self, destination: str, coords: Optional[Tuple[float, float]]) -> Dict[str, Any]:
        """
        Get local area information including restaurants, hotels, and parking.
        
        Args:
            destination: Destination city/area
            coords: Optional coordinates for more precise results
            
        Returns:
            Dict containing local area information
        """
        local_area = {
            "restaurants": [],
            "hotels": [],
            "parking": "Check local parking apps and city websites for rates"
        }
        
        # Generate sample restaurant recommendations based on destination
        if "boston" in destination.lower():
            local_area["restaurants"] = [
                {"name": "Legal Sea Foods", "rating": "4.2", "price_range": "$$$"},
                {"name": "Union Oyster House", "rating": "4.0", "price_range": "$$"},
                {"name": "Mike's Pastry", "rating": "4.1", "price_range": "$"}
            ]
        elif "new york" in destination.lower() or "nyc" in destination.lower():
            local_area["restaurants"] = [
                {"name": "Joe's Pizza", "rating": "4.3", "price_range": "$"},
                {"name": "Katz's Delicatessen", "rating": "4.2", "price_range": "$$"},
                {"name": "Peter Luger Steak House", "rating": "4.4", "price_range": "$$$$"}
            ]
        else:
            # Generic recommendations
            local_area["restaurants"] = [
                {"name": "Local Cafe", "rating": "4.0", "price_range": "$"},
                {"name": "Business District Restaurant", "rating": "4.1", "price_range": "$$"},
                {"name": "Fine Dining", "rating": "4.3", "price_range": "$$$"}
            ]
        
        # Generate hotel recommendations
        if "boston" in destination.lower():
            local_area["hotels"] = [
                {"name": "The Ritz-Carlton Boston", "rating": "4.5", "price_range": "$$$$"},
                {"name": "Boston Marriott Copley Place", "rating": "4.2", "price_range": "$$$"},
                {"name": "Hampton Inn Boston", "rating": "4.0", "price_range": "$$"}
            ]
        elif "new york" in destination.lower() or "nyc" in destination.lower():
            local_area["hotels"] = [
                {"name": "The Plaza", "rating": "4.4", "price_range": "$$$$"},
                {"name": "Marriott Marquis", "rating": "4.1", "price_range": "$$$"},
                {"name": "Holiday Inn Express", "rating": "3.9", "price_range": "$$"}
            ]
        else:
            local_area["hotels"] = [
                {"name": "Business Hotel", "rating": "4.0", "price_range": "$$$"},
                {"name": "Mid-Range Hotel", "rating": "3.8", "price_range": "$$"},
                {"name": "Budget Hotel", "rating": "3.5", "price_range": "$"}
            ]
        
        return local_area

    async def _generate_transportation_comparison(self, travel_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate comprehensive transportation options comparison.
        
        Args:
            travel_data: Travel data containing various transportation options
            
        Returns:
            Dict containing transportation comparison
        """
        comparison = {"options": []}
        
        # Add driving option
        if travel_data.get("directions"):
            directions = travel_data["directions"]
            comparison["options"].append({
                "mode": "Driving",
                "duration": directions.get("formatted_duration", "Unknown"),
                "cost": "Gas + tolls + parking",
                "pros": ["Flexible timing", "Direct route", "Can carry luggage"],
                "cons": ["Traffic delays", "Parking costs", "Weather dependent"]
            })
        
        # Add train option
        if travel_data.get("train_schedule"):
            train_info = travel_data["train_schedule"]
            comparison["options"].append({
                "mode": "Train",
                "duration": "4h 30m average",
                "cost": train_info.get("booking_info", {}).get("pricing", "Varies"),
                "pros": ["Reliable schedule", "WiFi available", "Scenic route"],
                "cons": ["Limited flexibility", "Station locations", "Weather delays possible"]
            })
        
        # Add flight option
        if travel_data.get("flights"):
            flights = travel_data["flights"]
            if flights.get("best_option"):
                best = flights["best_option"]
                comparison["options"].append({
                    "mode": "Flight",
                    "duration": best.get("duration", "1-2 hours"),
                    "cost": best.get("price", "Varies"),
                    "pros": ["Fastest option", "Weather independent", "Comfortable"],
                    "cons": ["Airport security", "Baggage fees", "Flight delays"]
                })
        
        return comparison

    def _generate_packing_recommendations(self, weather_data: Dict[str, Any]) -> List[str]:
        """
        Generate packing recommendations based on weather data.
        
        Args:
            weather_data: Weather information
            
        Returns:
            List of packing recommendations
        """
        recommendations = []
        
        current = weather_data.get("current", {})
        temp = current.get("temperature", 20)  # Default to 20°C if unknown
        
        if temp < 10:
            recommendations.extend([
                "Warm coat and layers",
                "Hat and gloves",
                "Waterproof shoes"
            ])
        elif temp < 20:
            recommendations.extend([
                "Light jacket or sweater",
                "Long pants",
                "Comfortable walking shoes"
            ])
        else:
            recommendations.extend([
                "Light clothing",
                "Sunscreen",
                "Comfortable shoes"
            ])
        
        # Add weather-specific recommendations
        forecast = weather_data.get("forecast", [])
        if forecast:
            for day in forecast[:2]:  # Check next 2 days
                precip_prob = day.get("precipitation_probability", 0)
                if precip_prob > 50:
                    recommendations.append("Umbrella or rain jacket")
                    break
        
        return recommendations

    async def _get_weather_conditions(self, lat: float, lon: float, 
                                     date: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get weather from Open-Meteo (free).
        
        Args:
            lat: Latitude
            lon: Longitude
            date: Optional date for forecast
            
        Returns:
            Dict containing weather data if successful, None otherwise
        """
        # Check cache first
        cache_key = f"{lat},{lon},{date if date else 'current'}"
        if cache_key in self.weather_cache:
            logger.info(f"Using cached weather data for {cache_key}")
            return self.weather_cache[cache_key]
            
        try:
            # Build the request URL
            url = f"{self.openmeteo_base_url}/forecast"
            
            # Prepare parameters
            params = {
                "latitude": lat,
                "longitude": lon,
                "current_weather": "true",
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,weathercode",
                "timezone": "auto"
            }
            
            # If a specific date is requested, add forecast days
            if date:
                # Calculate days from now to the requested date
                date_obj = datetime.fromisoformat(date.replace('Z', '+00:00'))
                days_diff = (date_obj - datetime.now()).days
                if days_diff > 0:
                    params["forecast_days"] = min(days_diff + 1, 7)  # Max 7 days for free API
            
            # Make the request
            logger.info(f"Fetching weather data for coordinates ({lat}, {lon})")
            response = await self.http_client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            # Process the response
            result = {
                "current": {
                    "temperature": data.get("current_weather", {}).get("temperature"),
                    "weather_code": data.get("current_weather", {}).get("weathercode"),
                    "wind_speed": data.get("current_weather", {}).get("windspeed"),
                    "weather_description": self._weather_code_to_text(data.get("current_weather", {}).get("weathercode", 0))
                },
                "forecast": []
            }
            
            # Add daily forecast data if available
            if "daily" in data:
                daily = data["daily"]
                time_values = daily.get("time", [])
                for i, day in enumerate(time_values):
                    forecast_day = {
                        "date": day,
                        "max_temp": daily["temperature_2m_max"][i],
                        "min_temp": daily["temperature_2m_min"][i],
                        "precipitation": daily["precipitation_sum"][i],
                        "precipitation_probability": daily["precipitation_probability_max"][i],
                        "weather_code": daily["weathercode"][i],
                        "weather_description": self._weather_code_to_text(daily["weathercode"][i])
                    }
                    result["forecast"].append(forecast_day)
            
            # Store in cache with 1-hour expiry
            self.weather_cache[cache_key] = result
            
            return result
            
        except Exception as e:
            logger.error(f"Error fetching weather data: {e}")
            return None
    
    async def _get_recruiting_specific_advice(self, origin: str, destination: str, 
                                             intent_type: str, 
                                             travel_data: Dict[str, Any]) -> List[str]:
        """
        Generate recruiting-specific travel advice.
        
        Args:
            origin: Origin location
            destination: Destination location
            intent_type: Type of recruiting intent
            travel_data: Travel data collected
            
        Returns:
            List of recruiting-specific advice items
        """
        try:
            # Get the travel mode from the data
            travel_mode = travel_data.get("travel_mode", "unknown")
            
            # Get weather data if available
            weather_data = travel_data.get("weather", {})
            weather_impact = self._assess_weather_impact(weather_data) if weather_data else "neutral"
            
            # Generate different advice based on intent type
            advice = []
            
            if intent_type == "interview_travel":
                # Interview-specific advice
                advice.append("🔹 For interviews, plan to arrive 15-20 minutes early to account for check-in and to compose yourself.")
                
                # Travel duration based advice
                if "directions" in travel_data:
                    duration_mins = travel_data["directions"].get("duration", 0) / 60  # Convert seconds to minutes
                    if duration_mins > 120:  # More than 2 hours
                        advice.append("🔹 Consider traveling the day before your interview to avoid any last-minute travel stress.")
                    elif duration_mins > 60:  # More than 1 hour
                        advice.append(f"🔹 Your travel time may be significant ({self._format_duration(duration_mins)}). Add at least 30 minutes buffer to account for unexpected delays.")
                    else:
                        advice.append("🔹 Your commute appears reasonable, but still plan for a buffer of 15-30 minutes.")
                
                # Weather advice for interviews
                if weather_impact == "severe":
                    advice.append("🔹 Weather conditions may be challenging. Consider alternative transportation options and bring appropriate clothing.")
                elif weather_impact == "moderate":
                    advice.append("🔹 Weather may cause slight delays. Allow extra travel time.")
                
                # Mode-specific advice
                if travel_mode == "driving":
                    advice.append("🔹 Research parking options in advance. Some companies offer visitor parking—ask your recruiter.")
                    advice.append("🔹 Have the office phone number saved in case you need to alert them about any delays.")
                elif travel_mode == "transit":
                    advice.append("🔹 If using public transit, have a backup route planned in case of service disruptions.")
                    advice.append("🔹 Download the local transit app for real-time updates.")
                elif travel_mode == "flying":
                    advice.append("🔹 For interview travel requiring flights, arrive at least 4-5 hours before your interview time to allow for any flight delays.")
                    advice.append("🔹 Consider carrying your interview outfit as a carry-on to prevent issues with lost luggage.")
                
                # General interview travel tips
                advice.append("🔹 Double-check the exact interview location including building, floor, and suite number.")
                advice.append("🔹 Save your recruiter's contact information in case you need to communicate any travel issues.")
                
            elif intent_type == "relocation":
                # Relocation-specific advice
                advice.append("🔹 When considering relocation for a role, research typical commute times during rush hours.")
                advice.append("🔹 Explore multiple neighborhoods based on your preferred commute length.")
                
                # Weather considerations for relocation
                if "weather" in travel_data and "forecast" in travel_data["weather"]:
                    advice.append("🔹 Consider the typical weather patterns in this area when making a relocation decision.")
                
                # Cost of living considerations
                advice.append("🔹 Research housing costs in neighborhoods with good commute options to the office.")
                advice.append("🔹 Factor commuting costs into your salary negotiations when relocating for a job.")
                
                # Family considerations
                advice.append("🔹 If relocating with family, research schools, amenities, and family-friendly activities in areas with reasonable commutes.")
                
            elif intent_type == "office_visit":
                # Office visit specific advice
                advice.append("🔹 When visiting a company office, follow the dress code guidelines even for non-interview visits.")
                
                # Security and check-in process
                advice.append("🔹 Bring a government ID for building security check-in processes.")
                advice.append("🔹 Ask for detailed instructions about the visitor check-in process before your visit.")
                
                # Find your contacts
                advice.append("🔹 Save the contact information of the person you're meeting to notify them of your arrival.")
                
            elif intent_type == "candidate_travel":
                # Candidate travel coordination advice
                advice.append("🔹 When coordinating candidate travel, provide clear expense reimbursement policies upfront.")
                advice.append("🔹 Send candidates detailed directions from major transit hubs to your office.")
                
                # Logistics for recruiters
                advice.append("🔹 Consider scheduling interviews mid-day to accommodate travel time for out-of-town candidates.")
                advice.append("🔹 Provide a contact person who can assist with travel emergencies or questions.")
                
                # Accommodation advice
                advice.append("🔹 Recommend hotels within easy commuting distance to your office for overnight stays.")
            
            # General advice for all recruiting-related travel
            advice.append("🔹 Research the company's neighborhood for options to spend additional time if you arrive early.")
            
            return advice
            
        except Exception as e:
            logger.error(f"Error generating recruiting travel advice: {e}")
            return ["Unable to generate recruiting-specific travel advice at this time."]
    
    # Response Generation Methods
    
    def generate_recruiting_response(self, query: str, travel_data: Dict[str, Any], 
                                     intent_data: Dict[str, Any]) -> str:
        """
        Generate a comprehensive, recruiting-focused response.
        
        Args:
            query: Original user query
            travel_data: Travel data collected
            intent_data: Intent classification data
            
        Returns:
            Formatted response string
        """
        logger.info(f"Generating recruiting response for query: {query}")
        
        try:
            # Extract key information from intent data
            intent_type = intent_data.get("intent_type", "general_travel")
            confidence = intent_data.get("confidence", 0.0)
            is_recruiting_related = intent_data.get("is_recruiting_related", False)
            
            # Add metadata to the response for analytics
            metadata = {
                "query_timestamp": datetime.now().isoformat(),
                "intent_type": intent_type,
                "confidence": confidence,
                "destinations": [travel_data.get("destination", "")],
                "travel_mode": travel_data.get("travel_mode", "unknown")
            }
            
            # Different response strategy based on intent confidence
            if confidence >= 0.7:
                # High confidence - use specific pattern-based templates
                response = self._generate_pattern_based_response(intent_type, travel_data)
            elif confidence >= 0.4:
                # Medium confidence - use general template but with intent-specific elements
                response = self._generate_pattern_based_response("general_travel", travel_data)
                
                # Add intent-specific disclaimer
                if is_recruiting_related and intent_type != "general_travel":
                    response += f"\n\n*Note: I've provided general travel information that may be relevant for {intent_type.replace('_', ' ')}, but feel free to ask more specific questions about your recruiting travel needs.*"
            else:
                # Low confidence - use very general response
                response = self._generate_pattern_based_response("general_travel", travel_data)
                response += "\n\n*Note: For more specific recruiting travel advice, please provide more details about your travel purpose (interview, relocation, etc.).*"
            
            # Add contextual follow-up suggestions based on intent
            response += self._add_follow_up_suggestions(intent_type, travel_data)
            
            # Add metadata as a hidden JSON string for tracking (in real system would be handled differently)
            # response += f"\n\n<!-- {json.dumps(metadata)} -->"
            
            return response
            
        except Exception as e:
            logger.error(f"Error generating recruiting response: {e}")
            # Fallback response
            return f"I found travel information for your journey from {travel_data.get('origin', 'origin')} to {travel_data.get('destination', 'destination')}. " + \
                   f"The journey would take approximately {travel_data.get('directions', {}).get('formatted_duration', 'an unknown amount of time')}."
    
    def _add_follow_up_suggestions(self, intent_type: str, travel_data: Dict[str, Any]) -> str:
        """
        Add contextual follow-up suggestions based on intent type.
        
        Args:
            intent_type: Type of recruiting intent
            travel_data: Travel data collected
            
        Returns:
            String with follow-up suggestions
        """
        suggestions = "\n\n## Related Questions You Might Have\n"
        
        if intent_type == "interview_travel":
            suggestions += "- What should I bring to my interview?\n"
            suggestions += "- How early should I arrive for my interview?\n"
            suggestions += "- What's the dress code for this company?\n"
            suggestions += "- Is there parking available at the office?\n"
        elif intent_type == "relocation":
            suggestions += "- What neighborhoods have good commute times to this office?\n"
            suggestions += "- What's the cost of living near this location?\n"
            suggestions += "- What relocation assistance does the company provide?\n"
            suggestions += "- Are there good schools in the area for families?\n"
        elif intent_type == "office_visit":
            suggestions += "- What should I expect during an office visit?\n"
            suggestions += "- Is there a security check-in process?\n"
            suggestions += "- What amenities are available near the office?\n"
            suggestions += "- Should I prepare anything for my office visit?\n"
        elif intent_type == "candidate_travel":
            suggestions += "- What's your travel reimbursement policy?\n"
            suggestions += "- Do you arrange travel for candidates or reimburse expenses?\n"
            suggestions += "- Are there preferred hotels near your office?\n"
            suggestions += "- How long should candidates plan to stay for interviews?\n"
        else:
            suggestions += "- Can you tell me about travel options for an upcoming interview?\n"
            suggestions += "- I'm relocating for a job, what should I consider?\n"
            suggestions += "- How do I plan a visit to your office?\n"
            suggestions += "- What should I know about travel arrangements for candidates?\n"
        
        return suggestions
    
    def _generate_pattern_based_response(self, intent_type: str, travel_data: Dict[str, Any]) -> str:
        """
        Generate response using patterns for specific intent types.
        
        Args:
            intent_type: Type of recruiting intent
            travel_data: Travel data collected
            
        Returns:
            Formatted response string
        """
        # Get origin and destination
        origin = travel_data.get("origin", "your location")
        destination = travel_data.get("destination", "the destination")
        travel_mode = travel_data.get("travel_mode", "unknown")
        
        # Format the travel data into a structured representation
        travel_options = self._format_travel_options_for_prompt(travel_data)
        
        # Get specialized recruiting advice if available
        recruiting_advice = travel_data.get("recruiting_advice", "")
        
        # Generate intent-specific responses
        response_parts = []
        
        if intent_type == "interview_travel":
            # Introduction
            response_parts.append(f"# Interview Travel: {origin} to {destination}\n")
            response_parts.append("Here's what you need to know for your interview travel:")
            
            # Main content
            response_parts.append("\n## Travel Details")
            response_parts.append(travel_options)
            
            # Recruiting-specific advice
            if recruiting_advice:
                response_parts.append("\n## Interview Travel Tips")
                response_parts.append(recruiting_advice)
                
            # Closing
            response_parts.append("\n## Final Notes")
            response_parts.append("Remember that punctuality is critical for interviews. Recruiters recommend arriving at least 15 minutes early, so plan your journey accordingly.")
            
        elif intent_type == "relocation":
            # Introduction
            response_parts.append(f"# Relocation Assessment: {origin} to {destination}\n")
            response_parts.append("Here's what you should consider for your potential relocation:")
            
            # Main content
            response_parts.append("\n## Commute Analysis")
            response_parts.append(travel_options)
            
            # Add quality of life considerations
            response_parts.append("\n## Quality of Life Considerations")
            response_parts.append("When relocating for a job, consider these factors:\n")
            response_parts.append("* Typical commute patterns during your working hours")
            response_parts.append("* Housing costs in neighborhoods with reasonable commute times")
            response_parts.append("* Weather patterns throughout the year")
            response_parts.append("* Public transportation options")
            
            # Recruiting-specific advice
            if recruiting_advice:
                response_parts.append("\n## Relocation Advice")
                response_parts.append(recruiting_advice)
                
            # Closing
            response_parts.append("\n## Final Notes")
            response_parts.append("Many companies offer relocation assistance packages. If you're considering accepting an offer that requires relocation, be sure to discuss support options with your recruiter.")
            
        elif intent_type == "office_visit":
            # Introduction
            response_parts.append(f"# Office Visit Guide: {origin} to {destination}\n")
            response_parts.append("Here's your guide for visiting the office:")
            
            # Main content
            response_parts.append("\n## Travel Information")
            response_parts.append(travel_options)
            
            # Recruiting-specific advice
            if recruiting_advice:
                response_parts.append("\n## Office Visit Tips")
                response_parts.append(recruiting_advice)
                
            # Closing
            response_parts.append("\n## Final Notes")
            response_parts.append("Office visits are a great opportunity to get a feel for the company culture. Take note of the work environment and how people interact while you're there.")
            
        elif intent_type == "candidate_travel":
            # Introduction - this is for recruiters arranging candidate travel
            response_parts.append(f"# Candidate Travel Coordination: {origin} to {destination}\n")
            response_parts.append("Here's information to help coordinate candidate travel:")
            
            # Main content
            response_parts.append("\n## Travel Options to Present")
            response_parts.append(travel_options)
            
            # Recruiting-specific advice
            if recruiting_advice:
                response_parts.append("\n## Best Practices for Candidate Travel")
                response_parts.append(recruiting_advice)
                
            # Closing
            response_parts.append("\n## Final Notes")
            response_parts.append("Providing a positive candidate travel experience reflects well on your company culture. Consider sending a digital information packet with clear instructions, contact information, and expense reimbursement details.")
            
        else:  # general travel
            # Introduction
            response_parts.append(f"# Travel Information: {origin} to {destination}\n")
            response_parts.append("Here's the travel information you requested:")
            
            # Main content
            response_parts.append(travel_options)
                
        # Combine all parts
        return "\n".join(response_parts)
    
    def _format_travel_options_for_prompt(self, travel_data: Dict[str, Any]) -> str:
        """
        Helper to format travel data for prompt.
        
        Args:
            travel_data: Travel data to format
            
        Returns:
            Formatted string for inclusion in prompts
        """
        if not travel_data:
            return "No travel data available."
        
        sections = []
        
        # Add basic travel information
        travel_info = [
            f"Journey: {travel_data.get('origin', 'Unknown')} to {travel_data.get('destination', 'Unknown')}",
            f"Travel mode: {travel_data.get('travel_mode', 'Unknown')}"
        ]
        
        if travel_data.get('travel_date'):
            travel_info.append(f"Travel date: {travel_data.get('travel_date')}")
            
        sections.append("\n".join(travel_info))
        
        # Add directions information if available
        if "directions" in travel_data:
            directions = travel_data["directions"]
            directions_info = [
                "### Route Information",
                f"Distance: {directions.get('distance', 0):.1f} miles",
                f"Duration: {directions.get('formatted_duration', 'Unknown')}"
            ]
            
            # Add key steps if available
            if directions.get("steps") and len(directions["steps"]) > 0:
                directions_info.append("\nKey directions:")
                # Only include first and last few steps to keep it concise
                steps_to_show = min(5, len(directions["steps"]))
                for i, step in enumerate(directions["steps"][:steps_to_show]):
                    if i < 3 or i >= len(directions["steps"]) - 2:
                        directions_info.append(f"- {step.get('instruction', '')}")
                        
                # Add ellipsis if we're not showing all steps
                if steps_to_show < len(directions["steps"]):
                    directions_info.append("- ...")
                    
            sections.append("\n".join(directions_info))
        
        # Add flight information if available
        if "flights" in travel_data:
            flight_data = travel_data["flights"]
            flights = flight_data.get("flights", [])
            
            if flights:
                flight_info = ["### Flight Options"]
                
                # Show up to 3 flight options
                for i, flight in enumerate(flights[:3]):
                    option_details = [
                        f"Option {i+1}: {flight.get('airlines', '')} - ${flight.get('price', 0)}",
                        f"Departure: {flight.get('departure', '').replace('T', ' ').split('.')[0]}",
                        f"Arrival: {flight.get('arrival', '').replace('T', ' ').split('.')[0]}",
                        f"Duration: {flight.get('flight_duration', 'Unknown')}",
                        f"Direct flight: {'Yes' if flight.get('direct', False) else 'No'}"
                    ]
                    flight_info.append("\n".join(option_details) + "\n")
                    
                sections.append("\n".join(flight_info))
                
                # Add airport to destination info if available
                if "airport_to_destination" in travel_data:
                    airport_transfer = travel_data["airport_to_destination"]
                    sections.append(
                        f"\nFrom airport to final destination:\n" +
                        f"Distance: {airport_transfer.get('distance', 0):.1f} miles\n" +
                        f"Duration: {airport_transfer.get('formatted_duration', 'Unknown')}"
                    )
        
        # Add weather information if available
        if "weather" in travel_data:
            weather = travel_data["weather"]
            current = weather.get("current", {})
            
            if current:
                weather_info = [
                    "### Weather Conditions",
                    f"Current: {current.get('weather_description', 'Unknown')}, {current.get('temperature', 'Unknown')}°C"
                ]
                
                # Add forecast if available
                forecast = weather.get("forecast", [])
                if forecast and len(forecast) > 0:
                    weather_info.append("\nForecast:")
                    # Only show up to 3 days forecast
                    for i, day in enumerate(forecast[:3]):
                        weather_info.append(
                            f"- {day.get('date', '')}: {day.get('weather_description', '')}, " +
                            f"{day.get('min_temp', '')}°C to {day.get('max_temp', '')}°C, " +
                            f"Precipitation: {day.get('precipitation_probability', '')}%"
                        )
                        
                sections.append("\n".join(weather_info))
        
        # Add recruiting assessment if available
        if "assessment" in travel_data:
            assessment = travel_data["assessment"]
            assessment_info = [
                "### Travel Assessment",
                f"Convenience: {assessment.get('overall_convenience', 'Unknown')}",
                f"Recommended buffer time: {assessment.get('recommended_buffer_time', 0)} minutes",
                f"Stress level: {assessment.get('stress_level', 'Unknown')}"
            ]
            
            if assessment.get("special_considerations"):
                assessment_info.append("\nSpecial considerations:")
                for consideration in assessment["special_considerations"]:
                    assessment_info.append(f"- {consideration}")
                    
            sections.append("\n".join(assessment_info))
        
        # Combine all sections with double line breaks
        return "\n\n".join(sections)
    
    def _format_duration(self, minutes: float) -> str:
        """
        Helper to format duration for display.
        
        Args:
            minutes: Duration in minutes
            
        Returns:
            Formatted duration string
        """
        if minutes < 1:
            return "less than a minute"
            
        hours = int(minutes // 60)
        remaining_minutes = int(minutes % 60)
        
        # Format based on duration
        if hours == 0:
            if remaining_minutes == 1:
                return "1 minute"
            else:
                return f"{remaining_minutes} minutes"
        elif hours == 1:
            if remaining_minutes == 0:
                return "1 hour"
            elif remaining_minutes == 1:
                return "1 hour and 1 minute"
            else:
                return f"1 hour and {remaining_minutes} minutes"
        else:
            if remaining_minutes == 0:
                return f"{hours} hours"
            elif remaining_minutes == 1:
                return f"{hours} hours and 1 minute"
            else:
                return f"{hours} hours and {remaining_minutes} minutes"
    
    def _weather_code_to_text(self, wmo_code: int) -> str:
        """
        Convert weather code to text.
        
        Args:
            wmo_code: WMO weather code
            
        Returns:
            Human-readable weather description
        """
        # WMO Weather interpretation codes (https://open-meteo.com/en/docs)
        weather_codes = {
            0: "Clear sky",
            1: "Mainly clear",
            2: "Partly cloudy",
            3: "Overcast",
            45: "Fog",
            48: "Depositing rime fog",
            51: "Light drizzle",
            53: "Moderate drizzle",
            55: "Dense drizzle",
            56: "Light freezing drizzle",
            57: "Dense freezing drizzle",
            61: "Slight rain",
            63: "Moderate rain",
            65: "Heavy rain",
            66: "Light freezing rain",
            67: "Heavy freezing rain",
            71: "Slight snow fall",
            73: "Moderate snow fall",
            75: "Heavy snow fall",
            77: "Snow grains",
            80: "Slight rain showers",
            81: "Moderate rain showers",
            82: "Violent rain showers",
            85: "Slight snow showers",
            86: "Heavy snow showers",
            95: "Thunderstorm",
            96: "Thunderstorm with slight hail",
            99: "Thunderstorm with heavy hail"
        }
        
        return weather_codes.get(wmo_code, "Unknown weather condition")
    
    def _assess_weather_impact(self, weather_data: Dict[str, Any]) -> str:
        """
        Assess weather impact on travel.
        
        Args:
            weather_data: Weather data
            
        Returns:
            Weather impact assessment as string: 'severe', 'moderate', 'slight', or 'neutral'
        """
        if not weather_data or not isinstance(weather_data, dict):
            return "neutral"
            
        # Check if we have current weather data
        current = weather_data.get("current", {})
        if not current:
            return "neutral"
            
        # Get the weather code
        weather_code = current.get("weather_code", 0)
        temperature = current.get("temperature", 20)  # Default to 20°C if missing
        wind_speed = current.get("wind_speed", 0)    # Default to 0 km/h if missing
        
        # Define impact levels for different weather conditions
        severe_weather_codes = [48, 55, 57, 65, 67, 75, 77, 82, 86, 95, 96, 99]
        moderate_weather_codes = [45, 53, 56, 63, 66, 73, 81, 85]
        slight_weather_codes = [3, 51, 61, 71, 80]
        
        # Assess based on weather code
        if weather_code in severe_weather_codes:
            return "severe"
        elif weather_code in moderate_weather_codes:
            return "moderate"
        elif weather_code in slight_weather_codes:
            return "slight"
            
        # Check for extreme temperatures
        if temperature > 35 or temperature < -5:
            return "severe"
        elif temperature > 32 or temperature < 0:
            return "moderate"
        elif temperature > 30 or temperature < 5:
            return "slight"
            
        # Check for high winds
        if wind_speed > 50:
            return "severe"
        elif wind_speed > 30:
            return "moderate"
        elif wind_speed > 20:
            return "slight"
            
        # Default to neutral impact
        return "neutral"

    def _run_startup_check(self):
        """
        Run a small asynchronous startup check in a background thread to validate
        routing API access and log actionable messages if authentication fails.
        """
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._startup_check_async())
            loop.close()
        except Exception as e:
            logger.debug(f"Routing startup check failed to run: {e}")

    async def _startup_check_async(self):
        """
        Async helper that performs a minimal directions request between two nearby
        points to check authentication/permission for the routing API.
        """
        # Skip check if no routing key configured at all
        if not getattr(self, 'openrouteservice_api_key', ''):
            logger.info("Routing startup check skipped: OPENROUTESERVICE_API_KEY not configured.")
            return

        # Use two close coordinates (small request) to minimize usage and latency
        origin = (40.7128, -74.0060)  # NYC
        dest = (40.7138, -74.0060)    # very close in NYC
        try:
            # Use internal request path but avoid caching and heavy processing
            url = f"{self.openroute_base_url}/v2/directions/driving-car/json"
            data = {"coordinates": [[origin[1], origin[0]], [dest[1], dest[0]]], "instructions": False}

            headers = {"Authorization": self.openrouteservice_api_key}
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=data, headers=headers)

            if resp.status_code == 200:
                logger.info("Routing API startup check passed: OpenRouteService directions are reachable.")
                return
            elif resp.status_code in (401, 403):
                logger.error("Routing API authentication failed (401/403). Please verify OPENROUTESERVICE_API_KEY in your environment or .env. "
                             "Ensure the key is active and has permissions for the directions endpoint.")
                # Log additional debugging info
                logger.error(f"API key length: {len(self.openrouteservice_api_key)}, starts with: {self.openrouteservice_api_key[:10]}...")
                try:
                    error_response = resp.json()
                    logger.error(f"API error response: {error_response}")
                    
                    # Check if this looks like an OpenRouter key being used for OpenRouteService
                    if self.openrouteservice_api_key.startswith("sk-or-v1-"):
                        logger.error("WARNING: The API key appears to be an OpenRouter key (starts with 'sk-or-v1-'). "
                                   "OpenRouteService requires a different API key. Please get a proper OpenRouteService API key from https://openrouteservice.org/")
                    
                except:
                    logger.error(f"API error response (text): {resp.text}")
            else:
                logger.warning(f"Routing API returned status {resp.status_code} during startup check. Response may indicate permissions or quota issues.")
                try:
                    error_response = resp.json()
                    logger.warning(f"API response: {error_response}")
                except:
                    logger.warning(f"API response (text): {resp.text}")

        except Exception as e:
            logger.warning(f"Routing API startup check could not be completed: {e}")

    def _estimate_driving_option(self, origin_coords: Tuple[float, float], dest_coords: Tuple[float, float]) -> Dict[str, Any]:
        """
        Estimate driving distance and duration between two coordinate pairs using the Haversine formula.
        This is a lightweight fallback when routing APIs are unavailable.
        Returns a dict matching the option schema used by get_transportation_options.
        """
        try:
            lat1, lon1 = origin_coords
            lat2, lon2 = dest_coords

            # Haversine formula
            R = 3958.8  # Earth radius in miles
            phi1 = math.radians(lat1)
            phi2 = math.radians(lat2)
            dphi = math.radians(lat2 - lat1)
            dlambda = math.radians(lon2 - lon1)

            a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2)**2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
            distance_miles = R * c

            # Assume average driving speed of 50 mph for estimation
            avg_speed_mph = 50.0
            duration_hours = distance_miles / avg_speed_mph if avg_speed_mph > 0 else 0
            duration_minutes = duration_hours * 60
            duration_seconds = int(duration_hours * 3600)

            return {
                "mode": "Driving (estimated)",
                "duration": self._format_duration(duration_minutes),
                "duration_seconds": duration_seconds,
                "distance_miles": round(distance_miles, 1),
                "cost": None,
                "note": "Estimated using great-circle distance as routing API was unavailable"
            }
        except Exception as e:
            logger.error(f"Error estimating driving option: {e}")
            return {
                "mode": "Driving (estimated)",
                "duration": "Unknown",
                "duration_seconds": None,
                "distance_miles": None,
                "cost": None
            }

    async def _get_train_schedule_info(self, origin: str, destination: str) -> Dict[str, Any]:
        """
        Get train schedule information for the given route.
        
        Args:
            origin: Origin location
            destination: Destination location
            
        Returns:
            Dict containing train schedule information
        """
        logger.info(f"Getting train schedule info from {origin} to {destination}")
        
        # For now, provide comprehensive train schedule information based on common routes
        # In a production system, this would integrate with Amtrak API or other train APIs
        
        train_info = {
            "route": f"{origin} → {destination}",
            "service_type": "Amtrak",
            "schedule": [],
            "general_info": {},
            "booking_info": {}
        }
        
        # Boston to NYC route information
        if "boston" in origin.lower() and "new york" in destination.lower():
            train_info.update({
                "route_name": "Northeast Regional",
                "service_type": "Amtrak",
                "schedule": [
                    {
                        "departure": "06:00 AM",
                        "arrival": "10:30 AM",
                        "duration": "4h 30m",
                        "train_number": "94",
                        "service": "Northeast Regional"
                    },
                    {
                        "departure": "08:00 AM", 
                        "arrival": "12:30 PM",
                        "duration": "4h 30m",
                        "train_number": "96",
                        "service": "Northeast Regional"
                    },
                    {
                        "departure": "10:00 AM",
                        "arrival": "2:30 PM", 
                        "duration": "4h 30m",
                        "train_number": "98",
                        "service": "Northeast Regional"
                    },
                    {
                        "departure": "12:00 PM",
                        "arrival": "4:30 PM",
                        "duration": "4h 30m", 
                        "train_number": "100",
                        "service": "Northeast Regional"
                    },
                    {
                        "departure": "2:00 PM",
                        "arrival": "6:30 PM",
                        "duration": "4h 30m",
                        "train_number": "102", 
                        "service": "Northeast Regional"
                    },
                    {
                        "departure": "4:00 PM",
                        "arrival": "8:30 PM",
                        "duration": "4h 30m",
                        "train_number": "104",
                        "service": "Northeast Regional"
                    }
                ],
                "general_info": {
                    "frequency": "Multiple daily departures",
                    "stations": {
                        "origin": "South Station, Boston",
                        "destination": "Penn Station, New York"
                    },
                    "amenities": ["WiFi", "Power outlets", "Café car", "Quiet car"],
                    "baggage": "2 carry-on bags, 2 checked bags (fees may apply)"
                },
                "booking_info": {
                    "website": "amtrak.com",
                    "phone": "1-800-USA-RAIL",
                    "advance_booking": "Recommended, especially for peak times",
                    "pricing": "Varies by date and time, typically $25-150"
                }
            })
        
        # NYC to Boston route information  
        elif "new york" in origin.lower() and "boston" in destination.lower():
            train_info.update({
                "route_name": "Northeast Regional",
                "service_type": "Amtrak", 
                "schedule": [
                    {
                        "departure": "7:00 AM",
                        "arrival": "11:30 AM",
                        "duration": "4h 30m",
                        "train_number": "93",
                        "service": "Northeast Regional"
                    },
                    {
                        "departure": "9:00 AM",
                        "arrival": "1:30 PM", 
                        "duration": "4h 30m",
                        "train_number": "95",
                        "service": "Northeast Regional"
                    },
                    {
                        "departure": "11:00 AM",
                        "arrival": "3:30 PM",
                        "duration": "4h 30m",
                        "train_number": "97", 
                        "service": "Northeast Regional"
                    },
                    {
                        "departure": "1:00 PM",
                        "arrival": "5:30 PM",
                        "duration": "4h 30m",
                        "train_number": "99",
                        "service": "Northeast Regional"
                    },
                    {
                        "departure": "3:00 PM",
                        "arrival": "7:30 PM",
                        "duration": "4h 30m",
                        "train_number": "101",
                        "service": "Northeast Regional"
                    },
                    {
                        "departure": "5:00 PM", 
                        "arrival": "9:30 PM",
                        "duration": "4h 30m",
                        "train_number": "103",
                        "service": "Northeast Regional"
                    }
                ],
                "general_info": {
                    "frequency": "Multiple daily departures",
                    "stations": {
                        "origin": "Penn Station, New York",
                        "destination": "South Station, Boston"
                    },
                    "amenities": ["WiFi", "Power outlets", "Café car", "Quiet car"],
                    "baggage": "2 carry-on bags, 2 checked bags (fees may apply)"
                },
                "booking_info": {
                    "website": "amtrak.com",
                    "phone": "1-800-USA-RAIL", 
                    "advance_booking": "Recommended, especially for peak times",
                    "pricing": "Varies by date and time, typically $25-150"
                }
            })
        
        # Generic train information for other routes
        else:
            train_info.update({
                "route_name": "Regional Service",
                "service_type": "Amtrak",
                "schedule": [
                    {
                        "departure": "Multiple daily departures",
                        "arrival": "Check schedule",
                        "duration": "Varies by route",
                        "train_number": "Various",
                        "service": "Regional"
                    }
                ],
                "general_info": {
                    "frequency": "Check Amtrak schedule",
                    "stations": {
                        "origin": f"Check Amtrak station in {origin}",
                        "destination": f"Check Amtrak station in {destination}"
                    },
                    "amenities": ["WiFi", "Power outlets", "Café car"],
                    "baggage": "2 carry-on bags, checked bags available"
                },
                "booking_info": {
                    "website": "amtrak.com",
                    "phone": "1-800-USA-RAIL",
                    "advance_booking": "Recommended",
                    "pricing": "Varies by route and date"
                }
            })
        
        return train_info

    async def get_travel_info(self, origin: str, destination: str, mode: str = None, query: str = "") -> Dict[str, Any]:
        """
        Get comprehensive travel information for recruiting scenarios.
        
        Args:
            origin: Starting location
            destination: Destination location  
            mode: Transportation mode (optional)
            query: Original query for context
            
        Returns:
            Dict containing travel information and recruiting-specific advice
        """
        logger.info(f"Getting recruiting travel info: {origin} -> {destination}")
        
        try:
            # Use the existing comprehensive data gathering method
            # Determine intent type from the query or use a default
            intent_type = "general_travel"
            if query:
                query_lower = query.lower()
                if any(word in query_lower for word in ["interview", "interviews", "interviewing"]):
                    intent_type = "interview_travel"
                elif any(word in query_lower for word in ["relocation", "relocate", "moving"]):
                    intent_type = "relocation"
                elif any(word in query_lower for word in ["visit", "visiting", "office"]):
                    intent_type = "office_visit"
                elif any(word in query_lower for word in ["candidate", "applicant"]):
                    intent_type = "candidate_travel"
            
            travel_data = await self.gather_recruiting_travel_data(origin, destination, intent_type, query=query)
            
            # Add standard interface fields for compatibility
            travel_data.update({
                "origin": origin,
                "destination": destination,
                "mode": mode or "mixed",
                "query": query,
                "has_results": bool(travel_data.get("directions") or travel_data.get("flights") or travel_data.get("transportation_options") or travel_data.get("train_schedule"))
            })
            
            return travel_data
            
        except Exception as e:
            logger.error(f"Error getting travel info: {e}")
            return {
                "origin": origin,
                "destination": destination,
                "mode": mode or "mixed",
                "query": query,
                "has_results": False,
                "error": str(e)
            }

    def format_travel_response(self, travel_data: Dict[str, Any], query: str) -> str:
        """
        Format travel information into a comprehensive, detailed response with recruiting focus.
        
        Args:
            travel_data: Travel data from get_travel_info
            query: Original user query
            
        Returns:
            Formatted response string with enhanced details
        """
        if not travel_data.get("has_results"):
            return f"I couldn't find travel information between {travel_data.get('origin', 'the origin')} and {travel_data.get('destination', 'the destination')}. Please check the location names and try again."
        
        origin = travel_data.get("origin", "")
        destination = travel_data.get("destination", "")
        
        response = f"**Travel Information:**\n"
        response += f"**Route:** {origin} → {destination}\n\n"
        
        # Enhanced driving route information
        if travel_data.get("directions"):
            directions = travel_data["directions"]
            response += f"🚗 **Driving Route:** {directions.get('duration', 'Unknown time')}"
            if directions.get('distance'):
                response += f" ({directions['distance']})"
            if directions.get('traffic_conditions'):
                response += f"\n   • Traffic: {directions['traffic_conditions']}"
            if directions.get('toll_costs'):
                response += f"\n   • Estimated tolls: {directions['toll_costs']}"
            response += "\n\n"
        
        # Enhanced train schedule with detailed information
        if travel_data.get("train_schedule"):
            train_info = travel_data["train_schedule"]
            response += f"🚂 **Train Schedule:** {train_info.get('route_name', 'Northeast Regional')}\n"
            
            # Add detailed schedule
            if train_info.get("schedule"):
                response += "\n**Departure Times:**\n"
                for i, train in enumerate(train_info["schedule"][:5]):  # Show first 5 trains
                    departure = train.get('departure', 'N/A')
                    arrival = train.get('arrival', 'N/A')
                    duration = train.get('duration', 'N/A')
                    train_num = train.get('train_number', 'N/A')
                    response += f"• {departure} - {arrival} ({duration}) - Train #{train_num}\n"
                
                if len(train_info["schedule"]) > 5:
                    response += f"• ... and {len(train_info['schedule']) - 5} more departures\n"
            
            # Enhanced station and amenity information
            if train_info.get("general_info"):
                general = train_info["general_info"]
                if general.get("stations"):
                    response += f"\n**Stations:** {general['stations'].get('origin', 'N/A')} → {general['stations'].get('destination', 'N/A')}\n"
                if general.get("amenities"):
                    amenities = general['amenities']
                    response += f"**Amenities:** {', '.join(amenities)}\n"
            
            # Enhanced booking and pricing information
            if train_info.get("booking_info"):
                booking = train_info["booking_info"]
                response += f"**Booking:** {booking.get('website', 'amtrak.com')} | {booking.get('phone', '1-800-USA-RAIL')}\n"
                if booking.get("pricing"):
                    response += f"**Pricing:** {booking['pricing']}\n"
            
            response += "\n"
        
        # Enhanced flight information
        if travel_data.get("flights"):
            flights = travel_data["flights"]
            if flights.get("options"):
                response += f"✈️ **Flight Options:** {flights.get('summary', 'Available')}\n"
                if flights.get("best_option"):
                    best = flights["best_option"]
                    response += f"   • Best option: {best.get('airline', 'N/A')} - {best.get('price', 'N/A')} ({best.get('duration', 'N/A')})\n"
                response += "\n"
        
        # Enhanced cost analysis
        if travel_data.get("cost_analysis"):
            cost_data = travel_data["cost_analysis"]
            response += f"💰 **Cost Analysis:**\n"
            
            if cost_data.get("transportation_costs"):
                trans_costs = cost_data["transportation_costs"]
                response += f"**Transportation:**\n"
                for mode, cost_info in trans_costs.items():
                    if isinstance(cost_info, dict):
                        response += f"   • {mode.title()}: {cost_info.get('cost', 'N/A')} ({cost_info.get('notes', '')})\n"
                    else:
                        response += f"   • {mode.title()}: {cost_info}\n"
            
            if cost_data.get("additional_costs"):
                add_costs = cost_data["additional_costs"]
                response += f"**Additional Costs:**\n"
                for item, cost in add_costs.items():
                    response += f"   • {item.title()}: {cost}\n"
            
            if cost_data.get("total_estimate"):
                response += f"**Total Estimated Cost:** {cost_data['total_estimate']}\n"
            
            response += "\n"
        
        # Enhanced weather information
        if travel_data.get("weather"):
            weather = travel_data["weather"]
            response += f"🌤️ **Weather:**\n"
            
            current = weather.get("current", {})
            if current:
                temp = current.get('temperature', 'N/A')
                desc = current.get('weather_description', 'Unknown conditions')
                response += f"**Current:** {desc}, {temp}°C\n"
                
                if current.get('wind_speed'):
                    response += f"   • Wind: {current['wind_speed']} km/h\n"
            
            # Enhanced forecast information
            forecast = weather.get("forecast", [])
            if forecast:
                response += f"**3-Day Forecast:**\n"
                for i, day in enumerate(forecast[:3]):
                    date = day.get('date', f'Day {i+1}')
                    high = day.get('max_temperature', 'N/A')
                    low = day.get('min_temperature', 'N/A')
                    desc = day.get('weather_description', 'Unknown')
                    precip = day.get('precipitation_probability', 0)
                    response += f"   • {date}: {desc}, {high}°C/{low}°C (Rain: {precip}%)\n"
            
            # Weather impact assessment
            if weather.get("travel_impact"):
                impact = weather["travel_impact"]
                response += f"**Travel Impact:** {impact}\n"
            
            response += "\n"
        
        # Enhanced recruiting-specific advice
        if travel_data.get("recruiting_advice"):
            advice = travel_data["recruiting_advice"]
            response += f"💼 **Recruiting Tips:**\n"
            
            if isinstance(advice, list):
                for tip in advice:
                    response += f"• {tip}\n"
            else:
                response += f"• {advice}\n"
            
            response += "\n"
        
        # Local area intelligence
        if travel_data.get("local_area"):
            local = travel_data["local_area"]
            response += f"🏢 **Local Area Information:**\n"
            
            if local.get("restaurants"):
                restaurants = local["restaurants"]
                response += f"**Nearby Restaurants:**\n"
                for restaurant in restaurants[:3]:  # Show top 3
                    name = restaurant.get('name', 'N/A')
                    rating = restaurant.get('rating', 'N/A')
                    price = restaurant.get('price_range', 'N/A')
                    response += f"   • {name} ({rating}/5, {price})\n"
            
            if local.get("hotels"):
                hotels = local["hotels"]
                response += f"**Nearby Hotels:**\n"
                for hotel in hotels[:3]:  # Show top 3
                    name = hotel.get('name', 'N/A')
                    rating = hotel.get('rating', 'N/A')
                    price = hotel.get('price_range', 'N/A')
                    response += f"   • {name} ({rating}/5, {price})\n"
            
            if local.get("parking"):
                parking = local["parking"]
                response += f"**Parking Options:** {parking}\n"
            
            response += "\n"
        
        # Alternative transportation comparison
        if travel_data.get("transportation_comparison"):
            comparison = travel_data["transportation_comparison"]
            response += f"🚌 **Transportation Comparison:**\n"
            
            for option in comparison.get("options", []):
                mode = option.get('mode', 'N/A')
                duration = option.get('duration', 'N/A')
                cost = option.get('cost', 'N/A')
                pros = option.get('pros', [])
                cons = option.get('cons', [])
                
                response += f"**{mode}:** {duration}"
                if cost and cost != 'N/A':
                    response += f" - {cost}"
                response += "\n"
                
                if pros:
                    response += f"   • Pros: {', '.join(pros[:2])}\n"  # Show top 2 pros
                if cons:
                    response += f"   • Cons: {', '.join(cons[:2])}\n"  # Show top 2 cons
                response += "\n"
        
        return response.strip()

    async def get_transportation_options(self, origin: str, destination: str) -> Dict[str, Any]:
        """
        Public API: Get summarized transportation options between origin and destination.

        This method is intentionally lightweight and composes results from existing
        internal helpers (geocoding, directions, flights) so it remains dynamic
        and does not hardcode any external specifics.

        Returns a dict with an 'options' list where each option contains mode,
        duration (human-friendly), duration_seconds (when available), and cost
        if estimable.
        """
        try:
            options = []

            # Geocode locations (best-effort)
            origin_coords = await self._geocode_nominatim(origin) if origin else None
            dest_coords = await self._geocode_nominatim(destination) if destination else None

            # 1) Driving / car option (if we have coordinates)
            driving = None
            if origin_coords and dest_coords:
                driving = await self._get_openroute_directions(origin_coords, dest_coords, profile="driving-car")
                if driving:
                    options.append({
                        "mode": "Driving",
                        "duration": driving.get("formatted_duration", "Unknown"),
                        "duration_seconds": driving.get("duration", None),
                        "distance_miles": driving.get("distance", None),
                        "cost": None
                    })
                else:
                    # Fallback estimate using haversine when routing API is not available
                    estimate = self._estimate_driving_option(origin_coords, dest_coords)
                    options.append(estimate)

                # 2) Walking (only if short distance)
                if driving and driving.get("distance", 0) and driving.get("distance", 0) < 3:
                    walking = await self._get_openroute_directions(origin_coords, dest_coords, profile="foot-walking")
                    if walking:
                        options.append({
                            "mode": "Walking",
                            "duration": walking.get("formatted_duration", "Unknown"),
                            "duration_seconds": walking.get("duration", None),
                            "distance_miles": walking.get("distance", None),
                            "cost": 0
                        })

                # 3) Cycling (if reasonable distance)
                if driving and driving.get("distance", 0) and driving.get("distance", 0) < 15:
                    cycling = await self._get_openroute_directions(origin_coords, dest_coords, profile="cycling-regular")
                    if cycling:
                        options.append({
                            "mode": "Cycling",
                            "duration": cycling.get("formatted_duration", "Unknown"),
                            "duration_seconds": cycling.get("duration", None),
                            "distance_miles": cycling.get("distance", None),
                            "cost": 0
                        })

            # 4) Transit / public transport - approximate via driving profile as fallback
            if origin_coords and dest_coords:
                transit_est = await self._get_openroute_directions(origin_coords, dest_coords, profile="driving-car")
                if transit_est:
                    # Use the driving duration to provide a transit estimate with a disclaimer
                    options.append({
                        "mode": "Public transit (estimate)",
                        "duration": transit_est.get("formatted_duration", "Unknown"),
                        "duration_seconds": transit_est.get("duration", None),
                        "distance_miles": transit_est.get("distance", None),
                        "cost": None,
                        "note": "Transit estimate approximated using driving data; ask for more precise transit info if needed"
                    })

            # 5) Flying - only if locations likely represent cities far apart or include airport codes
            # Do a conservative check: if either value is short (<=3) treat as possible airport code
            if (origin and len(origin.strip()) <= 3) or (destination and len(destination.strip()) <= 3) or (
                origin_coords and dest_coords and driving and driving.get("distance", 0) and driving.get("distance", 0) > 200):
                flights = await self._get_kiwi_flights(origin, destination)
                if flights and flights.get("flights"):
                    # Summarize first flight option
                    first = flights["flights"][0]
                    options.append({
                        "mode": "Flight",
                        "duration": first.get("flight_duration", "Unknown"),
                        "duration_seconds": None,
                        "price_estimate": first.get("price", None),
                        "details": first
                    })

            # Add a default fallback if no options were generated
            if not options:
                # Provide a minimal response so callers can handle gracefully
                return {"options": [], "note": "No transportation options could be determined with available data."}

            return {"options": options}

        except Exception as e:
            logger.error(f"Error in get_transportation_options: {e}")
            return {"options": [], "error": str(e)}


# Singleton instance
_recruitiq_travel_service = None

def get_recruitiq_travel_service() -> RecruitIQTravelService:
    """
    Factory function to get or create a RecruitIQTravelService instance.
    
    Returns:
        Singleton instance of RecruitIQTravelService
    """
    global _recruitiq_travel_service
    if _recruitiq_travel_service is None:
        _recruitiq_travel_service = RecruitIQTravelService()
    return _recruitiq_travel_service
