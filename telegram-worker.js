// Cloudflare Worker: Telegram bots, kas uzreiz atbild uz /skenet un /statuss.
// Iestatīšana – sk. README sadaļu "Telegram komandas".
// Vajadzīgie mainīgie (Settings → Variables and Secrets):
//   TG_TOKEN  – bota tokens (tas pats, kas GitHub secrets)
//   TG_CHAT   – tava čata ID (tas pats, kas GitHub secrets)
//   GH_TOKEN  – GitHub fine-grained tokens ar "Actions: Read and write" tikai repozitorijam cenu-skeneris
const REPO = "edz-driod/cenu-skeneris";
const PAGE = "https://edz-driod.github.io/cenu-skeneris/";
const OPS = { bite: "Bite", tele2: "Tele2", lmt: "LMT", tet: "Tet" };

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    const tg = (method, body) => fetch(`https://api.telegram.org/bot${env.TG_TOKEN}/${method}`, {
      method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) }).then(r => r.json());

    // vienreizēja iestatīšana: atver https://<worker>.workers.dev/setup pārlūkā
    if (url.pathname === "/setup") {
      const secret = await hash(env.TG_TOKEN);
      const r = await tg("setWebhook", { url: `${url.origin}/hook`, secret_token: secret, allowed_updates: ["message"] });
      await tg("setMyCommands", { commands: [
        { command: "skenet", description: "Skenēt cenas (var norādīt: bite tele2 lmt tet)" },
        { command: "statuss", description: "Kad pēdējo reizi skenēts" } ] });
      return new Response(r.ok ? "Gatavs! Atsūti botam /statuss." : "Kļūda: " + JSON.stringify(r),
        { headers: { "content-type": "text/plain; charset=utf-8" } });
    }
    if (url.pathname !== "/hook" || req.method !== "POST") return new Response("ok");
    if (req.headers.get("x-telegram-bot-api-secret-token") !== await hash(env.TG_TOKEN)) return new Response("nē", { status: 403 });

    const m = (await req.json()).message || {};
    if (String(m.chat?.id) !== String(env.TG_CHAT).trim()) return new Response("ok");   // svešiem neatbild
    const parts = (m.text || "").trim().split(/\s+/);
    const cmd = (parts[0] || "").replace(/^\//, "").split("@")[0].toLowerCase();
    const say = text => tg("sendMessage", { chat_id: env.TG_CHAT, text, disable_web_page_preview: true });
    const gh = (path, init = {}) => fetch(`https://api.github.com/repos/${REPO}${path}`, { ...init, headers: {
      authorization: `Bearer ${env.GH_TOKEN}`, accept: "application/vnd.github+json", "user-agent": "cenu-bots",
      "x-github-api-version": "2022-11-28", ...(init.body ? { "content-type": "application/json" } : {}) } });
    const running = async () => (await (await gh("/actions/workflows/scan.yml/runs?per_page=5")).json())
      .workflow_runs?.find(r => ["queued", "in_progress", "waiting", "pending"].includes(r.status));

    try {
      if (["skenet", "skenēt", "scan"].includes(cmd)) {
        const ops = parts.slice(1).map(s => s.toLowerCase().replace(/,/g, "")).filter(s => OPS[s]);
        const list = ops.length ? ops : Object.keys(OPS);
        if (await running()) await say("Skenēšana jau notiek. Kad beigsies, atsūtīšu izmaiņas.");
        else {
          const r = await gh("/actions/workflows/scan.yml/dispatches", { method: "POST",
            body: JSON.stringify({ ref: "main", inputs: { operatori: list.join(",") } }) });
          await say(r.ok ? `Sāku skenēt: ${list.map(o => OPS[o]).join(", ")}. Tas aizņem 5–15 min, izmaiņas atsūtīšu šeit.`
            : `Neizdevās palaist (GitHub ${r.status}). Pārbaudi GH_TOKEN.`);
        }
      } else if (["statuss", "status"].includes(cmd)) {
        const runs = (await (await gh("/actions/workflows/scan.yml/runs?per_page=10")).json()).workflow_runs || [];
        const cur = runs.find(r => r.status !== "completed"), last = runs.find(r => r.conclusion === "success");
        const mins = last ? Math.round((Date.now() - Date.parse(last.updated_at)) / 60000) : null;
        await say([cur && "Skenēšana pašlaik notiek.",
          last && `Pēdējā veiksmīgā skenēšana: pirms ${mins < 120 ? mins + " min" : Math.round(mins / 60) + " h"}.`, PAGE]
          .filter(Boolean).join("\n"));
      } else if (cmd) {
        await say("Komandas:\n/skenet – skenēt visus operatorus\n/skenet bite tele2 – tikai izvēlētos\n/statuss – pēdējā skenēšana");
      }
    } catch (e) { await say("Kļūda: " + e.message); }
    return new Response("ok");
  },
};

async function hash(s) {
  const b = await crypto.subtle.digest("SHA-256", new TextEncoder().encode("cenu-bots:" + s));
  return [...new Uint8Array(b)].map(x => x.toString(16).padStart(2, "0")).join("").slice(0, 48);
}
