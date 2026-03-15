import requests
import logging
from datetime import datetime
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class ExternalDataService:
    """
    Provides external context for seasonal/event-based recipe suggestions (BR07)
    """
    
    @staticmethod
    def get_weather_context(city_id: str = "729065") -> Dict[str, Any]:
        """
        Fetch current weather context for a city (default Bucharest)
        Uses Meteostat JSON Proxy or similar free source.
        """
        # Bucharest (729065) mock/limited real check
        # In production: replace with real Meteostat/OpenWeather API key
        return {
            "temp": 2,
            "condition": "Cloudy",
            "season": "Winter",
            "is_cold": True
        }

    @staticmethod
    def get_upcoming_holidays() -> List[Dict[str, Any]]:
        """
        Get upcoming Romanian holidays and events (BR07)
        """
        # Mock holiday check for Romania
        now = datetime.now()
        events = [
            {"date": "2026-11-30", "name": "Sfântul Andrei", "type": "National"},
            {"date": "2026-12-01", "name": "Ziua Națională", "type": "National"},
            {"date": "2026-12-25", "name": "Crăciun", "type": "Religious"},
            {"date": "2026-04-12", "name": "Paște", "type": "Religious"}
        ]
        
        upcoming = []
        for event in events:
            edate = datetime.strptime(event["date"], "%Y-%m-%d")
            # If within next 14 days
            if 0 <= (edate - now).days <= 14:
                upcoming.append(event)
                
        return upcoming

    @staticmethod
    def get_seasonal_produce() -> List[str]:
        """
        List of fruits and vegetables in peak season (BR07)
        """
        month = datetime.now().month
        
        # Simple Romanian seasonal map
        seasonal = {
            1: ["Cartofi", "Ceapă", "Morcovi", "Țelină", "Mere"],
            2: ["Cartofi", "Ceapă", "Păstârnac", "Sfeclă", "Mere"],
            3: ["Spanac", "Urzici", "Ceapă verde", "Ridichi"],
            4: ["Spanac", "Salată verde", "Mărar", "Leurda"],
            5: ["Căpșuni", "Mazăre", "Cireșe", "Cartofi noi"],
            6: ["Cireșe", "Vișine", "Roșii", "Castraveți", "Dovlecei"],
            7: ["Piersici", "Caise", "Roșii", "Ardei", "Păstăi"],
            8: ["Pepene", "Roșii", "Vinete", "Prune", "Struguri"],
            9: ["Dovleac", "Prune", "Mere", "Pere", "Gogoșari"],
            10: ["Dovleac", "Varză", "Nuci", "Mere", "Gutui"],
            11: ["Gulie", "Sfeclă", "Praz", "Varză"],
            12: ["Cartofi", "Ceapă", "Sfeclă", "Mere"]
        }
        
        return seasonal.get(month, [])
