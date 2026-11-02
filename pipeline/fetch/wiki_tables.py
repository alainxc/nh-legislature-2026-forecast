"""Helpers to parse Wikipedia polling wikitables, resolving footnote refs to URLs."""
import re, sys
from bs4 import BeautifulSoup

def load(path):
    return BeautifulSoup(open(path, encoding="utf8"), "lxml")

def ref_map(soup):
    """cite_note id -> (external urls, text)"""
    out = {}
    for li in soup.select("ol.references li"):
        rid = li.get("id", "")
        urls = [a["href"] for a in li.find_all("a", href=True)
                if a["href"].startswith("http") and "wikipedia.org" not in a["href"]]
        txt = li.get_text(" ", strip=True)
        txt = re.sub(r"^(\^|↑)\s*", "", txt)
        txt = re.sub(r"^(\d+\s)+", "", txt)
        out[rid] = (urls, txt)
    return out

def cell_info(td, refs):
    """returns (clean text, [ref urls], [note texts])"""
    urls, notes = [], []
    for sup in td.find_all("sup"):
        for a in sup.find_all("a", href=True):
            tgt = a["href"].lstrip("#")
            if tgt in refs:
                u, t = refs[tgt]
                if u: urls.extend(u)
                else: notes.append(t)
        sup.decompose()
    txt = td.get_text(" ", strip=True)
    return txt, urls, notes

def table_rows(table, refs):
    """Yield dict rows, handling rowspan carryover for the first columns."""
    trs = table.find_all("tr")
    hdr = [th.get_text(" ", strip=True) for th in trs[0].find_all(["th", "td"])]
    hdr = [re.sub(r"\s*\[.*?\]\s*", "", h).strip() for h in hdr]
    carry = {}   # col index -> (remaining rows, (text, urls, notes))
    for tr in trs[1:]:
        cells = tr.find_all(["th", "td"])
        row = [None]*len(hdr)
        ci = 0
        for col in range(len(hdr)):
            if col in carry and carry[col][0] > 0:
                row[col] = carry[col][1]
                carry[col] = (carry[col][0]-1, carry[col][1])
                continue
            if ci >= len(cells): break
            td = cells[ci]; ci += 1
            info = cell_info(td, refs)
            rs = int(td.get("rowspan", 1) or 1)
            if rs > 1: carry[col] = (rs-1, info)
            row[col] = info
        if all(r is None for r in row): continue
        yield dict(zip(hdr, row))
