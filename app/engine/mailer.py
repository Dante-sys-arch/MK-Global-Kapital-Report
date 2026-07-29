"""
E-Mail-Versand: HTML-Digest der neuen Clippings + Excel-Pressespiegel als Anhang.

SMTP-Zugang über Umgebungsvariablen:
  SMTP_HOST, SMTP_PORT (Default 587), SMTP_USER, SMTP_PASSWORD,
  SMTP_FROM (Default: SMTP_USER)
Ohne SMTP_HOST wird der Versand übersprungen (z.B. lokal / in Tests).
"""
import os
import smtplib
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path


def build_digest_html(cfg, new_articles, total_count):
    rows = "".join(
        f"""<tr>
          <td style="padding:8px 12px;border-bottom:1px solid #eee;white-space:nowrap">{a.get('date', '')}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #eee"><b>{a.get('outlet', '')}</b>
            {'<span style="background:#1a56db;color:#fff;border-radius:3px;padding:1px 6px;font-size:11px;margin-left:6px">Tier 1</span>' if str(a.get('tier')) == '1' else ''}</td>
          <td style="padding:8px 12px;border-bottom:1px solid #eee">
            <a href="{a.get('link', '')}" style="color:#1a56db;text-decoration:none">{a.get('title', '')}</a></td>
        </tr>"""
        for a in new_articles
    )
    return f"""<!doctype html>
<html><body style="font-family:Segoe UI,Arial,sans-serif;color:#1f2937;margin:0;padding:24px;background:#f9fafb">
  <div style="max-width:720px;margin:0 auto;background:#fff;border-radius:8px;padding:32px;border:1px solid #e5e7eb">
    <p style="font-size:13px;color:#6b7280;margin:0 0 4px">ClipRadar — Medienmonitoring</p>
    <h2 style="margin:0 0 16px">{cfg.name}: {len(new_articles)} neue Clipping{'s' if len(new_articles) != 1 else ''}</h2>
    <table style="border-collapse:collapse;width:100%;font-size:14px">
      <tr style="text-align:left;background:#f3f4f6">
        <th style="padding:8px 12px">Datum</th><th style="padding:8px 12px">Medium</th><th style="padding:8px 12px">Artikel</th>
      </tr>
      {rows}
    </table>
    <p style="font-size:13px;color:#6b7280;margin-top:24px">
      Insgesamt {total_count} Clippings im Bestand. Der vollständige Pressespiegel (Excel) ist angehängt.
    </p>
  </div>
</body></html>"""


def send_report(cfg, new_articles, total_count, attachment_path=None):
    """Digest + Report an alle delivery_emails des Kunden senden."""
    host = os.environ.get("SMTP_HOST")
    if not host:
        print("  Mail: SMTP_HOST nicht gesetzt — Versand übersprungen")
        return False
    if not cfg.delivery_emails:
        print(f"  Mail: Keine Empfänger für {cfg.client_id} konfiguriert")
        return False

    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER", "")
    password = os.environ.get("SMTP_PASSWORD", "")
    sender = os.environ.get("SMTP_FROM", user)

    msg = EmailMessage()
    today = datetime.now().strftime("%d.%m.%Y")
    msg["Subject"] = f"ClipRadar | {cfg.name}: {len(new_articles)} neue Clippings ({today})"
    msg["From"] = sender
    msg["To"] = ", ".join(cfg.delivery_emails)
    msg.set_content(
        f"{len(new_articles)} neue Clippings für {cfg.name}.\n"
        "Details im HTML-Teil bzw. im angehängten Excel-Pressespiegel."
    )
    msg.add_alternative(build_digest_html(cfg, new_articles, total_count), subtype="html")

    if attachment_path and Path(attachment_path).exists():
        with open(attachment_path, "rb") as f:
            msg.add_attachment(
                f.read(),
                maintype="application",
                subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                filename=Path(attachment_path).name,
            )

    with smtplib.SMTP(host, port, timeout=30) as server:
        server.starttls()
        if user:
            server.login(user, password)
        server.send_message(msg)
    print(f"  Mail: Versand an {len(cfg.delivery_emails)} Empfänger OK")
    return True
