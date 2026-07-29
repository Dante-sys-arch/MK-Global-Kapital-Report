"""
FinVoice — Redaktionsseite.

Baut pro Kunde eine statische HTML-Seite (finvoice/docs/<slug>/index.html)
mit allen Wochen-Entwürfen, neueste zuerst, inkl. Kopieren-Button.
Die Seite ist für den Betreiber und (nach Redaktion) den Kunden gedacht.
"""
import html
import json

from client_config import DATA_DIR, docs_path

STYLE = """
body{font-family:-apple-system,'Segoe UI',Roboto,sans-serif;max-width:760px;margin:2rem auto;
     padding:0 1rem;color:#1a1a2e;background:#f7f7fb;line-height:1.55}
h1{font-size:1.5rem} h2{font-size:1.1rem;margin-top:2.5rem;border-bottom:2px solid #d9d9e8;padding-bottom:.3rem}
.card{background:#fff;border:1px solid #e3e3ef;border-radius:10px;padding:1.1rem 1.3rem;margin:1rem 0;
      box-shadow:0 1px 3px rgba(0,0,0,.05)}
.meta{font-size:.8rem;color:#6b6b85;margin-bottom:.6rem}
.post{white-space:pre-wrap;font-size:.95rem}
.note{font-size:.82rem;color:#8a6d1a;background:#fdf6e3;border-radius:6px;padding:.5rem .7rem;margin-top:.8rem}
button{margin-top:.8rem;padding:.45rem .9rem;border:0;border-radius:6px;background:#2b3a67;color:#fff;
       cursor:pointer;font-size:.85rem}
button:hover{background:#1d2947}
a{color:#2b3a67}
"""

SCRIPT = """
function copyPost(id){
  const el = document.getElementById(id);
  navigator.clipboard.writeText(el.innerText).then(()=>{
    const btn = document.getElementById(id + '-btn');
    btn.textContent = 'Kopiert ✓'; setTimeout(()=>btn.textContent='Post kopieren', 1500);
  });
}
"""


def render_client_page(client: dict) -> None:
    client_data = DATA_DIR / client["slug"]
    weeks = sorted(client_data.glob("*.json"), reverse=True) if client_data.exists() else []

    sections = []
    for week_file in weeks:
        payload = json.loads(week_file.read_text(encoding="utf-8"))
        cards = []
        for i, draft in enumerate(payload.get("drafts", [])):
            post_id = f"{week_file.stem}-{i}"
            hook = ""
            if draft.get("hook_title"):
                link = html.escape(draft.get("hook_link") or "#")
                hook = f' · Aufhänger: <a href="{link}" target="_blank">{html.escape(draft["hook_title"])}</a>'
            note = ""
            if draft.get("redaktionsnotiz"):
                note = f'<div class="note">✏️ Redaktion: {html.escape(draft["redaktionsnotiz"])}</div>'
            cards.append(f"""<div class="card">
  <div class="meta">{html.escape(draft.get("format", ""))}{hook}</div>
  <div class="post" id="{post_id}">{html.escape(draft.get("post", ""))}</div>
  {note}
  <button id="{post_id}-btn" onclick="copyPost('{post_id}')">Post kopieren</button>
</div>""")
        sections.append(f"<h2>Woche {html.escape(payload.get('week', week_file.stem))} "
                        f"<small>({html.escape(payload.get('generated', ''))})</small></h2>\n" + "\n".join(cards))

    page = f"""<!DOCTYPE html>
<html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex">
<title>FinVoice — {html.escape(client['name'])}</title>
<style>{STYLE}</style></head>
<body>
<h1>FinVoice · Post-Entwürfe für {html.escape(client['name'])}</h1>
<p class="meta">{html.escape(client['role'])}, {html.escape(client['company'])} —
Entwürfe werden redigiert, bevor sie veröffentlicht werden. Nichts wird automatisch gepostet.</p>
{"".join(sections) or "<p>Noch keine Entwürfe generiert.</p>"}
<script>{SCRIPT}</script>
</body></html>"""

    out = docs_path(client) / "index.html"
    out.write_text(page, encoding="utf-8")
    print(f"  ✓ Redaktionsseite: {out}")
