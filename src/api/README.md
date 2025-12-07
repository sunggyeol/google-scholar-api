# Google Scholar REST API

A production-ready REST API with Redis caching for Google Scholar searches.

## Features

- 🚀 **FastAPI** - Modern, fast web framework with automatic OpenAPI documentation
- 💾 **Redis Caching** - Intelligent caching with configurable TTL per endpoint
- 📊 **Cache Statistics** - Monitor cache hit/miss rates
- 🔍 **Full Search Support** - Publications, authors, profiles, and citations
- 🐳 **Docker Ready** - Easy deployment with docker-compose
- 📝 **Auto Documentation** - Interactive API docs at `/docs`

## Quick Start

### Option 1: Using Docker (Recommended)

```bash
# Start API and Redis with docker-compose
docker-compose up -d

# API will be available at http://localhost:8000
# Documentation at http://localhost:8000/docs
```

### Option 2: Local Development

1. **Install Redis** (if not using Docker):
```bash
# Ubuntu/Debian
sudo apt-get install redis-server

# macOS
brew install redis
brew services start redis
```

2. **Install Python dependencies**:
```bash
pip install -r requirements.txt
# or
pip install -e .
```

3. **Configure environment** (optional):
```bash
cp .env.example .env
# Edit .env with your settings
```

4. **Run the API server**:
```bash
# From project root
uvicorn src.api.main:app --reload

# Or use Python directly
python -m uvicorn src.api.main:app --reload
```

The API will be available at `http://localhost:8000`

## API Endpoints

### Health & Status

#### GET /health
Health check endpoint with cache statistics.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T12:00:00",
  "version": "1.0.0",
  "cache_enabled": true,
  "cache_stats": {
    "hits": 42,
    "misses": 10,
    "total_requests": 52,
    "hit_rate_percent": 80.77
  }
}
```

### Search Publications

#### POST /api/v1/search/scholar
Search for scholarly publications.

**Request Body:**
```json
{
  "q": "machine learning",
  "num": 10,
  "start": 0,
  "hl": "en",
  "as_ylo": "2020",
  "as_yhi": "2024",
  "scisbd": 1
}
```

**Parameters:**
- `q` (required): Search query
- `num` (optional): Number of results (1-100, default: 10)
- `start` (optional): Start position for pagination (default: 0)
- `hl` (optional): Language code (default: "en")
- `as_ylo` (optional): Start year filter
- `as_yhi` (optional): End year filter
- `scisbd` (optional): Sort by date (0=relevance, 1=date)

**Cache:** 24 hours

**cURL Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/search/scholar" \
  -H "Content-Type: application/json" \
  -d '{"q": "deep learning", "num": 5}'
```

### Get Author Profile

#### GET /api/v1/author/{author_id}
Get detailed author profile by Google Scholar ID.

**Parameters:**
- `author_id` (path, required): Google Scholar author ID

**Common Author IDs:**
- `JicYPdAAAAAJ` - Geoffrey Hinton
- `WLN3QrAAAAAJ` - Yann LeCun
- `kukA0LcAAAAJ` - Yoshua Bengio

**Cache:** 7 days

**cURL Example:**
```bash
curl "http://localhost:8000/api/v1/author/JicYPdAAAAAJ"
```

**Response:**
```json
{
  "success": true,
  "cache_hit": false,
  "data": {
    "author": {
      "name": "Geoffrey Hinton",
      "affiliations": "University of Toronto",
      "interests": [
        {"title": "Machine Learning"},
        {"title": "Neural Networks"}
      ]
    },
    "articles": [...]
  }
}
```

### Search Author Profiles

#### POST /api/v1/search/profiles
Find author profiles by name.

**Request Body:**
```json
{
  "q": "Andrew Ng",
  "hl": "en"
}
```

**Cache:** 12 hours

**cURL Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/search/profiles" \
  -H "Content-Type: application/json" \
  -d '{"q": "Yann LeCun"}'
