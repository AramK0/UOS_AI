from fastapi import FastAPI, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, validator
from claude_api import ask_claude, reload_university_info, get_info_stats, smart_info_loader
from chatgpt_api import ask_openai
from email_service import send_feedback_email
from datetime import datetime
from pathlib import Path
import logging, os, yaml
from typing import List, Dict, Literal

# Configure logging
logging.basicConfig(
    filename='logs/chat_logs.txt',
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

app = FastAPI()

# Improved CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000", "*"],  # More specific origins
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Templates and static files
templates = Jinja2Templates(directory="frontend/templates")
app.mount("/static", StaticFiles(directory="/app/frontend/static"), name="static")

# Security setup for admin routes
security = HTTPBearer()
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN")

def verify_admin_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if credentials.credentials != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid admin token")
    return credentials

# Improved Pydantic models
class ChatMessage(BaseModel):
    message: str

class FeedbackMessage(BaseModel):
    name: str
    email: str
    category: Literal["feedback", "suggestion", "bug", "feature", "other"]
    subject: str
    message: str
    
    @validator('name', 'email', 'subject', 'message')
    def validate_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Field cannot be empty')
        return v.strip()
    
    @validator('email')
    def validate_email_format(cls, v):
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, v):
            raise ValueError('Invalid email format')
        return v

class KeywordUpdate(BaseModel):
    category: str
    files: List[str]
    keywords: Dict[str, List[str]]

# Health check endpoint
@app.get('/health')
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now()}

# Chat endpoint
@app.post("/chat")
async def chat_api(msg: ChatMessage):
    try:
        response = ask_claude(msg.message)
        logging.info(f"User message: {msg.message}")
        logging.info(f"Claude response: {response}")
        return {"response": response, "source": "claude"}
    except Exception as e:
        logging.error(f"Claude API failed: {str(e)}")
        try:
            response = ask_openai(msg.message)
            logging.info(f"OpenAI response for: {msg.message}")
            logging.info(f"Answer: {response}")
            return {"response": response, "source": "openai"}
        except Exception as e2:
            logging.error(f"Both APIs failed: Claude: {str(e)}, OpenAI: {str(e2)}")
            raise HTTPException(status_code=500, detail="Both AI services are unavailable")

#  feedback endpoint with  error handling
@app.post("/feedback")
async def submit_feedback(request: Request, feedback: FeedbackMessage):
    try:
        # Enhanced logging for debugging
        logging.info(f"=== FEEDBACK SUBMISSION START ===")
        logging.info(f"Raw request body: {await request.body()}")
        logging.info(f"Parsed feedback data: {feedback.dict()}")
        logging.info(f"Received feedback from: {feedback.name} ({feedback.email})")
        logging.info(f"Category: '{feedback.category}', Subject: '{feedback.subject}'")
        
        # Validate category explicitly (though Pydantic should handle this now)
        valid_categories = ["feedback", "suggestion", "bug", "feature", "other"]
        if feedback.category not in valid_categories:
            error_msg = f"Invalid category '{feedback.category}'. Must be one of: {valid_categories}"
            logging.error(error_msg)
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": error_msg
                }
            )
        
        # Attempt to send email with detailed error handling
        try:
            logging.info("Attempting to send feedback email...")
            send_feedback_email(
                name=feedback.name,
                email=feedback.email,
                category=feedback.category,
                subject=feedback.subject,
                message=feedback.message
            )
            logging.info("Email sent successfully!")
        except Exception as email_error:
            error_msg = f"Failed to send email: {str(email_error)}"
            logging.error(error_msg)
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "message": f"Email service error: {str(email_error)}"
                }
            )
        
        logging.info(f"Feedback process completed successfully for {feedback.name}")
        logging.info(f"=== FEEDBACK SUBMISSION END ===")
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True, 
                "message": "Feedback sent successfully and confirmation email sent to you!"
            }
        )
        
    except HTTPException as http_error:
        logging.error(f"HTTP Exception: {http_error.detail}")
        raise http_error
    except Exception as e:
        error_msg = str(e)
        logging.error(f"Unexpected error in feedback submission: {error_msg}")
        logging.error(f"Error type: {type(e).__name__}")
        
        return JSONResponse(
            status_code=500,
            content={
                "success": False, 
                "message": f"Server error: {error_msg}",
                "error_type": type(e).__name__
            }
        )

# Admin endpoints
@app.post("/admin/reload-info")
async def reload_info(_: HTTPAuthorizationCredentials = Depends(verify_admin_token)):
    try:
        reload_university_info()
        logging.info("University info reloaded successfully")
        return {"status": "success", "message": "Info reloaded", "timestamp": datetime.now()}
    except Exception as e:
        logging.error(f"Failed to reload university info: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/info-status")
