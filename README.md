# Cenu skeneris – Bite, Tele2, LMT

Divreiz dienā nolasa telefonu, viedpulksteņu un austiņu cenas no operatoriem, saglabā vēsturi `data/prices.csv`
un nosūta Telegram ziņu, ja kāda cena mainās, parādās jauns telefons vai kāds pazūd.
`index.html` ir lapa ar kategoriju cilnēm, meklēšanu un cenu vēstures grafikiem.
Lapa operatorus salīdzina pēc modeļa nosaukuma.
Viss darbojas bez maksas uz GitHub Actions un GitHub Pages.

## Kā tas strādā

Ko skenēt, nosaka saraksts `SOURCES` faila `scan.py` beigās. Katrs ieraksts ir operators, kategorija un funkcija.

| Avots | Statuss | Kā |
|---|---|---|
| Bite telefoni | ✅ | `bite.lv/lv/telefoni` satur produktu ID sarakstu (`data-listInfo`). Cenas nāk no `/lv/product-list/ajax/commerce_product/small__fti/<id-id-id>` pa 15 ID reizē. |
| Tele2 telefoni | ✅ | `tele2.lv/telefoni/?filter=1&p=N&xhr=1` atgriež JSON ar produktu HTML. |
| Tele2 viedpulksteņi | ✅ | `tele2.lv/viedpaligi/` ar filtru `C[ADTYPE][]=smartwatch`. |
| Tele2 austiņas | ✅ | `tele2.lv/viedpaligi/` ar filtru `speakers`. Šī sadaļa jauc austiņas un skaļruņus, tāpēc skaļruņus izmet pēc nosaukuma (`SPEAKER_WORDS`). |
| Bite viedpulksteņi | ✅ | `bite.lv/lv/viedpulksteni`, tāpat kā telefoni. |
| Bite austiņas | ✅ | `bite.lv/lv/austinas`, tāpat kā telefoni. |
| LMT telefoni, viedpulksteņi, austiņas | ✅ | `lmt.lv/veikals/<visi-telefoni / visi-viedpulksteni / austinas>?page=N&perPage=54`. LMT ir Nuxt lapa: cenas ir lapas `<script id="__NUXT_DATA__">` JSON (pilnā cena, 24 mēn. nomaksa, vecā cena). |

Starp pieprasījumiem ir 1,5 s pauze.

**LMT un Cloudflare:** LMT lapa ir aiz Cloudflare. Ja GitHub serveru IP adreses tiek bloķētas,
LMT avoti atsūtīs kļūdu "neatradu __NUXT_DATA__", bet Bite un Tele2 turpinās strādāt.
Tādā gadījumā skeneri var palaist savā datorā (`python scan.py` ar Windows Task Scheduler vai cron)
un rezultātu iestumt GitHub (`git add data && git commit -m cenas && git push`).

Katrai ierīcei saglabā: mēneša maksājumu, veco mēneša maksājumu (ja ir akcija),
pilno cenu, veco pilno cenu, saiti.

## Uzstādīšana (~10 min)

1. **Izveido repozitoriju** GitHub un ielādē šos failus. Ja gribi lapu bez maksas, repozitorijam jābūt publiskam (sk. 4. soli).
2. **Telegram bots:**
   - Telegram atrodi `@BotFather` → `/newbot` → saņemsi **token**.
   - Uzraksti savam botam jebkādu ziņu.
   - Atver `https://api.telegram.org/bot<TOKEN>/getUpdates` un atrodi `"chat":{"id":...}`. Tas ir **chat id**.
3. **Secrets:** repozitorijā *Settings → Secrets and variables → Actions → New repository secret*:
   - `TG_TOKEN` = bota token
   - `TG_CHAT` = chat id
4. **Lapa (GitHub Pages):** *Settings → Pages → Source: Deploy from a branch → `main` / `(root)` → Save*.
   Pēc ~1 min lapa būs pieejama `https://<lietotājs>.github.io/<repozitorijs>/`.
   ⚠️ Bezmaksas GitHub plānā Pages darbojas tikai **publiskiem** repozitorijiem.
   Ja vēlies privātu repozitoriju, lapu var atvērt lokāli: `python -m http.server`, tad `http://localhost:8000`.
5. **Pirmā palaišana:** *Actions → Cenu skenēšana → Run workflow*.
   Pirmajā reizē tiek tikai saglabātas cenas. Paziņojumi nāks no nākamās reizes.

## Lokāla palaišana

```bash
pip install -r requirements.txt
python scan.py          # bez TG_* mainīgajiem izmaiņas izdrukā terminālī
python -m http.server   # lapa: http://localhost:8000
```

## Dati

- `data/prices.csv` – rinda tiek pierakstīta tikai tad, kad parādās jauns telefons vai mainās cena,
  tāpēc fails aug lēni (gadā ~ dažus simtus KB).
- `data/latest.json` – pēdējās skenēšanas stāvoklis, ko izmanto salīdzināšanai un lapai.
- `data/meta.json` – pēdējās skenēšanas laiks un kļūdas.

## Ja kaut kas salūzt

Ja kāda lapa nomaina struktūru, skripts atsūta "⚠️ Kļūdas: ..." ziņu, un Actions
palaišana kļūst sarkana. Pārējo avotu dati tiek saglabāti normāli.
Parasti jāpielāgo tikai CSS selektori `parse_bite()` vai `parse_tele2()` funkcijā.
Ja kāds skaļrunis nonāk austiņu sarakstā, pievieno tā nosaukuma daļu `SPEAKER_WORDS`.

## Ko var pievienot vēlāk

- Tarifu plānus un internetu (tāda pati pieeja, citas lapas)
- Cenu brīdinājumu konkrētam telefonam (piem. “paziņo, ja iPhone 18 Pro < 1300 €”)
