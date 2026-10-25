import re
import shutil
import sys
import time
import unicodedata

from corpus import ROOT, load_records

WIKI = ROOT / "use_case" / "data" / "wiki"
FIELDS = {"ADM ID": r"ADM ID[: ]+(\d+)", "AAMS ID": r"AAMS ID[: ]+(\d+)", "Status": r"Status: ([^|\n]+)",
          "Naziv projekta": r"Naziv projekta: ([^|\n]+)", "TASK": r"TASK: ([^|\n]+)"}


ADDRESS = r"(?!(?:ADM|AAMS|Za|Uz|Da|Na|Kod)\b)[A-ZČĆŽŠĐ][^,()?:.]{1,40}? \d+(?: ?[A-Ha-h]\b|/\d+)?"
CITY = r"[A-ZČĆŽŠĐ][a-zčćžšđ]+(?:(?: (?:na|pri|nad|kod))? [A-ZČĆŽŠĐ][a-zčćžšđ]+|-[A-ZČĆŽŠĐ][a-zčćžšđ]+){0,2}"


def place(output):
    match = re.search(rf"({ADDRESS}), ({CITY})(?=[.:),]|\s|$)", output.split("\n")[0])
    return (match[1], match[2]) if match else (None, None)


def slug(city):
    text = unicodedata.normalize("NFKD", city.lower().replace("đ", "d"))
    return re.sub(r"[^a-z0-9]+", "_", "".join(c for c in text if not unicodedata.combining(c))).strip("_")


def build():
    started = time.perf_counter()
    shutil.rmtree(WIKI, ignore_errors=True)
    WIKI.mkdir(parents=True)
    cities, other = {}, []
    for r in load_records():
        address, city = place(r["output"])
        facts = {k: m[1].strip() for k, rx in FIELDS.items() if (m := re.search(rx, r["output"]))}
        title = f"{address}, {city}" if city else r["id"]
        lines = [f"# {title}", "", "## Podaci", *[f"- {k}: {v}" for k, v in facts.items()], "", "## Odgovor", r["output"], ""]
        (WIKI / f"{r['id']}.md").write_text("\n".join(lines), encoding="utf-8")
        if city:
            cities.setdefault(city, []).append((address, facts.get("ADM ID", ""), facts.get("AAMS ID", ""), r["id"]))
        else:
            other.append((r["id"], r["output"][:70].replace("\n", " ").replace("|", "/")))
    for city, rows in cities.items():
        table = [f"| {a} | {adm} | {aams} | `{rid}.md` |" for a, adm, aams, rid in sorted(rows)]
        (WIKI / f"grad_{slug(city)}.md").write_text(
            "\n".join([f"# {city}", "", "| Adresa | ADM | AAMS | Stranica |", "| --- | --- | --- | --- |", *table, ""]), encoding="utf-8")
    (WIKI / "ostalo.md").write_text("\n".join(["# Zapisi bez zgrade", "", "| Stranica | Početak odgovora |", "| --- | --- |",
                                               *[f"| `{rid}.md` | {text} |" for rid, text in other], ""]), encoding="utf-8")
    index = [f"| `grad_{slug(c)}.md` | {c} | {len(rows)} |" for c, rows in sorted(cities.items())]
    (WIKI / "index.md").write_text("\n".join(["# Fiberly: zapisi po gradovima", "", "Imena stranica su stalna. Grad vodi do zgrada, zgrada do zapisa.", "",
                                              "| Stranica | Grad | Zapisa |", "| --- | --- | --- |", *index,
                                              f"| `ostalo.md` | zapisi bez zgrade: nije pronađeno, pitanje natrag, izvan teme | {len(other)} |", ""]), encoding="utf-8")
    pages = list(WIKI.glob("*.md"))
    city_sizes = [p.stat().st_size for p in pages if p.name.startswith("grad_")]
    print(f"built in {time.perf_counter() - started:.1f} s: {len(pages)} pages, {len(cities)} cities, {len(other)} records with no building")
    print(f"index.md {(WIKI / 'index.md').stat().st_size} bytes, largest city page {max(city_sizes)} bytes, ostalo.md {(WIKI / 'ostalo.md').stat().st_size} bytes")


class Wiki:
    def __init__(self):
        self.pages = {p.name: p.read_text(encoding="utf-8") for p in sorted(WIKI.glob("*.md"))}

    def list_pages(self):
        return self.pages["index.md"]

    def grep_wiki(self, pattern):
        try:
            rx = re.compile(pattern, re.I)
        except re.error:
            rx = re.compile(re.escape(pattern), re.I)
        hits = [f"{page}:{n}: {line}" for page, text in self.pages.items() for n, line in enumerate(text.splitlines(), 1) if rx.search(line)]
        return "\n".join(hits[:40]) or "(no matches)"

    def read_page(self, page):
        return self.pages[page][:12000] if page in self.pages else f"(unknown page: {page})"


if __name__ == "__main__":
    {"build": build}[sys.argv[1]]()
