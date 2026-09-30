# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import base64
import inspect
import json
import os
import urllib.error
import urllib.parse
import urllib.request
import uuid

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.manager import A2uiSchemaManager
from dotenv import load_dotenv

try:
    from .a2ui_utils import a2ui_callback
except (ImportError, ValueError):
    from app.a2ui_utils import a2ui_callback
from google import genai
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.models import Gemini
from google.adk.tools import ToolContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.cloud import storage
from google.genai import types

load_dotenv()

MODEL = "gemini-2.5-flash"
BUCKET_NAME = "stride-running-coach"


WORKOUT_CATALOG = [
    {
        "id": "w1",
        "title": "20-Min Lactate Threshold Tempo",
        "type": "tempo",
        "target_zone": 4,
        "duration_mins": 45,
        "description": "Builds stamina and pushes back your lactate threshold pace.",
        "structure": "10 min easy warm-up, 20 min continuous tempo at Zone 4 (comfortably hard), 15 min cool-down.",
    },
    {
        "id": "w2",
        "title": "800m Track VO2 Max Repeats",
        "type": "interval",
        "target_zone": 5,
        "duration_mins": 50,
        "description": "High-intensity intervals to boost aerobic capacity (VO2 max) and speed.",
        "structure": "15 min warm-up drills, 5 x 800m at 5K race pace with 400m easy jog recovery between sets, 10 min cool-down.",
    },
    {
        "id": "w3",
        "title": "Aerobic Base Long Run",
        "type": "long_run",
        "target_zone": 2,
        "duration_mins": 75,
        "description": "Essential endurance builder to develop aerobic efficiency and capillary density.",
        "structure": "Continuous running strictly in Zone 2 (conversational pace). Finish with 4 x 20-second strides.",
    },
    {
        "id": "w4",
        "title": "Easy Recovery & Flush Run",
        "type": "recovery",
        "target_zone": 1,
        "duration_mins": 30,
        "description": "Gentle low-impact shakeout to promote blood flow and active recovery between hard days.",
        "structure": "30 min very relaxed jogging in Zone 1-2. Keep effort light and cadence smooth.",
    },
    {
        "id": "w5",
        "title": "Short Hill Repeats for Power",
        "type": "hills",
        "target_zone": 4,
        "duration_mins": 40,
        "description": "Develops running economy, muscular power, and injury-resistant leg strength.",
        "structure": "15 min easy warm-up, 8 x 30-second uphill sprints at 90-95% effort with walk-down recovery, 10 min cool-down.",
    },
]


def search_workouts(
    workout_type: str = "",
    target_zone: int = 0,
    max_duration_mins: int = 0,
) -> list[dict]:
    """Search the running workout catalog by workout type, target heart rate zone, or duration.

    Args:
        workout_type: Filter by workout type ('tempo', 'interval', 'long_run', 'recovery', 'hills'). Leave empty to match all.
        target_zone: Filter by target heart rate training zone (1 to 5). Set to 0 to match all.
        max_duration_mins: Maximum workout duration in minutes. Set to 0 to match all.

    Returns:
        A list of matching workout dictionaries containing title, type, target_zone, duration_mins, description, and structure.
    """
    results = []
    query_type = workout_type.strip().lower()

    for workout in WORKOUT_CATALOG:
        if query_type and query_type not in workout["type"].lower():
            continue
        if target_zone > 0 and workout["target_zone"] != target_zone:
            continue
        if max_duration_mins > 0 and workout["duration_mins"] > max_duration_mins:
            continue
        results.append(workout)

    return results


