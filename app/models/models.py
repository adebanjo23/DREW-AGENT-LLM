import aiohttp
from typing import List, Optional, Dict
from app.tools_integration.google_search import find_places
from pydantic import BaseModel, Field
from datetime import datetime, timedelta

from app.tools_integration.zillow_integration import search_properties


class PlacesSearch(BaseModel):
    """Search for places near a specific location."""
    location: str = Field(..., description="Location to search around")
    query_type: str = Field(
        ...,
        description=
        "Type of place to search for (e.g., restaurants, parks, schools)")

    def execute(self) -> List[str]:
        return find_places(self.location, self.query_type)


class BookingRequest(BaseModel):
    """Book an appointment with an agent."""
    lead_name: str = Field(..., description="The name of the lead to be scheduled for the appointment")
    start_time: str = Field(..., description="Start time in ISO format (YYYY-MM-DDTHH:MM:SS)")
    location: Optional[str] = Field(None, description="A meeting location if meeting would be in-person")
    description: str = Field(None, description="A clear and detailed appointment description")

    async def execute(self, backend_url: str, user_id: str) -> Dict:
        """Book the appointment after lead confirmation."""
        try:
            # Parse the ISO format string to datetime
            start_datetime = datetime.fromisoformat(self.start_time)

            # Prepare booking data without lead_id
            booking_data = {
                "user_id": user_id,
                "lead_name": self.lead_name,
                "start_time": start_datetime.isoformat(),
                "location": self.location,
                "description": self.description
            }

            async with aiohttp.ClientSession() as session:
                print(f"Booking data: {booking_data}")
                print("Booking started")
                booking_url = f"{backend_url}/book_appointment"
                print(f"This is the booking url: {booking_url}")
                async with session.post(booking_url, json=booking_data) as response:
                    response_data = await response.json()

                    # Handle different response status codes
                    if response.status == 202:  # Successful single lead booking
                        print(f"Booking completed successfully: {response_data}")
                        return response_data
                    elif response.status == 300:  # Multiple leads found
                        print(f"Multiple leads found: {response_data}")
                        return response_data
                    elif response.status == 404:  # No leads found
                        print(f"No leads found: {response_data}")
                        return response_data
                    else:
                        error_message = response_data.get('message', 'Unknown error occurred')
                        print(f"Booking failed: {error_message}")
                        raise ValueError(f"Booking failed: {error_message}")

        except Exception as e:
            print(f"Error in booking appointment: {e}")
            raise


class CallRequest(BaseModel):
    """Initiate a call with a contact."""
    contact_name: str = Field(..., description="Name of the contact to call")
    discussion_points: str = Field(
        None, description="Any specific discussion points you want to address during the call"
    )
    call_time: str = Field(
        ...,
        description=(
            "Scheduled call time in ISO format (YYYY-MM-DDTHH:MM:SS). "
            "It must be either 'now' (i.e. today) or scheduled for the next day."
        )
    )

    async def execute(self, backend_url: str, user_id: str) -> dict:
        try:
            # Parse the ISO format string to a datetime object
            call_datetime = datetime.fromisoformat(self.call_time)
            now = datetime.now()
            tomorrow = now + timedelta(days=1)

            # Validate that the call time is either today or tomorrow
            if call_datetime.date() not in [now.date(), tomorrow.date()]:
                raise ValueError("Call time must be either now (today) or the next day.")

            # Prepare the payload to send to your endpoint
            call_data = {
                "user_id": user_id,
                "contact_name": self.contact_name,
                "call_time": call_datetime.isoformat(),
                "discussion_points": self.discussion_points
            }
            print(f"Call data: {call_data}")

            async with aiohttp.ClientSession() as session:
                # Replace '/initiate_call' with your actual endpoint
                call_url = f"{backend_url}/initiate_call"
                async with session.post(call_url, json=call_data) as response:
                    response_data = await response.json()

                    if response.status in [200, 202]:
                        print(f"Call initiated successfully: {response_data}")
                        return response_data
                    elif response.status == 300:
                        print(f"Multiple leads found: {response_data}")
                        return response_data
                    elif response.status == 404:  # No leads found
                        print(f"No leads found: {response_data}")
                        return response_data
                    else:
                        error_message = response_data.get('message', 'Unknown error occurred')
                        print(f"Booking failed: {error_message}")
                        raise ValueError(f"Booking failed: {error_message}")

        except Exception as e:
            print(f"Error initiating call: {e}")
            raise


class MessageRequest(BaseModel):
    """Send a message to a lead via SMS or Email."""
    lead_name: str = Field(
        ...,
        description="The name of the lead to send the message to"
    )
    message_type: str = Field(
        ...,
        description="Type of message to send. Allowed values: 'SMS' or 'Email'"
    )
    message_content: str = Field(
        ...,
        description="The content of the message that should be sent"
    )

    async def execute(self, backend_url: str, user_id: str) -> Dict:
        """
        Send the message to the lead via the backend service.
        This method posts the message data to the '/send_message' endpoint.
        """
        try:
            # Prepare the message payload
            message_data = {
                "user_id": user_id,
                "lead_name": self.lead_name,
                "message_type": self.message_type,
                "message_content": self.message_content,
                "timestamp": datetime.utcnow().isoformat()
            }

            async with aiohttp.ClientSession() as session:
                message_url = f"{backend_url}/send_message"
                print(f"Sending message data: {message_data}")
                async with session.post(message_url, json=message_data) as response:
                    response_data = await response.json()

                    if response.status in [200, 202]:
                        print(f"Message sent successfully: {response_data}")
                        return response_data
                    elif response.status == 300:
                        print(f"Multiple leads found: {response_data}")
                        return response_data
                    elif response.status == 404:  # No leads found
                        print(f"No leads found: {response_data}")
                        return response_data
                    else:
                        error_message = response_data.get('message', 'Unknown error occurred')
                        print(f"Failed to send message: {error_message}")
                        raise ValueError(f"Failed to send message: {error_message}")
        except Exception as e:
            print(f"Error in sending message: {e}")
            raise


class PropertySearch(BaseModel):
    """Search for properties and provide property information in a specific location with given criteria."""
    location: str = Field(..., description="Location to search for properties")
    status_type: str = Field(default="ForSale", description="Status type: ForSale or ForRent")

    async def execute(self) -> dict:
        result = await search_properties(location=self.location, status_type=self.status_type)
        props = result.get("properties", [])
        if props:
            return {"properties": [vars(prop) for prop in props]}
        return result
