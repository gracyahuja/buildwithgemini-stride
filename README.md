# 🏃 Stride — Endurance & Running Coach

> An intelligent, conversational endurance and running coach built with Google's Agent Development Kit (ADK), Vertex AI Agent Platform, and Gemini.

[![Built with ADK](https://img.shields.io/badge/Built%20with-Google%20ADK-4285F4?logo=google&logoColor=white)](https://google.github.io/adk-docs/)
[![Model](https://img.shields.io/badge/Model-Gemini%202.5%20Flash-34A853?logo=google-gemini&logoColor=white)](https://cloud.google.com/vertex-ai)
[![Protocol](https://img.shields.io/badge/Protocol-A2A%201.0-EA4335)](https://github.com/google/agents-cli)
[![UI](https://img.shields.io/badge/UI-A2UI%200.8-FBBC05)](https://adk.dev/integrations/a2ui/)

---

## 📖 Overview

**Stride** is an agent-first running and endurance coach designed to guide athletes through every phase of training. Whether preparing for a first 5K or chasing a Boston Marathon qualifying standard, Stride personalizes workouts, calculates precise VDOT pacing splits, checks outdoor running weather, discovers scenic routes, and celebrates achievements with custom visual awards and race-day clips.

Stride runs on the **Vertex AI Agent Platform**, uses **Vertex AI Memory Bank** for cross-session continuity, executes pacing algorithms inside an isolated **Agent Engine Sandbox**, and returns rich interactive cards using **A2UI**.

---

## ⚡ Real Capabilities & Implemented Tools

All capabilities listed below are fully implemented in code and wired into the agent:

### 1. 🧠 Long-Term Athlete Memory
* **Powered by:** Vertex AI Memory Bank (`VertexAiMemoryBankService`, `PreloadMemoryTool`, and `generate_memories_callback`).
* **What it does:** Automatically persists and recalls athlete details across conversations — including target race distance, goal finish times, easy pace, weekly volume, injury history, and critical dietary or environmental allergies (e.g., ensuring fueling recommendations respect food allergies).

### 2. 🏃 Workout Catalog Search (`search_workouts`)
* **What it does:** Filters structured running sessions from a catalog of workouts (lactate threshold tempo runs, 800m track VO2 max repeats, Zone 2 aerobic base long runs, active recovery flush runs, and uphill power sprints).
* **Parameters:** Filter by workout type (`tempo`, `interval`, `long_run`, `recovery`, `hills`), target heart rate zone (Zone 1 to 5), and maximum duration.

### 3. 🌦️ Real-Time Running Weather & Advice (`get_running_weather`)
* **What it does:** Queries live atmospheric conditions for any city via the Open-Meteo API. Returns temperature, feels-like temperature, relative humidity, wind speed, precipitation, and running-specific coaching recommendations (e.g., pace adjustments for heat/humidity, hydration alerts, headwind strategies, cold-weather layering).

### 4. 📍 Route & Track Discovery (`geocode_address` & `find_nearby_places`)
* **Powered by:** Google Maps Platform (Geocoding API and Places API New).
* **What it does:** Converts runner locations into coordinates and discovers nearby parks, running trails, athletic tracks, fitness centers, and running stores within a search radius.

### 5. 🏅 Custom Milestone Badges & Medals (`generate_race_badge`)
* **Powered by:** Google's `gemini-3.1-flash-lite-image` model in the `global` region + Google Cloud Storage.
* **What it does:** Generates custom finisher medals, milestone badges, and race celebration artwork. The generated image bytes are saved directly as session artifacts (visible in the ADK Playground) and uploaded to a public Cloud Storage bucket (`gs://stride-running-coach/`), returning a permanent public HTTPS URL.

### 6. 🎬 Workout & Celebration Video Generation (`generate_running_video`)
* **Powered by:** Google's Omni model `gemini-omni-flash-preview` in the `global` region + Google Cloud Storage.
* **What it does:** Generates short video visualizations for running form demonstrations, finish-line celebrations, track workouts, or scenic courses. Saves video bytes to session artifacts and uploads directly to Cloud Storage in-memory.

### 7. 🧮 Pacing Math Sandbox (`AgentEngineSandboxCodeExecutor`)
* **Powered by:** Agent Engine Sandbox Code Execution.
* **What it does:** Safely runs generated Python code in an isolated environment to perform complex endurance running calculations:
  * Jack Daniels VDOT pacing tables and training paces (Easy, Marathon, Threshold, Interval, Repetition).
  * Race split projections (even vs. negative splits).
  * Heart rate zone calculations (Karvonen and % max HR formulas).
  * Weekly mileage progression and ramp rates.

### 8. 🪟 Agent-to-User Interface (A2UI)
* **Powered by:** `A2uiSchemaManager` (v0.8) and `a2ui_callback`.
* **What it does:** Emits structured A2UI JSON components (`Card`, `Column`, `Row`, `Text`, `Image`) instead of plain text, rendering formatted training plans and visual awards natively in the dev UI and web frontend.

### 9. 💬 Web Chat Frontend (FastAPI & A2A)
* **What it does:** A modern running-themed web interface built with FastAPI that communicates directly with the deployed agent over the Agent-to-Agent (A2A) protocol. Features custom dialogue styling, runner avatars, interactive prompt suggestions, and an embedded A2UI card renderer.

---

## ☁️ Google Cloud Services & Architecture

| Component | Service | Role in Stride |
|---|---|---|
| **Agent Reasoning** | Vertex AI (`gemini-2.5-flash`) | Core agent reasoning loop and orchestration |
| **Long-Term Memory** | Vertex AI Memory Bank | Cross-conversation memory extraction and preload |
| **Media Generation** | Vertex AI GenAI (`gemini-3.1-flash-lite-image`, `gemini-omni-flash-preview`) | Generates custom finisher badges and running videos |
| **Asset Storage** | Google Cloud Storage | Public bucket hosting generated badges and video assets |
| **Code Execution** | Agent Engine Sandbox | Safe Python execution for VDOT formulas and pace splits |
| **Agent Deployment** | Vertex AI Agent Platform (Agent Runtime) | Serverless A2A-compliant agent hosting |
| **Frontend Hosting** | Google Cloud Run | Containerized FastAPI proxy and chat interface |
| **Maps & Location** | Google Maps Platform | Geocoding and Places API for trail & track discovery |

---

## 📋 Roadmap / Planned (Not Yet Implemented)

The following features were outlined during initial brainstorming but are **not yet implemented** in the current code:

* ⏳ **Firestore Persistent Database:** Persistent database storage for athlete workout logs and race registration history (currently uses structured in-memory catalogs).
* ⏳ **Shoe & Gear Mileage Tracker:** Database-backed tracking of running shoe wear and replacement alerts based on accumulated mileage.
* ⏳ **Wearable API Sync:** Direct integration with Garmin Connect, Strava, or Apple Health for automatic activity ingestion.

---

## 🛠️ Project Structure

```
BuildWithGemini/
├── stride/                           # Core ADK Agent Project
│   ├── app/
│   │   ├── agent.py                  # Agent definition, tools, and A2UI instruction
│   │   ├── a2ui_utils.py             # A2UI response formatting callback
│   │   ├── fast_api_app.py           # Local FastAPI serving wrapper
│   │   └── app_utils/
│   │       ├── services.py           # Shared Session, Memory Bank, and Artifact services
│   │       ├── a2a.py                # A2A protocol handler
│   │       └── reasoning_engine_adapter.py
│   ├── tests/                        # Integration and unit test suite
│   ├── agents-cli-manifest.yaml      # Agent runtime deployment manifest
│   └── pyproject.toml                # Agent dependencies and tool configs
│
├── frontend/                         # Web Chat UI & FastAPI Proxy
│   ├── main.py                       # FastAPI proxy talking A2A to Agent Engine
│   ├── Dockerfile                    # Cloud Run container definition
│   ├── requirements.txt              # Frontend dependencies
│   └── static/
│       └── index.html                # Branded Stride UI with A2UI renderer
│
└── project_brief.md                  # Initial project design brief
```

---

## 🚀 Local Setup & Run Guide

### 1. Prerequisites

* Python 3.11+
* [Google Cloud SDK (`gcloud`)](https://cloud.google.com/sdk/docs/install)
* [uv](https://docs.astral.sh/uv/) (Python package manager)
* [`google-agents-cli`](https://google.github.io/agents-cli/guide/getting-started/)

### 2. Configure Authentication & Environment

Authenticate with your Google Cloud project:

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project <YOUR_PROJECT_ID>
```

Create a `.env` file in `stride/`:

```env
GOOGLE_GENAI_USE_VERTEXAI=true
GOOGLE_CLOUD_PROJECT=<YOUR_PROJECT_ID>
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_MAPS_API_KEY=<YOUR_MAPS_API_KEY>
```

### 3. Run the Agent Locally in ADK Dev UI

From the `stride/` directory:

```bash
cd stride

# Install dependencies
uv sync

# Launch local ADK dev UI
uv run adk web . --port 8000 --reload_agents
```

### 4. Run the Web Frontend Locally

From the `frontend/` directory in a separate terminal:

```bash
cd frontend

# Set up virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure agent connection
export AGENT_ENGINE_RESOURCE_NAME="projects/<PROJECT_ID>/locations/us-central1/reasoningEngines/<ENGINE_ID>"
export AGENT_DIRECTORY="app"

# Start the proxy and chat UI
python main.py
```

### 5. Run the Test Suite

From the `stride/` directory:

```bash
cd stride
uv run pytest
```

---

## 🚢 Deployment

### Deploy Agent to Agent Runtime

Deploy the agent to Vertex AI Agent Platform:

```bash
cd stride
agents-cli deploy --update-env-vars GOOGLE_MAPS_API_KEY=<YOUR_API_KEY>
```

### Deploy Frontend to Cloud Run

Build and deploy the containerized chat frontend to Cloud Run:

```bash
cd frontend
gcloud run deploy stride-frontend \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars AGENT_ENGINE_RESOURCE_NAME="projects/<PROJECT_ID>/locations/us-central1/reasoningEngines/<ENGINE_ID>",AGENT_DIRECTORY="app"
```

---

## 📄 License

Apache License 2.0. See LICENSE for details.
