# Selbsthilfe-Stunden

Web-Anwendung zur Verwaltung von Selbsthilfe-Stunden (basierend auf der Excel-Liste
`SelbsthilfeStd-Test2.xlsx`).

## Funktionen

- **Registrierung**: Benutzer registrieren sich selbst; das Konto wird erst nach
  Freigabe durch den Admin aktiv.
- **Admin**: sieht alle Nutzer, kann sie zulassen/sperren und Rollen ändern.
- **Benutzer-Ansicht**: Liste der eigenen Einträge mit Datumsfilter (von/bis),
  Summierung der Stunden und der Vergütung.
- **Neue Einträge**: mit Auswahllisten für **Art** und abhängig davon für die
  **Tätigkeit** („Andere Tätigkeit…" erlaubt freie Eingabe).
- **Datum Anerkennung**: kann ausschließlich vom Admin gesetzt/entfernt werden.
- **Gesamtliste (Admin)**: alle Einträge aller Benutzer, filterbar nach Datum
  von/bis, mit Gesamtsummen; Anerkennungsdatum pro Eintrag setzbar.

## Starten

```bash
pip install -r requirements.txt
python import_xlsx.py /pfad/zu/SelbsthilfeStd-Test2.xlsx   # einmalig, Daten importieren
python app.py                                              # Startet auf http://127.0.0.1:5000
```

Beim ersten Start von `app.py` wird automatisch eine leere Datenbank in
`data/selbsthilfe.db` angelegt.

## Konten nach dem Import

| Rolle  | Login                  | Passwort        |
|--------|------------------------|-----------------|
| Admin  | `admin@example.com`    | `admin123` (per Umgebungsvariable `ADMIN_PASSWORD` änderbar) |
| Demo   | `haushalt01@example.com` … `haushalt35@example.com` | `demo123` |

> Passwörter und Secret-Key vor produktivem Einsatz ändern
> (`ADMIN_PASSWORD`, `SECRET_KEY` als Umgebungsvariablen setzen).

## Konfiguration (Umgebungsvariablen)

| Variable       | Bedeutung                                   | Standard                        |
|----------------|---------------------------------------------|---------------------------------|
| `DB_PATH`      | Pfad zur SQLite-Datenbank                   | `data/selbsthilfe.db`           |
| `SECRET_KEY`   | Flask-Secret für Sessions                   | Platzhalter – **bitte setzen!** |
| `PORT`         | Port des Webservers                         | `5000`                          |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | Admin-Konto beim Import  | `admin@example.com` / `admin123` |
