from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from routers.intakes import router as intakes_router
from database import init_db
import os


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup - initialize database (fast operation)
    try:
        init_db()
        print("✓ Database initialized")
    except Exception as e:
        print(f"⚠ Database initialization warning: {e}")
    yield
    # Shutdown (if needed)


app = FastAPI(
    title="Pharmacy Workflow Automation API",
    description="Backend API for pharmacy workflow automation system",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    return {"status": "ok", "message": "Pharmacy Workflow API is running"}

app.include_router(intakes_router)

# Serve frontend static files (for hosting)
frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")
    
    @app.get("/")
    async def read_root():
        """Serve the frontend HTML file"""
        return FileResponse(os.path.join(frontend_path, "index.html"))
    
    @app.get("/{path:path}")
    async def serve_frontend(path: str):
        """Serve frontend files"""
        file_path = os.path.join(frontend_path, path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
        # If not found, serve index.html (for client-side routing)
        return FileResponse(os.path.join(frontend_path, "index.html"))