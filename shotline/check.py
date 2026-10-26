"""Check: gates every rendered PNG must pass before upload, plus review sheets.

Gates (exit 1 on any failure):
  size      exact store resolution for its device
  overflow  copy outside the canvas or crowding the device (from the render report)
Warnings (printed, don't fail):
  shrunk    auto-fit had to shrink a headline line — shorten the copy instead
  alpha     PNG has an alpha channel (ASC accepts it, but flatten if a reviewer complains)
Sheets (out/sheet-<locale>-<device>.png):
  a strip of every slide at ~200 px wide — the size of an App Store search result.
  Read it at arm's length: if a headline isn't legible, it isn't working.
"""
import base64
import json
import pathlib
import struct
import subprocess
import tempfile

from .compose import CHROME
from .config import Config
from .devices import device


def png_info(path: pathlib.Path) -> tuple[int, int, bool]:
    with open(path, 'rb') as f:
        head = f.read(33)
    if head[:8] != b'\x89PNG\r\n\x1a\n':
        raise SystemExit(f'{path.name}: not a PNG')
    w, h, _, color_type = struct.unpack('>IIBB', head[16:26])
    return w, h, color_type in (4, 6)


def sheet(cfg: Config, locale: str, dev_name: str, files: list[pathlib.Path]) -> pathlib.Path:
    w, h = device(dev_name)['size']
    tw = 200
    th = round(h * tw / w)
    imgs = ''.join(f'<img src="data:image/png;base64,{base64.b64encode(f.read_bytes()).decode()}" '
                   f'style="width:{tw}px;height:{th}px;border-radius:12px">' for f in files)
    page_w, page_h = len(files) * (tw + 16) + 32, th + 32
    doc = (f'<html><body style="margin:0;background:#f2f2f2;display:flex;gap:16px;padding:16px">{imgs}</body></html>')
    out = cfg.out / f'sheet-{locale}-{dev_name}.png'
    with tempfile.TemporaryDirectory() as tmp:
        p = pathlib.Path(tmp) / 's.html'
        p.write_text(doc)
        subprocess.run([CHROME, '--headless=new', f'--user-data-dir={tmp}/p', '--hide-scrollbars',
                        '--force-device-scale-factor=2', f'--window-size={page_w},{page_h}',
                        f'--screenshot={out}', p.as_uri()], capture_output=True, timeout=120)
    return out


def check(cfg: Config) -> bool:
    report_file = cfg.out / 'report.json'
    reports = {r['file']: r for r in json.loads(report_file.read_text())} if report_file.exists() else {}
    ok = True
    for dev_name in cfg.devices:
        want = device(dev_name)['size']
        for locale in cfg.locales:
            files = [cfg.out_path(locale, dev_name, n) for n in range(1, len(cfg['slides']) + 1)]
            for f in files:
                if not f.exists():
                    print(f'  ✖ {f.name}: missing — run `shotline compose`')
                    ok = False
                    continue
                w, h, alpha = png_info(f)
                r = reports.get(f.name, {})
                problems = []
                if (w, h) != want:
                    problems.append(f'size {w}×{h}, want {want[0]}×{want[1]}')
                problems += r.get('overflow', [])
                notes = [f"line {s['line']} shrunk to {s['scale']}%" for s in r.get('shrunk', [])]
                if alpha:
                    notes.append('has alpha')
                ok &= not problems
                mark = '✖' if problems else ('⚠' if notes else '✓')
                print(f'  {mark} {f.name}  ' + '; '.join(problems + notes))
            present = [f for f in files if f.exists()]
            if present:
                print(f'    sheet → {sheet(cfg, locale, dev_name, present).name}')
    return ok
