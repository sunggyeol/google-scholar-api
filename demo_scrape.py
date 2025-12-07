from google_scholar_api import GoogleScholar
import sys
import os

def test_requests():
    print("\n--- Testing Requests Backend ---")
    try:
        api = GoogleScholar(backend='requests')
        results = api.search_scholar("Agentic AI") 
        print(f"Found {len(results.organic_results)} results.")
        if results.organic_results:
            print(f"Top result: {results.organic_results[0].title}")
            print(f"Link: {results.organic_results[0].link}")
    except Exception as e:
        print(f"Requests backend failed: {e}")

def test_selenium():
    print("\n--- Testing Selenium Backend ---")
    try:
        api = GoogleScholar(backend='selenium')
        results = api.search_scholar("Deep Learning")
        print(f"Found {len(results.organic_results)} results.")
        if results.organic_results:
            print(f"Top result: {results.organic_results[0].title}")
    except Exception as e:
        print(f"Selenium backend failed: {e}")

def test_authors():
    print("\n--- Testing Author Search (Requests) ---")
    try:
        api = GoogleScholar(backend='requests')
        results = api.search_author(author_id="JicYPdAAAAAJ")
        if results.author:
            print(f"Author: {results.author.name}")
            print(f"Affiliation: {results.author.affiliations}")
        else:
            print("Author profile not found")
    except Exception as e:
        print(f"Author search failed: {e}")

def test_sunggyeol():
    print("\n--- Testing User Search 'Sunggyeol Oh' (Selenium) ---")
    try:
        api = GoogleScholar(backend='selenium')
        results = api.search(engine="google_scholar", q="Sunggyeol Oh", num=5)
        print(f"Total Results Found: {results.search_information.total_results}")
        for res in results.organic_results:
             print(f"[{res.position}] {res.title}")
    except Exception as e:
        print(f"Sunggyeol test failed: {e}")

def test_profile_search():
    print("\n--- Testing Profile Search 'Sunggyeol Oh' (Requests) ---")
    try:
        api = GoogleScholar(backend='requests')
        results = api.search(engine="google_scholar_profiles", q="Sunggyeol Oh")
        print(f"Found {len(results.profiles)} profiles.")
    except Exception as e:
        print(f"Profile search failed: {e}")

def test_scott():
    print("\n--- Testing Profile Search 'Scott McCrickard' (Standard Robust Behavior) ---")
    try:
        api = GoogleScholar(backend='selenium')
        
        # This now uses the robust publication-search fallback by default
        results = api.search(engine="google_scholar_profiles", q="Scott McCrickard")
        
        if results.profiles:
             print(f"Search successful! Found {len(results.profiles)} profiles.")
             p = results.profiles[0]
             print(f"Name: {p.name}")
             print(f"ID: {p.author_id}")
             print(f"Affiliation: {p.affiliations}")
        else:
             print("Search failed.")

    except Exception as e:
        print(f"Scott McCrickard test failed: {e}")

if __name__ == "__main__":
    # Note: Requests backend often gets blocked (429) without proxies.
    # test_requests() 
    
    # Author Search (specific ID)
    test_authors()
    
    # Selenium Backend Tests (requires Chrome)
    test_selenium()
    
    # User requested tests
    test_sunggyeol()
    test_scott()
