from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import psycopg2
import psycopg2.extras
import uuid
from datetime import datetime
import os
import smtplib
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from supabase import create_client, Client

# --- YAPILANDIRMA ---
# Gmail bilgilerin (Doğrulama mailleri için)
GMAIL_USER = "kaybedenvarmi@gmail.com"
GMAIL_PASS = "hvpj qhwz feoe wkid"

# Supabase PostgreSQL Bağlantısı (db.doukedhgnaonecbeenqx.supabase.co)
DATABASE_URL = "postgresql://postgres:Msbguv.12345!!!!!@db.doukedhgnaonecbeenqx.supabase.co:5432/postgres"

# Supabase Storage ve API Bilgileri
SUPABASE_URL = "https://doukedhgnaonecbeenqx.supabase.co"
# ÖNEMLİ: Supabase panelinden 'service_role' (secret) anahtarını buraya yapıştır!
SUPABASE_KEY = "BURAYA_SERVICE_ROLE_KEY_GELECEK" 

supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

app = FastAPI()

# Flutter ve Web uygulamaları için tam erişim izni
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

def get_db():
    """Supabase PostgreSQL bağlantısını kurar."""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        return conn
    except Exception as e:
        print(f"Veritabanı bağlantı hatası: {e}")
        return None

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

# --- YARDIMCI FONKSİYONLAR ---

def send_verification_email(email: str, code: str):
    """Kullanıcıya e-posta doğrulama linki gönderir."""
    # Vercel üzerindeki canlı URL'n
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
        print(f"E-posta gönderme hatası: {e}")

# --- API UÇLARI (ENDPOINTS) ---

@app.get("/")
def read_root():
    return {
        "mesaj": "Kayıp ve Bulunan API Vercel'de Aktif!",
        "veritabani": "Supabase Bağlı",
        "durum": "Sistemler normal çalışıyor"
    }

@app.post("/users/register")
def register(user: UserCreate):
    conn = get_db()
    if not conn: raise HTTPException(status_code=500, detail="Veritabanına ulaşılamıyor.")
    cur = conn.cursor()
    
    user_id = str(uuid.uuid4())
    code = str(random.randint(100000, 999999))
    
    try:
        cur.execute(
            'INSERT INTO users (id, email, name, "phoneNumber", "passwordHash", "createdAt", "verificationCode", "isVerified") VALUES (%s, %s, %s, %s, %s, %s, %s, 0)',
            (user_id, user.email, user.name, user.phoneNumber, user.passwordHash, datetime.now().isoformat(), code)
        )
        send_verification_email(user.email, code)
        return {"message": "Kayıt başarılı. Lütfen e-postanızı kontrol ederek hesabınızı doğrulayın."}
    except Exception as e:
        if "unique_violation" in str(e).lower() or "already exists" in str(e).lower():
            raise HTTPException(status_code=400, detail="Bu e-posta adresi zaten kayıtlı.")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

@app.post("/users/login")
def login(data: UserLogin):
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute('SELECT * FROM users WHERE email=%s AND "passwordHash"=%s', (data.email, data.passwordHash))
    user = cur.fetchone()
    cur.close()
    conn.close()
    
    if not user:
        raise HTTPException(status_code=401, detail="E-posta veya şifre yanlış.")
    if not user["isVerified"]:
        raise HTTPException(status_code=403, detail="Lütfen giriş yapmadan önce e-posta adresinizi doğrulayın.")
        
    return user

@app.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    """Resmi Supabase Storage 'images' bucket'ına yükler."""
    try:
        ext = os.path.splitext(file.filename)[1]
        filename = f"{str(uuid.uuid4())}{ext}"
        file_content = await file.read()
        
        # 'images' bucket'ı Supabase'de PUBLIC olarak oluşturulmuş olmalıdır.
        supabase_client.storage.from_("images").upload(
            path=filename,
            file=file_content,
            file_options={"content-type": file.content_type}
        )
        
        # Herkese açık URL'yi al
        public_url = supabase_client.storage.from_("images").get_public_url(filename)
        return {"imageUrl": public_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Resim yükleme hatası: {str(e)}")

@app.get("/posts")
def get_posts():
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    # Sadece onaylanmış ilanları getirir
    cur.execute("SELECT * FROM posts WHERE status='approved' ORDER BY \"datePosted\" DESC")
    posts = cur.fetchall()
    cur.close()
    conn.close()
    return posts

@app.post("/posts")
def create_post(post: PostCreate):
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            'INSERT INTO posts (id, "userId", title, description, category, type, "imageUrl", "datePosted", location, "contactInfo", status) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)',
            (str(uuid.uuid4()), post.userId, post.title, post.description, post.category, post.type, post.imageUrl, datetime.now().isoformat(), post.location, post.contactInfo, 'pending')
        )
        return {"message": "İlanınız başarıyla alındı. Yönetici onayından sonra yayınlanacaktır."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

@app.get("/users/verify-link")
def verify_link(email: str, code: str):
    """Linke tıklandığında hesabı onaylar."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT * FROM users WHERE email=%s AND "verificationCode"=%s', (email, code))
    user = cur.fetchone()
    
    if not user:
        cur.close()
        conn.close()
        return HTMLResponse(content="<h2>Üzgünüz, geçersiz veya süresi dolmuş bir link.</h2>", status_code=400)
    
    cur.execute('UPDATE users SET "isVerified"=1, "verificationCode"=NULL WHERE email=%s', (email,))
    cur.close()
    conn.close()
    
    return HTMLResponse(content="""
        <div style="text-align:center; margin-top:100px; font-family: Arial, sans-serif;">
            <h1 style="color: #4CAF50;">Tebrikler!</h1>
            <p>E-posta adresiniz başarıyla doğrulandı. Hesabınız artık aktif.</p>
            <p>Uygulamaya dönüp giriş yapabilirsiniz.</p>
        </div>
    """)
