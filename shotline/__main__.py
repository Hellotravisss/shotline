"""shotline <command> [-c shotline.json] [options]

  capture   drive simulators and save raw screenshots          (simctl + AXe)
  compose   render store-size PNGs from raw captures + copy     (headless Chrome)
  check     gate sizes/overflow, warn on shrunk copy, write review sheets
  ship      upload to App Store Connect and verify               (ASC API)
  verify    re-read App Store Connect and compare with out/
  submit    submit the version for App Review (only after verify passes)
"""
import argparse
import sys

from .config import Config


def main(argv=None):
    sys.stdout.reconfigure(line_buffering=True)   # progress shows up in logs and CI
    p = argparse.ArgumentParser(prog='shotline', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('command', choices=['capture', 'compose', 'check', 'ship', 'verify', 'submit'])
    p.add_argument('-c', '--config', default='shotline.json')
    p.add_argument('--locale')
    p.add_argument('--device')
    p.add_argument('--shot', help='capture only this shot id')
    p.add_argument('--version', help='App Store version string (ship/verify)')
    p.add_argument('--cancel-review', action='store_true', help='ship: pull a pending review to unlock screenshots')
    p.add_argument('--drop', nargs='*', default=[], help='ship: also delete these display types (e.g. APP_IPHONE_65)')
    a = p.parse_args(argv)
    cfg = Config(a.config)

    if a.command == 'capture':
        from .capture import capture
        capture(cfg, a.locale, a.device, a.shot)
    elif a.command == 'compose':
        from .compose import compose
        compose(cfg, a.locale, a.device)
    elif a.command == 'check':
        from .check import check
        sys.exit(0 if check(cfg) else 1)
    elif a.command in ('ship', 'verify', 'submit'):
        if not a.version:
            p.error('--version is required')
        from .ship import ship, submit, verify
        if a.command == 'ship':
            ok = ship(cfg, a.version, a.cancel_review, a.drop)
        elif a.command == 'verify':
            ok = verify(cfg, a.version)
        else:
            ok = submit(cfg, a.version)
        sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
