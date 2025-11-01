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

TIMEOUT_SECONDS = 10  # slightly higher for slower endpoints

def now_ts():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

def first_line(txt: str) -> str:
    return (txt.strip().splitlines() or [""])[0] if isinstance(txt, str) else ""

# ========================
# ABC iView (Akamai + HMAC)  — PATCHED with retries & logging
# ========================

SECRET_ABC = b'android.content.res.Resources'
ABC_API_BASE = 'https://api.iview.abc.net.au'
ABC_AUTH_PATH_TEMPLATE = '/auth/hls/sign?ts={ts}&hn={hn}&d=android-tablet'
ABC_TOKEN_SPOOF_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (PlayStation 4) AppleWebKit/531.3 (KHTML, like Gecko) SCEE/1.0 Nuanti/2.0',
    'Origin': 'http://tv.iview.abc.net.au',
    'Referer': 'http://tv.iview.abc.net.au/playstation.php',
    'Accept': '*/*',
}
ABC_LIVE_STREAM_MAP = {
    'abc-vic': {
        'hn': 'LS1807V001S00',
        'akamaiBase': 'https://abc-iview-mediapackagestreams-1.akamaized.net/out/v1/3198d7aadc42410abd6a68b1ac2f4e36/index.m3u8'
    },
    # add more ABC entries if you want
}

def abc_generate_url(hn, akamai_base_url, max_retries=3):
    """
    Patched: retry token fetch; log status/body; optional M3U8 sanity probe.
    Returns the final Akamai master URL with hdnea token or None on failure.
    """
    ts = str(int(time.time()))
    auth_path = ABC_AUTH_PATH_TEMPLATE.replace('{ts}', ts).replace('{hn}', hn)
    sig = hmac.new(SECRET_ABC, auth_path.encode('utf-8'), hashlib.sha256).hexdigest()
    token_url = f"{ABC_API_BASE}{auth_path}&sig={sig}"

    for attempt in range(1, max_retries + 1):
        try:
            r = requests.get(token_url, headers=ABC_TOKEN_SPOOF_HEADERS, timeout=TIMEOUT_SECONDS)
            if r.ok:
                token = r.text.strip()
                final_url = f"{akamai_base_url}?hdnea={token}"

                # Optional quick sanity check (won't fail the run if this errors)
                try:
                    m = requests.get(final_url, timeout=TIMEOUT_SECONDS, headers={'User-Agent': 'Python-ABC-Checker'})
                    fl = first_line(m.text)
                    if 200 <= m.status_code < 300 and fl.startswith('#EXTM3U'):
                        print(f"[ABC] M3U8 sanity OK ({m.status_code})")
                    else:
                        print(f"[ABC] M3U8 sanity WARN status={m.status_code} firstLine='{fl[:80]}'")
                except requests.exceptions.RequestException as me:
                    print(f"[ABC] M3U8 check ERROR: {type(me).__name__}: {me}")

                return final_url

            body = (r.text or '')[:200].replace('\n', ' ')
            print(f"[ABC] Attempt {attempt}/{max_retries} token fetch failed "
                  f"({r.status_code}) for hn={hn}; body: {body}")

        except requests.exceptions.RequestException as e:
            print(f"[ABC] Attempt {attempt}/{max_retries} network error for hn={hn}: {type(e).__name__}: {e}")

        if attempt < max_retries:
            backoff = 2 ** (attempt - 1)
            time.sleep(backoff)

    print("[ABC] Giving up after retries.")
    return None

# ========================
# 9Now (Nine)
# ========================

NINE_NOW_API_BASE = 'https://api.9now.com.au/web/live-experience'
NINE_REGION = 'vic'
NINE_CHANNEL_SLUGS = ['channel-9', 'gem', 'go', 'life', 'rush']

def nine_fetch_url(slug, region=NINE_REGION, max_retries=2):
    params = {
        'device': 'web',
        'slug': slug,
        'streamParams': 'web,chrome,macos',
        'region': region,
        'offset': 0
    }
    for attempt in range(1, max_retries + 1):
        try:
            r = requests.get(NINE_NOW_API_BASE, params=params, timeout=TIMEOUT_SECONDS)
            if not r.ok:
                print(f"[9Now] Fail {r.status_code} for {slug}")
            else:
                data = r.json()
                url = (
                    data.get('data', {})
                        .get('getLXP', {})
                        .get('stream', {})
                        .get('video', {})
                        .get('url')
                )
                if url:
                    return url
                print(f"[9Now] Missing URL in JSON for {slug}")
        except requests.exceptions.RequestException as e:
            print(f"[9Now] Attempt {attempt}/{max_retries} error {slug}: {e}")
        if attempt < max_retries:
            time.sleep(1)
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

