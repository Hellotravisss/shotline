"""App Store Connect API — just what screenshot work needs. Stdlib only.

Credentials come from the environment, never from the config file:
    ASC_KEY_ID      10-character key id
    ASC_ISSUER_ID   issuer UUID (App Store Connect → Users and Access → Integrations)
    ASC_KEY_PATH    path to AuthKey_<id>.p8 (default ~/.appstoreconnect/private_keys/AuthKey_<id>.p8)

The JWT is ES256-signed with the system `openssl`; Apple wants the raw r||s signature,
openssl emits DER, so it is unpacked here.
"""
import base64
import hashlib
import json
import os
import pathlib
import subprocess
import time
import urllib.error
import urllib.request

API = 'https://api.appstoreconnect.apple.com'


def _b64(b: bytes) -> bytes:
    return base64.urlsafe_b64encode(b).rstrip(b'=')


def _der_to_raw(der: bytes) -> bytes:
    # SEQUENCE { INTEGER r, INTEGER s }
    assert der[0] == 0x30
    i = 2 if der[1] < 0x80 else 2 + (der[1] & 0x7F)
    out = b''
    for _ in range(2):
        assert der[i] == 0x02
        n = der[i + 1]
        out += der[i + 2:i + 2 + n].lstrip(b'\x00').rjust(32, b'\x00')
        i += 2 + n
    return out


def token() -> str:
    kid = os.environ.get('ASC_KEY_ID')
    iss = os.environ.get('ASC_ISSUER_ID')
    if not kid or not iss:
        raise SystemExit('set ASC_KEY_ID and ASC_ISSUER_ID (and ASC_KEY_PATH if the key is elsewhere)')
    key = os.path.expanduser(os.environ.get('ASC_KEY_PATH', f'~/.appstoreconnect/private_keys/AuthKey_{kid}.p8'))
    now = int(time.time())
    msg = (_b64(json.dumps({'alg': 'ES256', 'kid': kid, 'typ': 'JWT'}).encode()) + b'.' +
           _b64(json.dumps({'iss': iss, 'iat': now, 'exp': now + 900, 'aud': 'appstoreconnect-v1'}).encode()))
    der = subprocess.run(['openssl', 'dgst', '-sha256', '-sign', key], input=msg,
                         capture_output=True, check=True).stdout
    return (msg + b'.' + _b64(_der_to_raw(der))).decode()


