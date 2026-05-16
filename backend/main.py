from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
import google.generativeai as genai
import json, os, httpx, secrets, smtplib, bcrypt
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="MyAI Final")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Gemini + Groq key rotation ──
GEMINI_KEYS = [k.strip() for k in os.environ.get("GEMINI_API_KEYS", "").split(",") if k.strip()]
GROQ_KEYS   = [k.strip() for k in os.environ.get("GROQ_API_KEYS", "").split(",") if k.strip()]
if os.environ.get("GEMINI_API_KEY") and os.environ.get("GEMINI_API_KEY") not in GEMINI_KEYS:
    GEMINI_KEYS.insert(0, os.environ.get("GEMINI_API_KEY"))
if os.environ.get("GROQ_API_KEY") and os.environ.get("GROQ_API_KEY") not in GROQ_KEYS:
    GROQ_KEYS.insert(0, os.environ.get("GROQ_API_KEY"))

GEMINI_KEY_INDEX = 0
GROQ_KEY_INDEX   = 0
GEMINI_MODELS    = ["gemini-1.5-flash-latest", "gemini-1.5-pro-latest", "gemini-pro"]
GROQ_MODELS      = ["llama-3.3-70b-versatile", "llama3-8b-8192"]

# ── Supabase via REST API (no library needed!) ──
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

def sb_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

def sb_get(table: str, filters: dict = {}):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return []
    try:
        params = "&".join([f"{k}=eq.{v}" for k, v in filters.items()])
        url = f"{SUPABASE_URL}/rest/v1/{table}?{params}&limit=1000"
        r = httpx.get(url, headers=sb_headers(), timeout=10)
        return r.json() if r.status_code == 200 else []
    except Exception as e:
        print(f"DB get error: {e}")
        return []

def sb_insert(table: str, data: dict):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    try:
        url = f"{SUPABASE_URL}/rest/v1/{table}"
        r = httpx.post(url, headers=sb_headers(), json=data, timeout=10)
        result = r.json()
        return result[0] if isinstance(result, list) and result else result
    except Exception as e:
        print(f"DB insert error: {e}")
        return None

def sb_update(table: str, filters: dict, data: dict):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    try:
        params = "&".join([f"{k}=eq.{v}" for k, v in filters.items()])
        url = f"{SUPABASE_URL}/rest/v1/{table}?{params}"
        r = httpx.patch(url, headers=sb_headers(), json=data, timeout=10)
        return r.json()
    except Exception as e:
        print(f"DB update error: {e}")
        return None

def sb_delete(table: str, filters: dict):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    try:
        params = "&".join([f"{k}=eq.{v}" for k, v in filters.items()])
        url = f"{SUPABASE_URL}/rest/v1/{table}?{params}"
        r = httpx.delete(url, headers=sb_headers(), timeout=10)
        return r.status_code
    except Exception as e:
        print(f"DB delete error: {e}")
        return None

# ── DB helpers ──
def db_get_user(email: str):
    rows = sb_get("users", {"email": email})
    return rows[0] if rows else None

