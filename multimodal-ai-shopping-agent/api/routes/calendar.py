"""
Calendar integration to fetch Public Holidays
"""
import os
import logging
import asyncio
from functools import partial
from fastapi import APIRouter
from datetime import datetime, timedelta, timezone
import requests

router = APIRouter(prefix="/api/v1/calendar", tags=["calendar"])
logger = logging.getLogger(__name__)

CALENDAR_ID = "en.romanian#holiday@group.v.calendar.google.com"

@router.get("/holidays")
async def get_holidays(days: int = 7):
    """
    Get Romanian public holidays for the next N days.
    """
    try:
        api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
        if not api_key:
            return {"error": "Missing GOOGLE_MAPS_API_KEY"}

        now = datetime.now(timezone.utc)
        time_min = now.isoformat().replace("+00:00", "Z")
        time_max = (now + timedelta(days=days)).isoformat().replace("+00:00", "Z")

        from urllib.parse import quote
        encoded_calendar_id = quote(CALENDAR_ID)

        url = f"https://www.googleapis.com/calendar/v3/calendars/{encoded_calendar_id}/events"
        params = {
            "key": api_key,
            "timeMin": time_min,
            "timeMax": time_max,
            "singleEvents": "true",
            "orderBy": "startTime"
        }

        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(None, partial(requests.get, url, params=params, timeout=5))
        response.raise_for_status()
        data = response.json()

        events = []
        for item in data.get("items", []):
            start = item.get("start", {}).get("date") or item.get("start", {}).get("dateTime")
            summary = item.get("summary", "Unknown Holiday")
            events.append({"date": start, "name": summary})

        return {"holidays": events}

    except Exception as e:
        logger.error(f"Calendar API error: {e}")
        return {"error": str(e), "message": "Failed to fetch holidays"}
