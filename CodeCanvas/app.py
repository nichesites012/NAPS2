#!/usr/bin/env python3
"""
Domain Research Web Application
FastAPI-based web interface for domain age research
"""

import asyncio
import uuid
import json
import io
from contextlib import asynccontextmanager
from typing import Dict, List, Optional, Any
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, Request, Form, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import pandas as pd

from research_backend import AsyncDomainResearcher, DomainData, apply_advanced_filter


# Global storage for research tasks and results with cleanup
research_tasks: Dict[str, Dict] = {}
research_task_objects: Dict[str, asyncio.Task] = {}  # Store asyncio task objects for cancellation
executor = ThreadPoolExecutor(max_workers=2)

# Task cleanup - remove tasks older than 1 hour
async def cleanup_old_tasks():
    """Remove old completed tasks to prevent memory leaks"""
    current_time = datetime.now()
    tasks_to_remove = []
    
    for task_id, task in research_tasks.items():
        if task["status"] in ["completed", "error", "cancelled"]:
            created_at = datetime.fromisoformat(task["created_at"])
            if (current_time - created_at).total_seconds() > 3600:  # 1 hour
                tasks_to_remove.append(task_id)
    
    for task_id in tasks_to_remove:
        if task_id in research_tasks:
            del research_tasks[task_id]
        if task_id in research_task_objects:
            del research_task_objects[task_id]

