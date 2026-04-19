from mangum import Mangum
from fastapi import FastAPI
from supabase import create_client

SUPABASE_URL = "https://kcqikeyytshemptxbvxz.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImtjcWlrZXl5dHNoZW1wdHhidnh6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzYyNTQzNjYsImV4cCI6MjA5MTgzMDM2Nn0.LyFRsohwV9YKT3W5BxsEhuzRsfLyxG0ppZ0H3ldPLZU"

app = FastAPI()

@app.get("/")
def root():
    try:
        client = create_client(SUPABASE_URL, SUPABASE_KEY)
        # Sadece bağlantıyı test et, tablo sorgulama
        return {
            "status": "alive",
            "supabase": "initialized",
            "message": "Supabase client created successfully"
        }
    except Exception as e:
        return {
            "status": "error", 
            "error": str(e)
        }

@app.get("/test-db")
def test_db():
    try:
        client = create_client(SUPABASE_URL, SUPABASE_KEY)
        # Gerçek bir sorgu dene
        result = client.table('users').select('*').limit(1).execute()
        return {
            "status": "connected",
            "data": result.data
        }
    except Exception as e:
        return {
            "status": "failed",
            "error": str(e)
        }

handler = Mangum(app)
