# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary user: the owner, a product category manager at LMT. He uses the page to see what competitors Bite, Tele2 and Tet are doing with device prices compared with LMT.

Secondary users: a few people close to him (family, friends), who use it to spot good deals. The page is not aimed at the general public.

The page is opened on phone and desktop about equally, often from a Telegram price-change notification.

## Product Purpose

Cenu skeneris collects device prices from the four Latvian mobile operators every weekday morning, keeps the history, and shows it on one page.

The jobs it must support:
- notice promotions, price drops, new models and removed models;
- follow a model's price history to judge whether now is a good moment;
- analyse the market: which operator is cheaper overall, by category, by brand and head to head.

Success: the owner sees competitor moves the morning they happen, without visiting four shops.

## Positioning

An operator-independent, side-by-side view of all four Latvian operators' device catalogues, matched by model and exact variant, with price history kept over time. The operators' own shops show only their own current prices.

## Operating Context

- Scanning runs on GitHub Actions on weekday mornings (~9:00). Weekends are skipped.
- Tele2 is fetched through Bright Data Web Unlocker (free tier). A Windows `.bat` on the owner's PC is the backup.
- Changes are announced through a Telegram bot. The page is served from GitHub Pages.
- Prices recorded per device: monthly payment, old monthly payment, full price, old full price, link.

## Capabilities and Constraints

- Operators: Bite, Tele2, LMT, Tet.
- Categories: phones, smartwatches, headphones, tablets, TVs, vacuums (handheld and robot), surveillance cameras.
- Exact variant (storage/size) prices for Bite and LMT phones and watches; Tele2 and Tet list each variant as its own product, and Tet each colour.
- Operators are compared by model name; matching rules handle manufacturer codes, bundles and colours.
- The page (`index.html`) has category tabs, search, price history charts, a per-device detail dialog and an analysis view ("Kurš lētāks?").
- Must remain free of charge: GitHub Pages, GitHub Actions, Bright Data free tier.
- Data lives in `data/` (`prices.csv`, `latest.json`, `variants.json`, `meta.json`).

## Brand Commitments

- Interface language is Latvian.
- Name: Cenu skeneris.

## Evidence on Hand

- Real scanned price data and history in `data/`.
- No testimonials, users or usage figures exist; do not invent them.

## Product Principles

1. Competitor movement first: changes and differences matter more than static listings.
2. Compare like with like: a price is only meaningful against the same model and variant.
3. History is the asset: never lose or obscure past prices.
4. Works at a glance on a phone and in depth on a desktop.
5. Stays free to run.
