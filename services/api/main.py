from fastapi import FastAPI
from routes import episodes, flags, knowledge_graph, recaps

app = FastAPI(title="Netflix LM API", version="1.0.0")

app.include_router(episodes.router, prefix="/api/v1")
app.include_router(flags.router, prefix="/api/v1")
app.include_router(recaps.router, prefix="/api/v1")
app.include_router(knowledge_graph.router, prefix="/api/v1")


@app.get("/health")
def health_check():
    return {"status": "ok"}
