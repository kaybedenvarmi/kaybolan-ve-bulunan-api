from mangum import Mangum
from fastapi import FastAPI, HTTPException, UploadFile, File, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import uuid
from datetime import datetime
import os
import traceback
from supabase import create_client, Client

# --- YAPILANDIRMA ---
SUPABASE_URL = "https://kcqikeyytshemptxbvxz.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImtjcWlrZXl5dHNoZW1wdHhidnh6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzYyNTQzNjYsImV4cCI6MjA5MTgzMDM2Nn0.LyFRsohwV9YKT3W5BxsEhuzRsfLyxG0ppZ0H3ldPLZU"

_supabase: Optional[Client] = None

def get_supabase() -> Client:
    global _supabase
    if _supabase is None:
        try:
            _supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        except Exception as e:
            print(f"KRİTİK HATA: Supabase bağlantısı kurulamadı: {str(e)}")
            raise RuntimeError(f"Veritabanı bağlantı hatası: {str(e)}")
    return _supabase

app = FastAPI(title="Kaybeden ve Bulan Kurumsal API", version="3.0.0")

# --- CORS AYARLARI ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- VERİ MODELLERİ ---
class UserCreate(BaseModel):
    name: str
    email: str
    passwordHash: str
    phoneNumber: Optional[str] = None

class PostCreate(BaseModel):
    userId: str
    title: str
    description: str
    category: str  # Örn: 'Elektronik', 'Cüzdan', 'Evcil Hayvan'
    type: str      # 'lost' (Kayıp) veya 'found' (Bulundu)
    imageUrl: Optional[str] = ""
    locationName: Optional[str] = "" # Örn: 'Kadıköy Sahil'
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    contactInfo: Optional[str] = None

# --- ROTALAR ---

@app.get("/")
def read_root():
    return {
        "status": "online",
        "message": "Kaybeden ve Bulan Profesyonel API Servisi Çalışıyor",
        "timestamp": datetime.now().isoformat()
    }

# --- ADMIN DASHBOARD ROTALARI ---

@app.get("/admin/stats")
def get_admin_stats():
    """Admin paneli için özet istatistikleri döndürür."""
    db = get_supabase()
    try:
        # İstatistikleri paralel gibi çekiyoruz
        users_count = db.table('users').select('id', count='exact').execute()
        pending_posts = db.table('posts').select('id', count='exact').eq('status', 'pending').execute()
        approved_posts = db.table('posts').select('id', count='exact').eq('status', 'approved').execute()
        
        return {
            "totalUsers": users_count.count,
            "pendingApprovals": pending_posts.count,
            "activePosts": approved_posts.count,
            "systemHealth": "Excellent"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/pending-posts")
def get_pending_posts():
    """Onay bekleyen ilanları listeler (Sadece admin için)."""
    db = get_supabase()
    result = db.table('posts').select('*').eq('status', 'pending').order('datePosted', desc=True).execute()
    return result.data

@app.post("/admin/approve-post/{post_id}")
def approve_post(post_id: str):
    """İlanı onaylar ve yayına alır."""
    db = get_supabase()
    db.table('posts').update({"status": "approved"}).eq('id', post_id).execute()
    return {"message": "İlan başarıyla onaylandı ve yayına alındı."}

# --- KULLANICI İŞLEMLERİ ---

@app.post("/users/register")
def register(user: UserCreate):
    db = get_supabase()
    user_id = str(uuid.uuid4())
    try:
        existing = db.table('users').select('id').eq('email', user.email).execute()
        if existing.data:
            raise HTTPException(status_code=400, detail="Bu e-posta adresi zaten kayıtlı.")
        
        db.table('users').insert({
            "id": user_id, 
            "email": user.email, 
            "name": user.name,
            "phoneNumber": user.phoneNumber, 
            "passwordHash": user.passwordHash,
            "createdAt": datetime.now().isoformat(), 
            "isVerified": True, 
            "isAdmin": False
        }).execute()
        
        return {"status": "success", "userId": user_id, "message": "Hoş geldiniz! Hesabınız oluşturuldu."}
    except Exception as e:
        if isinstance(e, HTTPException): raise e
        raise HTTPException(status_code=500, detail=str(e))

# --- İLAN İŞLEMLERİ ---

@app.get("/posts")
def get_posts(category: Optional[str] = None, type: Optional[str] = None):
    """Filtrelenebilir ilan listesi."""
    db = get_supabase()
    query = db.table('posts').select('*').eq('status', 'approved')
    
    if category:
        query = query.eq('category', category)
    if type:
        query = query.eq('type', type)
        
    result = query.order('datePosted', desc=True).execute()
    return result.data

@app.post("/posts")
def create_post(post: PostCreate):
    db = get_supabase()
    try:
        post_data = post.dict()
        post_data["id"] = str(uuid.uuid4())
        post_data["datePosted"] = datetime.now().isoformat()
        post_data["status"] = "pending"
        
        db.table('posts').insert(post_data).execute()
        return {"status": "success", "message": "İlanınız sisteme iletildi. Kontrol sonrası yayınlanacaktır."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    db = get_supabase()
    try:
        ext = os.path.splitext(file.filename)[1]
        filename = f"post_{uuid.uuid4()}{ext}"
        content = await file.read()
        
        db.storage.from_("images").upload(path=filename, file=content)
        url = db.storage.from_("images").get_public_url(filename)
        return {"imageUrl": url, "filename": filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Görsel yüklenirken bir hata oluştu.")

handler = Mangum(app)
