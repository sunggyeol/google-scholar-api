# Google Scholar API

A Python library for extracting data from Google Scholar using Selenium.

## Features

- **Publication Search** - Find papers by keywords
- **Author Profiles** - Get author details by ID or name
- **Citation Data** - Export citations in multiple formats (BibTeX, etc.)
- **Robust Search** - Automatic fallback strategies for blocked queries
- **ARM64 Support** - Works on Jetson, Raspberry Pi, and other ARM systems

## Requirements

- Python 3.8+
- Chrome or Chromium browser
- ChromeDriver

## Installation

```bash
pip install .
```

**For ARM64 systems (Jetson, Raspberry Pi):**
```bash
sudo apt install chromium-browser chromium-chromedriver
```

## Quick Start

```python
from google_scholar_api import GoogleScholar

# Initialize
api = GoogleScholar()

# Search for publications
results = api.search_scholar("Deep Learning", num=5)
for paper in results.organic_results:
    print(f"{paper.title} - {paper.link}")
```

## Usage Examples

### 1. Search Publications

```python
from google_scholar_api import GoogleScholar

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
from google_scholar_api.backends.selenium_backend import SeleniumBackend
backend = SeleniumBackend(headless=True)
```

## Legal

This tool is for educational and research purposes only. Please respect Google's Terms of Service and `robots.txt`.
