"""Ship: replace screenshots on App Store Connect, then verify per locale.

Screenshots are locked while a version waits for review. `--cancel-review` cancels a
pending submission first (state → DEVELOPER_REJECTED), which restarts the review
queue — say so to whoever owns the app before using it.

Verification is not optional: uploads can fail per asset while every call returns
200. After uploading, every locale × device set is re-read and must hold exactly the
expected number of shots, in order, all COMPLETE.
"""
from .asc import ASC
from .config import Config
from .devices import device


def ship(cfg: Config, version: str, cancel_review=False, drop=()):
    asc = ASC(cfg['ascAppId'])
    pending = asc.pending_submission()
    if pending:
        if not cancel_review:
            raise SystemExit(f"version is in review ({pending['attributes']['state']}); "
                             'screenshots are locked. Re-run with --cancel-review to pull it.')
        print(f"  cancelling review submission → {asc.cancel_submission(pending['id'])}")
    v = asc.version(version)
    print(f"  version {version}: {v['attributes']['appStoreState']}")
    locs = asc.localizations(v['id'])
    locale_map = cfg.get('ascLocales', {})          # e.g. {"zh": "zh-Hans", "en": "en-US"}
    for dev_name in cfg.devices:
        dtype = device(dev_name)['display_type']
        for locale in cfg.locales:
            asc_locale = locale_map.get(locale, locale)
            if asc_locale not in locs:
                print(f'  ! {asc_locale}: no such localization on {version} — skipped')
                continue
            files = [cfg.out_path(locale, dev_name, n) for n in range(1, len(cfg['slides']) + 1)]
            set_id = asc.replace(locs[asc_locale], dtype, files, drop)
            states = asc.wait_processed(set_id)
            print(f'  {asc_locale} {dtype}: {len(files)} uploaded → {states}')
    return verify(cfg, version)


def verify(cfg: Config, version: str) -> bool:
    asc = ASC(cfg['ascAppId'])
    v = asc.version(version)
    locs = asc.localizations(v['id'])
    locale_map = cfg.get('ascLocales', {})
    want = len(cfg['slides'])
    ok = True
    for locale in cfg.locales:
        loc_id = locs.get(locale_map.get(locale, locale))
        if not loc_id:
            continue
        sets = {s['attributes']['screenshotDisplayType']: s['id'] for s in asc.sets(loc_id)}
        for dev_name in cfg.devices:
            dtype = device(dev_name)['display_type']
            shots = asc.shots(sets[dtype]) if dtype in sets else []
            names = [s['attributes']['fileName'] for s in shots]
            states = {s['attributes']['assetDeliveryState']['state'] for s in shots}
            expected = [cfg.out_path(locale, dev_name, n).name for n in range(1, want + 1)]
            good = names == expected and states <= {'COMPLETE'}
            ok &= good
            print(f"  {'✓' if good else '✖'} {locale}/{dtype}: {len(shots)}/{want} {sorted(states)}"
                  + ('' if names == expected else f'  order/names differ: {names}'))
    return ok


def submit(cfg: Config, version: str) -> bool:
    """Refuses unless every screenshot set verifies — a half-processed set ships as blank tiles."""
    if not verify(cfg, version):
        print('  not submitting: fix the sets above first')
        return False
    asc = ASC(cfg['ascAppId'])
    v = asc.version(version)
    print(f"  {version} → review submission: {asc.submit(v['id'])}")
    return True
