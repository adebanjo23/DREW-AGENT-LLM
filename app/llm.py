import asyncio
import random
from datetime import datetime
from typing import List, Dict, Optional

import aiohttp
from openai import AsyncOpenAI
from pydantic import BaseModel, Field
import json
import os
from dotenv import load_dotenv

from .agent_prompt import agent_prompt
from .calendar_integration import book_appointment
from .google_search import find_places
from .custom_types import (
    ResponseRequiredRequest,
    ResponseResponse,
    Utterance,
)

load_dotenv()


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
    description: Optional[str] = Field(None, description="A clear and detailed appointment description")

    def execute(self, user_id: str, lead_id: str) -> dict:
        # Parse the ISO format string to datetime
        start_datetime = datetime.fromisoformat(self.start_time)
        print(start_datetime, self.location, self.description, self.lead_name)

        return book_appointment(
            user_id=user_id,
            lead_id=lead_id,
            lead_name=self.lead_name,
            start_time=start_datetime,
            location=self.location,
            description=self.description
        )


class LlmClient:

    def __init__(self):
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.call_id = None
        self.websocket_closed = False
        self.tools = [{
            "type": "function",
            "function": {
                "name": "PlacesSearch",
                "description": """Search for places near a location.
                    Use ONLY when:
                    - Agent specifically asks about local amenities
                    - You need to provide specific business/place names

                    DO NOT use when:
                    - Discussing general area features
                    - Already have area information from previous search
                    - Making casual conversation""",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "Location to search around"
                        },
                        "query_type": {
                            "type":
                                "string",
                            "description":
                                "Type of place to search for (e.g., restaurants, parks, schools)"
                        }
                    },
                    "required": ["location", "query_type"]
                }
            }
        }, {
            "type": "function",
            "function": {
                "name": "BookingRequest",
                "description": """agent requests to book a specific appointment.
                Use ONLY when:
                - Agent specifically requests to schedule/book an appointment
                - You have specific date/time information

                DO NOT use when:
                - Just discussing availability in general
                - Making casual conversation
                - Agent hasn't provided specific timing preferences""",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "lead_name": {
                            "type": "string",
                            "description": "The name of the lead to be scheduled for the appointment"
                        },
                        "start_time": {
                            "type": "string",
                            "description": "Start time in ISO format (YYYY-MM-DDTHH:MM:SS)"
                        },
                        "location": {
                            "type": "string",
                            "description": "A meeting location if meeting would be in-person"
                        },
                        "description": {
                            "type": "string",
                            "description": "A clear and detailed appointment description"
                        }
                    },
                    "required": ["start_time"]
                },
            },
        }]
        self.opening_lines = [
            "Hi, I'm Drew, your virtual real estate assistant. How can I help you today?",
            "Hello, I'm Drew! Ready to assist with all your real estate needs. What can I do for you?",
            "Hey there, I'm Drew! Looking for your dream home or need help with your listings?",
            "Hi, I'm Drew. Let's find the perfect property or tackle your real estate tasks together!",
            "Hello, I'm Drew, your AI assistant. Let's make your real estate journey smoother. What's on your mind?",
            "Hi, I'm Drew! Here to help with buying, selling, or managing your real estate needs.",
            "Hello, I'm Drew. Whether it's scheduling a showing or finding leads, I've got you covered!",
            "Hi there, I'm Drew! Ready to help with everything from listings to leads. How can I assist?",
            "Hey, I'm Drew, your personal real estate assistant. Let's get to work!",
            "Hi, I'm Drew! Need help finding a home or managing your clients? Just say the word!"
        ]
        self.wait_variants = [
            "Sure thing, just a sec.", "Hold on, let me check.",
            "Got it, give me a moment.", "Of course, let me sort that out.",
            "Alright, let me handle that.", "No problem, just a moment.",
            "Okay, let me get that for you.", "One second, I’m on it.",
            "Alright, let me take care of that.",
            "Sure, just a bit of patience.", "Right away, hold tight.",
            "Absolutely, hang on for a sec.", "Let me get to that real quick.",
            "Certainly, one moment, please.",
            "I’ll take care of it in just a second."
        ]
        self.metadata: Optional[Dict] = None
        self.message_history: List[Dict[str, str]] = []
        self.conversations: Dict[str, List] = {}
        self.backend_url = "https://drew-ai-backend-admin1339.replit.app"
        self.communications_data = {}
        self.is_first_interaction = True

    async def _init_communications(self, user_id: int):
        """Initialize communications data for the user."""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.backend_url}/get_user_communications/{user_id}"
                async with session.get(url) as response:
                    if response.status == 200:
                        self.communications_data = await response.json()

                        # Check if there are any previous Drew-User communications
                        if self.communications_data.get('communications'):
                            drew_communications = [
                                comm for comm in self.communications_data['communications']
                                if comm.get('communication_type') == 'UserDrewCommunication'
                            ]
                            self.is_first_interaction = len(drew_communications) == 0
                        print(self.communications_data)
                    else:
                        print(f"Failed to fetch user communications. Status: {response.status}")
        except Exception as e:
            print(f"Error fetching user communications: {e}")

    async def fetch_user_communications(self, user_id: int) -> Dict:
        """Fetch all user communications."""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.backend_url}/get_user_communications/{user_id}"
                async with session.get(url) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        print(f"Failed to fetch user communications. Status: {response.status}")
                        return {}
        except Exception as e:
            print(f"Error fetching user communications: {e}")
            return {}

    async def save_drew_communication(self, user_id: int, message_type: str, content: str, status: str = "successful"):
        """Save a communication between Drew and the user."""
        try:
            async with aiohttp.ClientSession() as session:
                data = {
                    "user_id": user_id,
                    "drew_id": self.metadata.get('drew_id'),
                    "type": message_type,
                    "status": status,
                    "details": {
                        "message": content,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }

                url = f"{self.backend_url}/save_communication"
                async with session.post(url, json=data) as response:
                    if response.status != 201:
                        print(f"Failed to save Drew communication. Status: {response.status}")
                        return None
                    return await response.json()
        except Exception as e:
            print(f"Error saving Drew communication: {e}")
            return None

    def _send_interim_message(self, message: str):
        """Send an interim message to the user about processing status."""
        print(f"\nDrew: {message}")

    def set_metadata(self, call_details: Dict):
        """Store call metadata and fetch user communications."""
        # Store call ID when we receive call details
        if call_details.get("call", {}).get("call_id"):
            self.call_id = call_details["call"]["call_id"]
        if call_details.get("call", {}).get("retell_llm_dynamic_variables"):
            self.metadata = call_details["call"]["retell_llm_dynamic_variables"]

            # If we have a user_id, fetch their communications history
            if user_id := self.metadata.get('user_id'):
                asyncio.create_task(self._init_communications(int(user_id)))

    def get_time_based_greeting(self) -> str:
        """Return a greeting based on the current time of day."""
        hour = datetime.now().hour

        if 5 <= hour < 12:
            return "Good morning"
        elif 12 <= hour < 17:
            return "Good afternoon"
        elif 17 <= hour < 22:
            return "Good evening"
        else:
            return "Happy late night"

    async def draft_begin_message(self) -> ResponseResponse:
        time_greeting = self.get_time_based_greeting()

        if not self.metadata:
            custom_wait_variants = [
                f"{time_greeting}! I'm Drew. How can I assist you today?",
                f"{time_greeting}! I'm Drew. What do you need help with?",
                f"{time_greeting}! I'm Drew. Ready to get started?",
                f"{time_greeting}! I'm Drew. How's your day going?",
                f"Hey there! I'm Drew. How can I support you today?",
                f"Hello! I'm Drew. What's on your mind?",
                f"{time_greeting}! I'm Drew. Let's make today productive!",
                f"{time_greeting}! I'm Drew. Let me know how I can help!",
                f"Hi! I'm Drew. Need help with anything?",
                f"Hey! I'm Drew. What's the plan for today?"
            ]
            greeting = random.choice(custom_wait_variants)
        else:
            user_name = self.metadata.get('user_name', '')

            if self.metadata.get('first_interaction') is not None:
                custom_greeting = [
                    f"{time_greeting}, {user_name}! Welcome aboard! I'm Drew, your personal assistant. I help manage leads, schedule appointments, track key metrics, and keep your workflow seamless. Let's get started!",

                    f"Hey {user_name}, great to have you here! I'm Drew, your AI-powered assistant. I'll help you stay organized by managing leads, scheduling, and tracking key performance metrics. Let's make things efficient!",

                    f"{time_greeting}, {user_name}! I'm Drew, your virtual assistant. I handle lead management, scheduling, and performance tracking so you can focus on closing more deals.",

                    f"Welcome, {user_name}! I'm Drew, designed to help you streamline your workflow by managing leads, scheduling appointments, and keeping track of your business performance.",

                    f"Nice to meet you, {user_name}! I'm Drew, your smart assistant. I help you stay on top of leads, appointments, and key insights, making your workflow smoother and more efficient.",

                    f"{time_greeting}, {user_name}! Congrats on getting started! I'm Drew, your AI assistant, here to help with lead tracking, scheduling, and performance insights. Let's get things rolling!",

                    f"Hey {user_name}! I'm Drew, your personal assistant! I'll handle scheduling, lead tracking, and key insights so you can focus on growing your business. Let's get started!",

                    f"{time_greeting}, {user_name}! I'm Drew, your AI-powered real estate assistant. I'll keep your workflow organized, track your performance, and help you stay productive. Let's go!"
                ]
            else:
                custom_greeting = [
                    # Casual & Friendly
                    f"{time_greeting}, {user_name}! Hope you're having a great day!",
                    f"Hey {user_name}, how's your day going?",
                    f"Hi {user_name}, what's new?",
                    f"Good to see you, {user_name}! What's on your plate today?",

                    # Professional & Supportive
                    f"{time_greeting}, {user_name}. How can I assist you today?",
                    f"Hello, {user_name}. Let me know how I can help!",
                    f"{time_greeting}, {user_name}. Ready to tackle the day?",
                    f"Welcome back, {user_name}. What's your priority today?",

                    # Engaging & Motivational
                    f"Hey {user_name}, let's make today productive!",
                    f"{time_greeting}, {user_name}! Ready to close some deals?",
                    f"Hope you're feeling great, {user_name}! Let's get started.",
                    f"{time_greeting}, {user_name}! What's the next big win for today?",

                    # Personalized & Conversational
                    f"Hi {user_name}, how's business looking today?",
                    f"Hey {user_name}, anything exciting happening in real estate?",
                    f"{time_greeting}, {user_name}! What's on your mind?",
                    f"Hello, {user_name}. Need help with anything specific?"
                ]

            greeting = random.choice(custom_greeting) if user_name else random.choice(self.opening_lines)

        self.message_history.append({"role": "assistant", "content": greeting})
        return ResponseResponse(response_id=0,
                                content=greeting,
                                content_complete=True,
                                end_call=False)

    async def _execute_tool(self, tool_name: str, args: dict) -> Dict:
        """Execute a tool and return its result"""
        if tool_name == "PlacesSearch":
            result = await asyncio.to_thread(PlacesSearch(**args).execute)
        elif tool_name == "BookingRequest":
            result = await asyncio.to_thread(
                BookingRequest(**args).execute,
                user_id=self.metadata.get('user_id'),
                lead_id=self.metadata.get('lead_id')
            )
        else:
            raise ValueError(f"Unknown tool: {tool_name}")
        return result

    def convert_transcript_to_messages(
            self, transcript: List[Utterance]) -> List[Dict]:
        """Convert transcript to OpenAI message format"""
        messages = []
        for msg in self.message_history:
            messages.append({"role": msg["role"], "content": msg["content"]})

        for utterance in transcript:
            if utterance.role == "agent":
                messages.append({
                    "role": "assistant",
                    "content": utterance.content
                })
            else:
                messages.append({"role": "user", "content": utterance.content})
        return messages

    def get_formatted_datetime(self) -> str:
        """Return current date and time in a human-readable format"""
        now = datetime.now()
        return now.strftime("%A, %B %d, %Y at %I:%M %p")

    async def prepare_prompt(self, request: ResponseRequiredRequest) -> List[Dict]:
        personalized_context = ""
        user_context = ""
        total_leads = 0

        if self.metadata:
            if self.communications_data:
                stats = self.communications_data.get('statistics', {})
                recent_comms = self.communications_data.get('communications', [])
                leads_data = self.communications_data.get('leads', [])

                # Format sample of leads (5 most recent)
                lead_samples = []
                total_leads = len(leads_data)
                active_leads_count = sum(
                    1 for lead in leads_data if lead.get('communication_counts', {}).get('total', 0) > 0)
                inactive_leads_count = total_leads - active_leads_count

                for lead in leads_data[:5]:
                    comm_counts = lead.get('communication_counts', {})
                    lead_samples.append(
                        f"- {lead['name']} ({lead['status']}): "
                        f"{comm_counts.get('total', 0)} total communications "
                        f"({comm_counts.get('drew', 0)} from Drew, {comm_counts.get('user', 0)} from agent)"
                    )

                # Format communication stats
                type_counts = stats.get('counts_by_type', {})
                success_rates = stats.get('success_rates', {})

                # Format recent communications
                total_communications = sum(type_counts.values())
                recent_interactions = []
                for comm in recent_comms[:5]:  # Last 5 communications
                    comm_type = comm.get('type', '')
                    details = comm.get('details', {})
                    created_at = datetime.fromisoformat(comm.get('created_at', '')).strftime("%B %d at %I:%M %p")
                    comm_source = "Drew" if "Drew" in comm.get('communication_type', '') else "Agent"

                    if comm_type == 'SMS':
                        recent_interactions.append(
                            f"- {comm_source} sent SMS on {created_at}: {details.get('message', 'No message')}"
                        )
                    elif comm_type == 'EMAIL':
                        recent_interactions.append(
                            f"- {comm_source} sent Email on {created_at}: Subject: {details.get('subject', 'No subject')}"
                        )
                    elif comm_type == 'CALL':
                        duration = comm.get('call', {}).get('duration', 0)
                        duration_mins = duration // 60
                        recent_interactions.append(
                            f"- {comm_source} had {duration_mins} minute call on {created_at}: {details.get('notes', 'No notes')}"
                        )

                # Format activity metrics
                recent_activity = stats.get('recent_activity', {})
                activity_summary = []
                for date, count in recent_activity.items():
                    formatted_date = datetime.fromisoformat(date).strftime("%B %d")
                    activity_summary.append(f"- {formatted_date}: {count} communications")

                # Build comprehensive context
                user_context = f"""
    Recent Activity Overview:
    Communications in the last 7 days:
    {chr(10).join(activity_summary)}

    Recent Interactions (showing 5 most recent out of {total_communications} total communications):
    {chr(10).join(recent_interactions)}
    Note: Full communication history is available in the dashboard.

    Lead Overview:
    Total Leads: {total_leads} ({active_leads_count} active, {inactive_leads_count} inactive)
    Recent Lead Sample (showing 5 most recent leads):
    {chr(10).join(lead_samples)}
    Note: Complete lead information and history is accessible through the dashboard.

    Communication Statistics:
    - Total SMS: {type_counts.get('SMS', 0)} (Success rate: {success_rates.get('SMS', 0)}%)
    - Total Emails: {type_counts.get('EMAIL', 0)} (Success rate: {success_rates.get('EMAIL', 0)}%)
    - Total Calls: {type_counts.get('CALL', 0)} (Success rate: {success_rates.get('CALL', 0)}%)
                """

            personalized_context = f"""
    You're speaking with {self.metadata.get('user_name', 'an agent')}.
    Role: {self.metadata.get('role', 'Agent')}
    Additional Information: {self.metadata.get('additional_info', '')}

    Current Status:
    {user_context}

    Instructions:
    - Use this context to personalize your responses and make relevant suggestions
    - Reference recent interactions when appropriate
    - You can mention specific leads from the sample when relevant
    - Be aware that you have access to all {total_leads} leads through the dashboard
    - Consider both active and inactive leads in your responses
    - Use communication patterns and success rates to inform suggestions
    - Remember you can access full historical data if needed through the dashboard
    """

        current_datetime = self.get_formatted_datetime()
        system_prompt = f"{agent_prompt}\n\nCurrent Date and Time: {current_datetime}\n\nPersonalized Context:\n{personalized_context}"

        print(system_prompt)  # For debugging
        messages = [{"role": "system", "content": system_prompt}]
        transcript_messages = self.convert_transcript_to_messages(request.transcript)
        messages.extend(transcript_messages)

        if request.interaction_type == "reminder_required":
            messages.append({
                "role": "user",
                "content": "(Provide tailored recommendations based on the agent's preferences and recent activity:)"
            })
        return messages

    async def draft_response(self, request: ResponseRequiredRequest):
        try:
            messages = await self.prepare_prompt(request)

            # Initial API call to get response and potential tool calls
            response = await self.client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                tools=self.tools,
                tool_choice="auto",
                temperature=0.3,
                stream=True)

            current_tool_calls = []
            current_content = ""

            async for chunk in response:
                delta = chunk.choices[0].delta

                # Handle tool calls
                if delta.tool_calls:
                    for tool_call in delta.tool_calls:
                        if tool_call.index is not None and tool_call.index >= len(
                                current_tool_calls):
                            current_tool_calls.append({
                                "id": tool_call.id,
                                "function": {
                                    "name": "",
                                    "arguments": ""
                                },
                                "type": "function"
                            })

                        if tool_call.function.name:
                            current_tool_calls[tool_call.index]["function"][
                                "name"] = tool_call.function.name
                        if tool_call.function.arguments:
                            current_tool_calls[tool_call.index]["function"][
                                "arguments"] += tool_call.function.arguments

                # Handle content
                if delta.content:
                    current_content += delta.content
                    yield ResponseResponse(
                        response_id=request.response_id,
                        content=delta.content,
                        content_complete=False,
                        end_call=False,
                    )

            # Process tool calls if any
            if current_tool_calls:
                yield ResponseResponse(
                    response_id=request.response_id,
                    content=random.choice(self.wait_variants),
                    content_complete=False,
                    end_call=False,
                )

                # Execute all tool calls concurrently
                tool_results = []
                for tool_call in current_tool_calls:
                    try:
                        args = json.loads(tool_call["function"]["arguments"])
                        result = await self._execute_tool(
                            tool_call["function"]["name"], args)
                        tool_results.append({
                            "tool_call_id":
                                tool_call["id"],
                            "role":
                                "tool",
                            "name":
                                tool_call["function"]["name"],
                            "content":
                                json.dumps(result)
                        })
                    except Exception as e:
                        print(f"Tool execution error: {e}")
                        yield ResponseResponse(
                            response_id=request.response_id,
                            content=
                            "I encountered an issue while searching. Let me try a different approach. ",
                            content_complete=False,
                            end_call=False,
                        )

                # Add tool results to messages and get final response
                messages.append({
                    "role": "assistant",
                    "content": current_content,
                    "tool_calls": current_tool_calls
                })
                for result in tool_results:
                    messages.append(result)

                # Get final response with tool results
                final_response = await self.client.chat.completions.create(
                    model="gpt-4o", messages=messages, stream=True)

                async for chunk in final_response:
                    if chunk.choices[0].delta.content:
                        yield ResponseResponse(
                            response_id=request.response_id,
                            content=chunk.choices[0].delta.content,
                            content_complete=False,
                            end_call=False,
                        )

            # Signal completion
            yield ResponseResponse(
                response_id=request.response_id,
                content="",
                content_complete=True,
                end_call=False,
            )

        except Exception as e:
            print(f"Error in draft_response: {e}")
            yield ResponseResponse(
                response_id=request.response_id,
                content=
                "I apologize, but I encountered an unexpected error. Could you please try again? ",
                content_complete=True,
                end_call=False,
            )

    async def cleanup(self):
        """Clean up resources and save final call data."""
        try:
            if self.call_id and self.metadata:
                user_id = self.metadata.get('user_id')
                if user_id:
                    max_retries = 3
                    for attempt in range(max_retries):
                        async with aiohttp.ClientSession() as session:
                            # Get call data from Retell
                            url = f"https://api.retellai.com/v2/get-call/{self.call_id}"
                            headers = {"Authorization": f"Bearer {os.getenv('RETELL_API_KEY')}"}

                            async with session.get(url, headers=headers) as response:
                                if response.status == 200:
                                    call_data = await response.json()

                                    # Check if call analysis is available
                                    if "call_analysis" in call_data and call_data["call_analysis"].get("call_summary"):
                                        duration_seconds = call_data['duration_ms'] / 1000

                                        # Save call data to backend
                                        data = {
                                            "user_id": int(user_id),
                                            "drew_id": self.metadata.get('drew_id'),
                                            "type": "CALL",
                                            "status": "successful",
                                            "details": {
                                                "notes": call_data["call_analysis"]["call_summary"],
                                                "recording_url": call_data.get("recording_url", "")
                                            },
                                            "duration": int(duration_seconds),
                                            "call_time": datetime.fromtimestamp(
                                                call_data["start_timestamp"] / 1000).isoformat(),
                                            "call_id": self.call_id
                                        }

                                        url = f"{self.backend_url}/save_communication"
                                        async with session.post(url, json=data) as response:
                                            if response.status != 201:
                                                print(f"Failed to save call data. Status: {response.status}")
                                        break  # Successfully processed, exit retry loop
                                    else:
                                        print(f"Attempt {attempt + 1}: Waiting for call analysis to be generated...")
                                        if attempt < max_retries - 1:
                                            await asyncio.sleep(2)
                                else:
                                    print(f"Failed to fetch call data. Status: {response.status}")
                                    break

        except Exception as e:
            print(f"Error in cleanup: {e}")
        finally:
            # Clear existing data
            self.message_history.clear()
            self.conversations.clear()
            self.metadata = None
            self.call_id = None

            # Close the OpenAI client
            if self.client:
                await self.client.close()
