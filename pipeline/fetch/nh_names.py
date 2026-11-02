"""Canonical names for New Hampshire towns, cities, wards and unincorporated places.

Every data source spells the unincorporated places (and a few towns) differently.
`norm_town()` maps any spelling to the statute spelling used in RSA 662:3 / 662:5 so
that results, district compositions and shapes join on one key.
"""
import re

ALIASES = {
    "Atkinson & Gilmanton Academy Grant": ["atkinson and gilmanton academy grant", "atk gilm ac gt", "atk and gilm ac gt", "at gil academy grant", "at and gil academy grant", "atkinson and gilmanton ac gt", "atkinson gilmanton academy grant", "atkinson and gilmanton acad grant", "at and gil ac gt", "at gil ac gt"],
    "Bean's Grant": ["beans grant"], "Bean's Purchase": ["beans purchase"],
    "Chandler's Purchase": ["chandlers purchase"], "Crawford's Purchase": ["crawfords purchase"],
    "Cutt's Grant": ["cutts grant"], "Dix's Grant": ["dixs grant"],
    "Erving's Location": ["ervings location", "ervings loc"],
    "Green's Grant": ["greens grant"], "Hadley's Purchase": ["hadleys purchase"],
    "Hale's Location": ["hales location", "hales loc"], "Hart's Location": ["harts location", "harts loc"],
    "Low and Burbank's Grant": ["low burbanks gt", "low and burbanks grant", "low burbanks grant", "low and burbank grant", "low and burbanks gt"],
    "Martin's Location": ["martins location", "martins loc"],
    "Pinkham's Grant": ["pinkhams grant"], "Sargent's Purchase": ["sargents purchase"],
    "Second College Grant": ["second college gt", "second college grant"],
    "Thompson and Meserve's Purchase": ["thompson mess pur", "thompson and mess pur", "thompson meserves pur", "thompson and meserves pur", "thompson and meserves purchase", "thompson meserves purchase", "thompson and meserve purchase", "thompson and meserves pur"],
    "Wentworth's Location": ["wentworths location", "wentworths loc", "wentworth location", "wentworth loc"],
    "Waterville Valley": ["waterville valley", "waterville"],
    "Hillsborough": ["hillsborough", "hillsboro"],
}


def _key(s: str) -> str:
    s = s.lower().replace("&", " and ").replace("'", "").replace("’", "").replace(".", "").replace(",", "")
    s = re.sub(r"\s+", " ", s).strip()
    return s


_ALIAS_LOOKUP = {}
for canon, vs in ALIASES.items():
    _ALIAS_LOOKUP[_key(canon)] = canon
    for v in vs:
        _ALIAS_LOOKUP[_key(v)] = canon


def norm_town(name: str) -> str:
    """Return the statute spelling for a town / city ward / unincorporated place."""
    s = re.sub(r"\s+", " ", str(name).strip())
    s = re.sub(r"\s+-\s+(?=[Ww]ard)", " ", s)        # "Dover - Ward 1" -> "Dover Ward 1"
    k = _key(s)
    m = re.match(r"^(.*?)\s+(?:ward|wd)\s*0*(\d+)$", k)
    if m:
        city = _ALIAS_LOOKUP.get(m.group(1), m.group(1).title())
        return f"{city} Ward {int(m.group(2))}"
    m = re.match(r"^ward\s*0*(\d+)\s+(.*)$", k)
    if m:
        city = _ALIAS_LOOKUP.get(m.group(2), m.group(2).title())
        return f"{city} Ward {int(m.group(1))}"
    if k in _ALIAS_LOOKUP:
        return _ALIAS_LOOKUP[k]
    t = " ".join(w.capitalize() if not w[:1].isdigit() else w for w in s.split(" "))
    t = t.replace(" And ", " and ").replace(" Of ", " of ")
    return t


def city_of(town: str) -> str:
    """'Manchester Ward 3' -> 'Manchester'; towns map to themselves."""
    m = re.match(r"^(.*) Ward \d+$", town)
    return m.group(1) if m else town
