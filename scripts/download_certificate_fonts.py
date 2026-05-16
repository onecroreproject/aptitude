"""
Download premium certificate fonts (OFL-licensed) into static/fonts/.

Run once locally, commit the resulting *.ttf files to the repo, then:
    python manage.py collectstatic --noinput

Fonts pulled (all SIL Open Font License — free for commercial use, variable
weight axis — actual weight is selected at render time by PIL):
  * Playfair Display   -> Certificate title & student name (used at Bold 700)
  * Cormorant Garamond -> Sub-headings & course banner    (used at Bold 700 / Medium 500)
  * Montserrat         -> Body description & footer       (used at Regular 400 / Medium 500)
"""

from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TARGET_DIR = PROJECT_ROOT / "static" / "fonts"

# (local_filename, [candidate_urls]) — first reachable URL wins.
# Source files are variable fonts named like "Family[wght].ttf" in the
# google/fonts repository. We save them under bracket-free filenames so
# Django collectstatic and Windows file tooling stay happy.
FONTS: list[tuple[str, list[str]]] = [
    (
        "PlayfairDisplay-Variable.ttf",
        [
            "https://raw.githubusercontent.com/google/fonts/main/ofl/playfairdisplay/PlayfairDisplay%5Bwght%5D.ttf",
            "https://cdn.jsdelivr.net/gh/google/fonts@main/ofl/playfairdisplay/PlayfairDisplay%5Bwght%5D.ttf",
        ],
    ),
    (
        "CormorantGaramond-Variable.ttf",
        [
            "https://raw.githubusercontent.com/google/fonts/main/ofl/cormorantgaramond/CormorantGaramond%5Bwght%5D.ttf",
            "https://cdn.jsdelivr.net/gh/google/fonts@main/ofl/cormorantgaramond/CormorantGaramond%5Bwght%5D.ttf",
        ],
    ),
    (
        "Montserrat-Variable.ttf",
        [
            "https://raw.githubusercontent.com/google/fonts/main/ofl/montserrat/Montserrat%5Bwght%5D.ttf",
            "https://cdn.jsdelivr.net/gh/google/fonts@main/ofl/montserrat/Montserrat%5Bwght%5D.ttf",
        ],
    ),
]

MIN_BYTES = 20 * 1024  # any real TTF will exceed 20 KB


def fetch(url: str, dest: Path) -> bool:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (certificate-font-installer)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
    except Exception as exc:  # noqa: BLE001
        print(f"    ! failed: {exc}")
        return False
    if len(data) < MIN_BYTES:
        print(f"    ! too small ({len(data)} bytes), skipping")
        return False
    dest.write_bytes(data)
    print(f"    + saved {len(data) // 1024} KB -> {dest.relative_to(PROJECT_ROOT)}")
    return True


def main() -> int:
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Target: {TARGET_DIR}")
    missing = []
    for filename, urls in FONTS:
        dest = TARGET_DIR / filename
        if dest.exists() and dest.stat().st_size >= MIN_BYTES:
            print(f"= {filename} (already present, {dest.stat().st_size // 1024} KB)")
            continue
        print(f"> {filename}")
        ok = False
        for url in urls:
            print(f"    fetching {url}")
            if fetch(url, dest):
                ok = True
                break
        if not ok:
            missing.append(filename)

    if missing:
        print("\nMissing fonts (download manually from https://fonts.google.com):")
        for name in missing:
            print(f"  - {name}")
        return 1
    print("\nAll premium certificate fonts installed.")
    print("Next: run  python manage.py collectstatic --noinput  before deploying.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
