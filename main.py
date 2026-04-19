from mangum import Mangum
from fastapi import FastAPI
from supabase import create_client, Client
import traceback

SUPABASE_URL = "https://kcqikeyytshemptxbvxz.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImtjcWlrZXl5dHNoZW1wdHhidnh6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzYyNTQzNjYsImV4cCI6MjA5MTgzMDM2Nn0.LyFRsohwV9YKT3W5BxsEhuzRsfLyxG0ppZ0H3ldPLZU"

app = FastAPI()

@app.get("/")
def root():
    result = {
        "status": "testing",
        "supabase_url": SUPABASE_URL,
        "key_prefix": SUPABASE_KEY[:50] + "..."
    }
    
    try:
        print(f"Connecting to Supabase...")
        client = create_client(SUPABASE_URL, SUPABASE_KEY)
        result["client_created"] = True
        
        print(f"Testing query...")
        response = client.table('users').select('count').execute()
        result["query_success"] = True
        result["data"] = response.data
        result["database"] = "connected"
        
    except Exception as e:
        result["error"] = str(e)
        result["error_type"] = type(e).__name__
        result["traceback"] = traceback.format_exc()
        result["database"] = "disconnected"
        print(f"ERROR: {traceback.format_exc()}")
    
    return result

handler = Mangum(app)
