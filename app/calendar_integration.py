import os
import requests
import asyncio
from typing import Dict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

executor = ThreadPoolExecutor(max_workers=5)


def _send_booking_request(user_id: str, lead_id: str, lead_name: str, start_time: str,
                          end_time: str, summary: str, timezone: str = "UTC",
                          description: str = None, location: str = None,
                          attendees: list = None) -> Dict:
    """
    Internal function to send the actual booking request.
    This runs in a separate thread.

    Args:
        user_id: The ID of the agent
        lead_id: The ID of the lead
        lead_name: The name of the lead
        start_time: ISO formatted start time
        end_time: ISO formatted end time
        summary: Event summary/title
        timezone: Timezone for the event (default: UTC)
        description: Optional event description
        location: Optional event location
        attendees: Optional list of attendee emails
    """
    try:
        api_url = os.getenv("BOOKING_API_URL", "https://drew-ai-backend-admin1339.replit.app/book_slot")

        booking_data = {
            "user_id": int(user_id),
            "lead_id": lead_id,
            "lead_name": lead_name,
            "start_time": start_time,
            "end_time": end_time,
            "summary": summary,
            "timezone": timezone,
            "request_time": datetime.now().isoformat(),
            "location": location,
        }

        if description:
            booking_data["description"] = description

        print(booking_data)

        response = requests.post(
            api_url,
            json=booking_data,
            headers={"Content-Type": "application/json"}
        )

        response.raise_for_status()
        print(f"Booking successful for agent {user_id} and lead {lead_id}")
        return response.json()

    except requests.RequestException as e:
        print(f"Error booking appointment: {e}")
        return {
            "error": "Failed to book appointment",
            "details": str(e)
        }


def book_appointment(
        user_id: str,
        lead_id: str,
        lead_name: str,
        start_time: datetime,
        duration_minutes: int = 30,
        summary: str = "Customer Appointment",
        timezone: str = "UTC",
        description: str = None,
        location: str = None,
        attendees: list = None
) -> Dict:
    """
    Book an appointment with the agent through the booking API.
    Returns immediately and processes the request in the background.

    Args:
        user_id: The ID of the agent
        lead_id: The ID of the lead
        lead_name: The name of the lead
        start_time: DateTime object for the start of the appointment
        duration_minutes: Duration of the appointment in minutes (default: 30)
        summary: Event summary/title (default: "Customer Appointment")
        timezone: Timezone for the event (default: UTC)
        description: Optional event description
        location: Optional event location
        attendees: Optional list of attendee emailss

    Returns:
        Dict with immediate acknowledgment
    """
    end_time = start_time + timedelta(minutes=duration_minutes)

    start_iso = start_time.isoformat()
    end_iso = end_time.isoformat()

    executor.submit(
        _send_booking_request,
        user_id,
        lead_id,
        lead_name,
        start_iso,
        end_iso,
        summary,
        timezone,
        description,
        location,
        attendees
    )

    return {
        "status": "scheduled",
        "message": "Booking request has been processed, invite sent.",
        "user_id": user_id,
        "lead_id": lead_id,
        "start_time": start_iso,
        "end_time": end_iso
    }
