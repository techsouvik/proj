import logging
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import Base, engine
from app.api import chat, ingest, analytics

# Setup detailed logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("API_Runner")

# Automatically initialize database schema tables on startup
try:
    logger.info("Initializing Database Tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database Schema created successfully.")
except Exception as e:
    logger.error(f"Critical error creating Database Tables on startup: {e}")

# Initialize FastAPI instance
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Inference Logging, Ingestion Pipeline & Analytics Dashboard Service"
)

# Enable CORS for Next.js frontend calls
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For local testing, allow wildcard. In production, restrict to frontend domain.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Routers
app.include_router(chat.router, prefix=settings.API_V1_STR)
app.include_router(ingest.router, prefix=settings.API_V1_STR)
app.include_router(analytics.router, prefix=settings.API_V1_STR)

@app.get("/")
def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION
    }

if __name__ == "__main__":
    # Boot server on port 8000
    uvicorn.run("run:app", host="0.0.0.0", port=8000, reload=True)
