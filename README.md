# Cenu skeneris – Bite, Tele2, LMT, Tet

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
| Tet telefoni, viedpulksteņi, austiņas | ✅ | `tet.lv/veikals/...html?page=N` (Magento, 58 preces lapā). Cenas no kartītes `data-pricing` JSON, mēneša maksājums no redzamā teksta. Katra krāsa ir atsevišķa prece – salīdzinājumā tās apvieno. |

Starp pieprasījumiem ir 1,5 s pauze.

**Tele2 un GitHub:** Tele2 GitHub serveriem rāda anti-bot pārbaudes lapu, tāpēc GitHub Actions
skenē Bite, LMT un Tet (`OPERATORI: bite,lmt,tet` failā `.github/workflows/scan.yml`).
Tele2 skenē tavs dators ar `skenet_tele2.bat` (Windows) vai `skenet_tele2.sh` (macOS/Linux).
Abi raksta tajos pašos `data/` failos, un katrs atjaunina tikai savu operatoru.

Uzstādīšana datorā:
1. Uzinstalē [Git](https://git-scm.com) un [Python](https://python.org) (Windows instalatorā atzīmē “Add to PATH”).
2. `git clone https://github.com/edz-driod/cenu-skeneris.git`
3. Palaid `skenet_tele2.bat` vienreiz ar roku. Pirmajā reizē Git prasīs pieslēgties GitHub.
4. Windows: *Task Scheduler → Create Basic Task → Daily*, 8:20, darbība *Start a program* → `skenet_tele2.bat`.
   Pēc tam *Properties → Triggers* pievieno otru laiku 18:20 un atzīmē *Run task as soon as possible after a scheduled start is missed*.

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

## Precīzie varianti (SKU)

Bite un LMT saraksta lapās katram modelim ir tikai cena “no”. Tāpēc skeneris papildus atver
Bite un LMT **telefonu un pulksteņu** produktu lapas un saglabā katra varianta cenu `data/variants.json`:
- **LMT:** produkta lapas JSON satur visus variantus (1 pieprasījums modelim).
- **Bite:** atmiņas / izmēra / LTE izvēle tiek pārslēgta ar to pašu AJAX pieprasījumu, ko sūta lapa,
  un cena tiek nolasīta no varianta lapas (`?v=<id>`).

Tele2 un Tet katrs variants jau ir atsevišķa prece. Lapā, uzspiežot uz ierīces, augšā redzama
tabula: rindās varianti (piem. 128 / 256 / 512 GB vai 40 mm / 44 mm · LTE), kolonnās operatori.
Variantu skenēšanai atvēlētas ≤10 min; ja laiks beidzas, nākamreiz turpina ar neatjaunotajiem.
Izslēgt: `VARIANTI=0`.

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
