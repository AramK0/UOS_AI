from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from claude_api import ask_claude
from chatgpt_api import ask_openai
from email_service import send_feedback_email
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(
    filename='logs/chat_logs.txt',
    level=logging.INFO, 
    format="%(asctime)s - %(levelname)s - %(message)s"
)

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Templates and static files
templates = Jinja2Templates(directory="frontend/templates")
app.mount("/static", StaticFiles(directory="/app/frontend/static"), name="static")

class ChatMessage(BaseModel):
    message: str

class FeedbackMessage(BaseModel):
    name: str
    email: str
    category: str
    subject: str
    message: str

@app.get('/health')
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now()}

@app.post("/chat")
async def chat_api(msg: ChatMessage):
    try:
        answer = ask_claude(msg.message)
        logging.info(f"Claude response for: {msg.message}")
        logging.info(f"Answer: {answer}")
        return {"response": answer}
    except Exception as e:
        logging.error(f"Claude API failed: {str(e)}")
        try:
            answer = ask_openai(msg.message)
            logging.info(f"OpenAI response for: {msg.message}")
            logging.info(f"Answer: {answer}")
            return {"response": answer}
        except Exception as e2:
            logging.error(f"Both APIs failed: Claude: {str(e)}, OpenAI: {str(e2)}")
            raise HTTPException(status_code=500, detail="Both AI services are unavailable")

@app.post("/feedback")
async def submit_feedback(feedback: FeedbackMessage):
    try:
        logging.info(f"Received feedback from {feedback.name} ({feedback.email})")
        logging.info(f"Category: {feedback.category}, Subject: {feedback.subject}")
        
        # Send both team notification and user auto-reply
        send_feedback_email(
            name=feedback.name,
            email=feedback.email,
            category=feedback.category,
            subject=feedback.subject,
            message=feedback.message
        )
        
        logging.info(f"Both team notification and auto-reply sent successfully for {feedback.name}")
        return JSONResponse(
            status_code=200,
            content={
                "success": True, 
                "message": "Feedback sent successfully and confirmation email sent to you!"
            }
        )
        
    except Exception as e:
        error_msg = str(e)
        logging.error(f"Feedback submission failed: {error_msg}")
        
        # Return detailed error for debugging (remove in production)
        return JSONResponse(
            status_code=500,
            content={
                "success": False, 
                "message": f"Failed to send feedback: {error_msg}",
                "error_details": error_msg  # Remove this in production
            }
        )

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