def get_running_weather(city: str) -> dict:
    """Fetch real-time outdoor weather and running conditions for a city via Open-Meteo API.

    Args:
        city: Name of the city (e.g. 'Boulder', 'San Francisco', 'Chicago', 'Boston').

    Returns:
        A dictionary containing temperature_f, feels_like_f, humidity_pct, wind_speed_mph, precipitation_in, and coaching tips.
    """
    try:
        encoded_city = urllib.parse.quote(city.strip())
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={encoded_city}&count=1&language=en&format=json"
        req = urllib.request.Request(geo_url, headers={"User-Agent": "StrideCoach/1.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            geo_data = json.loads(response.read().decode("utf-8"))

        results = geo_data.get("results")
        if not results:
            return {"error": f"City '{city}' not found."}

        location = results[0]
        lat = location["latitude"]
        lon = location["longitude"]
        matched_city = location.get("name", city)
        country = location.get("country", "")

        wx_url = (
            f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
            "&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,wind_speed_10m"
            "&temperature_unit=fahrenheit&wind_speed_unit=mph"
        )
        wx_req = urllib.request.Request(wx_url, headers={"User-Agent": "StrideCoach/1.0"})
        with urllib.request.urlopen(wx_req, timeout=5) as wx_response:
            wx_data = json.loads(wx_response.read().decode("utf-8"))

        current = wx_data.get("current", {})
        temp = current.get("temperature_2m")
        feels_like = current.get("apparent_temperature")
        humidity = current.get("relative_humidity_2m")
        wind = current.get("wind_speed_10m")
        precip = current.get("precipitation")

        tips = []
        if feels_like and feels_like > 80:
            tips.append("High heat: slow your target pace by 15-30s/mile and carry extra hydration.")
        elif feels_like and feels_like < 35:
            tips.append("Cold conditions: dress in layers, wear gloves, and extend your warm-up.")
        if humidity and humidity > 80:
            tips.append("High humidity: sweat evaporation will be impaired; monitor effort rather than pace.")
        if wind and wind > 15:
            tips.append(f"Windy ({wind} mph): start into the headwind so you have a tailwind on your return.")

        return {
            "city": f"{matched_city}, {country}".strip(", "),
            "temperature_f": temp,
            "feels_like_f": feels_like,
            "humidity_pct": humidity,
            "wind_speed_mph": wind,
            "precipitation_in": precip,
            "coaching_tip": " ".join(tips) or "Great weather conditions for running!",
        }
    except Exception as e:
        return {"error": f"Failed to fetch weather data: {str(e)}"}


def geocode_address(address: str) -> dict:
    """Turn an address or location name into geographic coordinates using the Google Maps Geocoding API.

    Args:
        address: The address or place name to geocode (e.g. '1600 Amphitheatre Pkwy, Mountain View, CA').

    Returns:
        A dictionary containing the key fields: name, address, and location (latitude and longitude).
    """
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "")
    if not api_key:
        return {"error": "GOOGLE_MAPS_API_KEY environment variable is not set."}

    encoded_address = urllib.parse.quote(address.strip())
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={encoded_address}&key={api_key}"
    req = urllib.request.Request(
        url,
        headers={
            "X-Goog-Api-Key": api_key,
            "User-Agent": "StrideCoach/1.0",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))

        status = data.get("status")
        if status != "OK":
            err_msg = data.get("error_message", f"Geocoding status: {status}")
            return {"error": err_msg}

        results = data.get("results", [])
        if not results:
            return {"error": f"No geocoding results found for address: {address}"}

        top_result = results[0]
        geom_loc = top_result.get("geometry", {}).get("location", {})
        return {
            "name": address,
            "address": top_result.get("formatted_address", ""),
            "location": {
                "latitude": geom_loc.get("lat"),
                "longitude": geom_loc.get("lng"),
            },
        }
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        return {"error": f"Geocoding API error (HTTP {e.code}): {err_body}"}
    except Exception as e:
        return {"error": f"Geocoding request failed: {str(e)}"}


def find_nearby_places(
    latitude: float,
    longitude: float,
    place_type: str = "park",
    radius_meters: float = 5000.0,
) -> list[dict]:
    """Find nearby places of a given type using the Google Maps Places API (New).

    Args:
        latitude: Latitude of search center.
        longitude: Longitude of search center.
        place_type: Type of place to find (e.g. 'park', 'athletic_field', 'fitness_center', 'gym', 'sporting_goods_store').
        radius_meters: Search radius in meters (default is 5000).

    Returns:
        A list of dictionaries with key fields: name, address, and location for matching places.
    """
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "")
    if not api_key:
        return [{"error": "GOOGLE_MAPS_API_KEY environment variable is not set."}]

    url = "https://places.googleapis.com/v1/places:searchNearby"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location",
        "User-Agent": "StrideCoach/1.0",
    }
    payload = {
        "includedTypes": [place_type],
        "maxResultCount": 10,
        "locationRestriction": {
            "circle": {
                "center": {
                    "latitude": latitude,
                    "longitude": longitude,
                },
                "radius": radius_meters,
            }
        },
    }

    try:
        req_data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))

        places = data.get("places", [])
        output = []
        for p in places:
            display_name = p.get("displayName", {}).get("text", "")
            formatted_address = p.get("formattedAddress", "")
            loc = p.get("location", {})
            output.append({
                "name": display_name,
                "address": formatted_address,
                "location": {
                    "latitude": loc.get("latitude"),
                    "longitude": loc.get("longitude"),
                },
            })
        return output
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        return [{"error": f"Places API error (HTTP {e.code}): {err_body}"}]
    except Exception as e:
        return [{"error": f"Places request failed: {str(e)}"}]


