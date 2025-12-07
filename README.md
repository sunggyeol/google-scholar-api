# Google Scholar API

A robust data extraction library for Google Scholar, designed for research and educational purposes.

## Features
- **Backends**: `selenium` (robust, recommended) and `requests` (lightweight).
- **Engines**: `google_scholar` (pubs), `google_scholar_author` (details), `google_scholar_profiles` (search), `google_scholar_cite` (BibTeX).

## Installation
```bash
pip install .
```

## Usage

**Initialize:**
```python
from google_scholar_api import GoogleScholar
api = GoogleScholar(backend='selenium')
```

**1. Publication Search:**
```python
res = api.search(engine="google_scholar", q="Generative AI", num=5)
for r in res.organic_results:
    print(f"{r.title} - {r.link}")
```

**2. Robust Author Search:**
*Finds author ID via publication analysis for improved reliability.*
```python
res = api.search(engine="google_scholar_profiles", q="Geoffrey Hinton")
for p in res.profiles:
    print(f"{p.name} (ID: {p.author_id})")
```

**3. Author Details:**
```python
res = api.search(engine="google_scholar_author", author_id="JicYPdAAAAAJ")
print(f"User: {res.author.name}, Publications: {len(res.articles)}")
```

**4. Citations (BibTeX):**
```python
res = api.search(engine="google_scholar_cite", q="RESULT_DATA_CID")
print(res.links) # [{'title': 'BibTeX', 'link': '...'}]
```

## Legal
This tool is for educational and research purposes only. Please respect Google's Terms of Service and `robots.txt`.