class ASC:
    def __init__(self, app_id: str):
        self.app_id = str(app_id)
        self.tok, self.tok_at = token(), time.time()

    def call(self, path: str, method: str = 'GET', body: dict | None = None):
        if time.time() - self.tok_at > 600:          # tokens live 15 min; uploads can take longer
            self.tok, self.tok_at = token(), time.time()
        req = urllib.request.Request(API + path, method=method,
                                     data=json.dumps(body).encode() if body else None,
                                     headers={'Authorization': 'Bearer ' + self.tok, 'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req) as r:
                raw = r.read()
                return r.status, (json.loads(raw) if raw else {})
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b'{}')

    def ok(self, path, method='GET', body=None, expect=(200, 201, 204)):
        st, r = self.call(path, method, body)
        if st not in expect:
            raise SystemExit(f'{method} {path} → {st}: {json.dumps(r)[:600]}')
        return r

    # ── versions & localizations ─────────────────────────────────────────
    def version(self, version_string: str) -> dict:
        r = self.ok(f'/v1/apps/{self.app_id}/appStoreVersions?filter[versionString]={version_string}&filter[platform]=IOS')
        if not r['data']:
            raise SystemExit(f'version {version_string} not found in App Store Connect')
        return r['data'][0]

    def localizations(self, version_id: str) -> dict:
        r = self.ok(f'/v1/appStoreVersions/{version_id}/appStoreVersionLocalizations?limit=50')
        return {l['attributes']['locale']: l['id'] for l in r['data']}

    # ── screenshots ──────────────────────────────────────────────────────
    def sets(self, loc_id: str) -> list:
        return self.ok(f'/v1/appStoreVersionLocalizations/{loc_id}/appScreenshotSets?limit=50')['data']

    def shots(self, set_id: str) -> list:
        return self.ok(f'/v1/appScreenshotSets/{set_id}/appScreenshots?limit=50')['data']

    def upload_one(self, set_id: str, path: pathlib.Path) -> str:
        data = path.read_bytes()
        shot = self.ok('/v1/appScreenshots', 'POST', {'data': {
            'type': 'appScreenshots', 'attributes': {'fileName': path.name, 'fileSize': len(data)},
            'relationships': {'appScreenshotSet': {'data': {'type': 'appScreenshotSets', 'id': set_id}}}}})['data']
        for op in shot['attributes']['uploadOperations']:
            part = data[op['offset']:op['offset'] + op['length']]
            req = urllib.request.Request(op['url'], data=part, method=op['method'],
                                         headers={h['name']: h['value'] for h in op['requestHeaders']})
            urllib.request.urlopen(req).read()
        self.ok(f"/v1/appScreenshots/{shot['id']}", 'PATCH', {'data': {
            'type': 'appScreenshots', 'id': shot['id'],
            'attributes': {'uploaded': True, 'sourceFileChecksum': hashlib.md5(data).hexdigest()}}})
        return shot['id']

    def replace(self, loc_id: str, display_type: str, files: list[pathlib.Path], drop: list[str] = ()):
        """Delete the target set (and any `drop` types), create it fresh, upload in order."""
        for s in self.sets(loc_id):
            if s['attributes']['screenshotDisplayType'] in (display_type, *drop):
                self.ok(f"/v1/appScreenshotSets/{s['id']}", 'DELETE')
        set_id = self.ok('/v1/appScreenshotSets', 'POST', {'data': {
            'type': 'appScreenshotSets', 'attributes': {'screenshotDisplayType': display_type},
            'relationships': {'appStoreVersionLocalization': {'data': {'type': 'appStoreVersionLocalizations', 'id': loc_id}}}}})['data']['id']
        for f in files:
            self.upload_one(set_id, f)
        return set_id

    def wait_processed(self, set_id: str, timeout: int = 300) -> list[str]:
        """Apple processes assets asynchronously; poll until every shot is COMPLETE or FAILED."""
        end = time.time() + timeout
        while True:
            states = [s['attributes']['assetDeliveryState']['state'] for s in self.shots(set_id)]
            if all(s in ('COMPLETE', 'FAILED') for s in states) or time.time() > end:
                return states
            time.sleep(5)

    # ── review submissions ───────────────────────────────────────────────
    def pending_submission(self):
        r = self.ok(f'/v1/reviewSubmissions?filter[app]={self.app_id}&filter[platform]=IOS&limit=10')
        return next((s for s in r['data'] if s['attributes']['state'] in ('WAITING_FOR_REVIEW', 'READY_FOR_REVIEW', 'UNRESOLVED_ISSUES')), None)

    def cancel_submission(self, submission_id: str):
        """Screenshots are locked while a version waits for review — cancel to edit them."""
        return self.ok(f'/v1/reviewSubmissions/{submission_id}', 'PATCH', {'data': {
            'type': 'reviewSubmissions', 'id': submission_id, 'attributes': {'canceled': True}}})['data']['attributes']['state']

    def submit(self, version_id: str) -> str:
        sub = self.ok('/v1/reviewSubmissions', 'POST', {'data': {'type': 'reviewSubmissions', 'attributes': {'platform': 'IOS'},
                      'relationships': {'app': {'data': {'type': 'apps', 'id': self.app_id}}}}})['data']['id']
        self.ok('/v1/reviewSubmissionItems', 'POST', {'data': {'type': 'reviewSubmissionItems', 'relationships': {
            'reviewSubmission': {'data': {'type': 'reviewSubmissions', 'id': sub}},
            'appStoreVersion': {'data': {'type': 'appStoreVersions', 'id': version_id}}}}})
        return self.ok(f'/v1/reviewSubmissions/{sub}', 'PATCH', {'data': {
            'type': 'reviewSubmissions', 'id': sub, 'attributes': {'submitted': True}}})['data']['attributes']['state']