async def generate_race_badge(prompt: str, tool_context: ToolContext) -> dict:
    """Generates a custom race badge, finisher medal, or motivational milestone award for a runner.

    Uses gemini-3.1-flash-lite-image in the global region.
    Saves the generated image as a session artifact and uploads it to the public Cloud Storage bucket.

    Args:
        prompt: Visual description of the award or badge (e.g. 'Gold finisher medal for a half marathon with mountain background').
        tool_context: ADK ToolContext for managing session artifacts.

    Returns:
        A dictionary containing the image's public_url, filename, and prompt.
    """
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "qwiklabs-gcp-04-f810749db8aa")
    client = genai.Client(vertexai=True, project=project, location="global")

    response = client.models.generate_content(
        model="gemini-3.1-flash-lite-image",
        contents=[prompt],
    )

    image_bytes = None
    mime_type = "image/jpeg"

    for candidate in response.candidates:
        for part in candidate.content.parts:
            if part.inline_data and part.inline_data.data:
                image_bytes = part.inline_data.data
                mime_type = part.inline_data.mime_type or "image/jpeg"
                break
        if image_bytes:
            break

    if not image_bytes:
        return {"error": "No image was generated by the model."}

    filename = f"badge_{uuid.uuid4().hex[:8]}.jpg"

    # 1. Save artifact with tool_context.save_artifact so it appears in Playground Artifacts panel
    if tool_context and hasattr(tool_context, "save_artifact"):
        part = types.Part(inline_data=types.Blob(mime_type=mime_type, data=image_bytes))
        save_res = tool_context.save_artifact(filename, part)
        if inspect.isawaitable(save_res):
            await save_res

    # 2. Upload same bytes to public Cloud Storage bucket directly without saving local file
    storage_client = storage.Client()
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(filename)
    blob.upload_from_string(image_bytes, content_type=mime_type)

    public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{filename}"
    return {
        "status": "success",
        "filename": filename,
        "public_url": public_url,
        "prompt": prompt,
    }


async def generate_running_video(prompt: str, tool_context: ToolContext = None) -> dict:
    """Generates a short video for an item in the running/endurance domain using Google's Omni model (gemini-omni-flash-preview) in the global region.

    Creates video clips such as running form demonstrations, finish-line celebrations,
    track interval workouts, or scenic marathon routes. Saves the video as a session
    artifact and uploads it to Cloud Storage.

    Args:
        prompt: Visual description of the running video to generate (e.g. 'A runner crossing the finish line in slow motion, celebratory cheering crowd').
        tool_context: ADK ToolContext for managing session artifacts.

    Returns:
        A dictionary containing status, filename, public_url, and prompt.
    """
    project = "qwiklabs-gcp-04-f810749db8aa"
    bucket_name = "stride-running-coach"

    client = genai.Client(vertexai=True, project=project, location="global")

    interaction = client.interactions.create(
        model="gemini-omni-flash-preview",
        input=prompt,
    )

    video_bytes = None
    mime_type = "video/mp4"

    # Extract video bytes from interaction output
    if hasattr(interaction, "output_video") and interaction.output_video:
        data = getattr(interaction.output_video, "data", None)
        if data:
            video_bytes = base64.b64decode(data) if isinstance(data, str) else data
            mime_type = getattr(interaction.output_video, "mime_type", mime_type) or mime_type

    if not video_bytes and hasattr(interaction, "output") and interaction.output:
        for content in interaction.output:
            parts = getattr(content, "parts", []) or []
            for part in parts:
                video = getattr(part, "video", None)
                if video:
                    b64 = getattr(video, "bytes_base64_encoded", None) or getattr(video, "data", None)
                    if b64:
                        video_bytes = base64.b64decode(b64) if isinstance(b64, str) else b64
                        mime_type = getattr(video, "mime_type", mime_type) or mime_type
                        break
            if video_bytes:
                break

    if not video_bytes and hasattr(interaction, "steps") and interaction.steps:
        for step in interaction.steps:
            content = getattr(step, "content", []) or []
            for item in content:
                if getattr(item, "type", None) == "video" or hasattr(item, "data"):
                    data = getattr(item, "data", None) or getattr(item, "bytes_base64_encoded", None)
                    if data:
                        video_bytes = base64.b64decode(data) if isinstance(data, str) else data
                        mime_type = getattr(item, "mime_type", mime_type) or mime_type
                        break
            if video_bytes:
                break

    if not video_bytes:
        return {"error": "No video was generated by the model."}

    filename = f"video_{uuid.uuid4().hex[:8]}.mp4"

    # 1. Save artifact with tool_context.save_artifact so it shows up in Playground's Artifacts panel
    if tool_context and hasattr(tool_context, "save_artifact"):
        part = types.Part(inline_data=types.Blob(mime_type=mime_type, data=video_bytes))
        save_res = tool_context.save_artifact(filename, part)
        if inspect.isawaitable(save_res):
            await save_res

    # 2. Upload same bytes directly to public Cloud Storage bucket without writing local file
    storage_client = storage.Client(project=project)
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(filename)
    blob.upload_from_string(video_bytes, content_type=mime_type)

    public_url = f"https://storage.googleapis.com/{bucket_name}/{filename}"
    return {
        "status": "success",
        "filename": filename,
        "public_url": public_url,
        "prompt": prompt,
    }


