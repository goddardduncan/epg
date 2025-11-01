import os
import re
import json
import time
import hmac
import hashlib
import base64
import requests
from urllib.parse import urlparse
from datetime import datetime, timezone

# ========================
# GitHub (reuse config)
# ========================

GITHUB_OWNER = 'goddardduncan'
GITHUB_REPO = 'epg'
GITHUB_PATH = 'redirect_urls.json'  # combined output file
GITHUB_MESSAGE = 'Automated live URL update (ABC/Nine/SBS/Seven/Ten)'
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{GITHUB_PATH}"
GITHUB_TOKEN = os.environ.get('GH_TOKEN')

if not GITHUB_TOKEN:
    raise SystemExit("Error: The GH_TOKEN environment variable is missing.")

# ========================
# Shared
# ========================

TIMEOUT_SECONDS = 8

def now_ts():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

# ========================
# ABC iView (Akamai + HMAC)
# ========================

SECRET_ABC = b'android.content.res.Resources'
ABC_API_BASE = 'https://api.iview.abc.net.au'
ABC_AUTH_PATH_TEMPLATE = '/auth/hls/sign?ts={ts}&hn={hn}&d=android-tablet'
ABC_TOKEN_SPOOF_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (PlayStation 4) AppleWebKit/531.3 (KHTML, like Gecko) SCEE/1.0 Nuanti/2.0',
    'Origin': 'http://tv.iview.abc.net.au',
    'Referer': 'http://tv.iview.abc.net.au/playstation.php'
}
ABC_LIVE_STREAM_MAP = {
    'abc-vic': {
        'hn': 'LS1807V001S00',
        'akamaiBase': 'https://abc-iview-mediapackagestreams-1.akamaized.net/out/v1/3198d7aadc42410abd6a68b1ac2f4e36/index.m3u8'
    },
    # add more ABC entries if you want
}

def abc_generate_url(hn, akamai_base_url):
    try:
        ts = str(int(time.time()))
        auth_path = ABC_AUTH_PATH_TEMPLATE.replace('{ts}', ts).replace('{hn}', hn)
        sig = hmac.new(SECRET_ABC, auth_path.encode('utf-8'), hashlib.sha256).hexdigest()
        token_url = f"{ABC_API_BASE}{auth_path}&sig={sig}"
        r = requests.get(token_url, headers=ABC_TOKEN_SPOOF_HEADERS, timeout=TIMEOUT_SECONDS)
        if not r.ok:
            print(f"[ABC] Token fetch failed ({r.status_code}) for hn={hn}")
            return None
        token = r.text.strip()
        return f"{akamai_base_url}?hdnea={token}"
    except Exception as e:
        print(f"[ABC] Error: {e}")
        return None

# ========================
# 9Now (Nine)
# ========================

NINE_NOW_API_BASE = 'https://api.9now.com.au/web/live-experience'
NINE_REGION = 'vic'
NINE_CHANNEL_SLUGS = ['channel-9', 'gem', 'go', 'life', 'rush']

def nine_fetch_url(slug, region=NINE_REGION):
    params = {
        'device': 'web',
        'slug': slug,
        'streamParams': 'web,chrome,macos',
        'region': region,
        'offset': 0
    }
    try:
        r = requests.get(NINE_NOW_API_BASE, params=params, timeout=TIMEOUT_SECONDS)
        if not r.ok:
            print(f"[9Now] Fail {r.status_code} for {slug}")
            return None
        data = r.json()
        return (
            data.get('data', {})
                .get('getLXP', {})
                .get('stream', {})
                .get('video', {})
                .get('url')
        )
    except Exception as e:
        print(f"[9Now] Error {slug}: {e}")
        return None

# ========================
# SBS (Google DAI / SSAI)
# ========================

SBS_CHANNELS = [
    {'name': 'SBS',               'key': 'sbs',       'streamKey': '57xy4s1FS1-sXx624PRryg'},
    {'name': 'SBS Food',          'key': 'sbsfood',   'streamKey': 'jebMy0KUTe-xe7RbPTaBDA'},
    {'name': 'Viceland',          'key': 'viceland',  'streamKey': '-55BKEWMTourUcUrCJnKqg'},
    {'name': 'SBS World Movies',  'key': 'sbsmovies', 'streamKey': 'hk8zv5vkQsS6OO0FkiiHrA'},
    {'name': 'NITV',              'key': 'nitv',      'streamKey': 'nUp81RPuRVSmDcOjT9yOKw'},
]