def db_create_user(name, email, password, phone=""):
    existing = db_get_user(email)
    if existing:
        raise HTTPException(400, "Email already registered. Please login.")
    result = sb_insert("users", {
        "name": name, "email": email,
        "password_hash": hash_pw(password),
        "phone": phone,
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    if not result:
        raise HTTPException(500, "Could not create user. Check database setup.")
    return result

def db_update_user(email, data):
    sb_update("users", {"email": email}, data)

def db_get_chats(email: str):
    rows = sb_get("chats", {"user_email": email})
    return rows or []

def db_save_chats(email: str, chats: list):
    sb_delete("chats", {"user_email": email})
    for c in chats:
        sb_insert("chats", {
            "id": str(c.get("id", "")),
            "user_email": email,
            "title": c.get("title", "New chat"),
            "messages": json.dumps(c.get("messages", [])),
            "pinned": c.get("pinned", False),
            "created_at": str(c.get("createdAt", datetime.now(timezone.utc).isoformat())),
            "updated_at": datetime.now(timezone.utc).isoformat()
        })

# ── Email ──
GMAIL_USER = os.environ.get("GMAIL_USER", "")
GMAIL_PASS = os.environ.get("GMAIL_PASS", "")
TAVILY_KEY = os.environ.get("TAVILY_API_KEY", "")
otps_db = {}

def NOW():
    return datetime.now(timezone.utc).strftime("%A, %B %d, %Y at %I:%M %p UTC")

def hash_pw(p): return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()
def check_pw(p, h): return bcrypt.checkpw(p.encode(), h.encode())

def send_otp_email(to_email: str, otp: str, name: str = "User"):
    if not GMAIL_USER or not GMAIL_PASS:
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "MyAI — Your OTP Code 🔐"
        msg["From"]    = f"MyAI <{GMAIL_USER}>"
        msg["To"]      = to_email
        html = f"""
<!DOCTYPE html><html><body style="margin:0;padding:0;background:#0a0a0f;font-family:'Segoe UI',sans-serif;">
  <div style="max-width:480px;margin:40px auto;background:#13131a;border-radius:20px;overflow:hidden;border:1px solid rgba(124,110,247,0.3);">
    <div style="background:linear-gradient(135deg,#7c6ef7,#6d5ce7);padding:30px;text-align:center;">
      <h1 style="color:white;margin:0;font-size:24px;">✦ MyAI</h1>
      <p style="color:rgba(255,255,255,0.8);margin:8px 0 0;font-size:14px;">Your Personal AI Assistant</p>
    </div>
    <div style="padding:32px;">
      <p style="color:#e8e8f0;font-size:16px;">Hello, <strong>{name}</strong>! 👋</p>
      <p style="color:#7a7a90;font-size:14px;margin-bottom:24px;">Use the OTP below to reset your password:</p>
      <div style="background:#1c1c26;border:2px solid #7c6ef7;border-radius:16px;padding:28px;text-align:center;margin-bottom:24px;">
        <p style="color:#7a7a90;font-size:12px;margin:0 0 12px;text-transform:uppercase;letter-spacing:2px;">Your OTP Code</p>
        <div style="font-size:42px;font-weight:700;letter-spacing:14px;color:#a89cf7;font-family:monospace;">{otp}</div>
      </div>
      <p style="color:#ef4444;font-size:13px;">⏰ Expires in 10 minutes</p>
      <p style="color:#7a7a90;font-size:13px;margin-top:12px;">If you didn't request this, ignore this email.</p>
    </div>
    <div style="background:#0a0a0f;padding:16px;text-align:center;">
      <p style="color:#4a4a60;font-size:12px;margin:0;">© 2025 MyAI</p>
    </div>
  </div>
</body></html>"""
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_PASS)
            server.sendmail(GMAIL_USER, to_email, msg.as_string())
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False

# ── Request models ──
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

# ── Endpoints ──
@app.get("/")
def root():
    db_ok = bool(SUPABASE_URL and SUPABASE_KEY)
    return {"status": "MyAI running", "time": NOW(), "db": db_ok,
            "gemini_keys": len(GEMINI_KEYS), "groq_keys": len(GROQ_KEYS)}

@app.post("/register")
def register(req: RegisterRequest):
    user = db_create_user(req.name, req.email, req.password, req.phone or "")
    return {"success": True, "name": user["name"], "email": user["email"]}

@app.post("/login")
def login(req: LoginRequest):
    user = db_get_user(req.email)
    if not user: raise HTTPException(401, "Email not found. Please register.")
    if not check_pw(req.password, user["password_hash"]):
        raise HTTPException(401, "Wrong password.")
    return {"success": True, "name": user["name"], "email": user["email"], "phone": user.get("phone", "")}

@app.post("/update-profile")
def update_profile(req: UpdateProfileRequest):
    if not db_get_user(req.email): raise HTTPException(404, "User not found")
    db_update_user(req.email, {"name": req.name, "phone": req.phone})
    return {"success": True, "name": req.name}

@app.post("/send-otp")
def send_otp(req: OTPRequest):
    user = db_get_user(req.email)
    if not user: raise HTTPException(404, "No account found with this email.")
    otp = str(secrets.randbelow(900000) + 100000)
    otps_db[req.email] = {"otp": otp, "time": datetime.now(timezone.utc).timestamp()}
    sent = send_otp_email(req.email, otp, user.get("name", "User"))
    if sent:
        return {"success": True, "message": f"✅ OTP sent to {req.email}! Check your inbox."}
    return {"success": True, "otp": otp, "message": f"⚠️ Email not configured. Your OTP is: {otp}"}

@app.post("/reset-password")
def reset_password(req: ResetPasswordRequest):
    record = otps_db.get(req.email)
    if not record: raise HTTPException(400, "OTP not found. Request a new one.")
    if datetime.now(timezone.utc).timestamp() - record["time"] > 600:
        del otps_db[req.email]; raise HTTPException(400, "OTP expired.")
    if record["otp"] != req.otp: raise HTTPException(400, "Wrong OTP.")
    db_update_user(req.email, {"password_hash": hash_pw(req.new_password)})
    del otps_db[req.email]
    return {"success": True}

@app.get("/chats/{email}")
def get_chats(email: str):
    raw = db_get_chats(email)
    chats = [{"id": r.get("id"), "title": r.get("title", "New chat"),
               "messages": json.loads(r.get("messages", "[]")),
               "pinned": r.get("pinned", False),
               "createdAt": r.get("created_at", "")} for r in raw]
    return {"chats": chats}

@app.post("/chats/{email}")
def save_chats(email: str, body: dict):
    db_save_chats(email, body.get("chats", []))
    return {"success": True}

@app.post("/chat")
def chat(request: ChatRequest):
    global GEMINI_KEY_INDEX, GROQ_KEY_INDEX
    now = NOW()
    search_context = ""
    if request.use_search and request.search_query and TAVILY_KEY:
        try:
            resp = httpx.post("https://api.tavily.com/search",
                json={"api_key": TAVILY_KEY, "query": request.search_query,
                      "max_results": 5, "include_answer": True}, timeout=8)
            data = resp.json()
            if data.get("answer"): search_context += f"\n\n[WEB ANSWER]\n{data['answer']}\n"
            if data.get("results"):
                search_context += "\n[WEB SOURCES]\n"
                for r in data["results"]:
                    search_context += f"- [{r.get('title','')}]({r.get('url','')}): {r.get('content','')[:300]}\n"
        except: pass

    system = f"""You are MyAI, a powerful AI assistant like ChatGPT.
Current date and time: {now}
FORMATTING: Use **bold**, ## headings, bullet lists, numbered lists, markdown tables, code blocks with language, clickable links [Text](url), relevant emojis. Be warm and friendly.
{search_context}"""

    messages = request.messages
    history = [{"role": "model" if m.role == "assistant" else "user", "parts": [m.content]} for m in messages[:-1]]
    last = messages[-1].content if messages else ""
    full_prompt = f"{system}\n\nUser: {last}"

    def generate():
        global GEMINI_KEY_INDEX, GROQ_KEY_INDEX

        # Try Gemini keys
        if GEMINI_KEYS:
            attempts = 0
            while attempts < len(GEMINI_KEYS):
                try:
                    key = GEMINI_KEYS[GEMINI_KEY_INDEX]
                    genai.configure(api_key=key)
                    model = genai.GenerativeModel(GEMINI_MODELS[0])
                    if history:
                        chat_s = model.start_chat(history=history)
                        response = chat_s.send_message(full_prompt, stream=True)
                    else:
                        response = model.generate_content(full_prompt, stream=True)
                    for chunk in response:
                        if chunk.text:
                            yield f"data: {json.dumps({'text': chunk.text})}\n\n"
                    yield "data: [DONE]\n\n"
                    return
                except Exception as e:
                    err = str(e).lower()
                    if any(x in err for x in ["429", "quota", "limit", "exhausted", "resource"]):
                        print(f"Gemini key {GEMINI_KEY_INDEX} exhausted, rotating...")
                        GEMINI_KEY_INDEX = (GEMINI_KEY_INDEX + 1) % len(GEMINI_KEYS)
                        attempts += 1
                    else:
                        print(f"Gemini error: {e}")
                        break

        # Try Groq keys
        if GROQ_KEYS:
            attempts = 0
            while attempts < len(GROQ_KEYS):
                try:
                    from groq import Groq
                    key = GROQ_KEYS[GROQ_KEY_INDEX]
                    client = Groq(api_key=key)
                    groq_msgs = [{"role": "user", "content": system}]
                    for h in history:
                        role = "assistant" if h["role"] == "model" else "user"
                        groq_msgs.append({"role": role, "content": h["parts"][0]})
                    groq_msgs.append({"role": "user", "content": last})
                    stream = client.chat.completions.create(
                        model=GROQ_MODELS[0], messages=groq_msgs,
                        max_tokens=2048, stream=True)
                    for chunk in stream:
                        delta = chunk.choices[0].delta.content
                        if delta:
                            yield f"data: {json.dumps({'text': delta})}\n\n"
                    yield "data: [DONE]\n\n"
                    return
                except Exception as e:
                    err = str(e).lower()
                    if any(x in err for x in ["429", "quota", "rate", "limit"]):
                        print(f"Groq key {GROQ_KEY_INDEX} exhausted, rotating...")
                        GROQ_KEY_INDEX = (GROQ_KEY_INDEX + 1) % len(GROQ_KEYS)
                        attempts += 1
                    else:
                        print(f"Groq error: {e}")
                        break

        yield f"data: {json.dumps({'text': '⚠️ All AI keys have hit their daily limit. Please try again tomorrow or add more keys.'})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
