#!/usr/bin/env python3
"""Drive an iOS app in a simulator by on-screen text (AXe), for App Store captures.

  drive.py <udid> dump [filter]          list visible elements (label, value, frame)
  drive.py <udid> tap <regex> [nth]      tap the element whose label matches (nth match, 0-based)
  drive.py <udid> tapxy <x> <y>
  drive.py <udid> field <nth> <text>     focus the nth TextField, clear it, type text
  drive.py <udid> swipe <up|down> [dist]
  drive.py <udid> scrollto <regex> [y]   swipe until the label sits near y (points from top)
  drive.py <udid> lang <code>            write the app's language key (SHOTLINE_LANG_KEY, default 'lang') into
                                         React Native AsyncStorage; relaunch afterwards
  drive.py <udid> setfield <nth> <text>  like field, for inputs whose UI collapses at 0 (see below)

Env: SHOTLINE_BUNDLE=<bundle id> (needed by lang/relaunch), AXE=<path to axe> (else PATH).

Field gotcha: `field` clears then types. If the screen hides a block when the value is 0
(a toggle derived from "amount > 0"), clearing collapses it before you can type. `setfield`
keeps the first digit, types the new value after it, then deletes that first digit, so the
value never passes through 0.
  drive.py <udid> relaunch
  drive.py <udid> shot <png>             full-resolution screenshot

Taps are real presses (--down --up --delay 0.08): iOS 26 swallows zero-length taps.
"""
import json, os, re, shutil, subprocess, sys, time

AXE = os.environ.get('AXE') or shutil.which('axe') or os.path.expanduser('~/.local/bin/axe')
BUNDLE = os.environ.get('SHOTLINE_BUNDLE', '')  # the app's bundle id; required for lang/relaunch


def run(*a, check=True):
    return subprocess.run(a, capture_output=True, text=True, check=check).stdout


def elements(udid):
    out = []
    def walk(n):
        if isinstance(n, dict):
            l = n.get('AXLabel'); v = n.get('AXValue'); f = n.get('frame') or {}
            if (l or v) and n.get('type') not in ('Application',):
                out.append({'label': l or '', 'value': v, 'type': n.get('type'), 'x': f.get('x', 0), 'y': f.get('y', 0), 'w': f.get('width', 0), 'h': f.get('height', 0)})
            for c in n.get('children', []): walk(c)
        elif isinstance(n, list):
            for c in n: walk(c)
    walk(json.loads(run(AXE, 'describe-ui', '--udid', udid)))
    seen, uniq = set(), []
    for e in out:
        k = (e['label'], e['type'], round(e['x']), round(e['y']))
        if k not in seen: seen.add(k); uniq.append(e)
    return uniq


def screen(udid):
    app = json.loads(run(AXE, 'describe-ui', '--udid', udid))
    f = (app[0] if isinstance(app, list) else app)['frame']
    return f['width'], f['height']


def press(udid, x, y):
    run(AXE, 'touch', '-x', str(int(x)), '-y', str(int(y)), '--down', '--up', '--delay', '0.08', '--udid', udid)


def find(udid, rx, nth=0):
    W, H = screen(udid)
    hits = [e for e in elements(udid) if re.search(rx, e['label']) and 0 <= e['y'] + e['h'] / 2 <= H and e['type'] != 'StaticText' or
            (re.search(rx, e['label']) and e['type'] == 'StaticText' and 0 <= e['y'] <= H)]
    # prefer tappable elements over plain text at the same place
    hits.sort(key=lambda e: (e['type'] == 'StaticText', e['y']))
    if len(hits) <= nth: raise SystemExit(f'no element matching {rx!r} (found {len(hits)})')
    return hits[nth]


def swipe(udid, direction, dist=400):
    W, H = screen(udid)
    x = W - 30; mid = H * 0.55
    a, b = (mid + dist / 2, mid - dist / 2) if direction == 'up' else (mid - dist / 2, mid + dist / 2)
    run(AXE, 'swipe', '--start-x', str(int(x)), '--start-y', str(int(a)), '--end-x', str(int(x)), '--end-y', str(int(b)), '--duration', '1.8', '--udid', udid)
    time.sleep(1.0)


