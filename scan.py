"""
Cenu skeneris: Bite, Tele2, LMT un Tet telefonu, viedpulksteņu un austiņu cenas.

Ko skenēt, nosaka saraksts SOURCES faila apakšā: (operators, kategorija, funkcija).

Palaišana:  python scan.py
Rezultāts:  data/prices.csv  (vēsture: rinda tiek pierakstīta, kad parādās jauns telefons vai mainās cena)
            data/latest.json (pēdējā skenēšana, ar ko salīdzina nākamo)
            data/meta.json   (pēdējās skenēšanas laiks, skaits, kļūdas – to rāda lapa)
Paziņojumi: ja iestatīti TG_TOKEN un TG_CHAT, izmaiņas tiek nosūtītas uz Telegram.
"""

import csv
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

DATA = Path(__file__).parent / "data"
LATEST = DATA / "latest.json"
HISTORY = DATA / "prices.csv"
META = DATA / "meta.json"
PRICE_FIELDS = ("monthly", "monthly_old", "full", "full_old")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
    ),
    "Accept-Language": "lv,en;q=0.8",
}
DELAY = 1.5  # sekundes starp pieprasījumiem, lai nenoslogotu lapas

CATEGORIES = {
    "telefoni": "Telefoni", "pulksteni": "Viedpulksteņi", "austinas": "Austiņas",
    "televizori": "Televizori", "puteklsuceji": "Putekļsūcēji", "kameras": "Novērošanas kameras",
}

FIELDS = [
    "scanned_at", "operator", "category", "id", "brand", "model",
    "monthly", "monthly_old", "full", "full_old", "url",
]


def price(text):
    """'1 209,00 €' -> 1209.0 ; '14,54 € / mēn.' -> 14.54"""
    if not text:
        return None
    text = text.replace("\xa0", " ")
    m = re.search(r"\d[\d ]*(?:[.,]\d+)?", text)
    if not m:
        return None
    return float(m.group(0).replace(" ", "").replace(",", "."))


# ---------------------------------------------------------------- Bite

def scan_bite(client, path):
    """path – kategorijas lapa, piem. "/lv/telefoni"."""
    base = "https://www.bite.lv"
    html = client.get(base + path, timeout=30).text

    # Lapā ir saraksts ar visu produktu ID: data-listInfo="23413-22509-..."
    m = re.search(r'data-listInfo="([\d-]+)"', html, re.I)
    if not m:
        raise RuntimeError(f"neatradu data-listInfo lapā {path} (struktūra mainījusies?)")
    ids = m.group(1).split("-")

    products = []
    for i in range(0, len(ids), 15):
        time.sleep(DELAY)
        chunk = "-".join(ids[i:i + 15])
        r = client.get(
            f"{base}/lv/product-list/ajax/commerce_product/small__fti/{chunk}",
            headers={"X-Requested-With": "XMLHttpRequest"},
            timeout=30,
        )
        r.raise_for_status()
        fragment = "".join(
            cmd["data"] for cmd in r.json() if cmd.get("command") == "insert" and isinstance(cmd.get("data"), str)
        )
        products += parse_bite(fragment, base)
    return products


def parse_bite(fragment, base="https://www.bite.lv"):
    soup = BeautifulSoup(fragment, "html.parser")
    out = []
    for w in soup.select(".js-product-wrapper[data-product-id]"):
        pid = str(w["data-product-id"]).strip('"')

        def field(name):
            el = soup.find(id=f"product-{pid}-{name}")
            return el.get_text(" ", strip=True) if el else None

        link = w.select_one("a.product__link")
        out.append({
            "operator": "bite",
            "id": pid,
            "brand": field("title"),
            "model": field("subtitle"),
            "monthly": price(field("monthly-price")),
            "monthly_old": price(field("old-monthly-price")),
            "full": price(field("full-price")),
            "full_old": price(field("old-full-price")),
            "url": base + link["href"] if link else None,
        })
    return out


# ---------------------------------------------------------------- Tele2

