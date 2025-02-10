import asyncio
import random
import aiohttp
import json
import os
from openai import AsyncOpenAI
from dotenv import load_dotenv
from app.models.models import PlacesSearch, BookingRequest, CallRequest, MessageRequest, PropertySearch
from app.prompts.agent_prompt import agent_prompt
from typing import List, Dict, Optional
from datetime import datetime
from app.utils.custom_types import (
    ResponseRequiredRequest,
    ResponseResponse,
    Utterance,
)
from app.core.config import settings

load_dotenv()


class LlmClient:

    def __init__(self):
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.call_id = None
        self.websocket_closed = False
        self.metadata: Optional[Dict] = None
        self.message_history: List[Dict[str, str]] = []
        self.conversations: Dict[str, List] = {}
        self.communications_data = {}
        self.is_first_interaction = True

    async def _init_communications(self, user_id: int):
        """Initialize communications data for the user."""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{settings.backend_url}/get_user_communications/{user_id}"
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
                url = f"{settings.backend_url}/get_user_communications/{user_id}"
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

                url = f"{settings.backend_url}/save_communication"
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
            bot_name = self.metadata.get('bot_name', 'Drew')

            if self.metadata.get('first_interaction') == "true":
                custom_greeting = [
                    f"{time_greeting}, {user_name}! Welcome aboard! I'm {bot_name}, your personal assistant. I help manage leads, schedule appointments, track key metrics, and keep your workflow seamless. Let's get started!",

                    f"Hey {user_name}, great to have you here! I'm {bot_name}, your AI-powered assistant. I'll help you stay organized by managing leads, scheduling, and tracking key performance metrics. Let's make things efficient!",

                    f"{time_greeting}, {user_name}! I'm {bot_name}, your virtual assistant. I handle lead management, scheduling, and performance tracking so you can focus on closing more deals.",

                    f"Welcome, {user_name}! I'm {bot_name}, designed to help you streamline your workflow by managing leads, scheduling appointments, and keeping track of your business performance.",

                    f"Nice to meet you, {user_name}! I'm {bot_name}, your smart assistant. I help you stay on top of leads, appointments, and key insights, making your workflow smoother and more efficient.",

                    f"{time_greeting}, {user_name}! Congrats on getting started! I'm {bot_name}, your AI assistant, here to help with lead tracking, scheduling, and performance insights. Let's get things rolling!",

                    f"Hey {user_name}! I'm {bot_name}, your personal assistant! I'll handle scheduling, lead tracking, and key insights so you can focus on growing your business. Let's get started!",

                    f"{time_greeting}, {user_name}! I'm {bot_name}, your AI-powered real estate assistant. I'll keep your workflow organized, track your performance, and help you stay productive. Let's go!"
                ]
            else:
                custom_greeting = [
                    # Casual & Friendly
                    f"{time_greeting}, {user_name}! Hope you're having a great day!",
                    f"Hey {user_name}, how's your day going?",
                    f"Hi {user_name}, How's your day going?",
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

            greeting = random.choice(custom_greeting) if user_name else random.choice(settings.opening_lines)

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
            result = await BookingRequest(**args).execute(settings.backend_url, self.metadata.get('user_id'))
        elif tool_name == "CallRequest":
            result = await CallRequest(**args).execute(settings.backend_url, self.metadata.get('user_id'))
        elif tool_name == "MessageRequest":
            result = await MessageRequest(**args).execute(settings.backend_url, self.metadata.get('user_id'))
        elif tool_name == "PropertySearch":  # Updated branch for PropertySearch
            result = await PropertySearch(**args).execute()
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

        if self.metadata and self.communications_data:
            metrics = self.communications_data.get('metrics', {})

            # Extract key metrics
            call_metrics = metrics.get('call_metrics', {})
            lead_metrics = metrics.get('lead_metrics', {})
            appointment_data = metrics.get('appointments', {})
            actionable_metrics = metrics.get('actionable_metrics', {})

            # Format lead statistics
            total_leads = lead_metrics.get('total_leads', 0)
            leads_by_status = lead_metrics.get('leads_by_status', {})

            # Format lead samples from latest interactions
            lead_samples = []
            latest_interactions = lead_metrics.get('latest_interactions', [])
            for interaction in latest_interactions:
                lead_samples.append(
                    f"- {interaction.get('lead_name', 'Unknown')} "
                    f"({interaction.get('type', 'Unknown interaction')}, "
                    f"{interaction.get('status', 'Unknown status')}): "
                    f"{interaction.get('details', {}).get('message', 'No details available')}"
                )

            # Format most active lead
            most_active_lead = lead_metrics.get('most_active_lead', {})
            active_lead_info = ""
            if most_active_lead:
                active_lead_info = (
                    f"\nMost Active Lead: {most_active_lead.get('name', 'Unknown')} "
                    f"({most_active_lead.get('interaction_count', 0)} interactions)"
                )

            # Format recent appointments
            recent_appointments = []
            for apt in appointment_data.get('recent_appointments', []):
                apt_time = datetime.fromisoformat(apt.get('appointment_time', '')).strftime("%B %d at %I:%M %p")
                recent_appointments.append(
                    f"- {apt_time}: {apt.get('status', 'Unknown status')} "
                    f"({apt.get('participant_details', {}).get('name', 'Unknown participant')})"
                )

            # Build comprehensive context
            user_context = f"""
    Recent Activity Overview:
    Call Statistics:
    - Total Calls: {call_metrics.get('total_calls', 0)}
    - Successful Calls: {call_metrics.get('calls_by_status', {}).get('successful', 0)}
    - Missed Calls: {call_metrics.get('calls_by_status', {}).get('missed', 0)}
    - Average Call Duration: {call_metrics.get('average_duration', 0)} seconds

    Lead Overview:
    Total Leads: {total_leads}
    Status Breakdown:
    - New: {leads_by_status.get('new', 0)}
    - Contacted: {leads_by_status.get('contacted', 0)}
    - Qualified: {leads_by_status.get('qualified', 0)}
    - Closed: {leads_by_status.get('closed', 0)}
    {active_lead_info}

    Recent Interactions (last 5):
    {chr(10).join(lead_samples)}

    Recent Appointments:
    {chr(10).join(recent_appointments)}
    Upcoming Appointments: {appointment_data.get('upcoming_count', 0)}

    Actionable Insights:
    - New leads in last 30 days: {actionable_metrics.get('new_leads_last_30_days', 0)}
    - Successful calls rate: {actionable_metrics.get('successful_calls_rate', 0)}%
    - Average interactions per lead: {actionable_metrics.get('average_interactions_per_lead', 0)}
    - Leads needing follow-up: {actionable_metrics.get('leads_needing_followup', 0)}
    """

            personalized_context = f"""
    Your are {self.metadata.get('bot_name', 'Drew')}
    You're speaking with {self.metadata.get('user_name', 'an agent')}.
    Role: {self.metadata.get('role', 'Agent')}
    Additional Information: {self.metadata.get('additional_info', '')}

    Current Status:
    {user_context}

    Instructions:
    - Use this context to personalize your responses and make relevant suggestions
    - Reference specific appointments and upcoming meetings when relevant
    - Prioritize leads needing follow-up in your recommendations
    - Consider the call success rate when making suggestions about communication methods
    - Use the lead status distribution to inform your strategy recommendations
    - Pay attention to the most active lead and recent interactions
    - Remember that the agent has access to full historical data through the dashboard
    """

        current_datetime = self.get_formatted_datetime()
        system_prompt = f"{agent_prompt}\n\nCurrent Date and Time: {current_datetime}\n\nPersonalized Context:\n{personalized_context}"

        messages = [{"role": "system", "content": system_prompt}]
        transcript_messages = self.convert_transcript_to_messages(request.transcript)
        messages.extend(transcript_messages)

        if request.interaction_type == "reminder_required":
            messages.append({
                "role": "user",
                "content": "(Provide tailored recommendations based on the agent's recent activity and pending follow-ups:)"
            })
        return messages

    async def draft_response(self, request: ResponseRequiredRequest):
        try:
            messages = await self.prepare_prompt(request)

            # Initial API call to get response and potential tool calls
            response = await self.client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                tools=settings.tools,
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

            if current_tool_calls:
                yield ResponseResponse(
                    response_id=request.response_id,
                    content=random.choice(settings.wait_variants),
                    content_complete=False,
                    end_call=False,
                )

                # Execute all tool calls (ensuring each tool call gets a response message)
                tool_results = []
                for tool_call in current_tool_calls:
                    try:
                        args = json.loads(tool_call["function"]["arguments"])
                        result = await self._execute_tool(tool_call["function"]["name"], args)
                    except Exception as e:
                        print(f"Tool execution error: {e}")
                        # Instead of only yielding a response, create a tool message with the error
                        result = {"error": f"Error executing tool: {str(e)}"}
                    # Append a tool message for every tool_call
                    tool_results.append({
                        "tool_call_id": tool_call["id"],
                        "role": "tool",
                        "name": tool_call["function"]["name"],
                        "content": json.dumps(result)
                    })

                # Append the assistant message that includes the tool_calls field
                messages.append({
                    "role": "assistant",
                    "content": current_content,
                    "tool_calls": current_tool_calls
                })
                # Append the tool response messages for each tool call
                for result in tool_results:
                    messages.append(result)

                # Get the final response that includes the tool results
                final_response = await self.client.chat.completions.create(
                    model="gpt-4o", messages=messages, stream=True
                )

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

                                        url = f"{settings.backend_url}/save_communication"
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