```

### Get Citation Formats

#### GET /api/v1/cite/{cite_id}
Get citation formats (BibTeX, MLA, APA, etc.) for a publication.

**Parameters:**
- `cite_id` (path, required): Citation ID (data-cid from a paper)

**Cache:** 30 days

**cURL Example:**
```bash
curl "http://localhost:8000/api/v1/cite/CITATION_ID"
```

### Cache Management

#### GET /api/v1/cache/stats
Get cache statistics.

**Response:**
```json
{
  "enabled": true,
  "hits": 150,
  "misses": 50,
  "errors": 0,
  "total_requests": 200,
  "hit_rate_percent": 75.0
}
```

#### POST /api/v1/cache/clear
Clear all cached entries.

**Response:**
```json
{
  "success": true,
  "message": "Cache cleared successfully"
}
```

## Response Headers

All search endpoints include a cache status header:

```
X-Cache-Status: HIT    # Response from cache
X-Cache-Status: MISS   # Fresh data fetched
```

## Configuration

Configuration is managed through environment variables or a `.env` file.

### Key Configuration Options

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_HOST` | localhost | Redis server host |
| `REDIS_PORT` | 6379 | Redis server port |
| `REDIS_ENABLED` | true | Enable/disable caching |
| `CACHE_TTL_SCHOLAR` | 86400 | Scholar search cache (24h) |
| `CACHE_TTL_AUTHOR` | 604800 | Author profile cache (7d) |
| `CACHE_TTL_PROFILES` | 43200 | Profile search cache (12h) |
| `CACHE_TTL_CITE` | 2592000 | Citation cache (30d) |
| `DEBUG` | false | Debug mode |
| `PORT` | 8000 | API server port |

See `.env.example` for all available options.

## Interactive Documentation

FastAPI provides automatic interactive API documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

These interfaces allow you to test all endpoints directly from your browser.

## Python Client Example

```python
import requests

# Base URL
BASE_URL = "http://localhost:8000"

# Search for publications
response = requests.post(
    f"{BASE_URL}/api/v1/search/scholar",
    json={
        "q": "quantum computing",
        "num": 10
    }
)
data = response.json()

# Check if cached
cache_status = response.headers.get("X-Cache-Status")
print(f"Cache: {cache_status}")

# Access results
if data["success"]:
    for paper in data["data"]["organic_results"]:
        print(f"{paper['title']}")
        print(f"  Authors: {', '.join(a['name'] for a in paper['authors'])}")
        print()

# Get author profile
response = requests.get(f"{BASE_URL}/api/v1/author/JicYPdAAAAAJ")
author_data = response.json()

if author_data["success"]:
    author = author_data["data"]["author"]
    print(f"Name: {author['name']}")
    print(f"Affiliation: {author['affiliations']}")
```

## JavaScript/TypeScript Example

```javascript
// Search publications
const response = await fetch('http://localhost:8000/api/v1/search/scholar', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    q: 'artificial intelligence',
    num: 10
  })
});

const data = await response.json();
const cacheStatus = response.headers.get('X-Cache-Status');

console.log(`Cache: ${cacheStatus}`);
if (data.success) {
  data.data.organic_results.forEach(paper => {
    console.log(paper.title);
  });
}

// Get author profile
const authorResponse = await fetch('http://localhost:8000/api/v1/author/JicYPdAAAAAJ');
const authorData = await authorResponse.json();
console.log(authorData.data.author.name);
```

## Production Deployment

### Using Docker Compose

```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f api

# Stop services
docker-compose down

# Rebuild after changes
docker-compose up -d --build
```

### Environment Variables for Production

Create a `.env` file with production settings:

```env
DEBUG=false
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=your-secure-password
CORS_ORIGINS=https://yourdomain.com
```

## Monitoring

### Check API Health
```bash
curl http://localhost:8000/health
```

### View Cache Statistics
```bash
curl http://localhost:8000/api/v1/cache/stats
```

### View API Logs
```bash
# Docker
docker-compose logs -f api

# Local
# Logs are output to stderr by default
```

## Troubleshooting

### Redis Connection Issues

If caching is disabled due to Redis connection failure:

1. **Check Redis is running**:
```bash
redis-cli ping
# Should return: PONG
```

2. **Check environment variables**:
```bash
echo $REDIS_HOST
echo $REDIS_PORT
```

3. **Check Docker services**:
```bash
docker-compose ps
```

### ChromeDriver Issues

The API uses Selenium for scraping. If you encounter ChromeDriver issues:

1. **For ARM64 systems** (Jetson, Raspberry Pi):
```bash
sudo apt install chromium-browser chromium-chromedriver
```

2. **For x86_64 systems**:
ChromeDriver is automatically managed by webdriver-manager.

## Performance Tips

1. **Use caching**: Redis caching dramatically reduces response times and avoids rate limiting
2. **Adjust TTL**: Configure cache duration based on your needs
3. **Monitor cache hit rate**: Aim for >70% cache hit rate
4. **Pagination**: Use `start` parameter for large result sets

## License

Same as the main Google Scholar library.

## Support

For issues and questions, please refer to the main project repository.

