"""Load a shotline.json and resolve its paths relative to the file.

One JSON holds everything that is cheap to change (copy, layout, theme, capture steps).
Raw captures are expensive and often not regenerable — they live in `raw/` and belong
in git. Rendered output in `out/` is disposable.
"""
import json
import pathlib


class Config:
    def __init__(self, path: str):
        self.path = pathlib.Path(path).resolve()
        self.root = self.path.parent
        self.data = json.loads(self.path.read_text(encoding='utf-8'))
        self.raw = self.root / self.data.get('rawDir', 'raw')
        self.out = self.root / self.data.get('outDir', 'out')

    def __getitem__(self, key):
        return self.data[key]

    def get(self, key, default=None):
        return self.data.get(key, default)

    @property
    def locales(self) -> list[str]:
        return list(self.data['locales'])

    @property
    def devices(self) -> list[str]:
        return list(self.data.get('devices', ['iphone']))

    def raw_path(self, locale: str, device: str, shot: str) -> pathlib.Path:
        return self.raw / f'{locale}-{device}-{shot}.png'

    def out_path(self, locale: str, device: str, n: int) -> pathlib.Path:
        return self.out / f'{locale}-{device}-{n:02d}.png'

    def text(self, value, locale: str) -> str:
        """Copy fields are either a plain string or {locale: string}."""
        if value is None:
            return ''
        if isinstance(value, str):
            return value
        if locale in value:
            return value[locale]
        raise SystemExit(f'missing "{locale}" copy in {value}')