def scan_tele2(client, path, params=None):
    """path – piem. "/telefoni/" vai "/viedpaligi/"; params – papildu filtri.

    Tele2 lapa ar ?p=N parāda visus produktus no 1. līdz N. lapai, tāpēc pietiek ar
    vienu pieprasījumu ar lielu N.
    """
    url = requests.Request(
        "GET", "https://www.tele2.lv" + path,
        params={"filter": 1, **(params or {}), "p": 30},
    ).prepare().url
    if os.getenv("BRIGHTDATA_API_KEY"):
        # Tele2 rāda GitHub serveriem anti-bot lapu – caur Bright Data Web Unlocker tā netiek
        r = brightdata_get(url)
    else:
        r = client.get(url, headers={"Accept": "text/html,application/xhtml+xml"}, timeout=30)
    r.raise_for_status()
    items = {p["id"]: p for p in parse_tele2(r.text)}  # dublikātus izmet
    if not items:
        title = re.search(r"<title>(.*?)</title>", r.text, re.S | re.I)
        raise RuntimeError(
            f"0 produktu (HTTP {r.status_code}, {len(r.text)} B, "
            f"title={title.group(1).strip()[:60] if title else '-'!r}, "
            f"sākums={r.text[:80].strip()!r})"
            + (" – Tele2 anti-bot pārbaude; skenē Tele2 no sava datora (sk. README)"
               if "anubis" in r.text.lower() or "Pārbaudei vajadzīgs JavaScript" in r.text else "")
        )
    return list(items.values())


