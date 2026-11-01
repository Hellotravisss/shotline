"""Compose: raw capture + copy + theme → store-size PNG, via headless Chrome.

Each slide is rendered twice: once to dump the DOM (the page writes a fit/overflow
report into <body data-report>), once to screenshot. Reports land in out/report.json
for `shotline check`.
"""
import base64
import html
import json
import pathlib
import re
import subprocess
import tempfile

from .config import Config
from .devices import device

CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
TEMPLATE = (pathlib.Path(__file__).parent / 'templates' / 'slide.html').read_text(encoding='utf-8')

# Two opinionated starting points. Override any token under "theme" in shotline.json.
THEMES = {
    # High-contrast neo-brutalism: flat saturated ground, thick black rules, hard offset shadows.
    'brutal': {
        'bg': '#240046', 'ink': '#FFFFFF', 'muted': 'rgba(255,255,255,.72)', 'line': 'rgba(255,255,255,.28)',
        'accents': ['#CCFF00', '#FF00FF', '#00D4FF', '#FFB800'], 'accentInk': '#000000',
        'surface': 'background-image:linear-gradient(rgba(255,255,255,.045) 2px,transparent 2px),'
                   'linear-gradient(90deg,rgba(255,255,255,.045) 2px,transparent 2px);background-size:calc(var(--w)/12) calc(var(--w)/12)',
        'emphasis': 'color:var(--accent-ink);background:var(--accent);padding:0 .14em;display:inline-block;'
                    'transform:rotate(-1.5deg);box-shadow:.06em .06em 0 #000;margin:.05em 0',
        'shadow': 'calc(var(--w)*.022) calc(var(--w)*.022) 0 var(--accent),0 0 0 4px #000',
        'tracking': {'zh': '.02em', 'default': '-.02em'},
    },
    # Quiet editorial: warm paper, serif display type, one coloured word, soft shadow.
    'editorial': {
        'bg': '#F4F1EC', 'ink': '#141414', 'muted': '#5B5750', 'line': 'rgba(0,0,0,.14)',
        'accents': ['#D9442B', '#1F5FD1', '#1E7A4C', '#B5741A'], 'accentInk': '#FFFFFF',
        'surface': '',
        'emphasis': 'color:var(--accent);background:linear-gradient(transparent 72%,color-mix(in srgb,var(--accent) 22%,transparent) 72%)',
        'shadow': '0 calc(var(--w)*.03) calc(var(--w)*.08) rgba(0,0,0,.18)',
        'tracking': {'zh': '.01em', 'default': '-.025em'},
        'fonts': {
            'url': 'https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;9..144,800&family=Noto+Serif+SC:wght@500;900&family=Inter+Tight:wght@500;700&display=block',
            'display': "'Fraunces','Noto Serif SC',serif", 'body': "'Inter Tight','Noto Serif SC',sans-serif",
        },
    },
}
DEFAULT_FONTS = {
    'url': 'https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@500;700;900&family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,700;12..96,800&display=block',
    'display': "'Bricolage Grotesque','Noto Sans SC',sans-serif", 'body': "'Bricolage Grotesque','Noto Sans SC',sans-serif",
}
CJK = {'zh', 'zh-Hans', 'zh-Hant', 'ja', 'ko'}


def theme_for(cfg: Config) -> dict:
    t = cfg.get('theme', {})
    base = dict(THEMES[t.get('preset', 'brutal')])
    base.update({k: v for k, v in t.items() if k != 'preset'})
    base.setdefault('fonts', DEFAULT_FONTS)
    return base


def _img(path: pathlib.Path) -> str:
    if not path.exists():
        raise SystemExit(f'missing raw capture: {path} — run `shotline capture` or add it by hand')
    return '<img src="data:image/png;base64,' + base64.b64encode(path.read_bytes()).decode() + '">'


