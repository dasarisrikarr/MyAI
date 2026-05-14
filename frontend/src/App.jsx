import { useState, useRef, useEffect } from "react";
import "./App.css";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";

// ── Markdown renderer ──
function MD({ content }) {
  const lines = content.split("\n");
  const els = []; let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (line.includes("|") && lines[i+1]?.includes("---")) {
      const headers = line.split("|").filter(c=>c.trim()).map(c=>c.trim());
      i += 2;
      const rows = [];
      while (i < lines.length && lines[i].includes("|")) { rows.push(lines[i].split("|").filter(c=>c.trim()).map(c=>c.trim())); i++; }
      els.push(<div key={i} className="table-wrap"><table className="md-table"><thead><tr>{headers.map((h,j)=><th key={j}><Inline text={h}/></th>)}</tr></thead><tbody>{rows.map((row,ri)=><tr key={ri}>{row.map((cell,ci)=><td key={ci}><Inline text={cell}/></td>)}</tr>)}</tbody></table></div>);
      continue;
    }
    if (line.startsWith("```")) {
      const lang = line.slice(3).trim()||"code"; const codeLines = []; i++;
      while (i < lines.length && !lines[i].startsWith("```")) { codeLines.push(lines[i]); i++; }
      els.push(<CodeBlock key={i} lang={lang} code={codeLines.join("\n")}/>); i++; continue;
    }
    if (line.startsWith("## ")) { els.push(<h2 key={i} className="md-h2"><Inline text={line.slice(3)}/></h2>); i++; continue; }
    if (line.startsWith("### ")) { els.push(<h3 key={i} className="md-h3"><Inline text={line.slice(4)}/></h3>); i++; continue; }
    if (line.startsWith("# ")) { els.push(<h1 key={i} className="md-h1"><Inline text={line.slice(2)}/></h1>); i++; continue; }
    if (line.match(/^[-*] /)) { els.push(<li key={i} className="md-li"><Inline text={line.slice(2)}/></li>); i++; continue; }
    if (line.match(/^\d+\. /)) { els.push(<li key={i} className="md-oli"><Inline text={line.replace(/^\d+\.\s/,"")}/></li>); i++; continue; }
    if (line.trim()==="") { els.push(<div key={i} className="md-spacer"/>); i++; continue; }
    els.push(<p key={i} className="md-p"><Inline text={line}/></p>); i++;
  }
  return <div className="md-body">{els}</div>;
}

function Inline({ text }) {
  const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|\[[^\]]+\]\([^)]+\))/g);
  return <>{parts.map((p,i)=>{
    if (p.startsWith("**")&&p.endsWith("**")) return <strong key={i}>{p.slice(2,-2)}</strong>;
    if (p.startsWith("*")&&p.endsWith("*")) return <em key={i}>{p.slice(1,-1)}</em>;
    if (p.startsWith("`")&&p.endsWith("`")) return <code key={i} className="icode">{p.slice(1,-1)}</code>;
    const lm = p.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
    if (lm) return <a key={i} href={lm[2]} target="_blank" rel="noreferrer" className="md-link">{lm[1]}</a>;
    return <span key={i}>{p}</span>;
  })}</>;
}

function CodeBlock({ lang, code }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="code-block">
      <div className="code-header">
        <span className="code-lang">{lang}</span>
        <button className="copy-btn" onClick={()=>{navigator.clipboard.writeText(code);setCopied(true);setTimeout(()=>setCopied(false),2000);}}>
          {copied?"✓ Copied!":"Copy"}
        </button>
      </div>
      <pre className="code-body"><code>{code}</code></pre>
    </div>
  );
}

function ImageGen({ prompt }) {
  const url = `https://image.pollinations.ai/prompt/${encodeURIComponent(prompt)}?width=512&height=512&nologo=true`;
  const [loaded, setLoaded] = useState(false);
  return (
    <div className="img-gen-wrap">
      {!loaded && <div className="img-loading">🎨 Generating image…</div>}
      <img src={url} alt={prompt} className="gen-img" onLoad={()=>setLoaded(true)} style={{display:loaded?"block":"none"}}/>
      {loaded && <a href={url} download className="dl-btn" target="_blank" rel="noreferrer">⬇ Download</a>}
    </div>
  );
}

