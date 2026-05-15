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
from supabase import create_client, Client

load_dotenv()

app = FastAPI(title="MyAI Final")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Multi-key AI Manager ──
# Add as many free keys as you want!
GEMINI_KEYS = [k.strip() for k in os.environ.get("GEMINI_API_KEYS", "").split(",") if k.strip()]
GROQ_KEYS   = [k.strip() for k in os.environ.get("GROQ_API_KEYS", "").split(",") if k.strip()]

# Single key fallback
if os.environ.get("GEMINI_API_KEY"):
    single = os.environ.get("GEMINI_API_KEY")
    if single not in GEMINI_KEYS:
        GEMINI_KEYS.insert(0, single)
if os.environ.get("GROQ_API_KEY"):
    single = os.environ.get("GROQ_API_KEY")
    if single not in GROQ_KEYS:
        GROQ_KEYS.insert(0, single)

GEMINI_KEY_INDEX = 0
GROQ_KEY_INDEX   = 0

GEMINI_MODELS = ["gemini-1.5-flash-latest", "gemini-1.5-pro-latest", "gemini-pro"]
GROQ_MODELS   = ["llama-3.3-70b-versatile", "llama3-8b-8192", "mixtral-8x7b-32768"]

def get_gemini_response(prompt: str, history: list, stream_callback):
    """Try all Gemini keys in rotation"""
    global GEMINI_KEY_INDEX
    start = GEMINI_KEY_INDEX
    attempts = 0
    while attempts < len(GEMINI_KEYS):
        key = GEMINI_KEYS[GEMINI_KEY_INDEX]
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel(GEMINI_MODELS[0])
            if history:
                chat_s = model.start_chat(history=history)
                response = chat_s.send_message(prompt, stream=True)
            else:
                response = model.generate_content(prompt, stream=True)
            full = ""
            for chunk in response:
                if chunk.text:
                    full += chunk.text
                    stream_callback(chunk.text)
            return full, "gemini"
        except Exception as e:
            err = str(e).lower()
            if "429" in err or "quota" in err or "limit" in err or "exhausted" in err:
                print(f"Gemini key {GEMINI_KEY_INDEX} limit hit, rotating...")
                GEMINI_KEY_INDEX = (GEMINI_KEY_INDEX + 1) % len(GEMINI_KEYS)
                attempts += 1
                continue
            raise e
    raise Exception("All Gemini keys exhausted")

def get_groq_response(prompt: str, history: list, stream_callback):
    """Try all Groq keys in rotation"""
    global GROQ_KEY_INDEX
    attempts = 0
    while attempts < len(GROQ_KEYS):
        key = GROQ_KEYS[GROQ_KEY_INDEX]
        try:
            from groq import Groq
            client = Groq(api_key=key)
            messages = []
            for h in history:
                role = "assistant" if h["role"] == "model" else "user"
                messages.append({"role": role, "content": h["parts"][0]})
            messages.append({"role": "user", "content": prompt})
            stream = client.chat.completions.create(
                model=GROQ_MODELS[0],
                messages=messages,
                max_tokens=2048,
                stream=True
            )
            full = ""
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    full += delta
                    stream_callback(delta)
            return full, "groq"
        except Exception as e:
            err = str(e).lower()
            if "429" in err or "quota" in err or "limit" in err or "rate" in err:
                print(f"Groq key {GROQ_KEY_INDEX} limit hit, rotating...")
                GROQ_KEY_INDEX = (GROQ_KEY_INDEX + 1) % len(GROQ_KEYS)
                attempts += 1
                continue
            raise e
    raise Exception("All Groq keys exhausted")

def get_cloudflare_response(prompt: str, stream_callback):
    """Cloudflare Workers AI — always free fallback"""
    CF_TOKEN   = os.environ.get("CF_API_TOKEN", "")
    CF_ACCOUNT = os.environ.get("CF_ACCOUNT_ID", "")
    if not CF_TOKEN or not CF_ACCOUNT:
        raise Exception("Cloudflare not configured")
    url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT}/ai/run/@cf/meta/llama-3-8b-instruct"
    resp = httpx.post(url,
        headers={"Authorization": f"Bearer {CF_TOKEN}"},
        json={"messages": [{"role": "user", "content": prompt}], "stream": False},
        timeout=30
    )
    text = resp.json().get("result", {}).get("response", "Sorry, I couldn't process that.")
    stream_callback(text)
    return text, "cloudflare"

