#!/usr/bin/env python3
"""
Interactive Google Scholar API Demo
Allows users to choose backend and engine for testing
"""

from google_scholar_api import GoogleScholar
import sys

def print_banner():
    print("\n" + "="*70)
    print("           Google Scholar API - Interactive Demo")
    print("="*70)

def choose_backend():
    """Let user choose backend (only selenium now)"""
    print("\n" + "-"*70)
    print("STEP 1: Backend")
    print("-"*70)
    print("\nSelenium Backend (robust, production-ready)")
    print("  - More resistant to rate limiting")
    print("  - Best for: All types of searches")
    print("  - Requires: Chrome/Chromium installed")
    print("\n✓ Using Selenium backend")
    
    return "selenium"

def choose_engine():
    """Let user choose search engine type"""
    print("\n" + "-"*70)
    print("STEP 2: Choose Search Engine")
    print("-"*70)
    print("\n1. Scholar Search (google_scholar)")
    print("   - Search for publications by keywords")
    print("   - Returns: Papers, citations, authors")
    print("\n2. Author Details (google_scholar_author)")
    print("   - Get author profile by ID")
    print("   - Returns: Name, affiliation, articles, interests")
    print("   - Most reliable option!")
    print("\n3. Profile Search (google_scholar_profiles)")
    print("   - Find author profiles by name")
    print("   - Returns: Profile matches with IDs")
    print("\n4. Citation Search (google_scholar_cite)")
    print("   - Get citation formats (BibTeX, etc.)")
    print("   - Returns: Citation links and formats")
    
    while True:
        choice = input("\nEnter your choice (1-4): ").strip()
        if choice == "1":
            return "google_scholar"
        elif choice == "2":
            return "google_scholar_author"
        elif choice == "3":
            return "google_scholar_profiles"
        elif choice == "4":
            return "google_scholar_cite"
        else:
            print("Invalid choice. Please enter a number between 1-4.")

def get_search_params(engine):
    """Get search parameters based on engine type"""
    print("\n" + "-"*70)
    print("STEP 3: Enter Search Parameters")
    print("-"*70)
    
    if engine == "google_scholar":
        query = input("\nEnter search query (e.g., 'Deep Learning'): ").strip()
        num = input("Number of results (default 10): ").strip()
        num = int(num) if num.isdigit() else 10
        return {"q": query, "num": num}
    
    elif engine == "google_scholar_author":
        print("\nExamples of author IDs:")
        print("  - JicYPdAAAAAJ (Geoffrey Hinton)")
        print("  - WLN3QrAAAAAJ (Yann LeCun)")
        print("  - kukA0LcAAAAJ (Yoshua Bengio)")
        author_id = input("\nEnter author ID: ").strip()
        return {"author_id": author_id}
    
    elif engine == "google_scholar_profiles":
        query = input("\nEnter author name (e.g., 'Andrew Ng'): ").strip()
        return {"q": query}
    
    elif engine == "google_scholar_cite":
        cid = input("\nEnter citation ID (data-cid from a paper): ").strip()
        return {"q": cid}

def display_scholar_results(results):
    """Display publication search results"""
    print("\n" + "="*70)
    print("RESULTS")
    print("="*70)
    
    if results.search_information and results.search_information.total_results:
        print(f"\nTotal Results: ~{results.search_information.total_results:,}")
    
    if not results.organic_results:
        print("\n⚠️  No results found (possibly rate limited)")
        return
    
    print(f"\nShowing {len(results.organic_results)} results:\n")
    
    for i, res in enumerate(results.organic_results, 1):
        print(f"[{i}] {res.title}")
        if res.link:
            print(f"    Link: {res.link}")
        if res.authors:
            authors = ', '.join([a.name for a in res.authors[:5]])
            print(f"    Authors: {authors}")
        if res.publication_info:
            print(f"    Info: {res.publication_info[:100]}")
        if res.inline_links and res.inline_links.cited_by:
            cited = res.inline_links.cited_by.get('total', 'N/A')
            print(f"    Cited by: {cited}")
        if res.snippet:
            print(f"    Snippet: {res.snippet[:150]}...")
        print()