async def get_info_status(_: HTTPAuthorizationCredentials = Depends(verify_admin_token)):
    try:
        stats = get_info_stats()
        logging.info("Info status retrieved successfully")
        return {"status": "success", "stats": stats, "last_check": datetime.now()}
    except Exception as e:
        logging.error(f"Failed to get info status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/keywords")
async def get_keywords(_: HTTPAuthorizationCredentials = Depends(verify_admin_token)):
    try:
        config_file = Path("config/keywords.yaml")
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                logging.info("Keywords retrieved successfully")
                return {"status": "success", "config": config}
        else:
            logging.warning("Keywords file not found")
            return {"status": "error", "message": "Keywords file not found"}
    except Exception as e:
        logging.error(f"Failed to get keywords: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/keywords/reload")
async def reload_keywords(_: HTTPAuthorizationCredentials = Depends(verify_admin_token)):
    try:
        smart_info_loader.reload_keywords()
        logging.info("Keywords reloaded successfully")
        return {"status": "success", "message": "Keywords reloaded", "timestamp": datetime.now()}
    except Exception as e:
        logging.error(f"Failed to reload keywords: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/keywords/add-category")
async def add_category(data: KeywordUpdate, _: HTTPAuthorizationCredentials = Depends(verify_admin_token)):
    return await modify_keywords(data, new=True)

@app.put("/admin/keywords/update-category/{category}")
async def update_category(category: str, data: KeywordUpdate, _: HTTPAuthorizationCredentials = Depends(verify_admin_token)):
    return await modify_keywords(data, category=category)

@app.delete("/admin/keywords/delete-category/{category}")
async def delete_category(category: str, _: HTTPAuthorizationCredentials = Depends(verify_admin_token)):
    try:
        config_file = Path("config/keywords.yaml")
        if not config_file.exists(): 
            raise HTTPException(status_code=404, detail="Keywords file not found")
        
        with open(config_file, 'r+', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            if category not in config: 
                raise HTTPException(status_code=404, detail="Category not found")
            
            del config[category]
            f.seek(0)
            f.truncate()
            yaml.dump(config, f, allow_unicode=True)
        
        smart_info_loader.reload_keywords()
        logging.info(f"Category '{category}' deleted successfully")
        return {"status": "success", "message": f"Deleted {category}", "timestamp": datetime.now()}
    except Exception as e:
        logging.error(f"Failed to delete category: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def modify_keywords(data: KeywordUpdate, new=False, category=None):
    try:
        config_file = Path("config/keywords.yaml")
        config = yaml.safe_load(config_file.read_text(encoding='utf-8')) if config_file.exists() else {}
        target = data.category if new else category
        config[target] = {"files": data.files, "keywords": data.keywords}
        config_file.write_text(yaml.dump(config, allow_unicode=True), encoding='utf-8')
        smart_info_loader.reload_keywords()
        action = "added" if new else "updated"
        logging.info(f"Category '{target}' {action} successfully")
        return {"status": "success", "message": f"{target} saved", "timestamp": datetime.now()}
    except Exception as e:
        logging.error(f"Failed to modify keywords: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin")
async def admin_dashboard(request: Request, _: HTTPAuthorizationCredentials = Depends(verify_admin_token)):
    return templates.TemplateResponse("admin.html", {"request": request})

# Public page routes
@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/index.html")
async def redirect_home():
    return RedirectResponse(url="/")

@app.get("/about")
async def about(request: Request):
    return templates.TemplateResponse("about.html", {"request": request})

@app.get("/about.html")
async def redirect_about():
    return RedirectResponse(url="/about")

@app.get("/contact")
async def contact(request: Request):
    return templates.TemplateResponse("contact.html", {"request": request})

@app.get("/contact.html")
async def redirect_contact():
    return RedirectResponse(url="/contact")

# Enhanced startup event
@app.on_event("startup")
async def startup_event():
    try:
        # Ensure required directories exist
        for folder in ["logs", "config", "university_info"]:
            Path(folder).mkdir(exist_ok=True)
        
        # Test logging
        logging.info("=== SYSTEM STARTUP ===")
        logging.info("System initialized successfully")
        logging.info("Available endpoints:")
        for route in app.routes:
            if hasattr(route, 'methods') and hasattr(route, 'path'):
                logging.info(f"  {list(route.methods)} {route.path}")
        logging.info("=== STARTUP COMPLETE ===")
        
    except Exception as e:
        logging.error(f"Startup failed: {e}")
        raise

# Add a test endpoint for debugging
@app.get("/test")
async def test_endpoint():
    return {
        "status": "test_successful",
        "timestamp": datetime.now(),
        "message": "API is working correctly"
    }

# Enhanced error handler for better debugging
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logging.error(f"Global exception handler: {type(exc).__name__}: {str(exc)}")
    logging.error(f"Request: {request.method} {request.url}")
    
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "Internal server error occurred",
            "error_type": type(exc).__name__,
            "path": str(request.url.path)
        }
    )