// ── Delete Confirm Modal ──
function ConfirmModal({ msg, onYes, onNo }) {
  return (
    <div className="modal-overlay">
      <div className="modal-box">
        <p className="modal-msg">{msg}</p>
        <div className="modal-btns">
          <button className="modal-no" onClick={onNo}>Cancel</button>
          <button className="modal-yes" onClick={onYes}>Delete</button>
        </div>
      </div>
    </div>
  );
}

// ── Profile Modal ──
function ProfileModal({ user, onClose, onSave }) {
  const [name, setName] = useState(user.name);
  const [phone, setPhone] = useState(user.phone||"");
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");

  const save = async () => {
    setSaving(true);
    const r = await fetch(`${API}/update-profile`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({email:user.email,name,phone})});
    const d = await r.json();
    setSaving(false);
    if (d.success) { setMsg("✅ Profile updated!"); onSave({...user,name,phone}); setTimeout(onClose,1200); }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-box profile-modal" onClick={e=>e.stopPropagation()}>
        <div className="profile-avatar-big">{user.name[0].toUpperCase()}</div>
        <h3 className="profile-title">Your Profile</h3>
        <input className="auth-input" value={name} onChange={e=>setName(e.target.value)} placeholder="Name"/>
        <input className="auth-input" value={user.email} disabled style={{opacity:0.5}} placeholder="Email"/>
        <input className="auth-input" value={phone} onChange={e=>setPhone(e.target.value)} placeholder="Phone (optional)"/>
        {msg && <div className="auth-msg">{msg}</div>}
        <div className="modal-btns">
          <button className="modal-no" onClick={onClose}>Cancel</button>
          <button className="modal-yes" style={{background:"var(--accent)"}} onClick={save} disabled={saving}>{saving?"Saving…":"Save Changes"}</button>
        </div>
      </div>
    </div>
  );
}

