from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
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

# ÖNEMLİ: Supabase doğrudan REST API kullanımı (PostgreSQL bağlantısı yerine)
# Bu yöntem Vercel serverless ortamında çok daha güvenilirdir
SUPABASE_URL = "https://doukedhgnaonecbeenqx.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRvdWtlZGhuZ25hb25lY2JlZW5xeCIsInJvbGUiOiJhbm9uIiwiaWF0IjoxNzQ0NDY2Mzk4LCJleHAiOjIwNjAwNDIzOTh9.gzeQTYlOLcN5Gx2HMg_6wIWJX3P2hWQNZXqhZq_tBIg"

# Supabase client oluştur
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

app = FastAPI()

# CORS Ayarları
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
        "durum": "Sistemler çalışıyor"
    }

@app.post("/users/register")
def register(user: UserCreate):
    """Yeni kullanıcı kaydı - Supabase REST API kullanarak"""
    user_id = str(uuid.uuid4())
    code = str(random.randint(100000, 999999))
    
    try:
        # Önce email kontrolü yap
        existing = supabase.table('users').select('*').eq('email', user.email).execute()
        if existing.data and len(existing.data) > 0:
            raise HTTPException(status_code=400, detail="Bu e-posta adresi zaten kayıtlı.")
        
        # Yeni kullanıcı ekle
        result = supabase.table('users').insert({
            "id": user_id,
            "email": user.email,
            "name": user.name,
            "phoneNumber": user.phoneNumber,
            "passwordHash": user.passwordHash,
            "createdAt": datetime.now().isoformat(),
            "verificationCode": code,
            "isVerified": 0,
            "isAdmin": 0
        }).execute()
        
        # E-posta gönder
        send_verification_email(user.email, code)
        
        return {"message": "Kayıt başarılı. Lütfen e-postanızı kontrol ederek hesabınızı doğrulayın."}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"REGISTER ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Kayıt hatası: {str(e)}")

@app.post("/users/login")
def login(data: UserLogin):
    """Kullanıcı girişi - Supabase REST API kullanarak"""
    try:
        # Kullanıcıyı bul
        result = supabase.table('users').select('*').eq('email', data.email).eq('passwordHash', data.passwordHash).execute()
        
        if not result.data or len(result.data) == 0:
            raise HTTPException(status_code=401, detail="E-posta veya şifre yanlış.")
        
        user = result.data[0]
        
        if not user.get("isVerified"):
            raise HTTPException(status_code=403, detail="Lütfen giriş yapmadan önce e-posta adresinizi doğrulayın.")
        
        return {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
            "isAdmin": user.get("isAdmin", 0)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"LOGIN ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Giriş hatası: {str(e)}")

@app.get("/users/verify-link")
def verify_link(email: str, code: str):
    """Linke tıklandığında hesabı onaylar."""
    try:
        # Kullanıcıyı bul
        result = supabase.table('users').select('*').eq('email', email).eq('verificationCode', code).execute()
        
        if not result.data or len(result.data) == 0:
            return HTMLResponse(content="<h2>Üzgünüz, geçersiz veya süresi dolmuş bir link.</h2>", status_code=400)
        
        # Kullanıcıyı doğrula
        supabase.table('users').update({
            "isVerified": 1,
            "verificationCode": None
        }).eq('email', email).execute()
        
        return HTMLResponse(content="""
            <div style="text-align:center; margin-top:100px; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; color: #333;">
                <h1 style="color: #4CAF50; font-size: 3rem;">✓ Başarılı!</h1>
                <p style="font-size: 1.2rem;">E-posta adresiniz başarıyla doğrulandı. Hesabınız artık aktif.</p>
                <p>Şimdi sitemize dönüp giriş yapabilirsiniz.</p>
                <a href="https://www.kaybedenvebulan.com.tr" style="display:inline-block; margin-top:20px; padding: 10px 20px; background-color: #2563eb; color: white; text-decoration: none; border-radius: 5px;">Sitemize Git</a>
            </div>
        """)
        
    except Exception as e:
        print(f"VERIFY ERROR: {str(e)}")
        return HTMLResponse(content=f"<h2>Doğrulama sırasında hata oluştu: {str(e)}</h2>", status_code=500)

