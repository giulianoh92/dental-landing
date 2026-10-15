# DentalOdoo Landing Page

Static landing page for [`dental.giulianoh.dev`](https://dental.giulianoh.dev). The Odoo Apps Store QA reviewer reaches this URL from the module manifest, so it must always be online and coherent with the product.

## Stack

- HTML 5 (no framework, no build step)
- Tailwind CSS via CDN (`<script src="https://cdn.tailwindcss.com"></script>`)
- Inter font via Google Fonts CDN
- Vanilla JS (none, scroll smooth via CSS)
- Heroicons inline SVG (no external icon font)

## Structure

```
landing/
├── index.html              # English landing (canonical /, hreflang en/x-default)
├── es/
│   ├── index.html          # Spanish landing (/es/)
│   └── articulos/          # Spanish articles: index.html + <slug>/index.html
├── robots.txt              # Allow all + sitemap reference
├── sitemap.xml             # Every page, hreflang alternates for the two landings
├── _headers                # Cloudflare Pages security & cache headers
├── scripts/check_seo.py    # SEO consistency check (stdlib only)
├── README.md               # This file
└── assets/
    ├── icon.png            # Logo (88x88, ~80 KB)
    ├── og-image.png        # OG share image (placeholder = icon)
    └── *.png               # Screenshots used by the landings and the articles
```

## SEO check

Run from the repository root before every push (no dependencies, exits 1 on any failure):

```bash
python3 scripts/check_seo.py
```

It verifies title, description, canonical, JSON-LD, hreflang reciprocity, local links and assets, `sitemap.xml` (must list exactly the pages in the repo) and `robots.txt`. When adding a page, add it to `sitemap.xml`.

## Local preview

```bash
cd landing/
python3 -m http.server 8000
# open http://localhost:8000
```

## Deploy options

### 1. Cloudflare Pages (recommended)

Free tier, automatic HTTPS, automatic deploys on `git push`.

1. Open <https://dash.cloudflare.com/?to=/:account/pages/new>.
2. **Connect to Git** (when the repo is on GitHub) or **Direct Upload** (drag the `landing/` folder).
3. Build configuration:
   - **Framework preset:** None
   - **Build command:** *(leave empty)*
   - **Build output directory:** `/`
   - **Root directory:** `landing/` (only if monorepo)
4. After the first deploy, go to **Custom domains** -> **Set up a custom domain** -> `dental.giulianoh.dev`.
5. Cloudflare will auto-create the `CNAME` since DNS is already on Cloudflare.

The `_headers` file is honored automatically by Cloudflare Pages.

### 2. GitHub Pages

1. Create a `gh-pages` branch (or use `/docs` on `main`).
2. Copy the contents of `landing/` to the root of that branch.
3. Add a `CNAME` file containing exactly `dental.giulianoh.dev`.
4. In **Settings -> Pages**, point to the branch and enable **Enforce HTTPS**.
5. In Cloudflare DNS, add a `CNAME dental -> giulianohillebrand.github.io` (proxied).

Note: GitHub Pages ignores `_headers`. Security headers will need to be set via Cloudflare Transform Rules.

### 3. Self-hosted Nginx

```nginx
server {
    listen 443 ssl http2;
    server_name dental.giulianoh.dev;

    root /var/www/dental-landing;
    index index.html;

    # Security
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Permissions-Policy "geolocation=(), microphone=(), camera=()" always;

    location /assets/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    location / {
        try_files $uri $uri/ =404;
    }
}
```

## Replacing the placeholder assets

The screenshots in `assets/` are copies of the ones shipped in `gh_dental_clinic/static/description/`. Replace them with higher-fidelity captures when ready. **Keep the filenames** so the HTML does not need to be updated:

| File | Current source | Recommended replacement |
|---|---|---|
| `assets/icon.png` | `gh_dental_clinic/static/description/icon.png` | Same (already final) |
| `assets/og-image.png` | Copy of `icon.png` | Custom 1200x630 OG image with product name + visual |
| `assets/screenshot-1.png` | `01_consultation_form.png` | Higher-res hero capture |
| `assets/screenshot-2.png` | `02_patient_odontogram.png` | Higher-res odontogram capture |
| `assets/screenshot-3.png` | `03_appointment_list.png` | Capture of `gh_dental_clinic_account` (e.g. invoice wizard) |

## Pending content placeholders

- `#docs` links currently point at the GitHub repo URL. Update to the published docs site when available.
- The `Privacy policy` footer link is a placeholder (`#`). Replace once the legal page is live.

## License

Source code of the landing page itself: free to reuse.
Module code, branding and product name are licensed under **OPL-1**.
