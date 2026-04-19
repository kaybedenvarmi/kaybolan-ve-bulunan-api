
import httpx
from fa# === VERCEL ASGI ADAPTÖRÜ ===
# Bu, FastAPI uygulamanızı Vercel'de çalıştırmak için GEREKLİ
from mangum import Mangum

# ... (mevcut import'larınız burada kalacak)
# import httpx
# from fastapi import FastAPI...
# ...

# App oluşturulduktan SONRA, en alta ekleyin:
app = FastAPI()

# ... (tüm route'larınız burada)

# === VERCEL HANDLER ===
# Bu SATIR ÇOK ÖNEMLİ - Vercel'in çağıracağı fonksiyon
handler = Mangum(app)stapi import FastAPI, HTTPException, UploadFile, File, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import uuid
from datetime import datetime
import os
import traceback

# --- MONKEYPATCH FOR HTTPX PROXY ERROR ---
# Bu blok, Supabase kütüphanesinin httpx'e geçersiz 'proxy' parametresi göndermesini engeller.
original_init = httpx.Client.__init__

def patched_init(self, *args, **kwargs):
    if "proxy" in kwargs:
        # Eğer 'proxy' varsa ve 'proxies' yoksa, parametreyi dönüştür veya sil
        if "proxies" not in kwargs:
            kwargs["proxies"] = kwargs.pop("proxy")
        else:
            kwargs.pop("proxy")
    original_init(self, *args, **kwargs)

httpx.Client.__init__ = patched_init
# -----------------------------------------

from supabase import create_client, Client

# --- CONFIGURATION ---
SUPABASE_URL = "https://kcqikeyytshemptxbvxz.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImtjcWlrZXl5dHNoZW1wdHhidnh6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzYyNTQzNjYsImV4cCI6MjA5MTgzMDM2Nn0.LyFRsohwV9YKT3W5BxsEhuzRsfLyxG0ppZ0H3ldPLZU"

_supabase: Optional[Client] = None

def get_supabase() -> Client:
    global _supabase
    if _supabase is None:
        try:
            # Yamalı httpx ile güvenli başlatma
            _supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        except Exception as e:
            print(f"CRITICAL: Supabase connection failed: {str(e)}")
            raise RuntimeError(f"Database connection failed: {str(e)}")
    return _supabase

app = FastAPI()

# Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    error_trace = traceback.format_exc()
    print(f"LOGS: {error_trace}")
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": str(exc)}
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- MODELS ---
class UserCreate(BaseModel):
    name: str
    email: str
    passwordHash: str
    phoneNumber: Optional[str] = None

class UserLogin(BaseModel):
    email: str
    passwordHash: str

class PostCreate(BaseModel):
    userId: str
    title: str
    description: str
    category: str
    type: str
    imageUrl: Optional[str] = ""
    location: Optional[str] = None
    contactInfo: Optional[str] = None

class CommentCreate(BaseModel):
    postId: str
    userId: str
    text: str

# --- ROUTES ---

@app.get("/")
def read_root():
    db_status = "disconnected"
    try:
        client = get_supabase()
        client.table('users').select('id').limit(1).execute()
        db_status = "connected"
    except Exception as e:
        print(f"Status check failed: {e}")

    return {
        "status": "active",
        "version": "2.2.4-patch",
        "database": db_status
    }

@app.post("/users/register")
def register(user: UserCreate):
    db = get_supabase()
    user_id = str(uuid.uuid4())
    try:
        existing = db.table('users').select('id').eq('email', user.email).execute()
        if existing.data:
            raise HTTPException(status_code=400, detail="E-posta zaten kayıtlı.")
        
        db.table('users').insert({
            "id": user_id, 
            "email": user.email, 
            "name": user.name,
            "phoneNumber": user.phoneNumber, 
            "passwordHash": user.passwordHash,
            "createdAt": datetime.now().isoformat(), 
            "isVerified": 1, 
            "isAdmin": 0
        }).execute()
        
        return {"message": "Kayıt başarılı", "userId": user_id}
    except Exception as e:
        if isinstance(e, HTTPException): raise e
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/users/login")
def login(data: UserLogin):
    db = get_supabase()
    try:
        result = db.table('users').select('*').eq('email', data.email).eq('passwordHash', data.passwordHash).execute()
        if not result.data:
            raise HTTPException(status_code=401, detail="E-posta veya şifre yanlış.")
        return result.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/posts")
def get_posts():
    db = get_supabase()
    try:
        result = db.table('posts').select('*').eq('status', 'approved').order('datePosted', desc=True).execute()
        return result.data
    except:
        return []

@app.post("/posts")
def create_post(post: PostCreate):
    db = get_supabase()
    try:
        data = post.dict()
        data["id"] = str(uuid.uuid4())
        data["datePosted"] = datetime.now().isoformat()
        data["status"] = "pending"
        db.table('posts').insert(data).execute()
        return {"message": "İlan oluşturuldu."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    db = get_supabase()
    try:
        ext = os.path.splitext(file.filename)[1]
        filename = f"{uuid.uuid4()}{ext}"
        content = await file.read()
        db.storage.from_("images").upload(path=filename, file=content)
        url = db.storage.from_("images").get_public_url(filename)
        return {"imageUrl": url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        # En altta, tüm route'lardan sonra
handler = Mangum(app)
        