// ── Auth Page ──
function AuthPage({ onLogin }) {
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({name:"",email:"",password:"",phone:"",otp:"",newPass:""});
  const [msg, setMsg] = useState(""); const [err, setErr] = useState(""); const [loading, setLoading] = useState(false);
  const set = (k,v) => setForm(f=>({...f,[k]:v}));

  const doRegister = async () => {
    if (!form.name||!form.email||!form.password) { setErr("Please fill all fields"); return; }
    setLoading(true); setErr("");
    const r = await fetch(`${API}/register`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({name:form.name,email:form.email,password:form.password,phone:form.phone})});
    const d = await r.json(); setLoading(false);
    if (!r.ok) { setErr(d.detail); return; }
    onLogin(d);
  };

  const doLogin = async () => {
    setLoading(true); setErr("");
    const r = await fetch(`${API}/login`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({email:form.email,password:form.password})});
    const d = await r.json(); setLoading(false);
    if (!r.ok) { setErr(d.detail); return; }
    onLogin(d);
  };

  const doSendOTP = async () => {
    setLoading(true); setErr("");
    const r = await fetch(`${API}/send-otp`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({email:form.email})});
    const d = await r.json(); setLoading(false);
    if (!r.ok) { setErr(d.detail); return; }
    setMsg(d.message); setMode("otp");
  };

  const doReset = async () => {
    setLoading(true); setErr("");
    const r = await fetch(`${API}/reset-password`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({email:form.email,otp:form.otp,new_password:form.newPass})});
    const d = await r.json(); setLoading(false);
    if (!r.ok) { setErr(d.detail); return; }
    setMsg("✅ Password reset! Please login."); setMode("login");
  };

  return (
    <div className="auth-bg">
      <div className="auth-card">
        <div className="auth-logo">✦ MyAI</div>
        <div className="auth-sub">Your personal AI assistant</div>
        {mode==="login"&&<>
          <h2 className="auth-title">Welcome back 👋</h2>
          {err&&<div className="auth-err">{err}</div>}
          {msg&&<div className="auth-msg">{msg}</div>}
          <input className="auth-input" placeholder="Email" value={form.email} onChange={e=>set("email",e.target.value)}/>
          <input className="auth-input" placeholder="Password" type="password" value={form.password} onChange={e=>set("password",e.target.value)} onKeyDown={e=>e.key==="Enter"&&doLogin()}/>
          <button className="auth-btn" onClick={doLogin} disabled={loading}>{loading?"Logging in…":"Login"}</button>
          <div className="auth-links"><span onClick={()=>{setMode("forgot");setErr("");}}>Forgot password?</span><span onClick={()=>{setMode("register");setErr("");}}>Create account →</span></div>
        </>}
        {mode==="register"&&<>
          <h2 className="auth-title">Create account 🚀</h2>
          {err&&<div className="auth-err">{err}</div>}
          <input className="auth-input" placeholder="Your name" value={form.name} onChange={e=>set("name",e.target.value)}/>
          <input className="auth-input" placeholder="Email" value={form.email} onChange={e=>set("email",e.target.value)}/>
          <input className="auth-input" placeholder="Phone (optional)" value={form.phone} onChange={e=>set("phone",e.target.value)}/>
          <input className="auth-input" placeholder="Password" type="password" value={form.password} onChange={e=>set("password",e.target.value)}/>
          <button className="auth-btn" onClick={doRegister} disabled={loading}>{loading?"Creating…":"Create Account"}</button>
          <div className="auth-links"><span onClick={()=>{setMode("login");setErr("");}}>← Back to login</span></div>
        </>}
        {mode==="forgot"&&<>
          <h2 className="auth-title">Reset password 🔑</h2>
          {err&&<div className="auth-err">{err}</div>}
          {msg&&<div className="auth-msg">{msg}</div>}
          <input className="auth-input" placeholder="Your email" value={form.email} onChange={e=>set("email",e.target.value)}/>
          <button className="auth-btn" onClick={doSendOTP} disabled={loading}>{loading?"Sending OTP…":"Send OTP to Email"}</button>
          <div className="auth-links"><span onClick={()=>setMode("login")}>← Back to login</span></div>
        </>}
        {mode==="otp"&&<>
          <h2 className="auth-title">Enter OTP 📧</h2>
          {err&&<div className="auth-err">{err}</div>}
          {msg&&<div className="auth-msg">{msg}</div>}
          <input className="auth-input" placeholder="6-digit OTP" value={form.otp} onChange={e=>set("otp",e.target.value)}/>
          <input className="auth-input" placeholder="New password" type="password" value={form.newPass} onChange={e=>set("newPass",e.target.value)}/>
          <button className="auth-btn" onClick={doReset} disabled={loading}>{loading?"Resetting…":"Reset Password"}</button>
        </>}
      </div>
    </div>
  );
}

