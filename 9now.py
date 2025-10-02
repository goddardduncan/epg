import requests
import json
import base64
import time
from datetime import datetime, timezone # Added for timestamp generation

#Config

GITHUB_TOKEN = 'MY_TOKEN'
GITHUB_OWNER = 'goddardduncan'
GITHUB_REPO = 'epg'
GITHUB_PATH = '9now.json'
GITHUB_MESSAGE = 'Automated M3U8 Token Update via Python'
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{GITHUB_PATH}"
NINE_NOW_API_BASE = 'https://api.9now.com.au/web/live-experience'
CHANNEL_SLUGS = {
    "mjh-channel-9-vic": "channel-9",
    "mjh-gem-vic": "gem",
    "mjh-go-vic": "go",
    "mjh-life-vic": "life",
    "mjh-rush-vic": "rush"
}

# --- Core Functions ---

def fetch_channel_url(slug):
    """
    Fetches the tokenized M3U8 URL for a given 9Now channel slug.
    This replicates the 'curl | jq' logic from your shell script.
    """
    print(f"Fetching URL for channel slug: {slug}...")
    
    # URL parameters configured based on your shell script:
    # device=web&slug={slug}&streamParams=web%2Cchrome%2Cmacos&region=vic&offset=0
    params = {
        'device': 'web',
        'slug': slug,
        'streamParams': 'web,chrome,macos',
        'region': 'vic',
        'offset': 0
    }

    try:
        # Added a check for the response object
        response = None
        response = requests.get(NINE_NOW_API_BASE, params=params, timeout=10)
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
        
        data = response.json()
        
        # Accessing the stream URL, replicating the 'jq' path: .data.getLXP.stream.video.url
        video_url = data.get('data', {}).get('getLXP', {}).get('stream', {}).get('video', {}).get('url')

        if video_url:
            print(f"Success: {slug} URL found.")
            return video_url
        else:
            print(f"Warning: Could not extract video URL for {slug}.")
            return None

    except requests.exceptions.RequestException as e:
        print(f"Error fetching URL for {slug}: {e}")
        # Pass the response object to error handling in case we got one before timeout
        if response is not None and not response.ok:
            try:
                error_data = response.json()
                print(f"API Response Error Details: {error_data}")
            except json.JSONDecodeError:
                print(f"API returned non-JSON error response: {response.text[:100]}...")
        return None

def create_content():
    """
    Fetches all channel URLs and structures them into a JSON string,
    including a 'timestamp' field in the required format.
    """
    # Generate timestamp in ISO 8601 format with 'Z' (Zulu/UTC) suffix, matching the example: 2025-10-02T20:06:49.118Z
    timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    
    new_data = {}
    new_data["timestamp"] = timestamp # Add the timestamp field first
    
    for channel_name, slug in CHANNEL_SLUGS.items():
        url = fetch_channel_url(slug)
        if url:
            new_data[channel_name] = url
        # Pause briefly to be polite to the 9Now API
        time.sleep(0.5)

    # Convert the Python dictionary to a JSON formatted string, ensuring it's pretty-printed
    return json.dumps(new_data, indent=4)

def get_file_sha():
    """
    Retrieves the current SHA hash of the file from GitHub, which is required for updates.
    """
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # Added a response variable to be available in the catch block
    response = None
    try:
        print(f"\nRetrieving current SHA for {GITHUB_PATH}...")
        response = requests.get(GITHUB_API_URL, headers=headers, timeout=10)
        response.raise_for_status()
        
        file_data = response.json()
        sha = file_data.get('sha')
        print(f"Current SHA retrieved: {sha}")
        return sha

    except requests.exceptions.RequestException as e:
        print(f"Error retrieving file SHA: {e}")
        # Check if we got a response and it's a 404
        if response is not None and response.status_code == 404:
             print("File not found on GitHub. Assuming first upload (no SHA required).")
             return None # Return None if file does not exist (for initial creation)
        return None

def upload_file(content, sha, max_retries=3):
    """
    Uploads the new content to GitHub, requiring the SHA for updates.
    This replicates the 'uploadFile' and 'retryUpload' logic.
    """
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # The content must be Base64 encoded for the GitHub API
    encoded_content = base64.b64encode(content.encode('utf-8')).decode('utf-8')

    payload = {
        "message": GITHUB_MESSAGE,
        "content": encoded_content,
    }
    
    # SHA is required for updating an existing file, but not for creating a new one
    if sha:
        payload["sha"] = sha

    for attempt in range(max_retries):
        response = None # Reset response for each attempt
        print(f"\nAttempting to upload file (Attempt {attempt + 1}/{max_retries})...")
        try:
            response = requests.put(GITHUB_API_URL, headers=headers, data=json.dumps(payload), timeout=15)
            response.raise_for_status()

            print(f"{GITHUB_PATH} updated successfully!")
            print(f"Commit URL: {response.json().get('commit', {}).get('html_url')}")
            return True

        except requests.exceptions.RequestException as e:
            print(f"Failed to update file (Attempt {attempt + 1}): {e}")
            if response is not None:
                try:
                    error_data = response.json()
                    print(f"GitHub API Error Details: {error_data}")
                except json.JSONDecodeError:
                    print(f"GitHub API returned non-JSON error response: {response.text[:100]}...")

            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff (1s, 2s, 4s...)
                print(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                print("Max retries reached. Upload failed.")
                return False

def main():
    """
    Main function to run the token collection and GitHub update workflow.
    """
    if GITHUB_TOKEN == 'YOUR_ACTUAL_GITHUB_TOKEN_HERE':
        print("CRITICAL ERROR: Please update the 'GITHUB_TOKEN' variable in the script with your GitHub Personal Access Token.")
        return

    # 1. Collect all tokenized URLs and format the new content
    new_content_json = create_content()
    
    try:
        parsed_content = json.loads(new_content_json)
    except json.JSONDecodeError:
        print("\nERROR: Failed to create valid JSON content. Aborting GitHub upload.")
        return

    # Check that we have a timestamp and all expected channels
    expected_keys = set(CHANNEL_SLUGS.keys())
    actual_channel_keys = set(parsed_content.keys()) - {"timestamp"}
    
    if not new_content_json or len(actual_channel_keys) < len(CHANNEL_SLUGS):
        print("\nERROR: Not all channel URLs were successfully retrieved. Aborting GitHub upload.")
        return

    print("\n--- New Content Summary ---")
    print(new_content_json)
    print("---------------------------")

    # 2. Get the current file SHA
    current_sha = get_file_sha()
    
    # 3. Upload the new content
    upload_file(new_content_json, current_sha)

if __name__ == "__main__":
    main()
