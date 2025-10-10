import requests
import json
import base64
import time
import os
import re
from datetime import datetime, timezone

# ========================
# Config
# ========================

# GitHub Repository Configuration (MUST BE UPDATED BY THE USER IF DIFFERENT)
GITHUB_OWNER = 'goddardduncan'
GITHUB_REPO = 'epg'
GITHUB_PATH = 'epg.xml' # IMPORTANT: Target file is now epg.xml
GITHUB_MESSAGE = 'Automated XMLTV Melbourne Channel ID Replacement'
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{GITHUB_PATH}"

# XMLTV Source Configuration
EXTERNAL_XML_URL = 'https://xmltv.net/xml_files/Melbourne.xml'

# Array of replacement rules: { 'from': 'string_to_find', 'to': 'replacement_string' }
REPLACEMENT_RULES = [
  # SBS - Original request
  {'from': '273191auepg.com.au', 'to': 'dmg-sbs-sbst'},
  
  # Network 10 channels
  {'from': '250185auepg.com.au', 'to': 'dmg-10-vic'},
  {'from': '403767auepg.com.au', 'to': 'dmg-10peach-vic'},
  {'from': '388610auepg.com.au', 'to': 'dmg-10bold-vic'},
  {'from': '432257auepg.com.au', 'to': 'dmg-10shake-vic'},
  {'from': '431563auepg.com.au', 'to': 'dmg-10-hd-vic'}, # 10 HD

  # ABC channels
  {'from': '92843auepg.com.au', 'to': 'dmg-abc-vic'},
  {'from': '284792auepg.com.au', 'to': 'dmg-abc-kids'},
  {'from': '391136auepg.com.au', 'to': 'dmg-abc-news'},
  
  # More SBS channels
  {'from': '431777auepg.com.au', 'to': 'dmg-sbs-2syd'},
  {'from': '432038auepg.com.au', 'to': 'dmg-sbs-4syd'},
  {'from': '431492auepg.com.au', 'to': 'dmg-sbs-3syd'},
  {'from': '430925auepg.com.au', 'to': 'dmg-sbs-5nsw'},
  
  # Community TV
  {'from': '251882auepg.com.au', 'to': 'dmg-c31'},
  
  # Channel 7 channels
  {'from': '96100auepg.com.au', 'to': 'dmg-seven-mel'},
  {'from': '410799auepg.com.au', 'to': 'dmg-7two-mel'},
  {'from': '388547auepg.com.au', 'to': 'dmg-7mate-mel'},
  {'from': '431544auepg.com.au', 'to': 'dmg-7flix-mel'},
  
  # Channel 9 channels
  {'from': '252342auepg.com.au', 'to': 'dmg-channel-9-vic'},
  {'from': '391132auepg.com.au', 'to': 'dmg-gem-vic'},
  {'from': '407657auepg.com.au', 'to': 'dmg-go-vic'},
  {'from': '431511auepg.com.au', 'to': 'dmg-life-vic'},
  {'from': '432224auepg.com.au', 'to': 'dmg-rush-vic'},
]

# GitHub Token Retrieval
GITHUB_TOKEN = os.environ.get('GH_TOKEN')

if not GITHUB_TOKEN:
    print("Error: The GH_TOKEN environment variable is missing.")
    # Exiting here is necessary if run standalone, but in a main() function
    # we can just return.
    # exit(1)

# ========================
# Core XML Processing Functions
# ========================

def escape_regex(string):
    """
    Helper function to escape special regex characters in a string.
    This is crucial because the channel IDs contain dots (.), which are wildcards in regex.
    """
    # Use re.escape to handle all special characters like '.', '+', etc.
    return re.escape(string)

