"""
One-time script to download Liberation fonts into static/fonts/.
Liberation Sans = drop-in replacement for Arial
Liberation Serif = drop-in replacement for Times New Roman

Run this once on your server:
    python download_fonts.py
"""
import os
import io
import zipfile
import urllib.request

FONTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'fonts')
# Using GitHub release of Liberation Fonts (SIL Open Font License)
LIBERATION_URL = "https://github.com/liberationfonts/liberation-fonts/files/7261482/liberation-fonts-ttf-2.1.5.zip"

NEEDED_FONTS = [
    "LiberationSans-Regular.ttf",
    "LiberationSans-Bold.ttf",
    "LiberationSerif-Regular.ttf",
    "LiberationSerif-Bold.ttf",
]


def download():
    os.makedirs(FONTS_DIR, exist_ok=True)

    # Check if already downloaded
    all_exist = all(os.path.exists(os.path.join(FONTS_DIR, f)) for f in NEEDED_FONTS)
    if all_exist:
        print("All fonts already exist. Skipping download.")
        return

    print(f"Downloading Liberation Fonts from GitHub...")
    try:
        req = urllib.request.Request(LIBERATION_URL, headers={'User-Agent': 'Mozilla/5.0'})
        response = urllib.request.urlopen(req, timeout=30)
        zip_data = response.read()
    except Exception as e:
        print(f"GitHub download failed: {e}")
        print("Trying alternative source...")
        # Fallback: try direct from a mirror
        alt_url = "https://github.com/liberationfonts/liberation-fonts/files/7261482/liberation-fonts-ttf-2.1.5.zip"
        try:
            req = urllib.request.Request(alt_url, headers={'User-Agent': 'Mozilla/5.0'})
            response = urllib.request.urlopen(req, timeout=30)
            zip_data = response.read()
        except Exception as e2:
            print(f"Alternative download also failed: {e2}")
            print("\nPlease manually download Liberation Fonts and place these files in static/fonts/:")
            for f in NEEDED_FONTS:
                print(f"  - {f}")
            return

    zf = zipfile.ZipFile(io.BytesIO(zip_data))
    extracted = 0
    for member in zf.namelist():
        basename = os.path.basename(member)
        if basename in NEEDED_FONTS:
            data = zf.read(member)
            dest = os.path.join(FONTS_DIR, basename)
            with open(dest, 'wb') as f:
                f.write(data)
            print(f"  Extracted: {basename}")
            extracted += 1

    if extracted == 0:
        # Try extracting any .ttf files
        for member in zf.namelist():
            if member.endswith('.ttf'):
                basename = os.path.basename(member)
                data = zf.read(member)
                dest = os.path.join(FONTS_DIR, basename)
                with open(dest, 'wb') as f:
                    f.write(data)
                print(f"  Extracted: {basename}")
                extracted += 1

    print(f"\nDone! {extracted} font files saved to {FONTS_DIR}")


if __name__ == '__main__':
    download()
