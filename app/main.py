import os
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from game import (
    generate_round,
    check_answer,
    build_llm_prompt,
    RULEBOOKS,
    DIFFICULTY_SETTINGS,
)

app = FastAPI(title="The Chinese Room")

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
MODEL_NAME = os.environ.get("MODEL_NAME", "qwen2.5:7b")

# In-memory session store (single-server, fine for a demo)
sessions: dict[str, dict] = {}


class NewGameRequest(BaseModel):
    category: str = "greetings"
    difficulty: str = "easy"


class SubmitAnswerRequest(BaseModel):
    session_id: str
    answer: str


class FreeChatRequest(BaseModel):
    session_id: str
    message: str


@app.get("/api/config")
async def get_config():
    return {
        "categories": {k: v["name"] for k, v in RULEBOOKS.items()},
        "difficulties": list(DIFFICULTY_SETTINGS.keys()),
    }


@app.post("/api/game/new")
async def new_game(req: NewGameRequest):
    import uuid

    session_id = str(uuid.uuid4())
    round_data = generate_round(req.category, req.difficulty)

    sessions[session_id] = {
        "category": req.category,
        "difficulty": req.difficulty,
        "round": 1,
        "score": 0,
        "current_round": round_data,
        "conversation": [],
        "mode": "rulebook",
    }

    return {
        "session_id": session_id,
        "round": 1,
        "incoming_message": round_data["incoming_message"],
        "rules": round_data["rules"],
        "grid": round_data["grid"],
        "grid_cols": round_data["grid_cols"],
        "time_limit": round_data["time_limit"],
    }


@app.post("/api/game/submit")
async def submit_answer(req: SubmitAnswerRequest):
    session = sessions.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    round_data = session["current_round"]
    result = check_answer(round_data["expected_answer"], req.answer)

    session["score"] += result["score"]
    session["conversation"].append(
        {"role": "user", "content": round_data["incoming_message"]}
    )
    session["conversation"].append({"role": "assistant", "content": req.answer})

    # Generate next round
    session["round"] += 1
    next_round = generate_round(session["category"], session["difficulty"])
    session["current_round"] = next_round

    return {
        "result": result,
        "total_score": session["score"],
        "round": session["round"],
        "expected_answer": round_data["expected_answer"],
        # Next round data
        "incoming_message": next_round["incoming_message"],
        "rules": next_round["rules"],
        "grid": next_round["grid"],
        "grid_cols": next_round["grid_cols"],
        "time_limit": next_round["time_limit"],
    }


@app.post("/api/game/freemode")
async def free_mode(req: FreeChatRequest):
    """Free conversation mode: talk directly with the LLM in Chinese."""
    session = sessions.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session["mode"] = "free"
    session["conversation"].append({"role": "assistant", "content": req.message})

    messages = build_llm_prompt(session["conversation"])

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{OLLAMA_HOST}/api/chat",
                json={"model": MODEL_NAME, "messages": messages, "stream": False},
            )
            resp.raise_for_status()
            data = resp.json()
            reply = data["message"]["content"]
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"LLM service error: {e}")

    session["conversation"].append({"role": "user", "content": reply})

    return {"reply": reply}


@app.post("/api/llm/start")
async def llm_start_conversation(req: NewGameRequest):
    """Ask the LLM to start a conversation (it sends the first message)."""
    import uuid

    session_id = str(uuid.uuid4())

    messages = build_llm_prompt([])

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{OLLAMA_HOST}/api/chat",
                json={"model": MODEL_NAME, "messages": messages, "stream": False},
            )
            resp.raise_for_status()
            data = resp.json()
            opening = data["message"]["content"]
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"LLM service error: {e}")

    sessions[session_id] = {
        "category": req.category,
        "difficulty": req.difficulty,
        "round": 1,
        "score": 0,
        "current_round": generate_round(req.category, req.difficulty),
        "conversation": [{"role": "user", "content": opening}],
        "mode": "llm",
    }

    round_data = sessions[session_id]["current_round"]

    return {
        "session_id": session_id,
        "llm_message": opening,
        "rules": round_data["rules"],
        "grid": round_data["grid"],
        "grid_cols": round_data["grid_cols"],
        "time_limit": round_data["time_limit"],
    }


@app.get("/api/model/status")
async def model_status():
    """Check if Ollama is reachable and model is available."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{OLLAMA_HOST}/api/tags")
            resp.raise_for_status()
            tags = resp.json()
            models = [m["name"] for m in tags.get("models", [])]
            has_model = any(MODEL_NAME.split(":")[0] in m for m in models)
            return {"ollama": True, "models": models, "has_model": has_model, "target": MODEL_NAME}
    except Exception:
        return {"ollama": False, "models": [], "has_model": False, "target": MODEL_NAME}


# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def index():
    return FileResponse("static/index.html")
