# MyAI v3 — Full Setup & Deployment Guide

## Local Setup

### Backend
```
cd myai-v3\backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
notepad .env
```

Add to .env:
```
GROQ_API_KEY=gsk_your_key
TAVILY_API_KEY=tvly_your_key
GMAIL_USER=youremail@gmail.com
GMAIL_PASS=your_app_password
```

Start:
```
uvicorn main:app --reload --port 8000
```

### Frontend
```
cd myai-v3\frontend
copy .env.example .env
npm install
npm run dev
```

Open: http://localhost:3000

---

## Get Gmail App Password (for real OTP emails)

1. Go to https://myaccount.google.com
2. Security → 2-Step Verification → turn ON
3. Search "App passwords" in Google account
4. Select app: Mail, device: Windows
5. Copy the 16-digit password
6. Paste in .env as GMAIL_PASS=xxxx xxxx xxxx xxxx

---

## Deploy Online (FREE)

### Step 1 — Push to GitHub
1. Go to https://github.com and create account
2. Create new repository called "myai"
3. Upload all files from myai-v3 folder

### Step 2 — Deploy Backend on Railway (FREE)
1. Go to https://railway.app
2. Sign up with GitHub
3. New Project → Deploy from GitHub → select myai repo
4. Set Root Directory: backend
5. Add environment variables:
   - GROQ_API_KEY = your key
   - TAVILY_API_KEY = your key
   - GMAIL_USER = your gmail
   - GMAIL_PASS = your app password
6. Railway gives you URL like: https://myai-backend.up.railway.app
7. Copy this URL

### Step 3 — Deploy Frontend on Vercel (FREE)
1. Go to https://vercel.com
2. Sign up with GitHub
3. New Project → Import myai repo
4. Set Root Directory: frontend
5. Add environment variable:
   - VITE_API_URL = https://myai-backend.up.railway.app
6. Deploy!
7. Vercel gives you URL like: https://myai.vercel.app

### Done! Share your URL with anyone in the world!

---

## Features
- Login / Signup / Forgot password with real OTP to email
- Real-time web search (Tavily)
- Image generation (Pollinations - free)
- Voice input + voice reply
- Rich markdown: bold, headings, tables, code blocks with copy
- Clickable links in responses
- Pin up to 3 chats
- Delete chats
- Share chat
- Chat history per user
- Current date/time awareness
