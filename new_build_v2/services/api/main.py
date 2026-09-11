from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
import sys

# Ensure pipeline is accessible 
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from pipeline.agents.script_critic import ScriptCritic
from pipeline.agents.recap_agent import RecapAgent
from pipeline.agents.continuity_inspector import ContinuityInspector

app = FastAPI(title="Netflix LM Agent API", version="0.1.0")

# Initialize Agents
critic_agent = ScriptCritic()
recap_agent = RecapAgent()
continuity_agent = ContinuityInspector()

class SceneRequest(BaseModel):
    scene_id: str
    content: dict

class RecapRequest(BaseModel):
    episode_id: str
    tone_variant: str = "standard"

@app.get("/health")
def health_check():
    return {"status": "healthy", "components": ["api", "agents"]}

@app.post("/analyze/scene")
def analyze_scene(request: SceneRequest):
    """
    Trigger the Script Critic to analyze a specific scene.
    """
    flags = critic_agent.analyze_scene(request.content)
    return {"scene_id": request.scene_id, "flags": flags}

@app.post("/generate/recap")
def generate_recap(request: RecapRequest):
    """
    Trigger the Recap Agent to generate an episode recap.
    """
    recap = recap_agent.generate_recap({"episode_id": request.episode_id}, tone_variant=request.tone_variant)
    return {"episode_id": request.episode_id, "recap": recap}

@app.post("/inspect/continuity")
def inspect_continuity(request: SceneRequest):
    """
    Trigger the Continuity Inspector.
    """
    flags = continuity_agent.inspect_visuals(request.content)
    return {"scene_id": request.scene_id, "flags": flags}