def main():
    udid, cmd, *args = sys.argv[1:]
    if cmd == 'dump':
        rx = args[0] if args else '.'
        for e in elements(udid):
            if re.search(rx, e['label'] + ' ' + str(e['value'])):
                print(f"{e['type']:<16} {e['label'][:60]!r:<64} v={e['value']!r:<10} x={e['x']:.0f} y={e['y']:.0f} w={e['w']:.0f} h={e['h']:.0f}")
    elif cmd == 'tap':
        e = find(udid, args[0], int(args[1]) if len(args) > 1 else 0)
        press(udid, e['x'] + e['w'] / 2, e['y'] + e['h'] / 2); time.sleep(1.2)
        print('tapped', e['label'][:40], int(e['y']))
    elif cmd == 'tapxy':
        press(udid, float(args[0]), float(args[1])); time.sleep(1.0)
    elif cmd == 'field':
        fields = [e for e in elements(udid) if e['type'] == 'TextField']
        e = fields[int(args[0])]
        press(udid, e['x'] + e['w'] - 12, e['y'] + e['h'] / 2); time.sleep(0.6)
        run(AXE, 'key-sequence', '--keycodes', ','.join(['42'] * 12), '--udid', udid, check=False)
        run(AXE, 'type', args[1], '--udid', udid); time.sleep(0.6)
        print('field', args[0], '=', [f['value'] for f in elements(udid) if f['type'] == 'TextField'][int(args[0])])
    elif cmd == 'setfield':
        fields = [e for e in elements(udid) if e['type'] == 'TextField']
        e = fields[int(args[0])]; old = str(e['value'] or '')
        press(udid, e['x'] + e['w'] - 12, e['y'] + e['h'] / 2); time.sleep(0.6)
        if len(old) > 1: run(AXE, 'key-sequence', '--keycodes', ','.join(['42'] * (len(old) - 1)), '--udid', udid, check=False)
        run(AXE, 'type', args[1], '--udid', udid)
        run(AXE, 'key-sequence', '--keycodes', ','.join(['80'] * len(args[1])), '--udid', udid, check=False)  # cursor left
        run(AXE, 'key-sequence', '--keycodes', '42', '--udid', udid, check=False)  # delete the kept digit
        time.sleep(0.6)
        print('field', args[0], '=', [f['value'] for f in elements(udid) if f['type'] == 'TextField'][int(args[0])])
    elif cmd == 'swipe':
        swipe(udid, args[0], float(args[1]) if len(args) > 1 else 400)
    elif cmd == 'scrollto':
        target = float(args[1]) if len(args) > 1 else 160
        for _ in range(14):
            hits = [e for e in elements(udid) if re.search(args[0], e['label'])]
            W, H = screen(udid)
            if hits:
                y = min(hits, key=lambda e: abs(e['y'] - target))['y']
                if abs(y - target) < 40: print('at', int(y)); return
                d = max(-H * 0.6, min(H * 0.6, y - target))
                swipe(udid, 'up' if d > 0 else 'down', abs(d))
            else:
                swipe(udid, 'up', H * 0.5)
        raise SystemExit(f'could not scroll {args[0]!r} to {target}')
    elif cmd == 'lang':
        data = run('xcrun', 'simctl', 'get_app_container', udid, BUNDLE, 'data').strip()
        p = f'{data}/Library/Application Support/{BUNDLE}/RCTAsyncLocalStorage_V1/manifest.json'
        d = json.load(open(p)); d[os.environ.get('SHOTLINE_LANG_KEY', 'lang')] = args[0]; json.dump(d, open(p, 'w'))
        print('lang', args[0])
    elif cmd == 'relaunch':
        run('xcrun', 'simctl', 'terminate', udid, BUNDLE, check=False)
        run('xcrun', 'simctl', 'launch', udid, BUNDLE); time.sleep(6)
    elif cmd == 'shot':
        run('xcrun', 'simctl', 'io', udid, 'screenshot', args[0]); print('shot', args[0])


if __name__ == '__main__':
    main()