def sbs_fetch_manifest(stream_key):
    endpoint = f"https://pubads.g.doubleclick.net/ssai/event/{stream_key}/streams"
    try:
        r = requests.post(endpoint, headers={'Content-Type': 'application/json'}, timeout=TIMEOUT_SECONDS)
        if not r.ok:
            print(f"[SBS] SSAI fail {r.status_code} for {stream_key}")
            return None
        data = r.json()
        return data.get('stream_manifest')
    except Exception as e:
        print(f"[SBS] Error {stream_key}: {e}")
        return None

# ========================
# Seven (7plus) – SWM / Brightcove JSON → M3U8
# ========================

SEVEN_CHANNEL_CONFIG = {
    'seven': {
        'API_URL': 'https://videoservice.swm.digital/playback?appId=7plus&deviceType=web&platformType=web&ppId=&deviceId=c33b2962-635c-436e-a9e1-42fa94603da3&pc=3196&advertid=null&accountId=5650355166001&referenceId=6363897092112&deliveryId=csai&videoType=live&marketId=26&tvid=null&ozid=fd471639-2e3b-418f-9223-9150fa68fab2&cp.encryptionType=cbcs&cp.drmSystems=widevine&cp.containerFormat=cmaf&cp.supportedCodecs=avc&deviceSubType=desktop&cp.drmAuth=true',
        'name': 'Seven',
    },
    'mate': {
        'API_URL': 'https://videoservice.swm.digital/playback?appId=7plus&deviceType=web&platformType=web&ppId=&deviceId=c33b2962-635c-436e-a9e1-42fa94603da3&pc=3196&advertid=null&accountId=5650355166001&referenceId=6363901773112&deliveryId=csai&videoType=live&marketId=26&tvid=null&ozid=ced4d5ad-ef72-4197-a530-9d990d03f965&cp.encryptionType=cbcs&cp.drmSystems=widevine&cp.containerFormat=cmaf&cp.supportedCodecs=avc&deviceSubType=desktop&cp.drmAuth=true',
        'name': '7mate',
    },
    'seven2': {
        'API_URL': 'https://videoservice.swm.digital/playback?appId=7plus&deviceType=web&platformType=web&ppId=&deviceId=c33b2962-635c-436e-a9e1-42fa94603da3&pc=3196&advertid=null&accountId=5650355166001&referenceId=6371773836112&deliveryId=csai&videoType=live&marketId=26&tvid=null&ozid=ebc45ca8-cb92-4a6b-8e54-1185287ac232&cp.encryptionType=cbcs&cp.drmSystems=widevine&cp.containerFormat=cmaf&cp.supportedCodecs=avc&deviceSubType=desktop&cp.drmAuth=true',
        'name': 'Seven2',
    },
    'flix': {
        'API_URL': 'https://videoservice.swm.digital/playback?appId=7plus&deviceType=web&platformType=web&ppId=&deviceId=c33b2962-635c-436e-a9e1-42fa94603da3&pc=3196&advertid=null&accountId=5650355166001&referenceId=6371776210112&deliveryId=csai&videoType=live&marketId=26&tvid=null&ozid=d0f3cec1-5844-4f3e-b6e3-312245d17563&cp.encryptionType=cbcs&cp.drmSystems=widevine&cp.containerFormat=cmaf&cp.supportedCodecs=avc&deviceSubType=desktop&cp.drmAuth=true',
        'name': 'Flix',
    },
}
SEVEN_MODIFICATION_REGEX = re.compile(r'([A-Z]{2}\.m3u8\?)')

def seven_fetch_url(key):
    api = SEVEN_CHANNEL_CONFIG[key]['API_URL']
    try:
        r = requests.get(api, headers={'User-Agent': 'Seven-Grabber'}, allow_redirects=True, timeout=TIMEOUT_SECONDS)
        if not r.ok:
            print(f"[Seven] API fail {r.status_code} for {key}")
            return None
        data = r.json()
        src = data.get('media', {}).get('sources', [{}])[0].get('src')
        if not src:
            print(f"[Seven] No 'src' for {key}")
            return None
        return SEVEN_MODIFICATION_REGEX.sub('.m3u8?', src)
    except Exception as e:
        print(f"[Seven] Error {key}: {e}")
        return None

# ========================
# 10play (Network 10) – HMAC header + Live endpoint → DAI URLs
# ========================

HEX_KEY_10 = 'b918ff793563080c5821c89ee6c415c363cb36d369db1020369ac4b405a0211d'
SECRET_10 = bytes.fromhex(HEX_KEY_10)
CONFIG_URL_10 = 'https://10play.com.au/api/v1/config'
HEADERS_10 = {
    'user-agent': 'Mozilla/5.0 (Linux; Android 11; SHIELD Android TV; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/136.0.7103.125 Mobile Safari/537.36 10play/6.28.0 UAP',
    'tp-acceptfeature': 'v2/Live',
    'tp-platform': 'UAP',
    'Accept': 'application/json',
}

