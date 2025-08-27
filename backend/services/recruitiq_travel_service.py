"""RecruitIQ Travel Service - Specialized travel service for recruiting scenarios."""
import logging
import json
import asyncio
import time
import re
from typing import Dict, Any, Optional, Tuple, List, Union
import httpx
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class RecruitIQTravelService:
    """Service for fetching and analyzing travel information specifically for recruiting scenarios."""
    
    def __init__(self):
        """Initialize the RecruitIQ travel service."""
        logger.info("Initializing RecruitIQTravelService for recruiting-focused travel intelligence")
        
        self.http_client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": "RecruitIQ Travel Assistant/1.0",
                "Accept": "application/json"
            }
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
                                           intent_type: str, travel_date: Optional[str] = None) -> Dict[str, Any]:
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
            "travel_mode": self._detect_travel_mode(f"from {origin} to {destination}")
        }
        
        try:
            # Step 1: Geocode origin and destination
            logger.info("Geocoding origin and destination locations")
            origin_coords = await self._geocode_nominatim(origin)
            dest_coords = await self._geocode_nominatim(destination)
            
            if origin_coords and dest_coords:
                result["origin_coords"] = origin_coords
                result["destination_coords"] = dest_coords
                
                # Step 2: Get weather at destination
                logger.info("Fetching weather conditions at destination")
                weather_data = await self._get_weather_conditions(dest_coords[0], dest_coords[1], travel_date)
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
                        # OpenRoute doesn't support transit directly, use driving as approximation
                        profile = "driving-car"
                        
                    directions = await self._get_openroute_directions(origin_coords, dest_coords, profile)
                    if directions:
                        result["directions"] = directions
                
            # Step 4: Get recruiting-specific advice
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
            response = await self.http_client.post(url, json=data)
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
                                             travel_data: Dict[str, Any]) -> str:
        """
        Generate recruiting-specific travel advice.
        
        Args:
            origin: Origin location
            destination: Destination location
            intent_type: Type of recruiting intent
            travel_data: Travel data collected
            
        Returns:
            String containing recruiting-specific advice
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
            
            # Combine all advice into a comprehensive string
            formatted_advice = "\n".join(advice)
            
            return formatted_advice
            
        except Exception as e:
            logger.error(f"Error generating recruiting travel advice: {e}")
            return "Unable to generate recruiting-specific travel advice at this time."
    
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