# Periodic cleanup task
async def periodic_cleanup():
    """Run cleanup every 10 minutes"""
    while True:
        await asyncio.sleep(600)  # 10 minutes
        await cleanup_old_tasks()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler"""
    # Startup
    asyncio.create_task(periodic_cleanup())
    yield
    # Shutdown - cleanup can be added here if needed

app = FastAPI(title="Domain Research Tool", version="1.0.0", lifespan=lifespan)

# Templates
templates = Jinja2Templates(directory="templates")

# Create templates directory and template file
import os
os.makedirs("templates", exist_ok=True)

# Pydantic models
class ResearchRequest(BaseModel):
    keywords: List[str]
    max_domains_per_keyword: int = 5
    serp_api_key: Optional[str] = None
    whois_api_key: Optional[str] = None

class FilterRequest(BaseModel):
    task_id: str
    min_age: int = 0
    max_age: int = 365
    min_domains: int = 1
    enable_filtering: bool = False


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve the main application page"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/research")
async def start_research(request: ResearchRequest):
    """Start a new domain research task"""
    task_id = str(uuid.uuid4())
    
    # Initialize task
    research_tasks[task_id] = {
        "status": "starting",
        "progress": 0,
        "total": len(request.keywords),
        "current_keyword": "",
        "results": [],
        "error": None,
        "created_at": datetime.now().isoformat(),
        "cancelled_event": asyncio.Event()  # For cooperative cancellation
    }
    
    # Start background task
    async def run_research():
        try:
            research_tasks[task_id]["status"] = "running"
            research_tasks[task_id]["domains_processed"] = 0
            research_tasks[task_id]["total_domains_estimated"] = len(request.keywords) * request.max_domains_per_keyword
            
            # Get cancellation event
            cancelled_event = research_tasks[task_id]["cancelled_event"]
            
            async def progress_callback(current, total, message):
                # Check for cancellation
                if cancelled_event.is_set():
                    raise asyncio.CancelledError("Task cancelled by user")
                research_tasks[task_id]["progress"] = current
                research_tasks[task_id]["current_keyword"] = message
                
            async def domain_progress_callback():
                # Check for cancellation
                if cancelled_event.is_set():
                    raise asyncio.CancelledError("Task cancelled by user")
                research_tasks[task_id]["domains_processed"] += 1
            
            async with AsyncDomainResearcher(request.serp_api_key, request.whois_api_key) as researcher:
                results = await researcher.research_keywords(
                    request.keywords, 
                    request.max_domains_per_keyword,
                    progress_callback,
                    domain_progress_callback,
                    cancelled_event
                )
                
                # Check one more time before marking as completed
                if cancelled_event.is_set():
                    research_tasks[task_id]["status"] = "cancelled"
                    research_tasks[task_id]["error"] = "Task cancelled by user"
                else:
                    research_tasks[task_id]["results"] = [
                        {
                            "keyword": r.keyword,
                            "domain": r.domain,
                            "creation_date": r.creation_date,
                            "age_days": r.age_days,
                            "age_display": r.age_display,
                            "status": r.status,
                            "google_string": r.google_string
                        }
                        for r in results
                    ]
                    research_tasks[task_id]["status"] = "completed"
                
        except asyncio.CancelledError:
            research_tasks[task_id]["status"] = "cancelled"
            research_tasks[task_id]["error"] = "Task cancelled by user"
        except Exception as e:
            if not research_tasks[task_id]["cancelled_event"].is_set():
                research_tasks[task_id]["status"] = "error"
                research_tasks[task_id]["error"] = str(e)
            else:
                research_tasks[task_id]["status"] = "cancelled"
                research_tasks[task_id]["error"] = "Task cancelled by user"
    
    # Run in background and store task object for cancellation
    task_obj = asyncio.create_task(run_research())
    research_task_objects[task_id] = task_obj
    
    return {"task_id": task_id}


@app.get("/api/status/{task_id}")
async def get_task_status(task_id: str):
    """Get the status of a research task"""
    if task_id not in research_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return research_tasks[task_id]


@app.get("/api/results/{task_id}")
async def get_results(task_id: str):
    """Get the results of a completed research task"""
    if task_id not in research_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = research_tasks[task_id]
    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail="Task not completed")
    
    return {"results": task["results"]}


@app.post("/api/filter")
async def filter_results(request: FilterRequest):
    """Apply filtering to results"""
    if request.task_id not in research_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = research_tasks[request.task_id]
    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail="Task not completed")
    
    # Convert dict results back to DomainData objects
    results = [
        DomainData(
            keyword=r["keyword"],
            domain=r["domain"],
            creation_date=r["creation_date"],
            age_days=r["age_days"],
            status=r["status"],
            google_string=r["google_string"],
            age_display=r.get("age_display", "")
        )
        for r in task["results"]
    ]
    
    if request.enable_filtering:
        filtered_results = apply_advanced_filter(
            results, request.min_age, request.max_age, request.min_domains
        )
    else:
        filtered_results = results
    
    # Convert back to dict format
    filtered_dict = [
        {
            "keyword": r.keyword,
            "domain": r.domain,
            "creation_date": r.creation_date,
            "age_days": r.age_days,
            "status": r.status,
            "google_string": r.google_string
        }
        for r in filtered_results
    ]
    
    return {"filtered_results": filtered_dict}


@app.get("/api/export/{task_id}")
async def export_results(task_id: str, format: str = "csv", filtered: bool = False, 
                        min_age: int = 0, max_age: int = 365, min_domains: int = 1):
    """Export results to CSV or Excel"""
    if task_id not in research_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = research_tasks[task_id]
    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail="Task not completed")
    
    # Apply filtering if requested
    if filtered:
        # Convert dict results to DomainData objects for filtering
        domain_data_results = [
            DomainData(
                keyword=r["keyword"],
                domain=r["domain"],
                creation_date=r["creation_date"],
                age_days=r["age_days"],
                status=r["status"],
                google_string=r["google_string"],
                age_display=r.get("age_display", "")
            )
            for r in task["results"]
        ]
        
        # Apply advanced filter
        filtered_results = apply_advanced_filter(
            domain_data_results, min_age, max_age, min_domains
        )
        
        # Convert back to dict format
        results = [
            {
                "keyword": r.keyword,
                "domain": r.domain,
                "creation_date": r.creation_date,
                "age_days": r.age_days,
                "status": r.status,
                "google_string": r.google_string
            }
            for r in filtered_results
        ]
    else:
        results = task["results"]
    
    # Create DataFrame
    df = pd.DataFrame(results)
    
    if format == "csv":
        # Export as CSV
        output = io.StringIO()
        df.to_csv(output, index=False)
        output.seek(0)
        
        response = StreamingResponse(
            io.BytesIO(output.getvalue().encode()),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=domain_research_{task_id}.csv"}
        )
        return response
    
    elif format == "excel":
        # Export as Excel
        try:
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Domain Research')
            output.seek(0)
            
            response = StreamingResponse(
                output,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f"attachment; filename=domain_research_{task_id}.xlsx"}
            )
            return response
        except ImportError:
            raise HTTPException(status_code=400, detail="Excel export requires openpyxl package. Use CSV format instead.")
    
    else:
        raise HTTPException(status_code=400, detail="Invalid format. Use 'csv' or 'excel'")


@app.post("/api/upload-keywords")
async def upload_keywords(file: UploadFile = File(...)):
    """Upload keywords from a text file"""
    try:
        contents = await file.read()
        text = contents.decode('utf-8')
        keywords = [line.strip() for line in text.split('\n') if line.strip()]
        return {"keywords": keywords}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error reading file: {str(e)}")


# Health check endpoint
@app.post("/api/cancel/{task_id}")
async def cancel_task(task_id: str):
    """Cancel a running task"""
    if task_id not in research_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = research_tasks[task_id]
    if task["status"] == "running":
        # Set cancellation event for cooperative cancellation
        if "cancelled_event" in task:
            task["cancelled_event"].set()
        
        # Cancel the asyncio task
        if task_id in research_task_objects:
            task_obj = research_task_objects[task_id]
            if not task_obj.done():
                task_obj.cancel()
        
        task["status"] = "cancelled"
        task["error"] = "Task cancelled by user"
        return {"message": "Task cancelled successfully"}
    else:
        raise HTTPException(status_code=400, detail="Task is not running")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    # Run cleanup on health check
    await cleanup_old_tasks()
    return {
        "status": "healthy", 
        "timestamp": datetime.now().isoformat(),
        "active_tasks": len([t for t in research_tasks.values() if t["status"] == "running"]),
        "total_tasks": len(research_tasks)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)