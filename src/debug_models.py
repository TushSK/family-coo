import google.generativeai as genai

# --- PASTE YOUR KEY BELOW ---
TEST_API_KEY = "AIzaSyBhGG_xuXT_2aYNgiEycKszUCJ-VY6e56Y" 

def list_available_models():
    print(f"🔍 Testing Key: {TEST_API_KEY[:10]}...")
    
    try:
        genai.configure(api_key=TEST_API_KEY)
        models = genai.list_models()
        
        print("\n✅ SUCCESS! HERE ARE YOUR AVAILABLE MODELS:")
        print("-------------------------------------------")
        found_any = False
        for m in models:
            if 'generateContent' in m.supported_generation_methods:
                print(f" -> {m.name}")
                found_any = True
        
        if not found_any:
            print("❌ Access granted, but no 'generateContent' models found.")
            
    except Exception as e:
        print(f"\n⛔ ERROR: {str(e)}")

if __name__ == "__main__":
    list_available_models()