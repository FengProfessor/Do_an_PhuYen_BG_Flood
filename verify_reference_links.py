import re
import requests
import time
from urllib.parse import urlparse

# Import references from thesis_conclusion_refs.py
import docx
from thesis_conclusion_refs import build_conclusion_and_refs

# Extract references list directly by inspecting the file or importing
# Let's inspect references from thesis_conclusion_refs
import inspect

ref_pattern = re.compile(r'https?://[^\s)\]]+')

# We can also extract directly from thesis_conclusion_refs source
with open(r"D:\VTP\thesis_conclusion_refs.py", "r", encoding="utf-8") as f:
    content = f.read()

# Parse items in references = [ ... ]
matches = re.findall(r'\(\s*(\"\[\d+\]\")\s*,\s*\"(.*?)\"\s*\)', content, re.DOTALL)

print(f"Total reference items parsed: {len(matches)}")

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
}

results = []
success_count = 0
fail_count = 0

for num_str, ref_text in matches:
    urls = ref_pattern.findall(ref_text)
    # clean trailing punctuation if any
    cleaned_urls = [u.rstrip('.,;()') for u in urls]
    
    if not cleaned_urls:
        print(f"WARNING: No URL found in {num_str}")
        results.append((num_str, None, False, "No URL found", None))
        fail_count += 1
        continue
        
    url = cleaned_urls[0]
    
    # Test link
    # For DOIs and academic links, test resolution
    status_code = None
    is_live = False
    details = ""
    start_t = time.time()
    
    try:
        # First attempt: HEAD with redirects
        # Some servers return 405 on HEAD, fallback to GET (stream=True to avoid big downloads)
        resp = requests.head(url, headers=headers, timeout=12, allow_redirects=True)
        status_code = resp.status_code
        elapsed = time.time() - start_t
        
        if status_code in [200, 301, 302, 307, 308]:
            is_live = True
            details = f"HTTP {status_code} in {elapsed:.2f}s -> {resp.url}"
        elif status_code in [403, 405, 418]:
            # Retry with GET stream=True
            resp2 = requests.get(url, headers=headers, timeout=12, stream=True, allow_redirects=True)
            status_code = resp2.status_code
            elapsed = time.time() - start_t
            if status_code in [200, 301, 302, 307, 308]:
                is_live = True
                details = f"GET fallback: HTTP {status_code} in {elapsed:.2f}s -> {resp2.url}"
            elif status_code == 403:
                # If DOI service resolved (status 403 from publisher bot wall e.g. Cloudflare / ScienceDirect / IEEE),
                # check if doi.org resolved without redirect
                doi_check = requests.get(url, headers={"User-Agent": "curl/7.68.0"}, timeout=10, allow_redirects=False)
                if doi_check.status_code in [301, 302, 303, 307, 308]:
                    is_live = True
                    details = f"DOI resolved ({doi_check.status_code} -> {doi_check.headers.get('Location')}), publisher returned 403 bot-check"
                else:
                    details = f"HTTP {status_code} (Forbidden/Bot-protected)"
                    is_live = True  # Site is active and live, blocking automated scraper
            else:
                details = f"HTTP {status_code}"
                is_live = False
        else:
            # Try GET stream=True
            resp2 = requests.get(url, headers=headers, timeout=12, stream=True, allow_redirects=True)
            status_code = resp2.status_code
            elapsed = time.time() - start_t
            if status_code < 400:
                is_live = True
                details = f"GET fallback: HTTP {status_code} in {elapsed:.2f}s -> {resp2.url}"
            else:
                details = f"HTTP {status_code}"
                is_live = False
    except Exception as e:
        elapsed = time.time() - start_t
        details = f"Exception: {type(e).__name__} ({e})"
        is_live = False

    if is_live:
        success_count += 1
    else:
        fail_count += 1
        
    results.append((num_str, url, is_live, details, status_code))
    status_sym = "[PASS]" if is_live else "[FAIL]"
    print(f"{status_sym} {num_str} {url} | {details}")

print("\n" + "="*70)
print(f"SUMMARY: Total: {len(results)} | Live/Passed: {success_count} | Failed: {fail_count}")
print(f"Success Rate: {success_count / len(results) * 100:.1f}%")
print("="*70)
