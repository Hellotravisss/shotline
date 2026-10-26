"""Store canvas sizes and how a device frame sits on each.

Only the sizes App Store Connect still requires are listed: Apple scales the largest
iPhone and iPad sets down to every smaller device, so one set per family is enough.
"""

DEVICES = {
    # 6.9" class (iPhone 16/17 Pro Max). ASC display type is still called APP_IPHONE_67.
    'iphone': {
        'size': (1290, 2796),
        'display_type': 'APP_IPHONE_67',
        'frame': {'width': 0.78, 'radius': 0.093, 'bezel': 0.019},
        'type': {'headline': 132, 'sub': 50, 'trust': 40},
    },
    # 13" iPad Pro. ASC display type APP_IPAD_PRO_3GEN_129 accepts 2064×2752.
    'ipad': {
        'size': (2064, 2752),
        'display_type': 'APP_IPAD_PRO_3GEN_129',
        'frame': {'width': 0.76, 'radius': 0.034, 'bezel': 0.014},
        'type': {'headline': 172, 'sub': 64, 'trust': 50},
    },
}


def device(name: str) -> dict:
    if name not in DEVICES:
        raise SystemExit(f'unknown device "{name}" — use one of: {", ".join(DEVICES)}')
    return DEVICES[name]
