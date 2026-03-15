# 🚀 Quick Start: Testing Bringo Live AI Agent

## Status Check Results

I've analyzed the `bringo-multimodal-live` project and created a complete testing framework. Here's what you need to know:

---

## 🏗️ Architecture Overview

Your system has **two main components**:

### 1. **Backend API** (Port 8080)

- **Path**: `ai_agents/bringo-multimodal-live/api/`
- **Purpose**: Handles authentication, product search, and cart operations
- **Technology**: FastAPI + Vector Search + Semantic Ranking
- **Status**: ❌ Not running (needs to be started)

### 2. **Live AI Agent** (Port 8000)

- **Path**: `ai_agents/bringo-multimodal-live/agent/shop-agent/`
- **Purpose**: Voice-enabled shopping assistant using Gemini Live
- **Model**: `gemini-live-2.5-flash-native-audio`
- **Language**: Romanian
- **Status**: ❌ Not running (needs to be started)

---

## 🔐 Authentication Requirement

**You're right!** The live agent needs **Bringo account credentials** to add items to the cart.

### How Authentication Works

```mermaid
graph LR
    A[User Credentials] -->|Login API| B[Selenium Browser]
    B -->|Automated Login| C[Bringo.ro]
    C -->|Session Cookie| D[SQLite Database]
    D -->|PHPSESSID| E[Cart Operations]
```

### Where to Set Credentials

**Option 1: Environment Variables** (Easiest)

Create or edit the `.env` file:

```bash
# ai_agents/bringo-multimodal-live/.env
BRINGO_USERNAME=your-email@example.com
BRINGO_PASSWORD=your-password
BRINGO_STORE=carrefour_park_lake
```

**Option 2: Login via API** (Persists to database)

After starting the backend API:

```bash
curl -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "your-email@example.com",
    "password": "your-password",
    "store": "carrefour_park_lake"
  }'
```

The session will be:

- ✅ Saved to SQLite database (`services/db.py`)
- ✅ Valid for 24 hours
- ✅ Used automatically by cart operations

---

## 🎯 Step-by-Step Testing Guide

### Step 1: Configure Credentials

```bash
cd /Users/radanpetrica/PFA/agents/agents-adk-mcp/ai_agents/bringo-multimodal-live

# Edit .env file
nano .env  # or use your preferred editor
```

Add these lines (replace with your Bringo credentials):

```mermaid
BRINGO_USERNAME=your-actual-email@example.com
BRINGO_PASSWORD=your-actual-password
BRINGO_STORE=carrefour_park_lake
```

### Step 2: Start Backend API

```bash
# Terminal 1
cd /Users/radanpetrica/PFA/agents/agents-adk-mcp/ai_agents/bringo-multimodal-live
source /Users/radanpetrica/PFA/agents/agents-adk-mcp/ai_env/bin/activate
python -m api.main
```

**Expected output:**

```
🚀 Starting Bringo Product Similarity API...
🔧 Configuration:
   • Env: Production Mode
   • Host: 0.0.0.0:8080
   • Model: multimodalembedding@001 (512D)
   • Ranking: semantic-ranker-default@latest
```

### Step 3: Verify Authentication

```bash
# Terminal 2 (new window)
cd /Users/radanpetrica/PFA/agents/agents-adk-mcp/ai_agents/bringo-multimodal-live
./test_live_agent.sh
```

**Expected output:**

```
✅ Backend API is running
✅ Session is active
   User: your-email@example.com
✅ Search successful - Found 5 products
✅ Cart accessible - 0 items
```

### Step 4: Start Live AI Agent

```bash
# Terminal 3
cd /Users/radanpetrica/PFA/agents/agents-adk-mcp/ai_agents/bringo-multimodal-live/agent/shop-agent
make local-backend
```

**Expected output:**

```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete.
```

### Step 5: Test Voice Interaction

1. **Open browser**: `http://localhost:8000`
2. **Click play button** to start voice interaction
3. **Grant microphone permissions**
4. **Test Romanian voice commands**:

```
🎤 "Caut lapte"
   → Agent searches for milk products

🎤 "Adaugă primul produs în coș"
   → Agent adds item to your Bringo cart

🎤 "Ce am în coș?"
   → Agent checks your cart status
```

### Step 6: Verify Real Cart

Go to `https://www.bringo.ro` and login with your credentials. You should see items added by the agent!

---

## 🧪 Complete Test Cases

I've created detailed test documentation:

### 📄 Files Created

1. **`TEST_PLAN_LIVE_AGENT.md`**
   - Complete testing methodology
   - All test cases with expected results
   - Error handling scenarios
   - Performance metrics

2. **`test_live_agent.sh`**
   - Automated health check script
   - Tests all components
   - Provides immediate status

---

## 🔍 What the Agent Can Do

### 1. **Product Search** (using Vector Search + Ranking)

```
Voice: "Caut laptele cel mai ieftin"
```

- Searches using multimodal embeddings (512D)
- Ranks by semantic relevance
- Returns top products with scores

### 2. **Smart Substitutions**

```
Voice: "Nu găsesc lapte Zuzu, recomandă altceva"
```

- Finds similar products
- Explains why it's a good match
- Shows price differences

