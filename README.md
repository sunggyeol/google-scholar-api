# Google Scholar Library & API

Google Scholar scraping with Python library and REST API with Redis caching.

## What's Included

- **Python Library** (`google_scholar_lib`) - Direct Python interface
- **REST API** (`src/api`) - FastAPI server with Redis caching

## Features

- Publication search, author profiles, citations (BibTeX, etc.)
- Automatic fallback for rate limiting
- Redis caching with configurable TTL
- Interactive API documentation at `/docs`
- ARM64 compatible (Jetson, Raspberry Pi)

## Requirements

- Python 3.8+
- Chrome or Chromium browser
- ChromeDriver
- Redis (for API caching - optional for library use)

## Installation

### Library Only

```bash
pip install .
```

### Library + API

```bash
pip install -r requirements.txt
# or
pip install -e .
```

**For ARM64 systems (Jetson, Raspberry Pi):**
```bash
sudo apt install chromium-browser chromium-chromedriver redis-server
```

---

## 🐍 Python Library Usage

### Quick Start

```python
from google_scholar_lib import GoogleScholar

# Initialize
api = GoogleScholar()

# Search for publications
results = api.search_scholar("Deep Learning", num=5)
for paper in results.organic_results:
    print(f"{paper.title} - {paper.link}")
```

### Usage Examples

### 1. Search Publications

```python
from google_scholar_lib import GoogleScholar

api = GoogleScholar()
results = api.search_scholar("Machine Learning", num=10)

for paper in results.organic_results:
    print(f"Title: {paper.title}")
    print(f"Authors: {', '.join([a.name for a in paper.authors])}")
    if paper.inline_links and paper.inline_links.cited_by:
        print(f"Citations: {paper.inline_links.cited_by['total']}")
    print()
```

### 2. Get Author Profile (by ID)

If you know the author's Google Scholar ID:

```python
api = GoogleScholar()
results = api.search_author(author_id="JicYPdAAAAAJ")  # Geoffrey Hinton

print(f"Name: {results.author.name}")
print(f"Affiliation: {results.author.affiliations}")
print(f"Interests: {', '.join([i.title for i in results.author.interests])}")

print("\nTop Publications:")
for article in results.articles[:5]:
    print(f"  - {article.title}")
```

**Common Author IDs:**
- `JicYPdAAAAAJ` - Geoffrey Hinton
- `WLN3QrAAAAAJ` - Yann LeCun  
- `kukA0LcAAAAJ` - Yoshua Bengio

### 3. Find Author Profile (by Name)

Search for an author by name. Uses automatic fallback if direct search is blocked:

```python
api = GoogleScholar()
results = api.search(engine="google_scholar_profiles", q="Andrew Ng")

for profile in results.profiles:
    print(f"Name: {profile.name}")
    print(f"ID: {profile.author_id}")
    print(f"Affiliation: {profile.affiliations}")
```

### 4. Get Citations

```python
api = GoogleScholar()
results = api.search_cite(data_cid="PAPER_CID")

# Available formats
for link in results.links:
    print(f"{link['title']}: {link['link']}")

# Citation text
for citation in results.citations:
    print(f"{citation['title']}")
    print(f"{citation['snippet']}\n")
```

---

## REST API Usage

### Quick Start

```bash
# 1. Start Redis (if not already running)
sudo systemctl start redis-server

# 2. Start API
cd src/api
uvicorn main:app --host 0.0.0.0 --port 8765

# Or with reload for development
uvicorn main:app --host 0.0.0.0 --port 8765 --reload
```

Access the API at `http://localhost:8765/docs`

### Example Requests

```bash
# Search publications
curl -X POST http://localhost:8765/api/v1/search/scholar \
  -H "Content-Type: application/json" \
  -d '{"q": "machine learning", "num": 10}'

# Get author profile
curl http://localhost:8765/api/v1/author/JicYPdAAAAAJ

# Check health & cache stats
curl http://localhost:8765/health
```

**Python:**
```python
import requests
response = requests.post("http://localhost:8765/api/v1/search/scholar",
                        json={"q": "quantum computing", "num": 10})
print(response.headers.get("X-Cache-Status"))  # HIT or MISS
```

**Full documentation:** [`src/api/README.md`](src/api/README.md) or visit `/docs` when running

---

## Interactive Demo

Test the API interactively:

```bash
python demo.py
```

The demo lets you:
- Choose between different search engines
- Enter custom search parameters
- View formatted results with metadata

## Search Engines

The API supports four search engines:

| Engine | Purpose | Returns |
|--------|---------|---------|
| `google_scholar` | Search publications | Papers, authors, citations |
| `google_scholar_author` | Get author by ID | Profile, publications, interests |
| `google_scholar_profiles` | Find author by name | Profile matches |
| `google_scholar_cite` | Get citation formats | BibTeX, EndNote, etc. |

## Advanced Features

### Headless Mode

Runs Chrome in headless mode by default (no visible browser window):

```python
# Headless by default
api = GoogleScholar()

# Or explicitly set headless mode
from google_scholar_lib.backends.selenium_backend import SeleniumBackend
backend = SeleniumBackend(headless=True)
```

### Caching (API Only)

The REST API automatically caches responses with configurable TTL:
- Scholar searches: 24 hours
- Author profiles: 7 days  
- Profile searches: 12 hours
- Citations: 30 days

Cache status is indicated in the `X-Cache-Status` response header.

---

## ☁️ Cloud Deployment (Google Cloud Free Tier)

This project runs on **Google Cloud's Always Free e2-micro** (1GB RAM). A 2GB swap file is required to prevent Chrome crashes.

### Setup (e2-micro, Debian 12)

```bash
# 1. Create 2GB Swap (Required!)
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# 2. Install Dependencies
sudo apt update
sudo apt install -y git python3-venv python3-pip redis-server chromium chromium-driver
sudo systemctl enable redis-server && sudo systemctl start redis-server

# 3. Clone & Install
git clone https://github.com/YOUR_USERNAME/google-scholar-api.git
cd google-scholar-api
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e .

# 4. Configure
cp .env.example .env
nano .env
```

### Run as Service

Create `/etc/systemd/system/scholar.service`:

```ini
[Unit]
Description=Google Scholar API
After=network.target redis-server.service

[Service]
User=YOUR_USERNAME
WorkingDirectory=/home/YOUR_USERNAME/google-scholar-api
Environment="PATH=/home/YOUR_USERNAME/google-scholar-api/venv/bin"
ExecStart=/home/YOUR_USERNAME/google-scholar-api/venv/bin/uvicorn src.api.main:app --host 0.0.0.0 --port 8765
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable scholar
sudo systemctl start scholar
```

### Public Access (Cloudflare Tunnel)

```bash
# Install
curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared.deb

# Quick tunnel (temporary URL)
cloudflared tunnel --url http://localhost:8765

# Or run as service for persistent tunnel
sudo cloudflared service install
```

**Note:** Use Standard Persistent Disk (30GB) in `us-central1`, `us-west1`, or `us-east1` to stay within free tier limits.

---

## Legal

This tool is for educational and research purposes only. Please respect Google's Terms of Service and `robots.txt`.