def brightdata_get(url):
    """Lejupielādē lapu caur Bright Data Web Unlocker (atslēga: BRIGHTDATA_API_KEY).

    Zona pēc noklusējuma ir "cli_unlocker" – to izveido `bdata login`. Katrs pieprasījums
    = 1 kredīts no bezmaksas 5000 mēnesī.
    """
    r = requests.post(
        "https://api.brightdata.com/request",
        headers={"Authorization": f"Bearer {os.environ['BRIGHTDATA_API_KEY']}"},
        json={
            "zone": os.getenv("BRIGHTDATA_ZONE", "cli_unlocker"),
            "url": url,
            "format": "raw",
            "country": "lv",
        },
        timeout=120,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Bright Data HTTP {r.status_code}: {r.text[:200]!r}")
    r.encoding = "utf-8"
    return r


def parse_tele2(html):
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for a in soup.select("a.deviceVw[data-gaid]"):
        if a.find_parent(class_="swiper"):  # akciju slīdnis augšā, nav produktu saraksts
            continue
        pr = a.select_one(".price")
        current = pr.select_one(".new, .normal") if pr else None
        prev = pr.select_one(".prev") if pr else None
        first = pr.select_one(".first") if pr else None
        first_old = first.select_one("s") if first else None
        model = a.select_one(".product .big")

        href = a.get("href", "")
        out.append({
            "operator": "tele2",
            "id": a["data-gaid"],
            "brand": a.get("data-gabrand"),
            "model": model.get_text(strip=True) if model else a.get("data-ganame"),
            "monthly": price(current.get_text(" ", strip=True)) if current else price(a.get("data-gaprice")),
            "monthly_old": price(prev.get_text()) if prev else None,
            "full": price(first.get_text(" ", strip=True)) if first else None,
            "full_old": price(first_old.get_text()) if first_old else None,
            "url": href if href.startswith("http") else "https://www.tele2.lv" + href,
        })
    return out


# ---------------------------------------------------------------- LMT

# LMT e-veikals ir Nuxt lietotne: visi produkta dati ir lapā <script id="__NUXT_DATA__">
# saspiestā "devalue" formātā (masīvs, kurā objektu vērtības ir atsauces uz citiem indeksiem).
NUXT_WRAPPERS = {"ShallowReactive", "Reactive", "Ref", "ShallowRef", "EmptyRef", "EmptyShallowRef", "NuxtError"}


def nuxt_data(html):
    m = re.search(r'<script[^>]*id="__NUXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        raise RuntimeError("neatradu __NUXT_DATA__ (iespējams, Cloudflare bloķē pieprasījumu)")
    arr = json.loads(m.group(1))
    memo = {}

    def h(i):
        if not isinstance(i, int) or isinstance(i, bool) or i < 0:
            return None
        if i in memo:
            return memo[i]
        v = arr[i]
        if isinstance(v, list):
            if v and isinstance(v[0], str) and v[0] in NUXT_WRAPPERS | {"Set", "Map", "Date"}:
                memo[i] = h(v[1]) if len(v) > 1 else None
                return memo[i]
            out = memo[i] = []
            out.extend(h(x) for x in v)
            return out
        if isinstance(v, dict):
            out = memo[i] = {}
            for k, x in v.items():
                out[k] = h(x)
            return out
        memo[i] = v
        return v

    return h(0)


def lmt_plan(sets, plan_type, when, field):
    for p in sets or []:
        if p.get("type") == plan_type:
            block = (p.get("prices") or {}).get(when) or {}
            val = (block.get(field) or {}).get("withVat")
            return float(val) if val not in (None, "") else None
    return None


def parse_lmt(html):
    root = nuxt_data(html)
    grid = next((v for k, v in (root.get("data") or {}).items() if k.startswith("productGrid")), None)
    if not grid or not grid.get("data"):
        raise RuntimeError("neatradu productGrid datus LMT lapā")
    data = grid["data"]
    out = []
    for s in data.get("productSets") or []:
        plans = (s.get("primaryProduct") or {}).get("pricePlans")
        name = (s.get("name") or "").strip()
        brand, _, model = name.partition(" ")
        out.append({
            "operator": "lmt",
            "id": s.get("id"),
            "brand": brand,
            "model": model or name,
            "monthly": lmt_plan(plans, "installment", "actual", "monthlyPayment"),
            "monthly_old": lmt_plan(plans, "installment", "before", "monthlyPayment"),
            "full": lmt_plan(plans, "full", "actual", "singlePayment"),
            "full_old": lmt_plan(plans, "full", "before", "singlePayment"),
            "url": s.get("primaryProductAbsoluteUrl"),
        })
    return out, (data.get("paginator") or {}).get("lastPage") or 1


def scan_lmt(client, slug):
    """slug – kategorija, piem. "visi-telefoni" (https://www.lmt.lv/veikals/<slug>)."""
    products, page, last = {}, 1, 1
    while page <= min(last, 20):
        if page > 1:
            time.sleep(DELAY)
        r = client.get(
            f"https://www.lmt.lv/veikals/{slug}",
            params={"page": page, "perPage": 54},  # 54 ir lielākais atļautais
            headers={"Accept": "text/html,application/xhtml+xml"},
            timeout=30,
        )
        r.raise_for_status()
        items, last = parse_lmt(r.text)
        for p in items:
            products[p["id"]] = p
        page += 1
    return list(products.values())


# ---------------------------------------------------------------- Tet

# Tet veikals (Magento): produkti ir lapas HTML, pa 58 lapā (?page=N). Katrā kartītē ir
# data-pricing JSON ar cenu un veco cenu; mēneša maksājumu ņem no redzamā teksta.
# Lapa aiz pēdējās atkal rāda 1. lapu, tāpēc apstājas, kad jaunu produktu vairs nav.

def parse_tet(html):
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for card in soup.select(".i-product-item[data-id]"):
        name = (card.get("data-name") or "").strip()
        if not name:
            continue
        brand, _, model = name.partition(" ")
        try:
            pricing = json.loads(card.select_one("[data-pricing]")["data-pricing"])
        except (TypeError, KeyError, ValueError):
            pricing = {}
        full = pricing.get("price") or price(card.get("data-price"))
        msrp = pricing.get("msrp") or None
        month = card.select_one(".js-price-with-vat .i-product-item__price-month span")
        link = card.select_one("a.i-product-item__link")
        href = link.get("href", "") if link else ""
        out.append({
            "operator": "tet",
            "id": card["data-id"],
            "brand": brand,
            "model": model or name,
            "monthly": price(month.get_text()) if month else None,
            "monthly_old": None,
            "full": float(full) if full else None,
            "full_old": float(msrp) if msrp and full and msrp > full else None,
            "url": href if href.startswith("http") else "https://www.tet.lv" + href,
        })
    return out


def scan_tet(client, path):
    """path – kategorija, piem. "/veikals/telefoni/telefoni-un-aksesuari/viedtalruni.html"."""
    products = {}
    for page in range(1, 30):
        if page > 1:
            time.sleep(DELAY)
        r = client.get("https://www.tet.lv" + path, params={"page": page}, timeout=30)
        r.raise_for_status()
        items = parse_tet(r.text)
        fresh = [p for p in items if p["id"] not in products]
        if not fresh:
            if page == 1:
                title = re.search(r"<title>(.*?)</title>", r.text, re.S | re.I)
                raise RuntimeError(f"0 produktu (HTTP {r.status_code}, {len(r.text)} B, "
                                   f"title={title.group(1).strip()[:60] if title else '-'!r})")
            break
        for p in fresh:
            products[p["id"]] = p
    return list(products.values())


# ---------------------------------------------------------------- Austiņas no jauktām audio sadaļām

# Tele2 (un dažkārt citi) austiņas un skaļruņus rāda vienā sadaļā.
# Skaļruņus atpazīst pēc nosaukuma; viss pārējais tiek uzskatīts par austiņām.
SPEAKER_WORDS = re.compile(
    r"skaļrun|skalrun|speaker|soundbar|boombox|partybox|homepod|home ?pod|"
    r"\bjbl (charge|flip|go|clip|xtreme|pulse|boombox|partybox|encore)|"
    r"wonderboom|megaboom|soundlink|\becho\b|\bnest\b|soundcore motion|\bboom ?\d|"
    r"\bht-s|\bsoundbar|logitech [sz] ?\d|\bsrs\b|\bbluetooth speaker|"
    r"\bsrs-|\bult field|emberton|stanmore|acton|woburn|marshall (middleton|willen|kilburn)",
    re.I,
)


# ---------------------------------------------------------------- Varianti (precīzi SKU)

# Bite un LMT sarakstos katram modelim ir tikai viena cena ("no"). Precīzās katra varianta
# (atmiņa, pulksteņa izmērs, LTE) cenas ir produkta lapā. Tās saglabā data/variants.json:
#   {"bite:24395": {"updated": "...", "variants": [{"sku", "label", "full", "url"}, ...]}, ...}
# Tele2 un Tet katrs variants jau ir atsevišķa prece sarakstā, tāpēc tiem tas nav vajadzīgs.
VARIANTS = DATA / "variants.json"
VARIANT_CATEGORIES = {"telefoni", "pulksteni", "plansetes"}
# LMT televizoriem katra sērija ir viena lapa ar visiem izmēriem (katram savs ražotāja kods un cena)
VARIANT_CATEGORIES_BY_OP = {"bite": VARIANT_CATEGORIES, "lmt": VARIANT_CATEGORIES | {"televizori"}}
VARIANT_DELAY = 0.8
VARIANT_ERRORS = []
BITE_VARIANT_ATTRS = ("capacity", "size_mm", "connectivity")  # krāsas neskenē – cena parasti tā pati


def _jsonld_offer(soup):
    for s in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(s.string or "")
        except ValueError:
            continue
        for node in data.get("@graph", [data]) if isinstance(data, dict) else []:
            if isinstance(node, dict) and node.get("@type") == "Product":
                offer = node.get("offers") or {}
                if isinstance(offer, list):
                    offer = offer[0] if offer else {}
                return node.get("sku"), price(str(offer.get("price") or ""))
    return None, None


def _bite_variant_page(client, url, vid=None):
    r = client.get(url, params={"v": vid} if vid else None, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    sku, full = _jsonld_offer(soup)
    lab = soup.select_one(".js-product-variation-attributes")
    vid_el = soup.select_one("[data-variation-id]")
    this_vid = vid or (vid_el.get("data-variation-id") if vid_el else None)
    return soup, {
        "sku": sku,
        "label": lab.get_text(" ", strip=True) if lab else "",
        "full": full,
        "url": f"{url}?v={this_vid}" if this_vid else url,
    }, this_vid


def bite_variants(client, url):
    soup, first, first_vid = _bite_variant_page(client, url)
    variants, vids = [first], {first_vid}
    form = next((f for f in soup.select("form") if f.select_one('input[name*="[attribute_"]')), None)
    if not form:
        return variants
    fields = {}
    for i in form.select("input, select"):
        name, typ = i.get("name"), (i.get("type") or "").lower()
        if not name or typ in ("submit", "button"):
            continue
        if typ in ("radio", "checkbox"):
            if i.has_attr("checked"):
                fields[name] = i.get("value", "")
        elif i.name == "select":
            opt = i.select_one("option[selected]") or i.select_one("option")
            fields[name] = opt.get("value", "") if opt else ""
        else:
            fields[name] = i.get("value", "")
    for attr in BITE_VARIANT_ATTRS:
        field = f"purchased_entity[0][attributes][attribute_{attr}]"
        options = [i.get("value") for i in form.select(f'input[name="{field}"]')]
        for val in dict.fromkeys(options):
            if val == fields.get(field):
                continue
            time.sleep(VARIANT_DELAY)
            r = client.post(
                url, params={"ajax_form": 1, "_wrapper_format": "drupal_ajax"},
                data={**fields, field: val, "_triggering_element_name": field, "_drupal_ajax": "1"},
                headers={"X-Requested-With": "XMLHttpRequest"}, timeout=30,
            )
            if r.status_code != 200 or not r.text.lstrip().startswith("["):
                raise RuntimeError(f"variantu AJAX: HTTP {r.status_code}, {r.text[:150]!r}")
            blob = "".join(c["data"] for c in r.json() if isinstance(c, dict) and isinstance(c.get("data"), str))
            m = re.search(r'variation-id="(\d+)"', blob)
            if m and m.group(1) not in vids:
                vids.add(m.group(1))
                time.sleep(VARIANT_DELAY)
                variants.append(_bite_variant_page(client, url, m.group(1))[1])
    return variants


def lmt_variants(client, url):
    r = client.get(url.split("?")[0], timeout=30)
    r.raise_for_status()
    root = nuxt_data(r.text)
    pset = next((v for k, v in (root.get("data") or {}).items() if k.startswith("product-set-")), None)
    data = (pset or {}).get("data") or {}
    base = url.split("?")[0].rsplit("/", 1)[0]
    out = []
    for p in data.get("products") or []:
        if p.get("generalCondition") not in (None, "new"):
            continue
        conds = p.get("conditions") or []
        cond = next((c for c in conds if c.get("type") == "new"), conds[0] if conds else {})
        plans = cond.get("pricePlans")
        out.append({
            "sku": p.get("sku"),
            "label": (p.get("slug") or "").replace("-", " "),
            "full": lmt_plan(plans, "full", "actual", "singlePayment"),
            "full_old": lmt_plan(plans, "full", "before", "singlePayment"),
            "url": f"{base}/{p.get('slug')}",
        })
    return out


def scan_variants(client, products, old_variants, now, budget_s=600):
    """Atjauno variantus Bite/LMT telefoniem un pulksteņiem. Kļūdas gadījumā paliek vecie dati."""
    fns = {"bite": bite_variants, "lmt": lmt_variants}
    result = {k: v for k, v in old_variants.items() if k in products}  # izmet vairs neesošos
    start, done, failed = time.monotonic(), 0, 0
    todo = [(k, p) for k, p in products.items()
            if p["operator"] in fns and p.get("category") in VARIANT_CATEGORIES_BY_OP.get(p["operator"], ()) and p.get("url")]
    # vispirms tie, kas nav atjaunoti visilgāk – ja laiks beidzas, nākamreiz turpina ar pārējiem
    todo.sort(key=lambda kp: (old_variants.get(kp[0]) or {}).get("updated", ""))
    for key, p in todo:
        if time.monotonic() - start > budget_s:
            break
        try:
            time.sleep(VARIANT_DELAY)
            variants = [v for v in fns[p["operator"]](client, p["url"]) if v.get("full")]
            if variants:
                result[key] = {"updated": now, "variants": variants}
                done += 1
        except Exception as e:  # viena produkta kļūda neaptur pārējos
            failed += 1
            VARIANT_ERRORS.append(f"{key}: {e}"[:300])
            print(f"  varianti {key}: {e}")
    print(f"varianti: {done} produkti atjaunoti, {failed} kļūdas, {len(todo) - done - failed} atlikti")
    return result


def only_headphones(items):
    return [p for p in items if not SPEAKER_WORDS.search(f"{p['brand'] or ''} {p['model'] or ''}")]


# Tele2 putekļsūcējus rāda jauktā sadaļā "household" kopā ar klaviatūrām, aerogriliem u.c.
VACUUM_WORDS = re.compile(
    r"vacuum|putek|robot|roborock|dreame|\bmova\b|dyson|k[aä]rcher|ezviz r[es]\d|xiaomi s\d|"
    r"deebot|ecovacs|roomba|irobot|eufy|aqua ?10|\bf25\b",
    re.I,
)
VACUUM_PARTS = re.compile(r"brush|birst|accessor|aksesuār|piederum|filtr|\bkit\b|maisi|\bbags?\b", re.I)


def only_vacuums(items):
    return [p for p in items
            if VACUUM_WORDS.search(f"{p['brand'] or ''} {p['model'] or ''}")
            and not VACUUM_PARTS.search(p["model"] or "")]


# ---------------------------------------------------------------- Izmaiņas un paziņojumi

def eur(v):
    return "–" if v is None else f"{v:.2f} €".replace(".", ",")


def diff(old, new, scanned):
    """scanned – (operators, kategorija) pāri, kas šoreiz noskenēti veiksmīgi."""
    msgs = []
    # pirmo reizi skenēta kategorija – nevis simtiem "🆕" rindu, bet viena kopsavilkuma rinda
    known = {(o["operator"], o.get("category", "telefoni")) for o in old.values()}
    first = {}
    for key, p in new.items():
        name = label(p)
        o = old.get(key)
        if o is None and (p["operator"], p["category"]) not in known:
            first[(p["operator"], p["category"])] = first.get((p["operator"], p["category"]), 0) + 1
            continue
        if o is None:
            msgs.append(f"🆕 {name}: {eur(p['full'])} ({eur(p['monthly'])}/mēn.)")
            continue
        if o.get("full") != p["full"] and p["full"] is not None and o.get("full") is not None:
            arrow = "🔻" if p["full"] < o["full"] else "🔺"
            msgs.append(f"{arrow} {name}: {eur(o['full'])} → {eur(p['full'])}")
        elif o.get("monthly") != p["monthly"] and p["monthly"] is not None and o.get("monthly") is not None:
            arrow = "🔻" if p["monthly"] < o["monthly"] else "🔺"
            msgs.append(f"{arrow} {name}: {eur(o['monthly'])}/mēn. → {eur(p['monthly'])}/mēn.")
    for key, o in old.items():
        if key not in new and (o["operator"], o.get("category", "telefoni")) in scanned:
            msgs.append(f"❌ Vairs nav: {label(o)}")
    for (op, cat), n in first.items():
        msgs.insert(0, f"🆕 Jauna kategorija {op.upper()} {CATEGORIES.get(cat, cat)}: {n} produkti")
    return msgs


def label(p):
    return f"{p['operator'].upper()} {p['brand'] or ''} {p['model'] or ''}".replace("  ", " ").strip()


def telegram(text):
    token, chat = os.getenv("TG_TOKEN"), os.getenv("TG_CHAT")
    if not (token and chat):
        print(text)
        return
    for i in range(0, len(text), 4000):  # Telegram limits 4096 zīmes vienā ziņā
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": chat, "text": text[i:i + 4000], "disable_web_page_preview": True},
            timeout=20,
        )


# ---------------------------------------------------------------- Galvenā daļa

def main():
    DATA.mkdir(exist_ok=True)
    old = json.loads(LATEST.read_text("utf-8")) if LATEST.exists() else {}
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    for v in old.values():  # vecie dati pirms kategoriju ieviešanas
        v.setdefault("category", "telefoni")

    # OPERATORI=bite,lmt – skenē tikai šos (pārējo dati paliek neskarti). Noderīgi, ja
    # daļu operatoru skenē GitHub, bet daļu – tavs dators (piem. Tele2 bloķē GitHub serverus).
    only = {x.strip() for x in os.getenv("OPERATORI", "").split(",") if x.strip()}

    new, errors, scanned, failed = {}, [], set(), set()
    with requests.Session() as client:
        client.headers.update(HEADERS)
        for op, cat, fn in SOURCES:
            if only and op not in only:
                failed.add((op, cat))  # nepieraksta vēsturi un neziņo "vairs nav"
                for k, v in old.items():
                    if (v["operator"], v["category"]) == (op, cat):
                        new.setdefault(k, v)
                continue
            try:
                items = fn(client)
                if not items:
                    raise RuntimeError("atrasti 0 produkti")
                print(f"{op}/{cat}: {len(items)} produkti")
                for p in items:
                    p["category"] = cat
                    new.setdefault(f"{op}:{p['id']}", p)
                scanned.add((op, cat))
            except Exception as e:  # viena avota kļūda neaptur pārējos
                errors.append(f"{op}/{cat}: {e}")
                failed.add((op, cat))
                # paturam iepriekšējos datus, lai nākamreiz nerādītu viltus izmaiņas
                for k, v in old.items():
                    if (v["operator"], v["category"]) == (op, cat):
                        new.setdefault(k, v)

    # vēsture (ja fails ir vecā formātā bez kategorijas – pārraksta to jaunajā)
    if HISTORY.exists():
        with HISTORY.open(encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        if rows and "category" not in rows[0]:
            with HISTORY.open("w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=FIELDS)
                w.writeheader()
                for r in rows:
                    w.writerow({**r, "category": "telefoni"})
    write_header = not HISTORY.exists()
    with HISTORY.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if write_header:
            w.writeheader()
        for key, p in new.items():
            if (p["operator"], p["category"]) in failed:
                continue
            o = old.get(key)
            if o is None or any(o.get(k) != p.get(k) for k in PRICE_FIELDS):
                w.writerow({"scanned_at": now, **p})

    LATEST.write_text(json.dumps(new, ensure_ascii=False, indent=1), "utf-8")

    # precīzās variantu cenas (Bite/LMT telefoni un pulksteņi) – tikai šoreiz skenētajiem operatoriem
    if os.getenv("VARIANTI", "1") != "0":
        old_var = json.loads(VARIANTS.read_text("utf-8")) if VARIANTS.exists() else {}
        todo = {k: p for k, p in new.items() if (p["operator"], p["category"]) in scanned}
        keep = {k: v for k, v in old_var.items() if k in new and k not in todo}
        with requests.Session() as client:
            client.headers.update(HEADERS)
            fresh = scan_variants(client, todo, old_var, now)
        VARIANTS.write_text(json.dumps({**keep, **fresh}, ensure_ascii=False, indent=0), "utf-8")
    old_meta = json.loads(META.read_text("utf-8")) if META.exists() else {}
    updated = old_meta.get("updated", {})
    updated.update({f"{op}/{cat}": now for op, cat in scanned})
    old_errors = [e for e in old_meta.get("errors", []) if only and e.split("/")[0] not in only]
    META.write_text(json.dumps({
        "scanned_at": now,
        "updated": updated,
        "counts": {f"{op}/{cat}": sum(1 for p in new.values() if (p["operator"], p["category"]) == (op, cat))
                   for op, cat, _ in SOURCES},
        "errors": old_errors + errors,
        "variant_errors": VARIANT_ERRORS[:5],
    }, ensure_ascii=False, indent=1), "utf-8")

    msgs = diff(old, new, scanned) if old else []
    if errors:
        msgs.insert(0, "⚠️ Kļūdas: " + "; ".join(errors))
    if msgs:
        telegram("📱 Cenu izmaiņas\n\n" + "\n".join(msgs))
    else:
        print("Izmaiņu nav.")

    sys.exit(1 if errors else 0)


# ---------------------------------------------------------------- Ko skenēt

SOURCES = [
    ("bite",  "telefoni",  lambda c: scan_bite(c, "/lv/telefoni")),
    ("tele2", "telefoni",  lambda c: scan_tele2(c, "/telefoni/")),
    ("tele2", "pulksteni", lambda c: scan_tele2(c, "/viedpaligi/", {"C[ADTYPE][]": "smartwatch"})),
    ("tele2", "austinas",  lambda c: only_headphones(scan_tele2(c, "/viedpaligi/", {"C[ADTYPE][]": "speakers"}))),
    ("bite",  "pulksteni", lambda c: scan_bite(c, "/lv/viedpulksteni")),
    ("bite",  "austinas",  lambda c: only_headphones(scan_bite(c, "/lv/austinas"))),
    ("lmt",   "telefoni",  lambda c: scan_lmt(c, "visi-telefoni")),
    ("lmt",   "pulksteni", lambda c: scan_lmt(c, "visi-viedpulksteni")),
    ("lmt",   "austinas",  lambda c: only_headphones(scan_lmt(c, "austinas"))),
    ("tet",   "telefoni",  lambda c: scan_tet(c, "/veikals/telefoni/telefoni-un-aksesuari/viedtalruni.html")),
    ("tet",   "pulksteni", lambda c: scan_tet(c, "/veikals/viedierices/viedpulksteni-un-aproces/viedie-pulksteni.html")),
    ("tet",   "austinas",  lambda c: only_headphones(scan_tet(c, "/veikals/datortehnika/audio-d/austinas.html"))),

    ("bite",  "televizori",   lambda c: scan_bite(c, "/lv/televizori")),
    ("tele2", "televizori",   lambda c: scan_tele2(c, "/televizori/")),
    ("lmt",   "televizori",   lambda c: scan_lmt(c, "visi-televizori")),
    ("tet",   "televizori",   lambda c: scan_tet(c, "/veikals/televizori-un-audio/televizori-un-piederumi/televizori.html")),
    ("bite",  "plansetes",    lambda c: scan_bite(c, "/lv/plansetes")),
    ("tele2", "plansetes",    lambda c: scan_tele2(c, "/plansetes/")),
    ("lmt",   "plansetes",    lambda c: scan_lmt(c, "visas-plansetes")),
    ("tet",   "plansetes",    lambda c: scan_tet(c, "/veikals/datortehnika/plansetdatori-un-aksesuari/plansetdatori.html")),
    # rokas un roboti vienā kategorijā (LMT pārdod tikai robotus)
    ("bite",  "puteklsuceji", lambda c: scan_bite(c, "/lv/puteklsuceji")),
    ("tele2", "puteklsuceji", lambda c: only_vacuums(scan_tele2(c, "/viedpaligi/", {"C[ADTYPE][]": "household"}))),
    ("lmt",   "puteklsuceji", lambda c: scan_lmt(c, "puteklu-suceji-roboti")),
    ("tet",   "puteklsuceji", lambda c: scan_tet(c, "/veikals/sadzives-tehnika/maza-sadzives-tehnika/puteklu-suceji.html")
                                        + scan_tet(c, "/veikals/sadzives-tehnika/maza-sadzives-tehnika/roboti-puteklu-suceji.html")),
    ("bite",  "kameras",      lambda c: scan_bite(c, "/lv/noverosanas-kameras")),
    ("tele2", "kameras",      lambda c: scan_tele2(c, "/viedpaligi/", {"C[ADTAGS][]": "Novērošanas kameras"})),
    ("lmt",   "kameras",      lambda c: scan_lmt(c, "noverosanas-kameras")),
    ("tet",   "kameras",      lambda c: scan_tet(c, "/veikals/viedierices/video/video-noverosanas-kameras.html")),
]


if __name__ == "__main__":
    main()
