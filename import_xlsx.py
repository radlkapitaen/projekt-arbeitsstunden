import os
import sys
from datetime import datetime

import openpyxl
from werkzeug.security import generate_password_hash

from app import BASE_DIR, DB_PATH, init_db

XLSX_PATH = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    BASE_DIR, "..", "MK5sIfyH-SelbsthilfeStd-Test2.xlsx"
)
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@example.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")


def to_iso(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    return str(value).strip()


def main():
    init_db()
    import sqlite3
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row

    if db.execute("SELECT COUNT(*) FROM entries").fetchone()[0] > 0:
        print("Datenbank enthält bereits Einträge – Import übersprungen.")
        print("Für einen Neuimport bitte die Datei data/selbsthilfe.db löschen.")
        return

    if not db.execute("SELECT 1 FROM users WHERE email = ?", (ADMIN_EMAIL,)).fetchone():
        db.execute(
            "INSERT INTO users (name, email, password_hash, role, approved) VALUES (?, ?, ?, 'admin', 1)",
            ("Administrator", ADMIN_EMAIL, generate_password_hash(ADMIN_PASSWORD)),
        )
        print(f"Admin-Konto angelegt: {ADMIN_EMAIL} / Passwort aus ADMIN_PASSWORD (Standard: admin123)")

    wb = openpyxl.load_workbook(XLSX_PATH, data_only=True)
    ws = wb.worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    header = [str(h).strip() if h else "" for h in rows[0]]
    idx = {name: i for i, name in enumerate(header)}

    user_cache = {}
    imported = 0
    for raw in rows[1:]:
        if not raw or not raw[idx["Wohnung"]]:
            continue
        wohnung = str(raw[idx["Wohnung"]]).strip()
        haushalt = str(raw[idx["Name(n)"]] or "").strip() or wohnung
        art = str(raw[idx["Art"]] or "").strip()
        taetigkeit = str(raw[idx["Tätigkeit"]] or "").strip()
        datum = to_iso(raw[idx["Datum"]])
        anerkennung = to_iso(raw[idx["Datum Anerkennung"]])
        stunden = float(raw[idx["Stunden"]] or 0)
        verguetung = float(raw[idx["Vergütung je Stunde"]] or 0)
        kommentar = raw[idx["Kommentar"]]
        kommentar = str(kommentar).strip() if kommentar else None

        email = haushalt.lower().replace(" ", "") + "@example.com"
        if email not in user_cache:
            existing = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
            if existing:
                user_cache[email] = existing["id"]
            else:
                cur = db.execute(
                    "INSERT INTO users (name, email, password_hash, wohnung, approved) "
                    "VALUES (?, ?, ?, ?, 1)",
                    (haushalt, email, generate_password_hash("demo123"), wohnung),
                )
                user_cache[email] = cur.lastrowid

        db.execute(
            "INSERT INTO entries (user_id, wohnung, haushalt, art, taetigkeit, datum, "
            "datum_anerkennung, stunden, verguetung_je_stunde, kommentar) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (user_cache[email], wohnung, haushalt, art, taetigkeit, datum,
             anerkennung, stunden, verguetung, kommentar),
        )
        imported += 1

    db.commit()
    db.close()
    print(f"{imported} Einträge importiert.")
    print("Demo-Nutzer: Passwort 'demo123' (z. B. haushalt01@example.com)")


if __name__ == "__main__":
    main()