def _get_code_executor() -> AgentEngineSandboxCodeExecutor:
    metadata_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "deployment_metadata.json"
    )
    sandbox_name = os.environ.get("AGENT_ENGINE_SANDBOX_RESOURCE_NAME")
    agent_engine_id = None
    if os.path.exists(metadata_path):
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
                sandbox_name = sandbox_name or meta.get("sandbox_resource_name")
                agent_engine_id = meta.get("remote_agent_runtime_id")
        except Exception:
            pass

    if not sandbox_name:
        sandbox_name = (
            "projects/134045787607/locations/us-central1/reasoningEngines/1484964670346362880/sandboxEnvironments/424381251751772160"
        )

    return AgentEngineSandboxCodeExecutor(
        sandbox_resource_name=sandbox_name,
        agent_engine_resource_name=agent_engine_id,
    )


# WRITE: after each turn, send the session to Memory Bank for extraction.
async def generate_memories_callback(callback_context: CallbackContext):
    try:
        await callback_context.add_session_to_memory()
    except Exception as e:
        # Gracefully continue if memory service is not configured (e.g. unit tests)
        pass
    return None


schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

a2ui_instruction = schema_manager.generate_system_prompt(
    role_description=(
        "You are Stride, an expert endurance and running coach. You remember the user's stated "
        "preferences, running history, race goals, and personal details from previous conversations "
        "and use them to personalize your coaching. Always remember and strictly adhere to all user "
        "allergies (food, medical, or environmental) and dietary restrictions across sessions, "
        "especially when suggesting nutrition, hydration, or fueling strategies. You help runners prepare for races, "
        "structure their training, and dial in their pacing. Use search_workouts to find specific workouts from the catalog, "
        "get_running_weather to check real-time outdoor weather conditions, geocode_address to convert an address to coordinates, "
        "find_nearby_places to discover running locations, generate_race_badge to create custom race badges, finisher medals, "
        "and milestone awards, and generate_running_video to create short running/workout visualization videos. You can also write and execute Python code in a safe sandbox to perform running calculations, "
        "such as pace splits, VO2 max estimations, heart rate zones, and race finish time projections."
    ),
    workflow_description="Analyze the request and return structured UI when appropriate.",
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        "{\"Image\": {\"url\": {\"literalString\": \"https://...\"}}}. Never point an "
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."
    ),
    include_schema=True,
    include_examples=True,
)


root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model=MODEL,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=a2ui_instruction,
    code_executor=_get_code_executor(),
    tools=[
        PreloadMemoryTool(),
        search_workouts,
        get_running_weather,
        geocode_address,
        find_nearby_places,
        generate_race_badge,
        generate_running_video,
    ],
    after_model_callback=a2ui_callback,
    after_agent_callback=generate_memories_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)