def display_author_results(results):
    """Display author profile results"""
    print("\n" + "="*70)
    print("RESULTS")
    print("="*70)
    
    if not results.author:
        print("\n⚠️  No author profile found")
        return
    
    author = results.author
    print(f"\n✓ Author Profile Found\n")
    print(f"Name: {author.name}")
    if author.affiliations:
        print(f"Affiliation: {author.affiliations}")
    if author.email:
        print(f"Email: {author.email}")
    if author.website:
        print(f"Website: {author.website}")
    
    if author.interests:
        interests = ', '.join([i.title for i in author.interests[:5]])
        print(f"Interests: {interests}")
    
    if results.articles:
        print(f"\nPublications ({len(results.articles)} shown):\n")
        for i, article in enumerate(results.articles[:10], 1):
            print(f"  [{i}] {article.title}")
            if article.publication_info:
                print(f"      {article.publication_info}")
            if article.link:
                print(f"      Link: {article.link}")

def display_profile_results(results):
    """Display profile search results"""
    print("\n" + "="*70)
    print("RESULTS")
    print("="*70)
    
    if not results.profiles:
        print("\n⚠️  No profiles found")
        return
    
    print(f"\n✓ Found {len(results.profiles)} profile(s):\n")
    
    for i, profile in enumerate(results.profiles, 1):
        print(f"[{i}] {profile.name}")
        print(f"    Author ID: {profile.author_id}")
        if profile.affiliations:
            print(f"    Affiliation: {profile.affiliations}")
        if profile.email:
            print(f"    Email: {profile.email}")
        if profile.interests:
            interests = ', '.join([intr.title for intr in profile.interests[:3]])
            print(f"    Interests: {interests}")
        print()

def display_cite_results(results):
    """Display citation results"""
    print("\n" + "="*70)
    print("RESULTS")
    print("="*70)
    
    if results.citations:
        print("\n✓ Citation Formats:\n")
        for i, citation in enumerate(results.citations, 1):
            print(f"[{i}] {citation.get('title', 'N/A')}")
            print(f"    {citation.get('snippet', '')}\n")
    
    if results.links:
        print("\nDownload Links:\n")
        for i, link in enumerate(results.links, 1):
            print(f"  [{i}] {link.get('title', 'N/A')}: {link.get('link', '')}")
    
    if not results.citations and not results.links:
        print("\n⚠️  No citation information found")

def run_search(backend_name, engine, params):
    """Execute the search and display results"""
    print("\n" + "="*70)
    print("EXECUTING SEARCH")
    print("="*70)
    print(f"\nBackend: {backend_name.upper()}")
    print(f"Engine: {engine}")
    print(f"Parameters: {params}")
    
    try:
        # Initialize API
        print("\nInitializing API...")
        api = GoogleScholar(backend=backend_name)
        print("✓ API initialized")
        
        # Execute search
        print("\nExecuting search...")
        results = api.search(engine=engine, **params)
        print("✓ Search completed")
        
        # Display results based on engine type
        if engine == "google_scholar":
            display_scholar_results(results)
        elif engine == "google_scholar_author":
            display_author_results(results)
        elif engine == "google_scholar_profiles":
            display_profile_results(results)
        elif engine == "google_scholar_cite":
            display_cite_results(results)
        
        # Display metadata
        if results.search_metadata:
            print("\n" + "-"*70)
            print("Metadata:")
            if results.search_metadata.request_time_taken:
                print(f"  Request time: {results.search_metadata.request_time_taken:.2f}s")
            if results.search_metadata.parsing_time_taken:
                print(f"  Parsing time: {results.search_metadata.parsing_time_taken:.2f}s")
            if results.search_metadata.total_time_taken:
                print(f"  Total time: {results.search_metadata.total_time_taken:.2f}s")
        
        return True
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Search cancelled by user")
        return False
    except Exception as e:
        print(f"\n\n✗ Error occurred: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main interactive loop"""
    print_banner()
    
    print("\nWelcome to the Google Scholar API Interactive Demo!")
    print("\nThis tool allows you to test different backends and engines.")
    
    while True:
        try:
            # Get user choices
            backend = choose_backend()
            engine = choose_engine()
            params = get_search_params(engine)
            
            # Run search
            success = run_search(backend, engine, params)
            
            # Ask if user wants to continue
            print("\n" + "="*70)
            again = input("\nWould you like to run another search? (y/n): ").strip().lower()
            if again != 'y' and again != 'yes':
                break
        
        except KeyboardInterrupt:
            print("\n\nExiting...")
            break
    
    print("\n" + "="*70)
    print("Thank you for using Google Scholar API!")
    print("="*70 + "\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nExiting...")
        sys.exit(0)

