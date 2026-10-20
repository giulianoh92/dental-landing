#!/usr/bin/env python3
"""SEO consistency check for the static landing. Stdlib only.

Run from the repository root:  python3 scripts/check_seo.py
Exits 1 and prints every failure when any check does not pass.
"""
import json
import re
import sys
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://dental.giulianoh.dev"
SKIP_DIRS = {".git", "node_modules", "scripts"}
ARTICLE_PREFIXES = ("/es/articulos/", "/articles/")
EN_ARTICLES = (
    "/articles/dental-clinic-module-odoo/",
    "/articles/odontogram-odoo/",
    "/articles/invoice-dental-consultations-odoo/",
)
# English page -> Spanish counterpart (hreflang pairs; x-default is the English URL)
PAIRS = {
    "/articles/": "/es/articulos/",
    "/articles/dental-clinic-module-odoo/": "/es/articulos/software-odontologico-odoo/",
    "/articles/odontogram-odoo/": "/es/articulos/odontograma-odoo/",
    "/articles/invoice-dental-consultations-odoo/": "/es/articulos/facturar-consultas-odontologicas-odoo/",
}
AUTHOR = {"name": "Giuliano Hillebrand", "url": "https://github.com/giulianoh92"}
STORE = "https://apps.odoo.com/apps/modules/19.0/"
REQUIRED_REDIRECTS = {"/index.html", "/es", "/es/index.html", "/es/articulos", "/articles"}
TRACK_SCRIPT = "/assets/track-v1.js"
TRACKED_PREFIXES = (
    "https://apps.odoo.com/apps/modules/19.0/gh_dental_clinic",
    "https://dental-demo.giulianoh.dev/demo",
)
REDIRECT_MARK = "data-lang-redirect"  # attribute of the redirect <script> on the English home
PRIVACY = {"en": "/privacy/", "es": "/es/privacidad/"}
SM_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.titles = []
        self.description = None
        self.canonicals = []
        self.alternates = {}
        self.jsonld = []
        self.links = []
        self.tracked_links = []
        self.script_srcs = []
        self.imgs = []
        self.footer_hrefs = []
        self.bare_hash_links = 0
        self._in_footer = False
        self._in_title = False
        self._in_jsonld = False
        self._buf = ""

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "title":
            self._in_title, self._buf = True, ""
        elif tag == "meta" and a.get("name") == "description":
            self.description = a.get("content")
        elif tag == "link":
            rel = (a.get("rel") or "").lower()
            if rel == "canonical":
                self.canonicals.append(a.get("href"))
            elif rel == "alternate" and a.get("hreflang"):
                self.alternates[a["hreflang"]] = a.get("href")
        elif tag == "script" and a.get("type") == "application/ld+json":
            self._in_jsonld, self._buf = True, ""
        if tag == "footer":
            self._in_footer = True
        if tag == "img":
            self.imgs.append((a, self._in_footer))
        if tag == "a":
            if a.get("href") == "#":
                self.bare_hash_links += 1
            if self._in_footer and a.get("href"):
                self.footer_hrefs.append(a["href"])
        if tag == "a" and (a.get("href") or "").startswith(TRACKED_PREFIXES):
            self.tracked_links.append(a["href"])
        elif tag == "script" and a.get("src"):
            self.script_srcs.append(a["src"])
        for key in ("href", "src"):
            if a.get(key) is not None and tag != "link" or (
                tag == "link" and key == "href" and a.get(key) and
                (a.get("rel") or "").lower() in ("icon", "apple-touch-icon", "stylesheet")
            ):
                self.links.append((tag, a[key]))

    def handle_data(self, data):
        if self._in_title or self._in_jsonld:
            self._buf += data

    def handle_endtag(self, tag):
        if tag == "footer":
            self._in_footer = False
        if tag == "title" and self._in_title:
            self.titles.append(self._buf.strip())
            self._in_title = False
        elif tag == "script" and self._in_jsonld:
            self.jsonld.append(self._buf)
            self._in_jsonld = False


def page_url_path(rel: Path) -> str:
    parts = rel.parts
    if parts[-1] == "index.html":
        parts = parts[:-1]
    return "/" + "/".join(parts) + ("/" if parts else "")


def resolve_local(page_rel: Path, ref: str):
    p = urlparse(ref)
    if p.scheme or ref.startswith("//") or ref.startswith(("#", "mailto:", "tel:", "data:")):
        return None
    if not p.path:
        return None
    if p.path.startswith("/"):
        target = ROOT / p.path.lstrip("/")
    else:
        target = (ROOT / page_rel.parent / p.path).resolve()
    return target


