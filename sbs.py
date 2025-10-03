import requests
import json
import base64
import time
import os
from datetime import datetime, timezone

# ========================
# Config
# ========================

GITHUB_OWNER = 'goddardduncan'
GITHUB_REPO = 'epg'
GITHUB_PATH = 'sbs.json'
GITHUB_MESSAGE = 'Automated SBS SSAI Token Update via Python'
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{GITHUB_PATH}"

# Google DFP SSAI event IDs -> channel keys
# Keys become the JSON keys in sbs.json
CHANNEL_EVENTS = {
    "sbs": "57xy4s1FS1-sXx624PRryg",
    "sbs-viceland": "-55BKEWMTourUcUrCJnKqg",
    "sbs-food": "jebMy0KUTe-xe7RbPTaBDA",
    "sbs-world-movies": "hk8zv5vkQsS6OO0FkiiHrA",
    "nitv": "nUp81RPuRVSmDcOjT9yOKw",
}

GITHUB_TOKEN = os.environ.get('GH_TOKEN')

if not GITHUB_TOKEN:
    print("Error: The GH_TOKEN environment variable is missing.")
    exit(1)

# ========================
# Core functions
# ========================

def fetch_stream_manifest(event_id):
    """
    POST to the SSAI streams endpoint for a given event ID and return .stream_manifest
    Example: https://pubads.g.doubleclick.net/ssai/event/<event_id>/streams
    """
    url = f"https://pubads.g.doubleclick.net/ssai/event/{event_id}/streams"
    try:
        # Empty POST body, reasonable timeout
        resp = requests.post(url, timeout=12)
        resp.raise_for_status()
        data = resp.json()
        manifest = data.get("stream_manifest")
        if not manifest:
            print(f"Warning: No stream_manifest in response for event {event_id}.")
            return None
        return manifest
    except requests.exceptions.RequestException as e:
        print(f"Error fetching manifest for event {event_id}: {e}")
        # Try to show API error body if JSON
        try:
            err_json = resp.json() if resp is not None else None
            if err_json:
                print(f"API Error Details: {err_json}")
        except Exception:
            if resp is not None and resp.text:
                print(f"Non-JSON error body (truncated): {resp.text[:200]}...")
        return None

def create_content():
    """
    Build the JSON payload with a UTC ISO-8601 Z timestamp and channel URLs.
    """
    timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    output = {"timestamp": timestamp}

    for channel_key, event_id in CHANNEL_EVENTS.items():
        print(f"Fetching {channel_key} (event: {event_id})...")
        url = fetch_stream_manifest(event_id)
        if url:
            output[channel_key] = url
        # Be polite between requests
        time.sleep(0.4)

    return json.dumps(output, indent=4)

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
    """
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/vnd.github.v3+json"
    }

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
    new_content_json = create_content()

    # Validate JSON
    try:
        parsed = json.loads(new_content_json)
    except json.JSONDecodeError:
        print("\nERROR: Generated content is not valid JSON. Aborting.")
        return

    # Ensure all channels are present
    missing = [k for k in CHANNEL_EVENTS.keys() if k not in parsed]
    if missing:
        print(f"\nERROR: Missing channel(s) in output: {', '.join(missing)}. Aborting upload.")
        print("Current JSON:")
        print(new_content_json)
        return

    print("\n--- New Content Summary ---")
    print(new_content_json)
    print("---------------------------")

    sha = get_file_sha()
    upload_file(new_content_json, sha)

if __name__ == "__main__":
    main()