def generate_xml_content():
    """
    Fetches the XMLTV file, performs all defined channel ID replacements,
    and returns the modified XML content as a string.
    """
    print(f"Fetching XML from: {EXTERNAL_XML_URL}...")

    # 1. Fetch the external XML data
    try:
        # Use a reasonable timeout
        xml_response = requests.get(EXTERNAL_XML_URL, timeout=20)
        # Raise an exception for HTTP error codes (4xx or 5xx)
        xml_response.raise_for_status() 
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Failed to fetch external XML. Exception: {e}")
        return None

    modified_xml_text = xml_response.text

    print(f"Successfully fetched XML (size: {len(modified_xml_text)} bytes).")

    # 2. Pre-process: remove non-breaking spaces (\u00A0)
    modified_xml_text = modified_xml_text.replace('\u00A0', ' ')
    
    replacements_made = 0
    # 3. Modify the content using all replacement rules
    for rule in REPLACEMENT_RULES:
        # Escape the original string to ensure dots are treated as literal characters.
        escaped_from = escape_regex(rule['from'])
        
        # Target the ID string globally.
        # re.DOTALL ensures '.' matches newlines if needed, though usually not for XML IDs
        regex = re.compile(escaped_from, re.IGNORECASE) 
        
        # Use re.sub to perform the replacement and count occurrences
        new_xml_text, count = re.subn(regex, rule['to'], modified_xml_text)
        
        if count > 0:
            print(f"  -> Replaced '{rule['from']}' {count} time(s) with '{rule['to']}'.")
            modified_xml_text = new_xml_text
            replacements_made += count

    print(f"Total replacements made: {replacements_made}")
    return modified_xml_text

# ========================
# GitHub Upload Functions (Adapted from User's Example)
# ========================

def get_file_sha():
    """
    Get the current SHA of the target file (needed for updates).
    Returns None if the file does not exist yet.
    """
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    response = None
    try:
        print(f"\nRetrieving current SHA for {GITHUB_PATH}...")
        response = requests.get(GITHUB_API_URL, headers=headers, timeout=10)
        if response.status_code == 404:
            print("File not found on GitHub. First upload (no SHA required).")
            return None
        response.raise_for_status()
        file_data = response.json()
        sha = file_data.get('sha')
        print(f"Current SHA: {sha}")
        return sha
    except requests.exceptions.RequestException as e:
        print(f"Error retrieving file SHA: {e}")
        if response is not None and response.text:
            print(f"Response (truncated): {response.text[:200]}...")
        return None

def upload_file(content, sha, max_retries=3):
    """
    Base64-encodes and uploads content to GitHub. Includes retries with backoff.
    Since the content is XML, we encode it as UTF-8.
    """
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # Encode the XML content string
    encoded_content = base64.b64encode(content.encode('utf-8')).decode('utf-8')

    payload = {
        "message": GITHUB_MESSAGE,
        "content": encoded_content,
    }
    if sha:
        payload["sha"] = sha

    for attempt in range(max_retries):
        response = None
        print(f"\nUploading {GITHUB_PATH} (attempt {attempt + 1}/{max_retries})...")
        try:
            response = requests.put(GITHUB_API_URL, headers=headers, data=json.dumps(payload), timeout=20)
            response.raise_for_status()
            commit_url = response.json().get('commit', {}).get('html_url')
            print(f"Success! Commit: {commit_url}")
            return True
        except requests.exceptions.RequestException as e:
            print(f"Upload failed: {e}")
            if response is not None:
                try:
                    print(f"GitHub API error: {response.json()}")
                except Exception:
                    if response.text:
                        print(f"Non-JSON body (truncated): {response.text[:200]}...")
            if attempt < max_retries - 1:
                wait = 2 ** attempt
                print(f"Retrying in {wait}s...")
                time.sleep(wait)
            else:
                print("Max retries reached. Upload failed.")
                return False

def main():
    if not GITHUB_TOKEN:
        print("\nFATAL: Cannot proceed without GH_TOKEN environment variable.")
        return

    # 1. Generate the modified XML content
    xml_content = generate_xml_content()
    
    if not xml_content:
        print("\nERROR: Could not generate XML content. Aborting upload.")
        return

    print("\n--- New Content Summary ---")
    print(f"Generated XML content length: {len(xml_content)} bytes")
    # Show first 3 lines of XML for quick verification
    print('\n'.join(xml_content.splitlines()[:3]))
    print("---------------------------")

    # 2. Get current SHA of the file to be updated
    sha = get_file_sha()
    
    # 3. Upload the new XML content
    upload_file(xml_content, sha)

if __name__ == "__main__":
    main()