# ── Supabase ──
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

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
<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;background:#0a0a0f;font-family:'Segoe UI',sans-serif;">
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
</body>
</html>"""
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_PASS)
            server.sendmail(GMAIL_USER, to_email, msg.as_string())
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False

# ── DB helpers ──
def db_get_user(email):
    if not supabase: return None
    try:
        r = supabase.table("users").select("*").eq("email", email).execute()
        return r.data[0] if r.data else None
    except: return None

def db_create_user(name, email, password, phone=""):
    if not supabase: raise HTTPException(500, "Database not configured")
    try:
        r = supabase.table("users").insert({
            "name": name, "email": email,
            "password_hash": hash_pw(password), "phone": phone,
            "created_at": datetime.now(timezone.utc).isoformat()
        }).execute()
        return r.data[0]
    except Exception as e:
        raise HTTPException(400, f"Could not create user: {e}")

def db_update_user(email, data):
    if not supabase: return
    supabase.table("users").update(data).eq("email", email).execute()

def db_get_chats(email):
    if not supabase: return []
    try:
        r = supabase.table("chats").select("*").eq("user_email", email).order("updated_at", desc=True).execute()
        return r.data or []
    except: return []

def db_save_chats(email, chats):
    if not supabase: return
    try:
        supabase.table("chats").delete().eq("user_email", email).execute()
        if chats:
            rows = [{"id": str(c.get("id","")), "user_email": email, "title": c.get("title","New chat"),
                     "messages": json.dumps(c.get("messages",[])), "pinned": c.get("pinned", False),
                     "created_at": str(c.get("createdAt", datetime.now(timezone.utc).isoformat())),
                     "updated_at": datetime.now(timezone.utc).isoformat()} for c in chats]
            supabase.table("chats").insert(rows).execute()
    except Exception as e:
        print(f"Chat save error: {e}")

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
    return {
        "status": "MyAI running with auto key rotation",
        "time": NOW(),
        "gemini_keys": len(GEMINI_KEYS),
        "groq_keys": len(GROQ_KEYS),
        "db": bool(supabase)
    }

@app.post("/register")
def register(req: RegisterRequest):
    if db_get_user(req.email):
        raise HTTPException(400, "Email already registered. Please login.")
    user = db_create_user(req.name, req.email, req.password, req.phone or "")
    return {"success": True, "name": user["name"], "email": user["email"]}

@app.post("/login")
def login(req: LoginRequest):
    user = db_get_user(req.email)
    if not user: raise HTTPException(401, "Email not found. Please register.")
    if not check_pw(req.password, user["password_hash"]):
        raise HTTPException(401, "Wrong password.")
    return {"success": True, "name": user["name"], "email": user["email"], "phone": user.get("phone","")}

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
    sent = send_otp_email(req.email, otp, user.get("name","User"))
    if sent:
        return {"success": True, "message": f"✅ OTP sent to {req.email}! Check your inbox."}
    return {"success": True, "otp": otp, "message": f"⚠️ Email not configured. Your OTP is: {otp}"}

@app.post("/reset-password")
def reset_password(req: ResetPasswordRequest):
    record = otps_db.get(req.email)
    if not record: raise HTTPException(400, "OTP not found. Request a new one.")
    if datetime.now(timezone.utc).timestamp() - record["time"] > 600:
        del otps_db[req.email]
        raise HTTPException(400, "OTP expired. Request a new one.")
    if record["otp"] != req.otp: raise HTTPException(400, "Wrong OTP.")
    db_update_user(req.email, {"password_hash": hash_pw(req.new_password)})
    del otps_db[req.email]
    return {"success": True}

@app.get("/chats/{email}")
def get_chats(email: str):
    raw = db_get_chats(email)
    chats = [{"id": r.get("id"), "title": r.get("title","New chat"),
               "messages": json.loads(r.get("messages","[]")),
               "pinned": r.get("pinned", False), "createdAt": r.get("created_at","")} for r in raw]
    return {"chats": chats}

@app.post("/chats/{email}")
def save_chats(email: str, body: dict):
    db_save_chats(email, body.get("chats",[]))
    return {"success": True}

@app.post("/chat")
def chat(request: ChatRequest):
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
        except Exception as e:
            search_context = f"\n[Search error: {e}]"

    system = f"""You are MyAI, a powerful AI assistant like ChatGPT.
Current date and time: {now}

FORMATTING RULES:
- Use **bold** for important terms
- Use ## headings, ### subheadings
- Use bullet lists and numbered lists
- Use markdown tables for comparisons
- Wrap code in triple backticks with language
- Make ALL URLs clickable as [Text](url)
- Add relevant emojis 🎯
- Be warm, friendly and conversational
{search_context}"""

    messages = request.messages
    history = [{"role": "model" if m.role == "assistant" else "user",
                 "parts": [m.content]} for m in messages[:-1]]
    last_msg = messages[-1].content if messages else ""
    full_prompt = f"{system}\n\nUser: {last_msg}"

    def generate():
        collected = []

        def on_text(text):
            collected.append(text)

        try:
            # 1. Try Gemini keys (rotate automatically)
            if GEMINI_KEYS:
                try:
                    get_gemini_response(full_prompt, history, lambda t: None)
                    # Stream properly
                    global GEMINI_KEY_INDEX
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
                    if "429" in err or "quota" in err or "limit" in err:
                        print("All Gemini keys exhausted, trying Groq...")
                    else:
                        yield f"data: {json.dumps({'text': f'❌ Gemini error: {str(e)}'})}\n\n"
                        yield "data: [DONE]\n\n"
                        return

            # 2. Try Groq keys (rotate automatically)
            if GROQ_KEYS:
                try:
                    from groq import Groq
                    global GROQ_KEY_INDEX
                    groq_msgs = []
                    groq_msgs.append({"role": "user", "content": system})
                    for h in history:
                        role = "assistant" if h["role"] == "model" else "user"
                        groq_msgs.append({"role": role, "content": h["parts"][0]})
                    groq_msgs.append({"role": "user", "content": last_msg})

                    attempts = 0
                    while attempts < len(GROQ_KEYS):
                        try:
                            client = Groq(api_key=GROQ_KEYS[GROQ_KEY_INDEX])
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
                            if "429" in err or "quota" in err or "rate" in err:
                                GROQ_KEY_INDEX = (GROQ_KEY_INDEX + 1) % len(GROQ_KEYS)
                                attempts += 1
                            else:
                                raise e
                except Exception as e:
                    print(f"All Groq keys exhausted: {e}")

            # 3. Final fallback message
            yield f"data: {json.dumps({'text': '⚠️ All AI keys have hit their daily limit. Please try again tomorrow or add more API keys in Railway settings.'})}\n\n"
            yield "data: [DONE]\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'text': f'❌ Error: {str(e)}'})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
