from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import uuid
from datetime import datetime
import os
import smtplib
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from supabase import create_client, Client

# --- YAPILANDIRMA ---
GMAIL_USER = "kaybedenvarmi@gmail.com"
GMAIL_PASS = "hvpj qhwz feoe wkid"

# SUPABASE PROJESİ: kcqikeyytshemptxbvxz
SUPABASE_URL = "https://kcqikeyytshemptxbvxz.supabase.co"
# En güncel anon public key yerleştirildi
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImtjcWlrZXl5dHNoZW1wdHhidnh6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzYyNTQzNjYsImV4cCI6MjA5MTgzMDM2Nn0.LyFRsohwV9YKT3W5BxsEhuzRsfLyxG0ppZ0H3ldPLZU"

# Supabase istemcisini başlat
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

app = FastAPI()

# CORS Ayarları: Frontend erişimi için tam izin
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

class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    phoneNumber: Optional[str] = None
    newPasswordHash: Optional[str] = None

class CommentCreate(BaseModel):
    postId: str
    userId: str
    text: str

# --- YARDIMCI FONKSİYONLAR ---

def send_verification_email(email: str, code: str):
    """Kullanıcıya e-posta doğrulama linki gönderir."""
    verify_link = f"https://kaybeden-ve-bulunan-bulut-api.vercel.app/users/verify-link?email={email}&code={code}"
    
    msg = MIMEMultipart()
    msg["From"] = GMAIL_USER
    msg["To"] = email
    msg["Subject"] = "Kayıp ve Bulunan - Hesap Doğrulama"
    
    body = f"""
    Merhaba,
    
    Kayıp ve Bulunan uygulamasına kayıt olduğunuz için teşekkürler.
    Hesabınızı aktifleştirmek için lütfen aşağıdaki linke tıklayın:
    
    {verify_link}
    
    Keyifli kullanımlar dileriz.
    """
    msg.attach(MIMEText(body, "plain"))
    
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_PASS)
            server.sendmail(GMAIL_USER, email, msg.as_string())
    except Exception as e:
        print(f"EMAIL ERROR: E-posta gönderilemedi: {e}")

# --- API UÇLARI ---

@app.get("/")
def read_root():
    return {
        "mesaj": "Kayıp ve Bulunan API Vercel'de Aktif!",
        "veritabani": "Supabase REST API",
        "proje": "kcqikeyytshemptxbvxz",
        "durum": "Sistemler çalışıyor (V2.1)"
    }

# --- KULLANICI İŞLEMLERİ ---

@app.post("/users/register")
def register(user: UserCreate):
    user_id = str(uuid.uuid4())
    code = str(random.randint(100000, 999999))
    try:
        # Email kontrolü
        existing = supabase.table('users').select('*').eq('email', user.email).execute()
        if existing.data and len(existing.data) > 0:
            raise HTTPException(status_code=400, detail="Bu e-posta adresi zaten kayıtlı.")
        
        # Kayıt
        supabase.table('users').insert({
            "id": user_id, "email": user.email, "name": user.name,
            "phoneNumber": user.phoneNumber, "passwordHash": user.passwordHash,
            "createdAt": datetime.now().isoformat(), "verificationCode": code,
            "isVerified": 0, "isAdmin": 0
        }).execute()
        
        send_verification_email(user.email, code)
        return {"message": "Kayıt başarılı. Lütfen e-postanızı kontrol edin."}
    except Exception as e:
        if isinstance(e, HTTPException): raise e
        raise HTTPException(status_code=500, detail=f"Kayıt hatası: {str(e)}")

@app.post("/users/login")
def login(data: UserLogin):
    try:
        result = supabase.table('users').select('*').eq('email', data.email).eq('passwordHash', data.passwordHash).execute()
        if not result.data:
            raise HTTPException(status_code=401, detail="E-posta veya şifre yanlış.")
        
        user = result.data[0]
        if not user.get("isVerified"):
            raise HTTPException(status_code=403, detail="Lütfen e-postanızı doğrulayın.")
        
        return {"id": user["id"], "name": user["name"], "email": user["email"], "isAdmin": user.get("isAdmin", 0)}
    except Exception as e:
        if isinstance(e, HTTPException): raise e
        raise HTTPException(status_code=500, detail="Giriş sırasında bir hata oluştu.")

@app.get("/users/verify-link")
def verify_link(email: str, code: str):
    try:
        result = supabase.table('users').select('*').eq('email', email).eq('verificationCode', code).execute()
        if not result.data:
            return HTMLResponse(content="<h2>Geçersiz link.</h2>", status_code=400)
        
        supabase.table('users').update({"isVerified": 1, "verificationCode": None}).eq('email', email).execute()
        return HTMLResponse(content="<div style='text-align:center;margin-top:100px;'><h1>✓ Doğrulandı</h1><a href='https://www.kaybedenvebulan.com.tr'>Siteye Dön</a></div>")
    except Exception as e:
        return HTMLResponse(content=f"<h2>Hata: {str(e)}</h2>", status_code=500)

@app.patch("/users/{user_id}")
def update_profile(user_id: str, data: ProfileUpdate):
    try:
        update_dict = {k: v for k, v in data.dict().items() if v is not None}
        if "newPasswordHash" in update_dict:
            update_dict["passwordHash"] = update_dict.pop("newPasswordHash")
        
        if update_dict:
            supabase.table('users').update(update_dict).eq('id', user_id).execute()
        return {"message": "Profil güncellendi"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Güncelleme hatası: {str(e)}")

# --- İLAN VE YORUM İŞLEMLERİ ---

@app.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    try:
        ext = os.path.splitext(file.filename)[1]
        filename = f"{uuid.uuid4()}{ext}"
        file_content = await file.read()
        supabase.storage.from_("images").upload(path=filename, file=file_content, file_options={"content-type": file.content_type})
        return {"imageUrl": supabase.storage.from_("images").get_public_url(filename)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Resim yükleme hatası: {str(e)}")

@app.get("/posts")
def get_posts():
    try:
        result = supabase.table('posts').select('*').eq('status', 'approved').order('datePosted', desc=True).execute()
        return result.data
    except: return []

@app.post("/posts")
def create_post(post: PostCreate):
    try:
        data = post.dict()
        data["id"] = str(uuid.uuid4())
        data["datePosted"] = datetime.now().isoformat()
        data["status"] = "pending"
        supabase.table('posts').insert(data).execute()
        return {"message": "İlan onay bekliyor."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/comments/{post_id}")
def get_comments(post_id: str):
    try:
        result = supabase.table('comments').select('*').eq('postId', post_id).execute()
        return result.data
    except: return []

@app.post("/comments")
def add_comment(comment: CommentCreate):
    try:
        data = comment.dict()
        data["id"] = str(uuid.uuid4())
        data["datePosted"] = datetime.now().isoformat()
        supabase.table('comments').insert(data).execute()
        return {"message": "Yorum eklendi"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- ADMIN İŞLEMLERİ ---

@app.get("/posts/pending")
def get_pending_posts():
    try:
        result = supabase.table('posts').select('*').eq('status', 'pending').execute()
        return result.data
    except: return []

@app.patch("/posts/{post_id}/status")
def update_post_status(post_id: str, status: str):
    try:
        supabase.table('posts').update({"status": status}).eq('id', post_id).execute()
        return {"message": f"Durum {status} yapıldı"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
