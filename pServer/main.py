from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
import uvicorn
import os
from contextlib import asynccontextmanager
from datetime import datetime
from database import database, db_operations

# Import routers from the correct 'routes' directory
from routers import exams, scan, results, reports, settings, students, omr, solutions

# Database path
DATABASE_PATH = os.getenv("DATABASE_PATH", "omr_database.db")

@asynccontextmanager
async def lifespan(app: FastAPI):
    global database
    try:
        # Initialize SQLite database
        database.db_path = DATABASE_PATH
        await database.connect()
        print(f"MongoDB connected successfully at {datetime.utcnow().isoformat()}")
    except Exception as e:
        print(f"SQLite database connection failed: {e}")
        raise
    
    app.state.database = database
    app.state.db_operations = db_operations
    yield
    await database.disconnect()
    print(f"SQLite database connection closed at {datetime.utcnow().isoformat()}")

app = FastAPI(
    title="OMR Processing API",
    description="Backend API for OMR (Optical Mark Recognition) processing system",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "file://", "app://"],  # Allow Electron origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(exams.router, prefix="/api/exams", tags=["exams"])
app.include_router(scan.router, prefix="/api/scan", tags=["scan"])
app.include_router(results.router, prefix="/api/results", tags=["results"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(students.router, prefix="/api/students", tags=["students"])
app.include_router(omr.router, prefix="/api/omr", tags=["omr"])
app.include_router(solutions.router, prefix="/api/solutions", tags=["solutions"])

# Health check endpoint
@app.get("/api/health")
async def health_check():
    return {
        "status": "OK",
        "timestamp": datetime.utcnow().isoformat()  # Updated to current UTC time
    }

# Error handling
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    print(f"Server error: {exc}")
    return HTTPException(
        status_code=500,
        detail={
            "error": "Internal server error",
            "message": str(exc),
            "timestamp": datetime.utcnow().isoformat()  # Add timestamp for debugging
        }
    )

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 3001)),
        reload=True
    )