# Certificate Fonts Configuration

## Overview
This directory contains font files for certificate generation. The system uses professional serif fonts to ensure consistent rendering across localhost and production servers.

## Current Font Configuration
The certificate generation system (`exams/utils.py`) uses **Liberation Serif** fonts as the primary choice, which are:
- ✓ Available on all Linux servers (standard system fonts)
- ✓ Available on Windows systems
- ✓ Available on macOS
- ✓ Provides consistent rendering everywhere
- ✓ Professional appearance for certificates

## Fonts Used
- **Liberation Serif Bold** → Certificate Title, Student Name, Course Name
- **Liberation Serif Regular** → Description Text, Footer

## How to Add Custom Premium Fonts

### Option 1: Add Google Fonts (Recommended for Premium Look)

1. **Download fonts from Google Fonts:**
   - Cinzel Bold (for titles): https://fonts.google.com/specimen/Cinzel
   - Playfair Display Bold (for names): https://fonts.google.com/specimen/Playfair+Display
   - Poppins SemiBold (for course): https://fonts.google.com/specimen/Poppins
   - Merriweather Regular (for text): https://fonts.google.com/specimen/Merriweather

2. **Download TTF files:**
   - Right-click "Download family" on Google Fonts page
   - Extract the TTF files from the zip
   - Place them in this directory (`static/fonts/`)

3. **Update the certificate code** in `exams/utils.py`:
   ```python
   font_cert = get_font("Cinzel-Bold.ttf", 85)
   font_name = get_font("PlayfairDisplay-Bold.ttf", 78)
   font_course = get_font("Poppins-SemiBold.ttf", 42)
   font_content = get_font("Merriweather-Regular.ttf", 24)
   ```

### Option 2: Add System Fonts to Static Directory

For production servers, copy system fonts to static/fonts/:
```bash
# Linux production server
cp /usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf static/fonts/
cp /usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf static/fonts/

# Or use equivalent paths for your server
```

### Option 3: Use Embedded Font Files (Safest for Production)

1. Download TTF files for your chosen fonts
2. Place them in `static/fonts/` directory
3. Update `exams/utils.py` with the exact filenames
4. Run `python manage.py collectstatic` before deploying

## Production Deployment Checklist

✓ **Before deploying to production:**
1. Place all TTF font files in `static/fonts/`
2. Run `python manage.py collectstatic --noinput`
3. Verify fonts are copied to `staticfiles/fonts/`
4. Test certificate generation on staging server
5. Verify fonts render correctly in generated PDFs

✓ **Troubleshooting:**
- If fonts don't load on production, ensure `collectstatic` was run
- Check server permissions on `staticfiles/` directory
- Verify font files are readable (644 permissions)
- Check Django STATIC_ROOT and STATICFILES_DIRS configuration

## Font File Naming Convention

When adding custom fonts, use standard TTF file names:
- `FontName-Regular.ttf` (normal weight)
- `FontName-Bold.ttf` (bold weight)
- `FontName-Italic.ttf` (italic)
- `FontName-BoldItalic.ttf` (bold + italic)

Example:
```
static/fonts/
├── LiberationSerif-Regular.ttf
├── LiberationSerif-Bold.ttf
├── Cinzel-Bold.ttf
└── PlayfairDisplay-Bold.ttf
```

## Current Font Loading System

The `get_font()` function in `exams/utils.py` searches fonts in this priority order:

1. **Django static fonts** (`static/fonts/`)
2. **System fonts** (platform-specific paths)
3. **Fallback fonts** (cross-platform available fonts)
4. **Default font** (PIL fallback)

This ensures certificates look identical on localhost and production!

## License & Credits

- **Liberation Fonts** - Free Software Foundation (GPL)
- **Google Fonts** - Open source font collection (OFL License)

All fonts used must comply with open-source licenses for commercial use.
