from dotenv import load_dotenv
import os

load_dotenv()


class Settings:
    def __init__(self):
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

        self.tools = [
            {
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
                                "type": "string",
                                "description": "Type of place to search for (e.g., restaurants, parks, schools)"
                            }
                        },
                        "required": ["location", "query_type"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "BookingRequest",
                    "description": """Agent requests to book a specific appointment.
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
                        "required": ["lead_name", "start_time", "description"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "CallRequest",
                    "description": """Initiate a call with a contact.
                                        Use ONLY when:
                                        - The agent requests to call someone.
                                        - You need to capture details like specific discussion points and the scheduled call time.

                                        **Note:** The call time must be either now (today) or scheduled for the next day.

                                        The assistant should ask clarifying questions if needed.
                                    """,
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "contact_name": {
                                "type": "string",
                                "description": "Name of the contact to call"
                            },
                            "discussion_points": {
                                "type": "string",
                                "description": "Any specific discussion points you want to address during the call"
                            },
                            "call_time": {
                                "type": "string",
                                "description": "Scheduled call time in ISO format (YYYY-MM-DDTHH:MM:SS). It must be either now or the next day."
                            }
                        },
                        "required": ["contact_name", "call_time", "discussion_points"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "MessageRequest",
                    "description": """Send a message to a lead.
                                        Use ONLY when:
                                        - The agent instructs to send a message to a lead
                                        - The details specify whether the message should be sent as an SMS or Email
                                        - The agent provides the lead's name and the content of the message

                                        The assistant should verify:
                                        - The type of message (SMS or Email)
                                        - The message details/content
                                        - The name of the recipient lead
                                    """,
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "lead_name": {
                                "type": "string",
                                "description": "The name of the lead to send the message to"
                            },
                            "message_type": {
                                "type": "string",
                                "description": "Type of message to send. Allowed values: 'SMS' or 'Email'"
                            },
                            "message_content": {
                                "type": "string",
                                "description": "The content of the message that should be sent"
                            }
                        },
                        "required": ["lead_name", "message_type", "message_content"]
                    }
                }
            }
        ]

        self.backend_url = "http://localhost:5000"


settings = Settings()
