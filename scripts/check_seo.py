#!/usr/bin/env python3
"""SEO consistency check for the static landing. Stdlib only.

Run from the repository root:  python3 scripts/check_seo.py
Exits 1 and prints every failure when any check does not pass.
"""
import json
import sys
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://dental.giulianoh.dev"
SKIP_DIRS = {".git", "node_modules", "scripts"}
ARTICLE_PREFIX = "/es/articulos/"
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
        pages[page_url_path(rel)] = (rel, f)

    parsed = {}
    for path, (rel, f) in pages.items():
        pg = Page()
        pg.feed(f.read_text(encoding="utf-8"))
        parsed[path] = pg
        where = str(rel)

        if len(pg.titles) != 1 or not pg.titles[0]:
            fail(where, f"expected exactly one non-empty <title>, found {len(pg.titles)}")
        elif path.startswith(ARTICLE_PREFIX) and len(pg.titles[0]) > 60:
            fail(where, f"title is {len(pg.titles[0])} chars (max 60)")
        if not pg.description:
            fail(where, "missing meta description")
        elif path.startswith(ARTICLE_PREFIX) and len(pg.description) > 155:
            fail(where, f"meta description is {len(pg.description)} chars (max 155)")

        expected = SITE + path
        if len(pg.canonicals) != 1:
            fail(where, f"expected one canonical, found {len(pg.canonicals)}")
        elif pg.canonicals[0] != expected:
            fail(where, f"canonical {pg.canonicals[0]!r} != {expected!r}")

        for i, raw in enumerate(pg.jsonld):
            try:
                json.loads(raw)
            except ValueError as e:
                fail(where, f"JSON-LD block {i + 1} does not parse: {e}")

        for tag, ref in pg.links:
            target = resolve_local(rel, ref)
            if target is None:
                continue
            if target.is_dir():
                target = target / "index.html"
            if not target.is_file():
                fail(where, f"<{tag}> reference {ref!r} does not resolve to a file")

    # hreflang reciprocity between the two landings
    en, es = parsed.get("/"), parsed.get("/es/")
    if en is None or es is None:
        fail("hreflang", "both / and /es/ must exist")
    else:
        want = {"en": SITE + "/", "es": SITE + "/es/", "x-default": SITE + "/"}
        for name, pg in (("/", en), ("/es/", es)):
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
        except ET.ParseError as e:
            fail("sitemap.xml", f"does not parse as XML: {e}")

    # robots
    rb = ROOT / "robots.txt"
    if not rb.is_file():
        fail("robots.txt", "missing")
    elif f"Sitemap: {SITE}/sitemap.xml" not in rb.read_text(encoding="utf-8"):
        fail("robots.txt", "does not reference the sitemap")

    for line in failures:
        print("FAIL", line)
    print(f"{len(pages)} page(s) checked, {len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