### 3. **Cart Management** (requires authentication)

```
Voice: "Adaugă două bucăți de pâine în coș"
```

- Adds items to real Bringo cart
- Uses your authenticated session
- Confirms operations in Romanian

### 4. **Market Research** (delegated to sub-agent)

```
Voice: "Am nevoie de ingrediente pentru mic dejun sănătos"
```

- Research agent uses Google Search
- Generates 5 diverse queries
- Returns curated product selection

---

## 🎯 Key Integration Points

### Backend API → Live Agent

The agent (`agent.py`) calls the backend API:

```python
BASE_API_URL = "http://34.78.177.35/api/v1"  # Your deployed backend
API_KEY = "bringo_secure_shield_2026"

def find_shopping_items(queries: List[str]):
    url = f"{BASE_API_URL}/search"
    headers = {
        "X-API-KEY": API_KEY,
        "Content-Type": "application/json"
    }
    # ... calls backend API
```

### Backend API → Bringo

The auth service (`auth_service.py`) uses Selenium:

```python
def authenticate_with_credentials(username, password, store):
    # 1. Launches headless Chrome
    # 2. Navigates to bringo.ro/login
    # 3. Fills credentials
    # 4. Extracts PHPSESSID cookie
    # 5. Saves to SQLite database
    # 6. Returns session (valid 24h)
```

---

## 🐛 Troubleshooting

### Issue: "Credentials not found"

**Solution**: Set credentials in `.env` file as shown in Step 1

### Issue: "Session expired"

**Solution**: Re-run authentication (valid for 24 hours):

```bash
curl -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "YOUR_EMAIL", "password": "YOUR_PASSWORD"}'
```

### Issue: ChromeDriver not found

**Solution**: Install ChromeDriver:

```bash
pip install webdriver-manager selenium
```

### Issue: Agent doesn't respond to voice

**Solutions**:

1. Check microphone permissions in browser
2. Verify WebSocket connection in browser console
3. Ensure Gemini Live API is enabled in your GCP project

---

## 📊 Expected Performance

| Metric | Target | Your Setup |
|--------|--------|------------|
| Product Search | <3s | Vector Search + Ranking |
| Authentication | One-time (24h) | Selenium automation |
| Cart Operations | <2s | Authenticated API calls |
| Voice Latency | <1s | Gemini Live streaming |

---

## 🔒 Security Notes

1. **Credentials** are stored in SQLite (`services/db.py`)
2. **Session cookies** expire after 24 hours
3. **API Key** (`bringo_secure_shield_2026`) protects backend
4. **Never commit** `.env` file to git (already in `.gitignore`)
5. **Selenium** runs in headless mode for automation

---

## 🚀 Quick Commands Reference

```bash
# 1. Start backend API
cd ai_agents/bringo-multimodal-live
python -m api.main

# 2. Run health check
./test_live_agent.sh

# 3. Start live agent
cd agent/shop-agent
make local-backend

# 4. Test authentication
curl http://localhost:8080/api/v1/auth/status

# 5. Test search
curl -X POST http://localhost:8080/api/v1/search \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: bringo_secure_shield_2026" \
  -d '{"query_text": "lapte", "top_k": 5}'

# 6. Check cart
curl http://localhost:8080/api/v1/cart
```

---

## 📚 Documentation Structure

```
bringo-multimodal-live/
├── TEST_PLAN_LIVE_AGENT.md      # Complete test plan (you are here)
├── test_live_agent.sh            # Automated health check
├── QUICKSTART.md                 # This file
├── README.md                     # Project overview
├── api/                          # Backend API
│   ├── main.py                   # FastAPI server
│   ├── routes/
│   │   ├── auth.py              # Authentication endpoints
│   │   ├── cart.py              # Cart management
│   │   └── live_search.py       # Product search
├── agent/shop-agent/             # Live AI Agent
│   ├── app/agent.py             # Gemini Live agent
│   └── frontend/                # Voice UI
└── services/
    ├── auth_service.py          # Selenium authentication
    ├── cart_service.py          # Cart operations
    └── db.py                    # SQLite persistence
```

---

## ✅ Validation Checklist

Before testing, ensure:

- [ ] Bringo credentials set in `.env`
- [ ] Backend API running on port 8080
- [ ] Authentication successful (check with `./test_live_agent.sh`)
- [ ] Live agent running on port 8000
- [ ] Frontend accessible at `http://localhost:8000`
- [ ] Microphone permissions granted in browser

---

## 🎉 Success Criteria

Your testing is successful when:

1. ✅ Voice commands work in Romanian
2. ✅ Product search returns relevant results
3. ✅ Items added to cart appear at <www.bringo.ro>
4. ✅ Session persists for 24 hours
5. ✅ Error handling is graceful
6. ✅ No crashes or unhandled exceptions

---

## 📞 Need Help?

1. **Check logs**: Both terminals show detailed execution logs
2. **Run diagnostics**: `./test_live_agent.sh`
3. **Review test plan**: `TEST_PLAN_LIVE_AGENT.md`
4. **Check API docs**: `http://localhost:8080/docs`

---

**Ready to test!** 🚀

Start with Step 1 above and follow the sequence. The agent should be fully functional for voice-based shopping with real cart integration.