def build_html(cfg: Config, locale: str, dev_name: str, n: int, slide: dict) -> str:
    d, th = device(dev_name), theme_for(cfg)
    w, h = d['size']
    scale = slide.get('scale', 1.0)
    cjk = locale.split('-')[0] in CJK or locale in CJK
    accent = slide.get('accent') or th['accents'][(n - 1) % len(th['accents'])]
    layout = slide.get('layout', 'hero')

    lines = cfg.text(slide['headline'], locale).split('\n')
    lines_html = ''.join(f'<span class="line">{_emph(html.escape(l))}</span>' for l in lines)
    sub = cfg.text(slide.get('sub'), locale)
    trust = cfg.text(slide.get('trust'), locale)
    eyebrow = cfg.text(slide.get('eyebrow', cfg.get('eyebrow')), locale)
    # Cover mark: the app's own logo file, used as is. It sits on a plate (theme
    # `logoPlate`) so a logo that shares the ground colour still reads.
    logo = slide.get('logo')
    logo_html = ''
    if logo:
        lp = (cfg.root / logo)
        if not lp.exists():
            raise SystemExit(f'missing logo: {lp}')
        mime = 'image/svg+xml' if lp.suffix == '.svg' else 'image/png' if lp.suffix == '.png' else 'image/jpeg'
        logo_html = f'<img class="logo" alt="" src="data:{mime};base64,' + base64.b64encode(lp.read_bytes()).decode() + '">'

    if layout == 'wall':
        items = slide.get('items', {})
        items = items.get(locale, []) if isinstance(items, dict) else items
        devices, lst = '', '<ul>' + ''.join(f'<li>{html.escape(i)}</li>' for i in items) + '</ul>'
    elif layout == 'mosaic':
        devices = '<div class="grid">' + ''.join(
            f'<div class="device">{_img(cfg.raw_path(locale, dev_name, s))}</div>' for s in slide['shots']) + '</div>'
        lst = ''
    else:
        devices, lst = f'<div class="device">{_img(cfg.raw_path(locale, dev_name, slide["shot"]))}</div>', ''

    fonts = th['fonts']
    repl = {
        '__FONT_URL__': fonts['url'], '__FONT__': fonts['body'], '__FONT_DISPLAY__': fonts['display'],
        '__W__': w, '__H__': h, '__PAD__': int(w * .06), '__GAP__': int(d['type']['headline'] * .5),
        '__BG__': slide.get('bg', th['bg']), '__INK__': th['ink'], '__MUTED__': th['muted'], '__LINE__': th['line'],
        '__ACCENT__': accent, '__ACCENT_INK__': th['accentInk'],
        '__H1__': int(d['type']['headline'] * scale), '__SUB__': d['type']['sub'], '__TRUST__': d['type']['trust'],
        '__FRAME_W__': int(w * d['frame']['width']), '__FRAME_R__': int(w * d['frame']['radius']),
        '__BEZEL__': int(w * d['frame']['bezel']), '__SHADOW__': th['shadow'],
        '__SURFACE__': th['surface'], '__EMPHASIS__': th['emphasis'],
        '__TRACKING__': th['tracking']['zh' if cjk else 'default'],
        '__LAYOUT__': layout, '__LINES__': lines_html,
        '__LOGO__': logo_html, '__LOGO_PLATE__': th.get('logoPlate', '#FFFFFF'),
        '__EYEBROW__': f'<div class="eyebrow">{_emph_b(html.escape(eyebrow))}</div>' if eyebrow else '',
        '__SUB_HTML__': f'<p class="sub">{html.escape(sub)}</p>' if sub else '',
        '__TRUST_HTML__': f'<p class="trust"><span>{html.escape(trust)}</span></p>' if trust else '',
        '__LIST__': lst, '__DEVICES__': devices,
    }
    out = TEMPLATE
    for k, v in repl.items():
        out = out.replace(k, str(v))
    return out


def _emph(s: str) -> str:
    """*word* marks the one emphasised segment of a headline line."""
    return re.sub(r'\*(.+?)\*', r'<em>\1</em>', s)


def _emph_b(s: str) -> str:
    return re.sub(r'\*(.+?)\*', r'<b>\1</b>', s)


def _chrome(args: list[str], page: pathlib.Path, w: int, h: int, tmp: str) -> subprocess.CompletedProcess:
    return subprocess.run([CHROME, '--headless=new', f'--user-data-dir={tmp}/p', '--hide-scrollbars',
                           '--force-device-scale-factor=1', f'--window-size={w},{h}', '--virtual-time-budget=10000',
                           *args, page.as_uri()], capture_output=True, text=True, timeout=180)


def render(cfg: Config, locale: str, dev_name: str, n: int, slide: dict) -> dict:
    w, h = device(dev_name)['size']
    out = cfg.out_path(locale, dev_name, n)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        page = pathlib.Path(tmp) / 'slide.html'
        page.write_text(build_html(cfg, locale, dev_name, n, slide), encoding='utf-8')
        dom = _chrome(['--dump-dom'], page, w, h, tmp).stdout
        _chrome([f'--screenshot={out}'], page, w, h, tmp)
    m = re.search(r'data-report="([^"]*)"', dom)
    report = json.loads(html.unescape(m.group(1))) if m else {'overflow': ['report missing — fonts or script failed']}
    return {'file': out.name, 'locale': locale, 'device': dev_name, 'slide': n, **report}


def compose(cfg: Config, only_locale=None, only_device=None) -> list[dict]:
    reports = []
    for dev_name in cfg.devices:
        if only_device and dev_name != only_device:
            continue
        for locale in cfg.locales:
            if only_locale and locale != only_locale:
                continue
            for n, slide in enumerate(cfg['slides'], 1):
                r = render(cfg, locale, dev_name, n, slide)
                flag = ' ⚠ shrunk' if r.get('shrunk') else ''
                flag += ' ✖ ' + '; '.join(r['overflow']) if r.get('overflow') else ''
                print(f"  {r['file']}{flag}")
                reports.append(r)
    (cfg.out / 'report.json').write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding='utf-8')
    return reports