@app.post("/users/send-verification")
def send_verification(email: str):
    """Doğrulama kodunu yeniden gönder"""
    try:
        result = supabase.table('users').select('*').eq('email', email).execute()
        
        if not result.data or len(result.data) == 0:
            raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")
        
        code = str(random.randint(100000, 999999))
        supabase.table('users').update({"verificationCode": code}).eq('email', email).execute()
        
        send_verification_email(email, code)
        return {"message": "Doğrulama linki gönderildi"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Hata: {str(e)}")

@app.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    """Resmi Supabase Storage 'images' bucket'ına yükler."""
    try:
        ext = os.path.splitext(file.filename)[1]
        filename = f"{str(uuid.uuid4())}{ext}"
        file_content = await file.read()
        
        supabase.storage.from_("images").upload(
            path=filename,
            file=file_content,
            file_options={"content-type": file.content_type}
        )
        
        public_url = supabase.storage.from_("images").get_public_url(filename)
        return {"imageUrl": public_url}
        
    except Exception as e:
        print(f"UPLOAD ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Resim yükleme hatası: {str(e)}")

@app.get("/posts")
def get_posts():
    """Onaylanmış ilanları getir"""
    try:
        result = supabase.table('posts').select('*').eq('status', 'approved').order('datePosted', desc=True).execute()
        return result.data
    except Exception as e:
        print(f"POSTS ERROR: {str(e)}")
        return []

@app.post("/posts")
def create_post(post: PostCreate):
    """Yeni ilan oluştur"""
    try:
        result = supabase.table('posts').insert({
            "id": str(uuid.uuid4()),
            "userId": post.userId,
            "title": post.title,
            "description": post.description,
            "category": post.category,
            "type": post.type,
            "imageUrl": post.imageUrl,
            "datePosted": datetime.now().isoformat(),
            "location": post.location,
            "contactInfo": post.contactInfo,
            "status": "pending"
        }).execute()
        
        return {"message": "İlanınız başarıyla alındı. Yönetici onayından sonra yayınlanacaktır."}
        
    except Exception as e:
        print(f"CREATE POST ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=f"İlan oluşturma hatası: {str(e)}")

@app.get("/posts/pending")
def get_pending_posts():
    """Bekleyen ilanları getir (Admin)"""
    try:
        result = supabase.table('posts').select('*').eq('status', 'pending').execute()
        return result.data
    except Exception as e:
        print(f"PENDING POSTS ERROR: {str(e)}")
        return []

@app.patch("/posts/{post_id}/status")
def update_post_status(post_id: str, status: str):
    """İlan durumunu güncelle (Admin)"""
    try:
        supabase.table('posts').update({"status": status}).eq('id', post_id).execute()
        return {"message": f"İlan durumu '{status}' olarak güncellendi"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Güncelleme hatası: {str(e)}")

@app.get("/comments/{post_id}")
def get_comments(post_id: str):
    """İlan yorumlarını getir"""
    try:
        result = supabase.table('comments').select('*').eq('postId', post_id).execute()
        return result.data
    except Exception as e:
        print(f"COMMENTS ERROR: {str(e)}")
        return []

@app.post("/comments")
def add_comment(comment: CommentCreate):
    """Yorum ekle"""
    try:
        result = supabase.table('comments').insert({
            "id": str(uuid.uuid4()),
            "postId": comment.postId,
            "userId": comment.userId,
            "text": comment.text,
            "datePosted": datetime.now().isoformat()
        }).execute()
        
        return {"message": "Yorum eklendi"}
        
    except Exception as e:
        print(f"ADD COMMENT ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Yorum ekleme hatası: {str(e)}")

@app.patch("/users/{user_id}")
def update_profile(user_id: str, data: ProfileUpdate):
    """Kullanıcı profilini güncelle"""
    try:
        update_data = {}
        if data.name:
            update_data["name"] = data.name
        if data.phoneNumber:
            update_data["phoneNumber"] = data.phoneNumber
        if data.newPasswordHash:
            update_data["passwordHash"] = data.newPasswordHash
        
        if update_data:
            supabase.table('users').update(update_data).eq('id', user_id).execute()
        
        return {"message": "Profil güncellendi"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Profil güncelleme hatası: {str(e)}")