def ten_x_n10_sig(url):
    ts = str(int(time.time()))
    p = urlparse(url)
    signed = p.path + (f"?{p.query}" if p.query else "")
    msg = f"{ts}:{signed}".encode('utf-8')
    sig = hmac.new(SECRET_10, msg, hashlib.sha256).hexdigest()
    return f"{ts}_{sig}"

def ten_fetch_config():
    cfg_url = f"{CONFIG_URL_10}?SystemName=android&manufacturer=nvidia"
    r = requests.get(cfg_url, headers=HEADERS_10, timeout=TIMEOUT_SECONDS)
    r.raise_for_status()
    return r.json()

def ten_fetch_live_channels(state='VIC'):
    cfg = ten_fetch_config()
    live_endpoint = cfg['liveTvEndpoint']
    full = f"{live_endpoint}/{state}?limit=16"
    headers = {**HEADERS_10, 'X-N10-SIG': ten_x_n10_sig(full)}
    r = requests.get(full, headers=headers, timeout=TIMEOUT_SECONDS)
    r.raise_for_status()
    return r.json().get('channels', [])

def ten_channel_url_from_streamkey(stream_key):
    return f"https://dai.google.com/ssai/event/{stream_key}/master.m3u8"

# ========================
# GitHub helpers
# ========================

def github_get_file_sha():
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    try:
        r = requests.get(GITHUB_API_URL, headers=headers, timeout=15)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json().get('sha')
    except requests.exceptions.RequestException as e:
        print(f"[GitHub] SHA lookup error: {e}")
        return None

def github_upload_content(content_str, sha=None, max_retries=3):
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/vnd.github.v3+json"
    }
    payload = {
        "message": GITHUB_MESSAGE,
        "content": base64.b64encode(content_str.encode('utf-8')).decode('utf-8')
    }
    if sha:
        payload["sha"] = sha

    for attempt in range(max_retries):
        try:
            r = requests.put(GITHUB_API_URL, headers=headers, data=json.dumps(payload), timeout=30)
            r.raise_for_status()
            commit_url = r.json().get('commit', {}).get('html_url')
            print(f"[GitHub] Success! {commit_url}")
            return True
        except requests.exceptions.RequestException as e:
            print(f"[GitHub] Upload failed (attempt {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                backoff = 2 ** attempt
                print(f"Retrying in {backoff}s...")
                time.sleep(backoff)
            else:
                print("[GitHub] Max retries reached.")
                return False

# ========================
# Main
# ========================

def main():
    results = {"timestamp": now_ts()}

    # ABC
    for slug, data in ABC_LIVE_STREAM_MAP.items():
        print(f"[ABC] {slug} …")
        url = abc_generate_url(data['hn'], data['akamaiBase'])
        if url:
            results[slug] = {"url": url}

    # Nine (9Now)
    for slug in NINE_CHANNEL_SLUGS:
        print(f"[9Now] {slug} …")
        url = nine_fetch_url(slug)
        if url:
            results[slug] = {"url": url}

    # SBS
    for ch in SBS_CHANNELS:
        print(f"[SBS] {ch['key']} …")
        live_url = sbs_fetch_manifest(ch['streamKey'])
        if live_url:
            results[ch['key']] = {"url": live_url}

    # Seven (7plus)
    for key in SEVEN_CHANNEL_CONFIG.keys():
        print(f"[Seven] {key} …")
        url = seven_fetch_url(key)
        if url:
            results[key] = {"url": url}

    # 10play (dynamic list)
    try:
        print("[10play] fetching live channels …")
        channels = ten_fetch_live_channels('VIC')
        for ch in channels:
            key = ch.get('key')
            sk = ch.get('streamKey')
            if key and sk:
                # prefix keys with "10-" to avoid collisions and keep flat map
                results[f"10-{key.lower()}"] = {"url": ten_channel_url_from_streamkey(sk)}
    except Exception as e:
        print(f"[10play] Error fetching channels: {e}")

    # Upload to GitHub
    content_str = json.dumps(results, indent=2)
    sha = github_get_file_sha()
    ok = github_upload_content(content_str, sha)
    if ok:
        print("\n✅ Uploaded redirect URLs to GitHub at", GITHUB_PATH)
    else:
        print("\n❌ Upload failed.")

if __name__ == '__main__':
    main()