def main() -> int:
    failures = []

    def fail(where, msg):
        failures.append(f"{where}: {msg}")

    pages = {}
    for f in sorted(ROOT.rglob("*.html")):
        rel = f.relative_to(ROOT)
        if set(rel.parts) & SKIP_DIRS:
            continue
        if rel.as_posix() == "404.html":
            continue
        pages[page_url_path(rel)] = (rel, f)

    parsed = {}
    for path, (rel, f) in pages.items():
        pg = Page()
        pg.feed(f.read_text(encoding="utf-8"))
        parsed[path] = pg
        where = str(rel)

        if len(pg.titles) != 1 or not pg.titles[0]:
            fail(where, f"expected exactly one non-empty <title>, found {len(pg.titles)}")
        elif path.startswith(ARTICLE_PREFIXES) and len(pg.titles[0]) > 60:
            fail(where, f"title is {len(pg.titles[0])} chars (max 60)")
        if not pg.description:
            fail(where, "missing meta description")
        elif path.startswith(ARTICLE_PREFIXES) and len(pg.description) > 155:
            fail(where, f"meta description is {len(pg.description)} chars (max 155)")

        expected = SITE + path
        if len(pg.canonicals) != 1:
            fail(where, f"expected one canonical, found {len(pg.canonicals)}")
        elif pg.canonicals[0] != expected:
            fail(where, f"canonical {pg.canonicals[0]!r} != {expected!r}")

        if pg.tracked_links and pg.script_srcs.count(TRACK_SCRIPT) != 1:
            fail(where, f"has store/demo links but does not load {TRACK_SCRIPT} exactly once")

        for i, raw in enumerate(pg.jsonld):
            try:
                json.loads(raw)
            except ValueError as e:
                fail(where, f"JSON-LD block {i + 1} does not parse: {e}")

        if pg.bare_hash_links:
            fail(where, f'{pg.bare_hash_links} link(s) with href="#"')
        if re.search(r"Dental ?Odoo|Dental Clinic Odoo", f.read_text(encoding="utf-8")):
            fail(where, "product name must be exactly 'Dental Clinic' (no Odoo fused into the name)")

        for a, _ in pg.imgs:
            if not (a.get("width") or "").isdigit() or not (a.get("height") or "").isdigit():
                fail(where, f"<img src={a.get('src')!r}> lacks numeric width/height")
        content = [a for a, _ in pg.imgs if "icon.png" not in (a.get("src") or "")]
        if path in ("/", "/es/") and content:
            hero = content[0]
            if hero.get("fetchpriority") != "high" or hero.get("loading") == "lazy":
                fail(where, "hero image must be eager with fetchpriority=\"high\"")
            for a in content[1:]:
                if a.get("loading") != "lazy" or a.get("decoding") != "async":
                    fail(where, f"below-the-fold <img src={a.get('src')!r}> needs loading=\"lazy\" decoding=\"async\"")
        privacy = PRIVACY["es" if path.startswith("/es/") else "en"]
        if privacy not in pg.footer_hrefs:
            fail(where, f"footer has no link to {privacy}")

        for tag, ref in pg.links:
            target = resolve_local(rel, ref)
            if target is None:
                continue
            if target.is_dir():
                target = target / "index.html"
            if not target.is_file():
                fail(where, f"<{tag}> reference {ref!r} does not resolve to a file")

    # the retired name must not survive in any published file (sitemap, assets, headers, docs)
    for f in sorted(ROOT.rglob("*")):
        rel = f.relative_to(ROOT)
        if not f.is_file() or f.suffix in (".png", ".html") or set(rel.parts) & SKIP_DIRS:
            continue
        try:
            if re.search(r"Dental ?Odoo", f.read_text(encoding="utf-8")):
                fail(str(rel), "retired product name 'DentalOdoo' still present")
        except UnicodeDecodeError:
            pass

    # hreflang reciprocity between the two landings
    en, es = parsed.get("/"), parsed.get("/es/")
    if en is None or es is None:
        fail("hreflang", "both / and /es/ must exist")
    else:
        want = {"en": SITE + "/", "es": SITE + "/es/", "x-default": SITE + "/"}
        for name, pg in (("/", en), ("/es/", es)):
            if pg.alternates != want:
                fail(name, f"hreflang set {pg.alternates} != {want}")

    # privacy pages: reciprocal hreflang pair
    pe, ps = parsed.get("/privacy/"), parsed.get("/es/privacidad/")
    if pe is None or ps is None:
        fail("privacy", "both /privacy/ and /es/privacidad/ must exist")
    else:
        want = {"en": SITE + "/privacy/", "es": SITE + "/es/privacidad/", "x-default": SITE + "/privacy/"}
        for name, pg in (("/privacy/", pe), ("/es/privacidad/", ps)):
            if pg.alternates != want:
                fail(name, f"hreflang set {pg.alternates} != {want}")

    # sitemap
    sm = ROOT / "sitemap.xml"
    if not sm.is_file():
        fail("sitemap.xml", "missing")
    else:
        try:
            tree = ET.parse(sm)
            locs = {e.text.strip() for e in tree.getroot().iter(SM_NS + "loc") if e.text}
            expected = {SITE + p for p in pages}
            for u in sorted(expected - locs):
                fail("sitemap.xml", f"missing page {u}")
            for u in sorted(locs - expected):
                fail("sitemap.xml", f"lists unknown page {u}")
            lastmod = {}
            for url in tree.getroot().iter(SM_NS + "url"):
                loc, lm = url.find(SM_NS + "loc"), url.find(SM_NS + "lastmod")
                if loc is not None and lm is not None and lm.text:
                    lastmod[loc.text.strip()] = lm.text.strip()
            for p_, pg in parsed.items():
                mods = []
                for raw in pg.jsonld:
                    try:
                        d = json.loads(raw)
                    except ValueError:
                        continue
                    if isinstance(d, dict) and d.get("dateModified"):
                        mods.append(d["dateModified"])
                lm = lastmod.get(SITE + p_)
                if lm is None:
                    fail("sitemap.xml", f"{p_} has no <lastmod>")
                elif not re.fullmatch(r"\d{4}-\d{2}-\d{2}", lm):
                    fail("sitemap.xml", f"{p_} lastmod {lm!r} is not YYYY-MM-DD")
                for m in mods:
                    if lm and lm < m[:10]:
                        fail("sitemap.xml", f"{p_} lastmod {lm} is older than JSON-LD dateModified {m}")
        except ET.ParseError as e:
            fail("sitemap.xml", f"does not parse as XML: {e}")

    # robots
    rb = ROOT / "robots.txt"
    if not rb.is_file():
        fail("robots.txt", "missing")
    elif f"Sitemap: {SITE}/sitemap.xml" not in rb.read_text(encoding="utf-8"):
        fail("robots.txt", "does not reference the sitemap")

    # automatic language: the redirect script lives only on the English home
    for path, (rel, f) in pages.items():
        text = f.read_text(encoding="utf-8")
        has_redirect = REDIRECT_MARK in text
        if path == "/" and not has_redirect:
            fail(str(rel), "English home is missing the Spanish-browser redirect script")
        if path != "/" and has_redirect:
            fail(str(rel), "only the English home may carry the language redirect")
        for m in re.finditer(r'<a\b[^>]*\bhreflang="(en|es)"[^>]*>', text):
            tag = m.group(0)
            if f"lang_choice','{m.group(1)}'" not in tag.replace('"', "'").replace("\\'", "'"):
                fail(str(rel), f"language switch to {m.group(1)} does not store lang_choice")

    # hreflang pairs for the articles (EN <-> ES, x-default = English)
    for en_path, es_path in PAIRS.items():
        want = {"en": SITE + en_path, "es": SITE + es_path, "x-default": SITE + en_path}
        for name in (en_path, es_path):
            pg = parsed.get(name)
            if pg is None:
                fail(name, "page missing (hreflang pair)")
            elif pg.alternates != want:
                fail(name, f"hreflang set {pg.alternates} != {want}")

    # English articles: self-contained set, cross-linked, linked from the English home and index
    home = parsed.get("/")
    for a_path in EN_ARTICLES + ("/articles/",):
        pg = parsed.get(a_path)
        if pg is None:
            continue
        hrefs = {h for t, h in pg.links if t == "a"}
        if home is not None and a_path not in {h for t, h in home.links if t == "a"}:
            fail("/", f"English home does not link to {a_path}")
        if a_path in EN_ARTICLES:
            for other in EN_ARTICLES:
                if other != a_path and other not in hrefs:
                    fail(a_path, f"does not link to related article {other}")
            if not any(h.startswith("https://dental-demo.giulianoh.dev/demo?lang=en") for h in hrefs):
                fail(a_path, "missing demo link with ?lang=en")
            if not any(h.startswith(STORE + "gh_dental_clinic") for h in hrefs):
                fail(a_path, "missing Apps Store link")
            kinds = [json.loads(r).get("@type") for r in pg.jsonld if r.strip().startswith("{")]
            if "Article" not in kinds:
                fail(a_path, "missing Article JSON-LD")
    if home is not None:
        foot = {h for t, h in home.links if t == "a"}
        if "/articles/" not in foot:
            fail("/", "English home does not link to /articles/")

    # structured data: author Person, two products with offers
    def blocks(pg):
        out = []
        for raw in pg.jsonld:
            try:
                d = json.loads(raw)
            except ValueError:
                continue
            out.extend(d if isinstance(d, list) else [d])
        return out

    def offers(node):
        o = node.get("offers")
        return o if isinstance(o, list) else ([o] if o else [])

    for h_path in ("/", "/es/"):
        pg = parsed.get(h_path)
        if pg is None:
            continue
        apps = {b.get("name"): b for b in blocks(pg) if b.get("@type") == "SoftwareApplication"}
        for name, price in (("Dental Clinic", "349"), ("Dental Clinic - Invoicing", "448")):
            node = apps.get(name)
            if node is None:
                fail(h_path, f"no SoftwareApplication named {name!r} in JSON-LD")
                continue
            prices = {str(o.get("price", "")).split(".")[0] for o in offers(node) if o.get("priceCurrency") == "USD"}
            if price not in prices:
                fail(h_path, f"{name!r} lacks an Offer of {price} USD")
            auth = node.get("author") or {}
            if auth.get("@type") != "Person" or auth.get("name") != AUTHOR["name"] or auth.get("url") != AUTHOR["url"]:
                fail(h_path, f"{name!r} author must be Person {AUTHOR}")
        inv = apps.get("Dental Clinic - Invoicing")
        if inv is not None and "Dental Clinic" not in json.dumps(inv.get("isRelatedTo", "")) + str(inv.get("requirements", "")):
            fail(h_path, "invoicing product must reference Dental Clinic (isRelatedTo/requirements)")
    for path, pg in parsed.items():
        if path.startswith(ARTICLE_PREFIXES) and path not in ("/articles/", "/es/articulos/"):
            arts = [b for b in blocks(pg) if b.get("@type") == "Article"]
            if not arts:
                fail(path, "missing Article JSON-LD")
            for a in arts:
                for role in ("author", "publisher"):
                    r = a.get(role) or {}
                    if r.get("@type") != "Person" or r.get("name") != AUTHOR["name"] or r.get("url") != AUTHOR["url"]:
                        fail(path, f"Article {role} must be Person {AUTHOR}")

    # 404 page and redirects
    nf = ROOT / "404.html"
    if not nf.is_file():
        fail("404.html", "missing")
    else:
        pg = Page()
        pg.feed(nf.read_text(encoding="utf-8"))
        hrefs = {h for t, h in pg.links if t == "a"}
        if len(pg.titles) != 1 or not pg.titles[0]:
            fail("404.html", "needs exactly one <title>")
        for want_href in ("/", "/es/"):
            if want_href not in hrefs:
                fail("404.html", f"must link to {want_href}")
        for tag, ref in pg.links:
            target = resolve_local(Path("404.html"), ref)
            if target is not None:
                target = target / "index.html" if target.is_dir() else target
                if not target.is_file():
                    fail("404.html", f"<{tag}> reference {ref!r} does not resolve to a file")
    rd = ROOT / "_redirects"
    if not rd.is_file():
        fail("_redirects", "missing")
    else:
        seen = set()
        for n, line in enumerate(rd.read_text(encoding="utf-8").splitlines(), 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) != 3 or parts[2] != "301":
                fail("_redirects", f"line {n} must be '<from> <to> 301': {line!r}")
                continue
            seen.add(parts[0])
            dest = parts[1]
            if dest not in parsed:
                fail("_redirects", f"line {n} target {dest!r} is not a known page")
        for src in sorted(REQUIRED_REDIRECTS - seen):
            fail("_redirects", f"missing 301 rule for {src}")

    for line in failures:
        print("FAIL", line)
    print(f"{len(pages)} page(s) checked, {len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
