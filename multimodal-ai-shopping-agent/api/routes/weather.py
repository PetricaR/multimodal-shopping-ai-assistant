"""
Weather Routes
Proxies Google Maps Weather API (hourly history) to keep the API key server-side.
"""

import os
import logging
import httpx
from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/weather", tags=["weather"])

WEATHER_BASE = "https://weather.googleapis.com/v1/history/hours:lookup"


@router.get("/current")
async def get_current_weather(
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude"),
    hours: int = Query(3, ge=1, le=24, description="Hours of history to fetch"),
):
    """
    Returns the most recent hour of weather data for the given location.
    Uses Google Maps Weather API (history/hours) to keep the key server-side.
    """
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="Weather API key not configured")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                WEATHER_BASE,
                params={
                    "key": api_key,
                    "location.latitude": lat,
                    "location.longitude": lon,
                    "hours": hours,
                    "pageSize": 1,
                },
            )
            resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        logger.error(f"Weather API error: {e.response.status_code} {e.response.text[:200]}")
        raise HTTPException(status_code=502, detail="Weather API request failed")
    except httpx.RequestError as e:
        logger.error(f"Weather API connection error: {e}")
        raise HTTPException(status_code=502, detail="Weather API unreachable")

    data = resp.json()
    hours_data = data.get("historyHours", [])
    if not hours_data:
        raise HTTPException(status_code=404, detail="No weather data for this location")

    # Use the most recent hour (first item)
    h = hours_data[0]

    def _deg(obj: dict | None) -> float | None:
        return obj.get("degrees") if obj else None

    wind = h.get("wind", {})
    precip = h.get("precipitation", {})
    prob = precip.get("probability", {})

    return {
        "temperature": _deg(h.get("temperature")),
        "feels_like": _deg(h.get("feelsLikeTemperature")),
        "condition": h.get("weatherCondition", {}).get("description", {}).get("text"),
        "condition_type": h.get("weatherCondition", {}).get("type"),
        "humidity": h.get("relativeHumidity"),
        "uv_index": h.get("uvIndex"),
        "is_daytime": h.get("isDaytime", True),
        "precipitation_probability": prob.get("percent"),
        "precipitation_type": prob.get("type"),
        "wind_speed_kmh": wind.get("speed", {}).get("value"),
        "wind_direction": wind.get("direction", {}).get("cardinal"),
        "visibility_km": h.get("visibility", {}).get("distance"),
        "cloud_cover_pct": h.get("cloudCover"),
        "timezone": data.get("timeZone", {}).get("id"),
    }
