"""Capture: drive the simulator through scripted steps and save raw screenshots.

Uses `xcrun simctl` for lifecycle, deep links, status bar and screenshots, and
AXe (https://github.com/cameroncooke/AXe) for taps and swipes. No UI-test target
or app changes needed; deep links do most of the navigation.

Every shot starts from a cold launch (terminate → launch → open link) because:
  * a deep link to a route that is already on screen often doesn't reload it;
  * opening a link while the app is already frontmost skips iOS's
    "Open in <App>?" confirmation that a link from the home screen triggers.

Step vocabulary (inside "shots" and "setup" in shotline.json):
  {"open": "app://path?x={var}"}       deep link; {var} from capture.vars[locale]
  {"tap": [x, y]}                      point coordinates (iOS points, not pixels)
  {"tap": {"iphone": [x,y], "ipad": [x,y]}}   per-device coordinates
  {"tap": {"label": "Visa Free"}}      by accessibility label (AXe)
  {"swipe": [[x1,y1],[x2,y2]], "duration": 3}  slow drags don't fling — positions repeat
  {"wait": 2}                          seconds
  {"mergeJson": {"file": "Library/…/manifest.json", "set": {"key": "value"}}}
                                       seed app state: merge keys into a JSON file inside the
                                       app's data container (React Native AsyncStorage keeps
                                       small values in RCTAsyncLocalStorage_V1/manifest.json)
  {"defaults": {"key": "value"}}       seed NSUserDefaults (native apps) via `defaults write`

Seed state instead of clicking through it. Typing into forms and spinning date pickers
is the flakiest part of any capture script; one write before launch is not.
"""
import json
import pathlib
import shutil
import subprocess
import time

from .config import Config


def sh(*args, check=True, retries=0, **kw) -> subprocess.CompletedProcess:
    for attempt in range(retries + 1):
        r = subprocess.run(list(args), capture_output=True, text=True, **kw)
        if r.returncode == 0 or not check:
            return r
        if attempt < retries:
            time.sleep(2)
    raise SystemExit(f"command failed ({r.returncode}): {' '.join(map(str, args))}\n{(r.stderr or r.stdout).strip()}")


def axe(*args, udid: str):
    # AXe's first call against a freshly booted device sometimes fails; the second works.
    exe = shutil.which('axe')
    if not exe:
        raise SystemExit('taps/swipes need AXe: https://github.com/cameroncooke/AXe/releases')
    return sh(exe, *map(str, args), '--udid', udid, retries=1)


def resolve_udid(name_or_udid: str) -> str:
    devs = json.loads(sh('xcrun', 'simctl', 'list', 'devices', 'available', '-j').stdout)['devices']
    for runtime in devs.values():
        for d in runtime:
            if name_or_udid in (d['udid'], d['name']):
                return d['udid']
    raise SystemExit(f'simulator "{name_or_udid}" not found (xcrun simctl list devices available)')


def boot(udid: str, status_bar: dict):
    sh('xcrun', 'simctl', 'boot', udid, check=False)          # already booted is fine
    sh('xcrun', 'simctl', 'bootstatus', udid, '-b', timeout=600)
    bar = {'time': '9:41', 'batteryState': 'discharging', 'batteryLevel': '100',
           'wifiBars': '3', 'cellularBars': '4', 'dataNetwork': 'wifi', **status_bar}
    args = []
    for k, v in bar.items():
        args += [f'--{k}', str(v)]
    sh('xcrun', 'simctl', 'status_bar', udid, 'override', *args)


def _pt(spec, dev: str):
    if isinstance(spec, dict) and dev in spec:
        spec = spec[dev]
    return spec


def _subst(s, vars_: dict):
    if not isinstance(s, str):
        return s
    for k, v in vars_.items():
        s = s.replace('{' + k + '}', str(v))
    return s


def run_steps(steps: list, udid: str, dev: str, vars_: dict, bundle: str):
    for step in steps:
        if 'open' in step:
            sh('xcrun', 'simctl', 'openurl', udid, _subst(step['open'], vars_))
            time.sleep(step.get('settle', 3))
        elif 'tap' in step or 'swipe' in step:
            if 'tap' in step:
                t = _pt(step['tap'], dev)
                if isinstance(t, dict) and 'label' in t:
                    axe('tap', '--label', _subst(t['label'], vars_), udid=udid)
                else:
                    axe('tap', '-x', t[0], '-y', t[1], udid=udid)
            else:
                a, b = _pt(step['swipe'], dev)
                axe('swipe', '--start-x', a[0], '--start-y', a[1], '--end-x', b[0], '--end-y', b[1],
                    '--duration', step.get('duration', 3), udid=udid)
            time.sleep(step.get('settle', 1.5))
        elif 'mergeJson' in step or 'defaults' in step:
            # The app caches storage in memory and would write it back over ours.
            sh('xcrun', 'simctl', 'terminate', udid, bundle, check=False)
            if 'defaults' in step:
                for k, v in step['defaults'].items():
                    sh('xcrun', 'simctl', 'spawn', udid, 'defaults', 'write', bundle, k, str(v))
            else:
                spec = step['mergeJson']
                container = sh('xcrun', 'simctl', 'get_app_container', udid, bundle, 'data').stdout.strip()
                f = pathlib.Path(container) / spec['file'].replace('{bundle}', bundle)
                f.parent.mkdir(parents=True, exist_ok=True)
                data = json.loads(f.read_text()) if f.exists() else {}
                data.update({k: _subst(v, vars_) for k, v in spec['set'].items()})
                f.write_text(json.dumps(data))
        elif 'wait' in step:
            time.sleep(step['wait'])
        elif 'launch' in step:
            sh('xcrun', 'simctl', 'terminate', udid, bundle, check=False)
            sh('xcrun', 'simctl', 'launch', udid, bundle)
            time.sleep(step.get('settle', 4))


def capture(cfg: Config, only_locale=None, only_device=None, only_shot=None):
    cap = cfg['capture']
    bundle = cap['bundleId']
    cfg.raw.mkdir(parents=True, exist_ok=True)
    for dev in cfg.devices:
        if only_device and dev != only_device:
            continue
        udid = resolve_udid(cap['simulators'][dev])
        boot(udid, cap.get('statusBar', {}))
        for locale in cfg.locales:
            if only_locale and locale != only_locale:
                continue
            vars_ = cap.get('vars', {}).get(locale, {})
            setup = cap.get('setup', [])
            setup = setup.get(locale, []) if isinstance(setup, dict) else setup   # shared list or per-locale
            run_steps(setup, udid, dev, vars_, bundle)
            for shot, steps in cap['shots'].items():
                if only_shot and shot != only_shot:
                    continue
                sh('xcrun', 'simctl', 'terminate', udid, bundle, check=False)
                launch = ['xcrun', 'simctl', 'launch', udid, bundle, *cap.get('launchArgs', {}).get(locale, [])]
                sh(*launch)
                time.sleep(cap.get('launchWait', 4))
                run_steps(steps, udid, dev, vars_, bundle)
                time.sleep(cap.get('settleBeforeShot', 2))   # let scroll momentum and fades finish
                out = cfg.raw_path(locale, dev, shot)
                sh('xcrun', 'simctl', 'io', udid, 'screenshot', str(out))
                print(f'  {out.name}')
