from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import players
from app.routers.matches import matches_router, team_router
app = FastAPI(title="PitchIQ API")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "healthy", "service": "PitchIQ API"}

app.include_router(players.router)
app.include_router(matches_router)
app.include_router(team_router)