def sbs_fetch_manifest(stream_key, max_retries=2):
    endpoint = f"https://pubads.g.doubleclick.net/ssai/event/{stream_key}/streams"
    for attempt in range(1, max_retries + 1):
        try:
            r = requests.post(endpoint, headers={'Content-Type': 'application/json'}, timeout=TIMEOUT_SECONDS)
            if r.ok:
                data = r.json()
                manifest = data.get('stream_manifest')
                if manifest:
                    return manifest
                print(f"[SBS] No stream_manifest for {stream_key}")
            else:
                print(f"[SBS] SSAI fail {r.status_code} for {stream_key}")
        except requests.exceptions.RequestException as e:
            print(f"[SBS] Attempt {attempt}/{max_retries} error {stream_key}: {e}")
        if attempt < max_retries:
            time.sleep(1)
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

def seven_fetch_url(key, max_retries=2):
    api = SEVEN_CHANNEL_CONFIG[key]['API_URL']
    for attempt in range(1, max_retries + 1):
        try:
            r = requests.get(api, headers={'User-Agent': 'Seven-Grabber'}, allow_redirects=True, timeout=TIMEOUT_SECONDS)
            if not r.ok:
                print(f"[Seven] API fail {r.status_code} for {key}")
            else:
                data = r.json()
                src = data.get('media', {}).get('sources', [{}])[0].get('src')
                if src:
                    return SEVEN_MODIFICATION_REGEX.sub('.m3u8?', src)
                print(f"[Seven] No 'src' for {key}")
        except requests.exceptions.RequestException as e:
            print(f"[Seven] Attempt {attempt}/{max_retries} error {key}: {e}")
        if attempt < max_retries:
            time.sleep(1)
    return None

# ========================
# 10play (Network 10) — PATCHED with retries & logging
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

def ten_fetch_config(max_retries=3):
    cfg_url = f"{CONFIG_URL_10}?SystemName=android&manufacturer=nvidia"
    for attempt in range(1, max_retries + 1):
        try:
            r = requests.get(cfg_url, headers=HEADERS_10, timeout=TIMEOUT_SECONDS)
            if r.ok:
                return r.json()
            print(f"[10play] Config fail {r.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"[10play] Config attempt {attempt}/{max_retries} error: {e}")
        if attempt < max_retries:
            time.sleep(1)
    raise RuntimeError("10play config fetch failed after retries")

def ten_fetch_live_channels(state='VIC', max_retries=3):
    cfg = ten_fetch_config()
    live_endpoint = cfg['liveTvEndpoint']
    full = f"{live_endpoint}/{state}?limit=32"
    headers = {**HEADERS_10, 'X-N10-SIG': ten_x_n10_sig(full)}

    for attempt in range(1, max_retries + 1):
        try:
            r = requests.get(full, headers=headers, timeout=TIMEOUT_SECONDS)
            if r.ok:
                data = r.json()
                chs = data.get('channels', [])
                if chs:
                    return chs
                print("[10play] Empty channels list")
            else:
                print(f"[10play] Live channels fail {r.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"[10play] Live attempt {attempt}/{max_retries} error: {e}")
        if attempt < max_retries:
            time.sleep(1)
    return []

def ten_channel_url_from_streamkey(stream_key):
    # DAI master
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

    for attempt in range(1, max_retries + 1):
        try:
            r = requests.put(GITHUB_API_URL, headers=headers, data=json.dumps(payload), timeout=30)
            r.raise_for_status()
            commit_url = r.json().get('commit', {}).get('html_url')
            print(f"[GitHub] Success! {commit_url}")
            return True
        except requests.exceptions.RequestException as e:
            print(f"[GitHub] Upload failed (attempt {attempt}/{max_retries}): {e}")
        if attempt < max_retries:
            backoff = 2 ** (attempt - 1)
            print(f"Retrying in {backoff}s...")
            time.sleep(backoff)
    print("[GitHub] Max retries reached.")
    return False

# ========================
# Main
# ========================

def main():
    results = {"timestamp": now_ts()}

    # ABC (patched)
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

    # 10play (patched)
    try:
        print("[10play] fetching live channels …")
        channels = ten_fetch_live_channels('VIC')
        for ch in channels:
            key = ch.get('key')
            sk = ch.get('streamKey')
            if key and sk:
                # prefix with "10-" to keep flat namespace + avoid collisions
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
