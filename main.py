from fastapi import FastAPI, HTTPException, UploadFile, File, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import uuid
from datetime import datetime
import os
import traceback
from supabase import create_client, Client

# --- CONFIGURATION ---
# SUPABASE PROJECT: kcqikeyytshemptxbvxz
SUPABASE_URL = "https://kcqikeyytshemptxbvxz.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImtjcWlrZXl5dHNoZW1wdHhidnh6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzYyNTQzNjYsImV4cCI6MjA5MTgzMDM2Nn0.LyFRsohwV9YKT3W5BxsEhuzRsfLyxG0ppZ0H3ldPLZU"

# Supabase client singleton
_supabase: Optional[Client] = None

def get_supabase() -> Client:
    """
    Returns the Supabase client, initializing it if necessary.
    Uses lazy loading to avoid errors during the initial module import in Vercel.
    """
    global _supabase
    if _supabase is None:
        try:
            # create_client can fail if network is blocked or versions mismatch
            _supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        except Exception as e:
            print(f"SUPABASE CONNECTION ERROR: {str(e)}")
            # Raise a more descriptive error for internal logging
            raise RuntimeError(f"Database connection failed: {str(e)}")
    return _supabase

app = FastAPI()

# Global Exception Handler for debugging in Vercel logs
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    error_trace = traceback.format_exc()
    print(f"CRITICAL ERROR: {error_trace}")
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": str(exc),
            "type": type(exc).__name__
        }
    )

# CORS Configuration
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
    error_detail = None
    try:
        client = get_supabase()
        # Bir basit sorgu ile bağlantıyı doğrula
        client.table('users').select('count', count='exact').limit(1).execute()
        db_status = "connected"
    except Exception as e:
        error_detail = str(e)
        print(f"Root check failed: {error_detail}")

    return {
        "status": "active",
        "version": "2.2.1-stable",
        "database": db_status,
        "diag": error_detail if db_status == "disconnected" else "OK"
    }

@app.get("/health")
def health_check():
    return {"status": "ok", "time": datetime.now().isoformat()}

# --- USER OPERATIONS ---

@app.post("/users/register")
def register(user: UserCreate):
    db = get_supabase()
    user_id = str(uuid.uuid4())
    try:
        # Check existing user
        existing = db.table('users').select('id').eq('email', user.email).execute()
        if existing.data:
            raise HTTPException(status_code=400, detail="E-posta zaten kayıtlı.")
        
        # Insert user
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
        raise HTTPException(status_code=500, detail=f"Kayıt hatası: {str(e)}")

@app.post("/users/login")
def login(data: UserLogin):
    db = get_supabase()
    try:
        result = db.table('users').select('*').eq('email', data.email).eq('passwordHash', data.passwordHash).execute()
        if not result.data:
            raise HTTPException(status_code=401, detail="E-posta veya şifre yanlış.")
        
        user = result.data[0]
        return {"id": user["id"], "name": user["name"], "email": user["email"], "isAdmin": user.get("isAdmin", 0)}
    except Exception as e:
        if isinstance(e, HTTPException): raise e
        raise HTTPException(status_code=500, detail=str(e))

# --- POST OPERATIONS ---

@app.get("/posts")
def get_posts():
    db = get_supabase()
    try:
        result = db.table('posts').select('*').eq('status', 'approved').order('datePosted', desc=True).execute()
        return result.data
    except Exception as e:
        print(f"Fetch error: {e}")
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
        return {"message": "İlan oluşturuldu, onay bekliyor."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"İlan hatası: {str(e)}")

@app.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    db = get_supabase()
    try:
        ext = os.path.splitext(file.filename)[1]
        filename = f"{uuid.uuid4()}{ext}"
        content = await file.read()
        
        db.storage.from_("images").upload(
            path=filename, 
            file=content, 
            file_options={"content-type": file.content_type}
        )
        
        url = db.storage.from_("images").get_public_url(filename)
        return {"imageUrl": url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Yükleme hatası: {str(e)}")

# --- COMMENT OPERATIONS ---

@app.get("/comments/{post_id}")
def get_comments(post_id: str):
    db = get_supabase()
    try:
        result = db.table('comments').select('*').eq('postId', post_id).execute()
        return result.data
    except:
        return []

@app.post("/comments")
def add_comment(comment: CommentCreate):
    db = get_supabase()
    try:
        data = comment.dict()
        data["id"] = str(uuid.uuid4())
        data["datePosted"] = datetime.now().isoformat()
        db.table('comments').insert(data).execute()
        return {"message": "Yorum eklendi"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