// ── Main App ──
export default function App() {
  const [user, setUser] = useState(()=>{ const s=localStorage.getItem("myai_user"); return s?JSON.parse(s):null; });
  const [chats, setChats] = useState([]);
  const [activeChatId, setActiveChatId] = useState(null);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [uploadedFile, setUploadedFile] = useState(null);
  const [webSearch, setWebSearch] = useState(false);
  const [ttsEnabled, setTtsEnabled] = useState(false);
  const [listening, setListening] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [toast, setToast] = useState("");
  const [confirm, setConfirm] = useState(null); // {msg, onYes}
  const [showProfile, setShowProfile] = useState(false);
  const [editingMsgIdx, setEditingMsgIdx] = useState(null);
  const [editText, setEditText] = useState("");

  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);
  const fileInputRef = useRef(null);
  const recognitionRef = useRef(null);

  const showToast = (msg) => { setToast(msg); setTimeout(()=>setToast(""),3000); };

  useEffect(()=>{
    if (!user) return;
    fetch(`${API}/chats/${user.email}`).then(r=>r.json()).then(d=>{
      const loaded = d.chats||[];
      if (loaded.length===0) { const f=makeNewChat(); setChats([f]); setActiveChatId(f.id); }
      else { setChats(loaded); setActiveChatId(loaded[0].id); }
    }).catch(()=>{ const f=makeNewChat(); setChats([f]); setActiveChatId(f.id); });
  },[user]);

  useEffect(()=>{
    if (!user||chats.length===0) return;
    fetch(`${API}/chats/${user.email}`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({chats})});
  },[chats]);

  useEffect(()=>{
    const SR = window.SpeechRecognition||window.webkitSpeechRecognition;
    if (SR) {
      const rec = new SR();
      rec.continuous=false; rec.interimResults=false;
      rec.onresult=e=>{setInput(e.results[0][0].transcript);setListening(false);};
      rec.onerror=()=>setListening(false); rec.onend=()=>setListening(false);
      recognitionRef.current=rec;
    }
  },[]);

  useEffect(()=>{ messagesEndRef.current?.scrollIntoView({behavior:"smooth"}); },[chats,activeChatId]);

  const makeNewChat = ()=>({ id:Date.now(), title:"New chat",
    messages:[{role:"assistant",content:"Hello! 👋 I'm **MyAI** — your personal AI assistant powered by Google Gemini.\n\nI can help you with:\n- 💬 **Any question** — coding, writing, math, science\n- 🔍 **Web search** — real-time info (toggle in sidebar)\n- 🎨 **Image generation** — say *draw a sunset*\n- 🎤 **Voice input** — click the mic\n- 🔊 **Voice reply** — toggle in sidebar\n- 📄 **File reading** — upload any file\n- 🌍 **Translation** — 100+ languages\n- 📊 **Tables & charts** — structured comparisons\n\nWhat can I help you with today? ✨"}],
    pinned:false, createdAt:Date.now()
  });

  const handleLogin = (u)=>{ localStorage.setItem("myai_user",JSON.stringify(u)); setUser(u); };
  const handleLogout = ()=>{ localStorage.removeItem("myai_user"); setUser(null); setChats([]); setActiveChatId(null); };
  const handleSaveProfile = (u)=>{ localStorage.setItem("myai_user",JSON.stringify(u)); setUser(u); };

  const newChat = ()=>{ const c=makeNewChat(); setChats(p=>[c,...p]); setActiveChatId(c.id); setUploadedFile(null); setInput(""); };

  const deleteChat = (id)=>{
    setConfirm({ msg:"Delete this chat? This cannot be undone.", onYes:()=>{
      setChats(p=>p.filter(c=>c.id!==id));
      if (activeChatId===id){ const rest=chats.filter(c=>c.id!==id); if(rest.length>0)setActiveChatId(rest[0].id); else{const nc=makeNewChat();setChats([nc]);setActiveChatId(nc.id);} }
      setConfirm(null);
    }});
  };

  const deleteAllChats = ()=>{
    setConfirm({ msg:"Delete ALL chat history? This cannot be undone.", onYes:()=>{
      const nc=makeNewChat(); setChats([nc]); setActiveChatId(nc.id); setConfirm(null);
      showToast("🗑️ All chats deleted");
    }});
  };

  const pinChat = (id,e)=>{
    e.stopPropagation();
    const pinned=chats.filter(c=>c.pinned).length;
    setChats(p=>p.map(c=>{ if(c.id!==id)return c; if(!c.pinned&&pinned>=3){showToast("📌 Max 3 chats can be pinned!");return c;} return{...c,pinned:!c.pinned}; }));
  };

  const shareChat = ()=>{
    const chat=chats.find(c=>c.id===activeChatId); if(!chat)return;
    const text=chat.messages.map(m=>`${m.role==="user"?"You":"MyAI"}: ${m.content}`).join("\n\n");
    navigator.clipboard.writeText(text);
    showToast("✅ Chat copied to clipboard!");
  };

  const refreshChat = ()=>{
    const chat=chats.find(c=>c.id===activeChatId); if(!chat)return;
    const msgs=chat.messages;
    if(msgs.length<2)return;
    // Remove last assistant message and resend
    const withoutLast=msgs.slice(0,-1);
    setChats(p=>p.map(c=>c.id===activeChatId?{...c,messages:withoutLast}:c));
    setTimeout(()=>resendMessages(withoutLast),100);
  };

  const resendMessages = async (msgs)=>{
    setLoading(true);
    setChats(p=>p.map(c=>c.id===activeChatId?{...c,messages:[...msgs,{role:"assistant",content:""}]}:c));
    const apiMsgs=msgs.map(m=>({role:m.role,content:m.content}));
    try{
      const res=await fetch(`${API}/chat`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({messages:apiMsgs,use_search:webSearch,search_query:webSearch?msgs[msgs.length-1].content:""})});
      const reader=res.body.getReader(); const decoder=new TextDecoder(); let full="";
      while(true){
        const{done,value}=await reader.read(); if(done)break;
        for(const line of decoder.decode(value).split("\n")){
          if(line.startsWith("data: ")){const d=line.slice(6);if(d==="[DONE]")break;try{full+=JSON.parse(d).text;setChats(p=>p.map(c=>{if(c.id!==activeChatId)return c;const m=[...c.messages];m[m.length-1]={role:"assistant",content:full};return{...c,messages:m};}));}catch{}}
        }
      }
    }catch{} finally{setLoading(false);}
  };

  const startEdit = (idx,content)=>{ setEditingMsgIdx(idx); setEditText(content); };

  const saveEdit = async ()=>{
    if (!editText.trim()) return;
    const chat=chats.find(c=>c.id===activeChatId); if(!chat)return;
    const msgs=[...chat.messages];
    msgs[editingMsgIdx]={...msgs[editingMsgIdx],content:editText};
    const truncated=msgs.slice(0,editingMsgIdx+1);
    setChats(p=>p.map(c=>c.id===activeChatId?{...c,messages:truncated}:c));
    setEditingMsgIdx(null); setEditText("");
    setTimeout(()=>resendMessages(truncated),100);
  };

  const autoResize=()=>{ const ta=textareaRef.current; if(!ta)return; ta.style.height="auto"; ta.style.height=Math.min(ta.scrollHeight,200)+"px"; };
  const speak=(text)=>{ if(!ttsEnabled)return; window.speechSynthesis.cancel(); const clean=text.replace(/```[\s\S]*?```/g,"code block").replace(/[*`#\[\]]/g,""); const u=new SpeechSynthesisUtterance(clean.slice(0,500)); u.rate=1.05; u.onstart=()=>setSpeaking(true); u.onend=()=>setSpeaking(false); window.speechSynthesis.speak(u); };
  const toggleListen=()=>{ if(!recognitionRef.current)return alert("Use Chrome for voice."); if(listening){recognitionRef.current.stop();setListening(false);}else{recognitionRef.current.start();setListening(true);} };

  const isImageReq=t=>/^(draw|paint|generate image|create image|make image|show me a picture)/i.test(t.trim());
  const imgPrompt=t=>t.replace(/^(draw|paint|generate image of|create image of|make image of|show me a picture of)\s*/i,"").trim();

  const updateActive=(updater)=>setChats(p=>p.map(c=>c.id===activeChatId?updater(c):c));

  const sendMessage=async()=>{
    const text=input.trim(); if((!text&&!uploadedFile)||loading)return;
    if(text&&isImageReq(text)){
      const prompt=imgPrompt(text);
      updateActive(c=>({...c,title:text.slice(0,30)+"…",messages:[...c.messages,{role:"user",content:text},{role:"assistant",content:`🎨 Generating image: **${prompt}**`,imagePrompt:prompt}]}));
      setInput(""); return;
    }
    let userContent=text;
    if(uploadedFile?.type==="text") userContent=`${text?text+"\n\n":""} [File: ${uploadedFile.name}]\n\`\`\`\n${uploadedFile.data.slice(0,10000)}\n\`\`\``;
    if(uploadedFile?.type==="image") userContent=`${text||"Describe this image."}\n[Image: ${uploadedFile.name}]`;
    const userMsg={role:"user",content:userContent,filePreview:uploadedFile};
    const curMsgs=chats.find(c=>c.id===activeChatId)?.messages||[];
    const newMsgs=[...curMsgs,userMsg,{role:"assistant",content:""}];
    setChats(p=>p.map(c=>{if(c.id!==activeChatId)return c; const firstUser=c.messages.find(m=>m.role==="user"); const title=!firstUser?userContent.slice(0,32)+"…":c.title; return{...c,title,messages:newMsgs};}));
    setInput(""); setUploadedFile(null); setLoading(true);
    if(textareaRef.current)textareaRef.current.style.height="auto";
    const apiMsgs=[...curMsgs,userMsg].map(m=>({role:m.role,content:m.content}));
    try{
      const res=await fetch(`${API}/chat`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({messages:apiMsgs,use_search:webSearch,search_query:webSearch?text:""})});
      const reader=res.body.getReader(); const decoder=new TextDecoder(); let full="";
      while(true){
        const{done,value}=await reader.read(); if(done)break;
        for(const line of decoder.decode(value).split("\n")){
          if(line.startsWith("data: ")){const d=line.slice(6);if(d==="[DONE]")break;try{full+=JSON.parse(d).text;setChats(p=>p.map(c=>{if(c.id!==activeChatId)return c;const m=[...c.messages];m[m.length-1]={role:"assistant",content:full};return{...c,messages:m};}));}catch{}}
        }
      }
      speak(full);
    }catch{updateActive(c=>{const m=[...c.messages];m[m.length-1]={role:"assistant",content:"❌ Error connecting to backend."};return{...c,messages:m};});}
    finally{setLoading(false);}
  };

  if(!user) return <AuthPage onLogin={handleLogin}/>;

  const activeChat=chats.find(c=>c.id===activeChatId);
  const messages=activeChat?.messages||[];
  const isEmpty=messages.length===1&&messages[0].role==="assistant";
  const pinnedChats=chats.filter(c=>c.pinned);
  const unpinnedChats=chats.filter(c=>!c.pinned);
  const starters=["🔭 Explain quantum computing","🐍 Write a Python web scraper","🌄 Draw a mountain sunset","📊 Compare React vs Vue in a table"];

  return (
    <div className="app">
      {toast&&<div className="toast">{toast}</div>}
      {confirm&&<ConfirmModal msg={confirm.msg} onYes={confirm.onYes} onNo={()=>setConfirm(null)}/>}
      {showProfile&&<ProfileModal user={user} onClose={()=>setShowProfile(false)} onSave={handleSaveProfile}/>}

      <aside className={`sidebar ${sidebarOpen?"open":"closed"}`}>
        <div className="sidebar-header">
          <span className="logo">✦ MyAI</span>
          <button className="icon-btn" onClick={()=>setSidebarOpen(false)}>✕</button>
        </div>
        <button className="new-chat-btn" onClick={newChat}>+ New chat</button>

        {pinnedChats.length>0&&<>
          <p className="sidebar-label">📌 Pinned</p>
          {pinnedChats.map(c=>(
            <div key={c.id} className={`history-item ${c.id===activeChatId?"active":""}`} onClick={()=>setActiveChatId(c.id)}>
              <span className="hi-title">{c.title}</span>
              <span className="hi-actions">
                <button title="Unpin" onClick={e=>pinChat(c.id,e)}>📌</button>
                <button title="Delete" onClick={e=>{e.stopPropagation();deleteChat(c.id);}}>🗑</button>
              </span>
            </div>
          ))}
          <div className="sidebar-divider"/>
        </>}

        <p className="sidebar-label">💬 Chats</p>
        <div className="chats-scroll">
          {unpinnedChats.map(c=>(
            <div key={c.id} className={`history-item ${c.id===activeChatId?"active":""}`} onClick={()=>setActiveChatId(c.id)}>
              <span className="hi-title">{c.title}</span>
              <span className="hi-actions">
                <button title="Pin" onClick={e=>pinChat(c.id,e)}>📍</button>
                <button title="Delete" onClick={e=>{e.stopPropagation();deleteChat(c.id);}}>🗑</button>
              </span>
            </div>
          ))}
        </div>

        <div className="sidebar-footer">
          <div className="feature-toggle"><span>🔍 Web search</span><label className="toggle"><input type="checkbox" checked={webSearch} onChange={e=>setWebSearch(e.target.checked)}/><span className="slider"/></label></div>
          <div className="feature-toggle"><span>🔊 Voice reply</span><label className="toggle"><input type="checkbox" checked={ttsEnabled} onChange={e=>{setTtsEnabled(e.target.checked);if(!e.target.checked)window.speechSynthesis.cancel();}}/><span className="slider"/></label></div>
          <button className="delete-all-btn" onClick={deleteAllChats}>🗑️ Delete all chats</button>
          <div className="user-row">
            <button className="user-btn" onClick={()=>setShowProfile(true)}>
              <span className="user-avatar">{user.name[0].toUpperCase()}</span>
              <span className="user-name">{user.name}</span>
            </button>
            <button className="logout-btn" onClick={handleLogout}>Logout</button>
          </div>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          {!sidebarOpen&&<button className="icon-btn" onClick={()=>setSidebarOpen(true)}>☰</button>}
          <div style={{flex:1}}/>
          {webSearch&&<span className="badge search-badge">🔍 Live Search</span>}
          {speaking&&<button className="stop-btn" onClick={()=>{window.speechSynthesis.cancel();setSpeaking(false);}}>⏹ Stop</button>}
          {!loading&&messages.length>1&&<button className="icon-btn" title="Regenerate response" onClick={refreshChat}>🔄</button>}
          <button className="share-btn" onClick={shareChat}>🔗 Share</button>
        </header>

        <div className="messages-area">
          {isEmpty?(
            <div className="welcome">
              <div className="welcome-logo">✦</div>
              <h1>Hello, {user.name}! 👋</h1>
              <p className="welcome-sub">How can I help you today?</p>
              <div className="starters">{starters.map((s,i)=><button key={i} className="starter-btn" onClick={()=>{setInput(s.replace(/^[^\s]+\s/,""));textareaRef.current?.focus();}}>{s}</button>)}</div>
            </div>
          ):(
            <div className="messages">
              {messages.map((msg,i)=>(
                <div key={i} className={`message ${msg.role}`}>
                  <div className="avatar">{msg.role==="user"?user.name[0].toUpperCase():"✦"}</div>
                  <div className="bubble">
                    {msg.filePreview?.type==="image"&&<img src={msg.filePreview.data} alt="upload" className="uploaded-img"/>}
                    {msg.filePreview?.type==="text"&&<div className="file-badge">📄 {msg.filePreview.name}</div>}
                    {editingMsgIdx===i?(
                      <div className="edit-box">
                        <textarea className="edit-textarea" value={editText} onChange={e=>setEditText(e.target.value)}/>
                        <div className="edit-actions">
                          <button className="edit-cancel" onClick={()=>setEditingMsgIdx(null)}>Cancel</button>
                          <button className="edit-save" onClick={saveEdit}>Send ↑</button>
                        </div>
                      </div>
                    ):(
                      <>
                        <MD content={msg.content}/>
                        {msg.imagePrompt&&<ImageGen prompt={msg.imagePrompt}/>}
                        {msg.role==="user"&&<button className="edit-btn" onClick={()=>startEdit(i,msg.content)} title="Edit message">✏️</button>}
                      </>
                    )}
                    {i===messages.length-1&&loading&&msg.role==="assistant"&&msg.content===""&&<span className="cursor">▋</span>}
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef}/>
            </div>
          )}
        </div>

        <div className="input-area">
          {uploadedFile&&(
            <div className="file-preview-bar">
              {uploadedFile.type==="image"?<img src={uploadedFile.data} alt="p" className="file-thumb"/>:<span>📄 {uploadedFile.name}</span>}
              <button className="remove-file" onClick={()=>setUploadedFile(null)}>✕</button>
            </div>
          )}
          <div className="input-box">
            <button className="attach-btn" onClick={()=>fileInputRef.current.click()} title="Upload file">📎</button>
            <input ref={fileInputRef} type="file" style={{display:"none"}} accept="image/*,.txt,.py,.js,.html,.css,.json,.csv,.md" onChange={e=>{const f=e.target.files[0];if(!f)return;const r=new FileReader();r.onload=ev=>{if(f.type.startsWith("image/"))setUploadedFile({type:"image",name:f.name,data:ev.target.result});else setUploadedFile({type:"text",name:f.name,data:ev.target.result});};if(f.type.startsWith("image/"))r.readAsDataURL(f);else r.readAsText(f);e.target.value="";}}/>
            <button className={`mic-btn ${listening?"active":""}`} onClick={toggleListen} title="Voice input">{listening?"🔴":"🎤"}</button>
            <textarea ref={textareaRef} value={input} onChange={e=>{setInput(e.target.value);autoResize();}} onKeyDown={e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();sendMessage();}}} placeholder={listening?"🎤 Listening…":"Message MyAI… (or: draw a sunset)"} rows={1} disabled={loading}/>
            <button className={`send-btn ${loading?"loading":""}`} onClick={sendMessage} disabled={loading||(!input.trim()&&!uploadedFile)}>{loading?"●":"↑"}</button>
          </div>
          <p className="disclaimer">✦ MyAI can make mistakes. Verify important info. Say "draw [anything]" to generate images.</p>
        </div>
      </main>
    </div>
  );
}
