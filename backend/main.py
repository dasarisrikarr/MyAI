from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
import google.generativeai as genai
import json, os, httpx, hashlib, secrets, smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="MyAI API v4")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

# Try available models in order
def get_model():
    for m in ["gemini-2.0-flash", "gemini-1.5-flash-latest", "gemini-1.5-pro-latest", "gemini-pro"]:
        try:
            model = genai.GenerativeModel(m)
            return model
        except:
            continue
    raise Exception("No Gemini model available")

TAVILY_KEY = os.environ.get("TAVILY_API_KEY", "")
GMAIL_USER = os.environ.get("GMAIL_USER", "")
GMAIL_PASS = os.environ.get("GMAIL_PASS", "")

users_db = {}
otps_db  = {}
chats_db = {}

def NOW():
    return datetime.now(timezone.utc).strftime("%A, %B %d, %Y at %I:%M %p UTC")

def hash_password(p):
    return hashlib.sha256(p.encode()).hexdigest()

def send_email_otp(to_email: str, otp: str):
    if not GMAIL_USER or not GMAIL_PASS:
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "MyAI — Your OTP Code"
        msg["From"]    = GMAIL_USER
        msg["To"]      = to_email
        html = f"""
        <div style="font-family:sans-serif;max-width:480px;margin:auto;padding:32px;background:#1a1a1a;border-radius:16px;color:#e8e8e6;">
          <h2 style="color:#a89cf7;">✦ MyAI</h2>
          <p style="color:#8a8a85;margin-bottom:24px;">Password Reset Request</p>
          <p>Your OTP code is:</p>
          <div style="font-size:36px;font-weight:700;letter-spacing:10px;color:#7c6ef7;background:#242424;padding:20px;border-radius:12px;text-align:center;margin:20px 0;">{otp}</div>
          <p style="color:#8a8a85;font-size:13px;">Expires in 10 minutes. If you didn't request this, ignore this email.</p>
        </div>"""
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_PASS)
            server.sendmail(GMAIL_USER, to_email, msg.as_string())
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False

class RegisterRequest(BaseModel):
    name: str; email: str; password: str; phone: Optional[str] = ""

class LoginRequest(BaseModel):
    email: str; password: str

class UpdateProfileRequest(BaseModel):
    email: str; name: str; phone: Optional[str] = ""

class OTPRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    email: str; otp: str; new_password: str

class Message(BaseModel):
    role: str; content: str

class ChatRequest(BaseModel):
    messages: List[Message]
    use_search: Optional[bool] = False
    search_query: Optional[str] = ""

@app.get("/")
def root():
    return {"status": "MyAI v4 running with Gemini", "time": NOW()}

@app.post("/register")
def register(req: RegisterRequest):
    if req.email in users_db:
        raise HTTPException(400, "Email already registered")
    users_db[req.email] = {"name": req.name, "email": req.email, "password_hash": hash_password(req.password), "phone": req.phone}
    chats_db[req.email] = []
    return {"success": True, "name": req.name, "email": req.email}

@app.post("/login")
def login(req: LoginRequest):
    u = users_db.get(req.email)
    if not u or u["password_hash"] != hash_password(req.password):
        raise HTTPException(401, "Invalid email or password")
    return {"success": True, "name": u["name"], "email": u["email"], "phone": u.get("phone","")}

@app.post("/update-profile")
def update_profile(req: UpdateProfileRequest):
    if req.email not in users_db:
        raise HTTPException(404, "User not found")
    users_db[req.email]["name"] = req.name
    users_db[req.email]["phone"] = req.phone
    return {"success": True, "name": req.name}

@app.post("/send-otp")
def send_otp(req: OTPRequest):
    if req.email not in users_db:
        raise HTTPException(404, "Email not found")
    otp = str(secrets.randbelow(900000) + 100000)
    otps_db[req.email] = otp
    sent = send_email_otp(req.email, otp)
    if sent:
        return {"success": True, "message": f"OTP sent to {req.email}"}
    return {"success": True, "otp": otp, "message": f"Email not configured. OTP: {otp}"}

@app.post("/reset-password")
def reset_password(req: ResetPasswordRequest):
    if otps_db.get(req.email) != req.otp:
        raise HTTPException(400, "Invalid OTP")
    users_db[req.email]["password_hash"] = hash_password(req.new_password)
    del otps_db[req.email]
    return {"success": True}

@app.get("/chats/{email}")
def get_chats(email: str):
    return {"chats": chats_db.get(email, [])}

@app.post("/chats/{email}")
def save_chats(email: str, body: dict):
    chats_db[email] = body.get("chats", [])
    return {"success": True}

@app.post("/chat")
def chat(request: ChatRequest):
    now = NOW()
    search_context = ""
    if request.use_search and request.search_query:
        if TAVILY_KEY:
            try:
                resp = httpx.post("https://api.tavily.com/search",
                    json={"api_key": TAVILY_KEY, "query": request.search_query, "max_results": 5, "include_answer": True}, timeout=8)
                data = resp.json()
                answer = data.get("answer", "")
                results = data.get("results", [])
                if answer: search_context += f"\n\n[WEB ANSWER]\n{answer}\n"
                if results:
                    search_context += "\n[WEB SOURCES]\n"
                    for r in results:
                        search_context += f"- [{r.get('title','')}]({r.get('url','')}): {r.get('content','')[:300]}\n"
            except Exception as e:
                search_context = f"\n[Search error: {e}]"

    system = f"""You are MyAI, a powerful AI assistant. Current date/time: {now}

FORMATTING — always follow:
- Use **bold** for important terms
- Use ## headings, ### subheadings  
- Use bullet lists and numbered lists
- Use markdown tables for comparisons
- Wrap code in triple backticks with language
- Make ALL URLs clickable: [Text](url) never raw URLs
- Add relevant emojis to make responses engaging and friendly 🎯
- Include images suggestions as: 🖼️ [Image: description] when visual would help
- Include tables when comparing or listing structured data
- Be conversational, warm and helpful
{search_context}"""

    messages = request.messages

    def generate():
        try:
            model = get_model()
            history = []
            for msg in messages[:-1]:
                role = "model" if msg.role == "assistant" else "user"
                history.append({"role": role, "parts": [msg.content]})
            
            last = messages[-1].content if messages else ""
            full_prompt = f"{system}\n\nUser: {last}"

            if history:
                chat_s = model.start_chat(history=history)
                response = chat_s.send_message(full_prompt, stream=True)
            else:
                response = model.generate_content(full_prompt, stream=True)

            for chunk in response:
                if chunk.text:
                    yield f"data: {json.dumps({'text': chunk.text})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'text': f'❌ Error: {str(e)}'})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
