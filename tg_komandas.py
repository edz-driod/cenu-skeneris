"""Telegram komandas cenu skenerim.

Palaiž GitHub Actions ik pēc ~5 min (.github/workflows/telegram.yml). Nolasa jaunās ziņas botam
un, ja tās ir no atļautā čata (TG_CHAT), izpilda komandu:

  /skenet                – palaiž pilnu skenēšanu (visi operatori)
  /skenet bite tele2     – tikai norādītos operatorus
  /statuss               – kad pēdējo reizi skenēts un vai skenēšana pašlaik notiek
  /palidziba             – komandu saraksts

Izmanto tikai standarta bibliotēku, lai darbs būtu ātrs (bez pip install).
"""
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone

TOKEN = os.environ["TG_TOKEN"]
CHAT = str(os.environ["TG_CHAT"]).strip()
GH_TOKEN = os.environ["GH_TOKEN"]
REPO = os.environ["GITHUB_REPOSITORY"]
OPERATORI = ["bite", "tele2", "lmt", "tet"]
PAGE = "https://" + REPO.split("/")[0].lower() + ".github.io/" + REPO.split("/")[1] + "/"


def tg(method, **params):
    data = urllib.parse.urlencode(params).encode()
    with urllib.request.urlopen(f"https://api.telegram.org/bot{TOKEN}/{method}", data, timeout=30) as r:
        return json.load(r)


def gh(method, path, body=None):
    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}{path}", method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {GH_TOKEN}", "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28"})
    with urllib.request.urlopen(req, timeout=30) as r:
        txt = r.read()
        return json.loads(txt) if txt else None


def say(text):
    tg("sendMessage", chat_id=CHAT, text=text, disable_web_page_preview="true")


def running_scan():
    runs = gh("GET", "/actions/workflows/scan.yml/runs?per_page=5")["workflow_runs"]
    return next((r for r in runs if r["status"] in ("queued", "in_progress", "waiting", "pending")), None)


def cmd_scan(args):
    ops = [a.lower().strip(",") for a in args if a.lower().strip(",") in OPERATORI] or OPERATORI
    if running_scan():
        say("Skenēšana jau notiek. Kad beigsies, atsūtīšu izmaiņas.")
        return
    gh("POST", "/actions/workflows/scan.yml/dispatches", {"ref": "main", "inputs": {"operatori": ",".join(ops)}})
    say(f"Sāku skenēt: {', '.join(o.capitalize() if o != 'lmt' else 'LMT' for o in ops)}. "
        f"Tas aizņem 5–15 min; izmaiņas atsūtīšu šeit.")


def cmd_status(_):
    run = running_scan()
    last = gh("GET", "/actions/workflows/scan.yml/runs?per_page=10&status=completed")["workflow_runs"]
    last = next((r for r in last if r["conclusion"] == "success"), None)
    lines = []
    if run:
        lines.append("Skenēšana pašlaik notiek.")
    if last:
        t = datetime.fromisoformat(last["updated_at"].replace("Z", "+00:00"))
        mins = int((datetime.now(timezone.utc) - t).total_seconds() // 60)
        ago = f"pirms {mins} min" if mins < 120 else f"pirms {mins // 60} h"
        lines.append(f"Pēdējā veiksmīgā skenēšana: {ago}.")
    lines.append(PAGE)
    say("\n".join(lines))


def cmd_help(_):
    say("Komandas:\n/skenet – skenēt visus operatorus\n/skenet bite tele2 – tikai izvēlētos\n/statuss – pēdējā skenēšana")


COMMANDS = {"skenet": cmd_scan, "skenēt": cmd_scan, "scan": cmd_scan, "statuss": cmd_status, "status": cmd_status,
            "palidziba": cmd_help, "help": cmd_help, "start": cmd_help}


def main():
    updates = tg("getUpdates", timeout=0, allowed_updates='["message"]').get("result", [])
    if not updates:
        return
    # apstiprina saņemtās ziņas, lai tās nenolasītu atkārtoti
    tg("getUpdates", offset=updates[-1]["update_id"] + 1, timeout=0)
    done = set()
    for u in updates:
        m = u.get("message") or {}
        if str(m.get("chat", {}).get("id")) != CHAT:
            continue  # svešiem neatbild
        parts = (m.get("text") or "").strip().split()
        if not parts or not parts[0].startswith("/"):
            continue
        name = parts[0][1:].split("@")[0].lower()
        fn = COMMANDS.get(name)
        if fn and (name, tuple(parts[1:])) not in done:  # vienādas komandas vienā partijā – vienreiz
            done.add((name, tuple(parts[1:])))
            fn(parts[1:])


if __name__ == "__main__":
    main()
