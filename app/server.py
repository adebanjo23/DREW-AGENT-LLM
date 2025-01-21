import json
import os
import asyncio
import time

from dotenv import load_dotenv
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from concurrent.futures import TimeoutError as ConnectionTimeoutError
from retell import Retell
from custom_types import (
    ConfigResponse,
    ResponseRequiredRequest, ResponseResponse,
)
from llm import LlmClient  # or use .llm_with_func_calling

load_dotenv(override=True)
app = FastAPI()
retell = Retell(api_key=os.environ["RETELL_API_KEY"])


# Handle webhook from Retell server. This is used to receive events from Retell server.
# Including call_started, call_ended, call_analyzed
@app.post("/webhook")
async def handle_webhook(request: Request):
    try:
        post_data = await request.json()
        valid_signature = retell.verify(
            json.dumps(post_data, separators=(",", ":"), ensure_ascii=False),
            api_key=str(os.environ["RETELL_API_KEY"]),
            signature=str(request.headers.get("X-Retell-Signature")),
        )
        if not valid_signature:
            print(
                "Received Unauthorized",
                post_data["event"],
                post_data["data"]["call_id"],
            )
            return JSONResponse(status_code=401, content={"message": "Unauthorized"})
        if post_data["event"] == "call_started":
            print("Call started event", post_data["data"]["call_id"])
        elif post_data["event"] == "call_ended":
            print("Call ended event", post_data["data"]["call_id"])
        elif post_data["event"] == "call_analyzed":
            print("Call analyzed event", post_data["data"]["call_id"])
        else:
            print("Unknown event", post_data["event"])
        return JSONResponse(status_code=200, content={"received": True})
    except Exception as err:
        print(f"Error in webhook: {err}")
        return JSONResponse(
            status_code=500, content={"message": "Internal Server Error"}
        )


@app.websocket("/llm-websocket/{call_id}")
async def websocket_handler(websocket: WebSocket, call_id: str):
    """
    Handle WebSocket connections with proper connection maintenance.
    """
    active_tasks = set()
    llm_client = None
    heartbeat_task = None

    async def send_heartbeat():
        """Send periodic heartbeats to keep the connection alive."""
        try:
            while True:
                await websocket.send_json({
                    "response_type": "ping_pong",
                    "timestamp": int(time.time() * 1000)
                })
                await asyncio.sleep(20)  # Send heartbeat every 20 seconds
        except Exception as e:
            print(f"Heartbeat error: {e}")

    async def handle_response_required(request_json):
        """Handle response required and reminder required interactions."""
        nonlocal response_id
        try:
            response_id = request_json["response_id"]
            request = ResponseRequiredRequest(
                interaction_type=request_json["interaction_type"],
                response_id=response_id,
                transcript=request_json["transcript"],
            )

            print(f"Processing {request_json['interaction_type']} for response_id={response_id}")

            # Create a task for the LLM response
            async for event in llm_client.draft_response(request):
                if request.response_id < response_id:
                    print(f"Abandoning response {request.response_id} for newer {response_id}")
                    break
                await websocket.send_json(event.__dict__)

        except WebSocketDisconnect:
            print("WebSocket disconnected during response")
            raise
        except Exception as e:
            print(f"Error in response generation: {e}")
            try:
                error_response = ResponseResponse(
                    response_id=request.response_id,
                    content="I encountered an error. Let me try again.",
                    content_complete=True,
                    end_call=False
                )
                await websocket.send_json(error_response.__dict__)
            except Exception as send_error:
                print(f"Error sending error response: {send_error}")

    try:
        await websocket.accept()
        llm_client = LlmClient()
        call_details_received = False
        response_id = 0

        # Start heartbeat task
        heartbeat_task = asyncio.create_task(send_heartbeat())

        # Send initial configuration
        config = ConfigResponse(
            response_type="config",
            config={
                "auto_reconnect": True,
                "call_details": True,
            },
            response_id=1,
        )
        await websocket.send_json(config.__dict__)

        async def handle_message(data):
            """Process incoming WebSocket messages."""
            nonlocal call_details_received

            try:
                if data["interaction_type"] == "call_details":
                    print(f"Call details received for {call_id}:",
                          json.dumps(data, indent=2))
                    llm_client.set_metadata(data)
                    call_details_received = True

                    first_event = await llm_client.draft_begin_message()
                    await websocket.send_json(first_event.__dict__)
                    return

                elif data["interaction_type"] == "ping_pong":
                    await websocket.send_json({
                        "response_type": "ping_pong",
                        "timestamp": data["timestamp"],
                    })
                    return

                elif data["interaction_type"] == "update_only":
                    return

                elif data["interaction_type"] in ["response_required", "reminder_required"]:
                    task = asyncio.create_task(handle_response_required(data))
                    active_tasks.add(task)
                    task.add_done_callback(active_tasks.discard)
                    await task

            except Exception as e:
                print(f"Error handling message: {e}")
                try:
                    error_response = ResponseResponse(
                        response_id=data.get("response_id", 0),
                        content="I encountered an error. Please try again.",
                        content_complete=True,
                        end_call=False
                    )
                    await websocket.send_json(error_response.__dict__)
                except Exception as send_error:
                    print(f"Error sending error response: {send_error}")

        # Main message processing loop with connection monitoring
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_json(), timeout=30)
                asyncio.create_task(handle_message(data))
            except asyncio.TimeoutError:
                # Check if connection is still alive
                try:
                    await websocket.send_json({
                        "response_type": "ping_pong",
                        "timestamp": int(time.time() * 1000)
                    })
                except Exception:
                    print("Connection dead after timeout")
                    break
            except WebSocketDisconnect:
                print(f"WebSocket disconnected for {call_id}")
                break

    except WebSocketDisconnect:
        print(f"WebSocket disconnected for call {call_id}")
    except Exception as e:
        print(f"Unexpected error in WebSocket handler: {e}")
    finally:
        # Cleanup
        if heartbeat_task:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass

        if active_tasks:
            print(f"Canceling {len(active_tasks)} active tasks")
            for task in active_tasks:
                task.cancel()
            await asyncio.gather(*active_tasks, return_exceptions=True)

        if llm_client:
            await llm_client.cleanup()

        try:
            await websocket.close()
        except Exception as e:
            print(f"Error during WebSocket cleanup: {e}")

        print(f"WebSocket connection closed for call {call_id}")