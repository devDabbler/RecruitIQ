"""InterviewTravelAssistant - A specialized component for interview candidate travel needs."""
import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from services.recruitiq_travel_service import get_recruitiq_travel_service

logger = logging.getLogger(__name__)

class InterviewTravelAssistant:
    """Specialized service for managing interview candidate travel needs.
    
    This class focuses specifically on travel requirements for interview candidates,
    providing features like interview-specific travel recommendations, preparation
    timelines, and stress reduction strategies.
    """
    
    def __init__(self):
        """Initialize the Interview Travel Assistant service."""
        logger.info("Initializing InterviewTravelAssistant for candidate travel support")
        
        # Get instance of the RecruitIQTravelService for data gathering
        self.travel_service = get_recruitiq_travel_service()
        
        # Interview-specific preparation timing templates (in hours before interview)
        self.preparation_templates = {
            "local_interview": {
                "arrival_buffer": 0.5,  # 30 minutes early to interview location
                "preparation_time": 1.5,  # 1.5 hours for final preparation
                "sleep_hours": 8,        # Recommended sleep hours
                "meal_time": 1,          # Time for proper meal before interview
                "clothing_preparation": 0.5  # Time to dress and final appearance check
            },
            "travel_interview": {
                "arrival_buffer": 1,     # 1 hour buffer for unfamiliar location
                "hotel_checkin_buffer": 2,  # Time to check in and settle at hotel
                "preparation_time": 2,    # Extended preparation in unfamiliar setting
                "sleep_hours": 8.5,      # Extra sleep recommended when traveling
                "exploration_time": 1,   # Time to explore/familiarize with location
                "meal_time": 1.5,        # Extended meal time in unfamiliar location
                "clothing_preparation": 0.75  # Extra time for unpacking/preparing appearance
            },
            "remote_interview": {
                "setup_time": 0.5,       # Tech setup time
                "test_time": 0.25,       # Time to test camera/mic/connection
                "preparation_time": 1,    # Time to prepare physical space
                "arrival_buffer": 0.25,   # Be ready 15 minutes early
                "sleep_hours": 8,         # Recommended sleep
                "meal_time": 0.75         # Quick but proper meal
            }
        }
        
        # Stress reduction strategies organized by timing
        self.stress_reduction_strategies = {
            "day_before": [
                "Review your research about the company one final time",
                "Prepare your interview outfit and try it on",
                "Print extra copies of your resume and reference list",
                "Plan your travel route and perform a test run if possible",
                "Prepare a small meal for the morning of the interview",
                "Pack a water bottle and small snack",
                "Set multiple alarms for the morning",
                "Practice deep breathing or meditation before sleep",
                "Avoid excessive caffeine or alcohol",
                "Get to bed early to ensure adequate rest"
            ],
            "morning_of": [
                "Wake up with extra time to spare",
                "Eat a moderate, protein-rich breakfast",
                "Review your key talking points briefly",
                "Perform light exercise or stretching",
                "Practice power poses for confidence",
                "Listen to music that energizes or calms you",
                "Drink water but moderate caffeine intake",
                "Check traffic and transit status"
            ],
            "just_before": [
                "Arrive early and find a quiet place to center yourself",
                "Use deep breathing techniques (4-7-8 method)",
                "Avoid looking at phone or email",
                "Use positive visualization techniques",
                "Review your strengths and recent accomplishments",
                "Practice a confident smile and posture",
                "Use a restroom for final appearance check",
                "Drink a small amount of water",
                "Engage in small talk with receptionist or others"
            ],
            "during_travel": [
                "Focus on your breathing while in transit",
                "Listen to calming music or a motivational podcast",
                "Avoid excessive email checking or social media",
                "Stay hydrated during your journey",
                "Use travel time for light review, not cramming",
                "If flying, get up and stretch periodically",
                "Download a meditation app for quick calming sessions",
                "Bring healthy snacks to maintain energy levels"
            ]
        }

    async def get_interview_travel_plan(self, origin: str, destination: str, 
                                   interview_datetime: str, 
                                   return_datetime: Optional[str] = None,
                                   preferred_mode: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate a comprehensive interview travel plan with recommendations tailored
        to interview scenarios.
        
        Args:
            origin: Origin location of the candidate
            destination: Interview location
            interview_datetime: Date and time of the interview (ISO format)
            return_datetime: Optional return date/time for round-trip planning
            preferred_mode: Preferred mode of transportation
            
        Returns:
            Dictionary containing detailed interview travel plan
        """
        logger.info(f"Generating interview travel plan from {origin} to {destination} for {interview_datetime}")
        
        # Parse interview datetime
        interview_dt = datetime.fromisoformat(interview_datetime)
        
        # Initialize the travel plan structure
        travel_plan = {
            "candidate_origin": origin,
            "interview_location": destination,
            "interview_datetime": interview_datetime,
            "travel_recommendations": {},
            "preparation_timeline": {},
            "contingency_plans": [],
            "special_considerations": []
        }
        
        try:
            # Use RecruitIQTravelService to gather base travel data
            travel_data = await self.travel_service.gather_recruiting_travel_data(
                origin=origin,
                destination=destination,
                intent_type="interview_travel",
                travel_date=interview_dt.strftime("%Y-%m-%d")
            )
            
            if not travel_data or "error" in travel_data:
                logger.error(f"Failed to gather travel data: {travel_data.get('error', 'Unknown error')}")
                travel_plan["error"] = "Could not retrieve travel information"
                return travel_plan
            
            # Add basic travel information from the travel service
            travel_plan["travel_recommendations"] = self._generate_interview_specific_recommendations(
                travel_data, interview_dt, preferred_mode
            )
            
            # Determine if this is a local interview or requires traveling from another city
            is_long_distance = self._is_long_distance_travel(travel_data)
            travel_plan["is_long_distance"] = is_long_distance
            
            # Generate preparation timeline based on travel circumstances
            timeline_type = "travel_interview" if is_long_distance else "local_interview"
            travel_plan["preparation_timeline"] = self._generate_preparation_timeline(
                interview_dt, timeline_type, travel_data
            )
            
            # Add contingency plans based on travel data
            travel_plan["contingency_plans"] = self._generate_contingency_plans(travel_data, interview_dt)
            
            # Add interview-specific considerations
            travel_plan["special_considerations"] = self._get_interview_specific_considerations(
                travel_data, interview_dt
            )
            
            return travel_plan
            
        except Exception as e:
            logger.error(f"Error generating interview travel plan: {e}")
            travel_plan["error"] = str(e)
            return travel_plan
            
    def _generate_interview_specific_recommendations(self, travel_data: Dict[str, Any], 
                                                   interview_dt: datetime,
                                                   preferred_mode: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate interview-specific travel recommendations based on general travel data.
        
        Args:
            travel_data: Base travel data from RecruitIQTravelService
            interview_dt: Interview date and time
            preferred_mode: Preferred mode of transport
            
        Returns:
            Dictionary with interview-focused travel recommendations
        """
        recommendations = {
            "optimal_departure_time": None,
            "recommended_travel_mode": preferred_mode or travel_data.get("travel_mode", "driving"),
            "estimated_travel_duration": None,
            "buffer_time_recommendation": 30,  # Default 30 min buffer
            "arrival_time": None,
            "departure_time": None,
            "route_complexity": "low",
            "interview_day_considerations": []
        }
        
        # Calculate travel duration from travel_data
        duration_minutes = 0
        if "directions" in travel_data:
            duration_seconds = travel_data["directions"].get("duration", 0)
            duration_minutes = duration_seconds / 60
            recommendations["estimated_travel_duration"] = duration_minutes
            
            # More complex routes may need more buffer time
            route_steps = len(travel_data["directions"].get("steps", []))
            if route_steps > 10:
                recommendations["route_complexity"] = "high"
                recommendations["buffer_time_recommendation"] = 45  # More buffer time for complex routes
            elif route_steps > 5:
                recommendations["route_complexity"] = "medium"
                recommendations["buffer_time_recommendation"] = 30
            
        elif "flights" in travel_data:
            # For air travel
            recommendations["recommended_travel_mode"] = "flying"
            flight_info = travel_data["flights"].get("options", [])[0] if travel_data["flights"].get("options") else {}
            if flight_info:
                # Convert flight duration to minutes if available
                if "duration" in flight_info:
                    duration_minutes = flight_info["duration"]
                    recommendations["estimated_travel_duration"] = duration_minutes
                
                # For flights, always recommend higher buffer times
                recommendations["buffer_time_recommendation"] = 60  # 1 hour minimum for flights
                recommendations["route_complexity"] = "high"
        
        # Calculate optimal departure and arrival times
        if duration_minutes > 0:
            # Add buffer time to ensure punctuality
            buffer_minutes = recommendations["buffer_time_recommendation"]
            
            # Calculate arrival time (before interview time)
            arrival_time = interview_dt - timedelta(minutes=buffer_minutes)
            recommendations["arrival_time"] = arrival_time.isoformat()
            
            # Calculate departure time based on duration
            departure_time = arrival_time - timedelta(minutes=duration_minutes)
            recommendations["departure_time"] = departure_time.isoformat()
            recommendations["optimal_departure_time"] = departure_time.isoformat()
        
        # Add interview-day specific travel considerations
        if "weather" in travel_data:
            weather_impact = travel_data.get("assessment", {}).get("special_considerations", [])
            weather_impact = [item for item in weather_impact if "weather" in item.lower()]
            
            if weather_impact:
                recommendations["interview_day_considerations"].extend(weather_impact)
                recommendations["buffer_time_recommendation"] += 15  # Add 15 minutes for bad weather
        
        # Add considerations based on time of day (rush hour)
        interview_hour = interview_dt.hour
        if 7 <= interview_hour <= 10:  # Morning rush hour
            recommendations["interview_day_considerations"].append(
                "Interview is during morning rush hour - consider extra travel time")
            recommendations["buffer_time_recommendation"] += 15
        elif 16 <= interview_hour <= 19:  # Evening rush hour
            recommendations["interview_day_considerations"].append(
                "Interview is during evening rush hour - consider extra travel time")
            recommendations["buffer_time_recommendation"] += 15
            
        # Add interview-specific travel advice
        recommendations["interview_day_considerations"].extend([
            "Dress professionally and comfortably for travel",
            "Bring interview materials in a professional folder or portfolio",
            "Save interview location contact information in case you need to notify them of delays",
            "Check parking options in advance if driving"
        ])
        
        return recommendations
        
    def _is_long_distance_travel(self, travel_data: Dict[str, Any]) -> bool:
        """
        Determine if the travel is considered long-distance (requiring different preparation
        strategies for interview candidates).
        
        Args:
            travel_data: Base travel data from RecruitIQTravelService
            
        Returns:
            Boolean indicating if this is long-distance travel
        """
        # Consider flight travel as long distance by default
        if "flights" in travel_data:
            return True
            
        # For driving or other ground transportation, use distance/duration thresholds
        if "directions" in travel_data:
            # Consider anything over 100km or 2 hours as long distance
            distance_meters = travel_data["directions"].get("distance", 0)
            distance_km = distance_meters / 1000
            
            duration_seconds = travel_data["directions"].get("duration", 0)
            duration_hours = duration_seconds / 3600
            
            return distance_km > 100 or duration_hours > 2
            
        # If we can't determine, use a geographic distance calculation as fallback
        if "origin_coords" in travel_data and "destination_coords" in travel_data:
            # Simple calculation (doesn't account for Earth's curvature, but sufficient for estimation)
            origin = travel_data["origin_coords"]
            dest = travel_data["destination_coords"]
            
            # Rough distance calculation (1 degree lat ≈ 111 km)
            lat_diff = abs(origin[0] - dest[0])
            lon_diff = abs(origin[1] - dest[1])
            
            # Very rough approximation of distance
            approx_distance = ((lat_diff * 111) ** 2 + (lon_diff * 111 * 0.85) ** 2) ** 0.5
            
            return approx_distance > 100
        
        # If we still can't determine, check if travel mode is flying
        travel_mode = travel_data.get("travel_mode", "")
        if travel_mode == "flying":
            return True
            
        # Default - if we can't determine, assume it's not long distance
        return False

    def _generate_preparation_timeline(self, interview_dt: datetime, timeline_type: str, travel_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a preparation timeline for the candidate based on interview type and timing.
        Args:
            interview_dt: Interview datetime
            timeline_type: One of 'local_interview', 'travel_interview', or 'remote_interview'
            travel_data: Travel data dict
        Returns:
            Dict with preparation steps and recommended times
        """
        template = self.preparation_templates.get(timeline_type, {})
        timeline = {}
        if not template:
            return timeline
        # Calculate key times
        sleep_time = interview_dt - timedelta(hours=template.get("sleep_hours", 8))
        meal_time = interview_dt - timedelta(hours=template.get("meal_time", 1))
        prep_time = interview_dt - timedelta(hours=template.get("preparation_time", 1))
        arrival_time = interview_dt - timedelta(hours=template.get("arrival_buffer", 0.5))
        clothing_time = interview_dt - timedelta(hours=template.get("clothing_preparation", 0.5)) if "clothing_preparation" in template else None
        setup_time = interview_dt - timedelta(hours=template.get("setup_time", 0.5)) if "setup_time" in template else None
        test_time = interview_dt - timedelta(hours=template.get("test_time", 0.25)) if "test_time" in template else None
        exploration_time = interview_dt - timedelta(hours=template.get("exploration_time", 1)) if "exploration_time" in template else None
        # Build timeline
        if clothing_time:
            timeline["Clothing Preparation"] = clothing_time.isoformat()
        if setup_time:
            timeline["Tech Setup"] = setup_time.isoformat()
        if test_time:
            timeline["Test Equipment"] = test_time.isoformat()
        if exploration_time:
            timeline["Familiarize with Location"] = exploration_time.isoformat()
        timeline["Final Preparation"] = prep_time.isoformat()
        timeline["Meal"] = meal_time.isoformat()
        timeline["Sleep"] = sleep_time.isoformat()
        timeline["Arrival Buffer"] = arrival_time.isoformat()
        return timeline

    def _generate_contingency_plans(self, travel_data: Dict[str, Any], interview_dt: datetime) -> List[str]:
        """
        Generate contingency plans for common travel disruptions or interview-day issues.
        Args:
            travel_data: Travel data dict
            interview_dt: Interview datetime
        Returns:
            List of contingency plan suggestions
        """
        plans = []
        # Weather
        if "weather" in travel_data:
            plans.append("Check weather forecast 24 hours before and pack accordingly.")
            if travel_data["weather"].get("severity", "") in ["rain", "snow", "storm"]:
                plans.append("Bring umbrella or rain gear; allow extra travel time for bad weather.")
        # Traffic
        if "traffic" in travel_data:
            plans.append("Monitor real-time traffic updates and have an alternate route ready.")
        # Flights
        if "flights" in travel_data:
            plans.append("Sign up for flight delay/cancellation alerts. Have airline and hotel contact info handy.")
        # Transit
        if travel_data.get("travel_mode", "") == "transit":
            plans.append("Check transit schedules and have rideshare app as backup.")
        # General
        plans.append("Save interview location and recruiter contact in your phone.")
        plans.append("Prepare a list of nearby coffee shops or lobbies in case you arrive too early.")
        plans.append("Pack a portable phone charger.")
        plans.append("Have digital and paper copies of your resume and references.")
        return plans

    def _get_interview_specific_considerations(self, travel_data: Dict[str, Any], interview_dt: datetime) -> List[str]:
        """
        Return a list of special considerations for the interview based on travel and timing.
        Args:
            travel_data: Travel data dict
            interview_dt: Interview datetime
        Returns:
            List of considerations
        """
        considerations = []
        # Early/late interview
        if interview_dt.hour < 9:
            considerations.append("Interview is early in the morning; plan for extra rest and earlier meal.")
        if interview_dt.hour >= 17:
            considerations.append("Interview is late in the day; keep energy up with snacks and hydration.")
        # Dress code
        if "company_info" in travel_data and "dress_code" in travel_data["company_info"]:
            considerations.append(f"Company dress code: {travel_data['company_info']['dress_code']}")
        # Security
        if "security" in travel_data:
            considerations.append("Bring government-issued ID for building security check.")
        # Accessibility
        if "accessibility" in travel_data:
            considerations.append("Confirm accessibility accommodations in advance if needed.")
        # Remote
        if travel_data.get("travel_mode", "") == "remote":
            considerations.append("Test your internet connection and webcam/microphone ahead of time.")
        return considerations

    def generate_preparation_timeline(self, interview_datetime: str, timeline_type: str, travel_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Public method to generate a preparation timeline for the candidate.
        Args:
            interview_datetime: Interview datetime in ISO format
            timeline_type: One of 'local_interview', 'travel_interview', or 'remote_interview'
            travel_data: Travel data dict
        Returns:
            Dict with preparation steps and recommended times
        """
        try:
            interview_dt = datetime.fromisoformat(interview_datetime)
        except Exception as e:
            logger.error(f"Invalid interview_datetime format: {e}")
            return {"error": "Invalid interview_datetime format. Please use ISO format."}
        if timeline_type not in self.preparation_templates:
            logger.error(f"Invalid timeline_type: {timeline_type}")
            return {"error": f"Invalid timeline_type: {timeline_type}."}
        return self._generate_preparation_timeline(interview_dt, timeline_type, travel_data)

    def get_stress_reduction_tips(self, timing: str) -> Dict[str, Any]:
        """
        Public method to get stress reduction tips for a given timing.
        Args:
            timing: One of 'day_before', 'morning_of', 'just_before', 'during_travel'
        Returns:
            Dict with tips or error message
        """
        if timing not in self.stress_reduction_strategies:
            logger.error(f"Invalid timing for stress reduction tips: {timing}")
            return {"error": f"Invalid timing: {timing}. Must be one of {list(self.stress_reduction_strategies.keys())}."}
        return {"tips": self.stress_reduction_strategies[timing]}
