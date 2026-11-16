import os
import sqlite3
from datetime import date
from functools import wraps

from flask import (
    Flask, flash, g, redirect, render_template, request, session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "data", "selbsthilfe.db"))

ART_TATIGKEIT = {
    "Garten": ["Laub fegen"],
    "Reinigung": ["Kellergänge fegen", "Fenster", "Briefkastenanlage", "Treppenhaus", "Eingangsportal"],
    "Schneeräumen": ["Schneeräumung", "Rund ums Haus"],
    "Beleuchtung": ["Bewegungsmelder kontrollieren"],
    "Kaminkehrer": ["Gasleitungsschau"],
    "Straßenreinigung": ["Gehweg fegen"],
    "Hauswart": ["Kontrollgang"],
    "Sonstiges": ["Kontrolle Wartungsarbeiten"],
    "Dachrinnenreinigung": ["Vorderhaus"],
    "Entwässerung": ["Reinigung Rinnen, Rigolen"],
    "Müll": ["Bereitstellung Mülltonnen"],
    "Heizungsanlage": ["Nachfüllen Wasser"],
    "Aufzug": ["Reinigung Führungsschienen"],
    "Ungezieferbekämpfung": ["Papierfische in Keller"],
    "Wascheinrichtung": ["Reinigung Raum"],
    "Lüftung": ["Filter wechseln"],
}

DEFAULT_VERGUETUNG = 14.0

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "bitte-SECRET_KEY-umsetzen")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            approved INTEGER NOT NULL DEFAULT 0,
            wohnung TEXT
        );
        CREATE TABLE IF NOT EXISTS entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            wohnung TEXT NOT NULL,
            haushalt TEXT,
            art TEXT NOT NULL,
            taetigkeit TEXT NOT NULL,
            datum TEXT NOT NULL,
            datum_anerkennung TEXT,
            stunden REAL NOT NULL,
            verguetung_je_stunde REAL NOT NULL,
            kommentar TEXT
        );
        """
    )
    db.commit()
    db.close()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if session.get("role") != "admin":
            flash("Zugriff nur für Administratoren.", "error")
            return redirect(url_for("entries"))
        return view(*args, **kwargs)
    return wrapped


def current_user():
    if "user_id" not in session:
        return None
    row = get_db().execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    return row


@app.context_processor
def inject_current_user():
    return {"current_user": current_user}


def parse_date(value, field):
    if not value:
        flash(f"Bitte {field} angeben.", "error")
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        flash(f"Ungültiges Datum bei {field}.", "error")
        return None


def filter_params():
    datum_von = request.args.get("von", "").strip()
    datum_bis = request.args.get("bis", "").strip()
    clauses, params = [], []
    if datum_von:
        clauses.append("datum >= ?")
        params.append(datum_von)
    if datum_bis:
        clauses.append("datum <= ?")
        params.append(datum_bis)
    return datum_von, datum_bis, clauses, params


@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("entries"))
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        wohnung = request.form.get("wohnung", "").strip()
        password = request.form.get("password", "")
        password2 = request.form.get("password2", "")

        if not name or not email or not password:
            flash("Name, E-Mail und Passwort sind erforderlich.", "error")
        elif password != password2:
            flash("Die Passwörter stimmen nicht überein.", "error")
        elif len(password) < 6:
            flash("Das Passwort muss mindestens 6 Zeichen lang sein.", "error")
        elif get_db().execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
            flash("Diese E-Mail ist bereits registriert.", "error")
        else:
            db = get_db()
            db.execute(
                "INSERT INTO users (name, email, password_hash, wohnung) VALUES (?, ?, ?, ?)",
                (name, email, generate_password_hash(password), wohnung),
            )
            db.commit()
            flash("Registrierung erfolgreich. Ein Administrator muss das Konto noch freigeben.", "ok")
            return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            if not user["approved"]:
                flash("Ihr Konto wurde noch nicht vom Administrator freigegeben.", "error")
            else:
                session.clear()
                session["user_id"] = user["id"]
                session["role"] = user["role"]
                return redirect(url_for("entries"))
        else:
            flash("E-Mail oder Passwort falsch.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/eintraege")
@login_required
def entries():
    datum_von, datum_bis, clauses, params = filter_params()
    where = "WHERE user_id = ?" + (" AND " + " AND ".join(clauses) if clauses else "")
    rows = get_db().execute(
        f"SELECT * FROM entries {where} ORDER BY datum DESC, id DESC",
        [session["user_id"]] + params,
    ).fetchall()
    totals = get_db().execute(
        f"SELECT COALESCE(SUM(stunden), 0) AS stunden, "
        f"COALESCE(SUM(stunden * verguetung_je_stunde), 0) AS summe, COUNT(*) AS anzahl "
        f"FROM entries {where}",
        [session["user_id"]] + params,
    ).fetchone()
    return render_template(
        "entries.html", rows=rows, totals=totals,
        datum_von=datum_von, datum_bis=datum_bis,
        art_tatigkeit=ART_TATIGKEIT, default_verguetung=DEFAULT_VERGUETUNG,
    )


@app.route("/eintraege/neu", methods=["POST"])
@login_required
def create_entry():
    wohnung = request.form.get("wohnung", "").strip()
    art = request.form.get("art", "").strip()
    taetigkeit = request.form.get("taetigkeit", "").strip()
    taetigkeit_sonstiges = request.form.get("taetigkeit_sonstiges", "").strip()
    datum = parse_date(request.form.get("datum", ""), "Datum")
    stunden_raw = request.form.get("stunden", "").replace(",", ".")
    verguetung_raw = request.form.get("verguetung_je_stunde", "").replace(",", ".") or str(DEFAULT_VERGUETUNG)
    kommentar = request.form.get("kommentar", "").strip()

    if taetigkeit == "__sonstiges__":
        taetigkeit = taetigkeit_sonstiges

    try:
        stunden = float(stunden_raw)
        verguetung = float(verguetung_raw)
    except ValueError:
        stunden = verguetung = None

    if not wohnung:
        flash("Bitte Wohnung angeben.", "error")
    elif art not in ART_TATIGKEIT:
        flash("Bitte eine gültige Art auswählen.", "error")
    elif not taetigkeit:
        flash("Bitte eine Tätigkeit auswählen oder eingeben.", "error")
    elif datum is None:
        pass
    elif stunden is None or stunden <= 0:
        flash("Bitte gültige Stunden (> 0) angeben.", "error")
    elif verguetung is None or verguetung < 0:
        flash("Bitte eine gültige Vergütung je Stunde angeben.", "error")
    else:
        db = get_db()
        db.execute(
            "INSERT INTO entries (user_id, wohnung, haushalt, art, taetigkeit, datum, stunden, "
            "verguetung_je_stunde, kommentar) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (session["user_id"], wohnung, current_user()["name"], art, taetigkeit, datum,
             stunden, verguetung, kommentar or None),
        )
        db.commit()
        flash("Eintrag gespeichert.", "ok")
    return redirect(url_for("entries", von=request.form.get("von", ""), bis=request.form.get("bis", "")))


@app.route("/eintraege/<int:entry_id>/loeschen", methods=["POST"])
@login_required
def delete_entry(entry_id):
    db = get_db()
    if session["role"] == "admin":
        db.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
    else:
        db.execute(
            "DELETE FROM entries WHERE id = ? AND user_id = ? AND datum_anerkennung IS NULL",
            (entry_id, session["user_id"]),
        )
    db.commit()
    flash("Eintrag gelöscht.", "ok")
    return redirect(request.referrer or url_for("entries"))


@app.route("/admin/eintraege")
@admin_required
def admin_entries():
    datum_von, datum_bis, clauses, params = filter_params()
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = get_db().execute(
        f"SELECT e.*, u.name AS user_name, u.email AS user_email FROM entries e "
        f"JOIN users u ON u.id = e.user_id {where} ORDER BY e.datum DESC, e.id DESC",
        params,
    ).fetchall()
    totals = get_db().execute(
        f"SELECT COALESCE(SUM(stunden), 0) AS stunden, "
        f"COALESCE(SUM(stunden * verguetung_je_stunde), 0) AS summe, COUNT(*) AS anzahl "
        f"FROM entries {where}",
        params,
    ).fetchone()
    return render_template("admin_entries.html", rows=rows, totals=totals,
                           datum_von=datum_von, datum_bis=datum_bis)


@app.route("/admin/eintraege/<int:entry_id>/anerkennung", methods=["POST"])
@admin_required
def set_anerkennung(entry_id):
    datum = parse_date(request.form.get("datum_anerkennung", ""), "Datum Anerkennung")
    if datum:
        get_db().execute(
            "UPDATE entries SET datum_anerkennung = ? WHERE id = ?", (datum, entry_id)
        )
        get_db().commit()
        flash("Datum Anerkennung gesetzt.", "ok")
    return redirect(request.referrer or url_for("admin_entries"))


@app.route("/admin/eintraege/<int:entry_id>/anerkennung_entfernen", methods=["POST"])
@admin_required
def remove_anerkennung(entry_id):
    get_db().execute("UPDATE entries SET datum_anerkennung = NULL WHERE id = ?", (entry_id,))
    get_db().commit()
    flash("Datum Anerkennung entfernt.", "ok")
    return redirect(request.referrer or url_for("admin_entries"))


@app.route("/admin/nutzer")
@admin_required
def admin_users():
    rows = get_db().execute(
        "SELECT u.*, COUNT(e.id) AS eintraege FROM users u "
        "LEFT JOIN entries e ON e.user_id = u.id "
        "GROUP BY u.id ORDER BY u.approved ASC, u.name ASC"
    ).fetchall()
    return render_template("admin_users.html", rows=rows)


@app.route("/admin/nutzer/<int:user_id>/freigeben", methods=["POST"])
@admin_required
def approve_user(user_id):
    get_db().execute("UPDATE users SET approved = 1 WHERE id = ?", (user_id,))
    get_db().commit()
    flash("Nutzer freigegeben.", "ok")
    return redirect(url_for("admin_users"))


@app.route("/admin/nutzer/<int:user_id>/sperren", methods=["POST"])
@admin_required
def block_user(user_id):
    if user_id == session["user_id"]:
        flash("Sie können sich nicht selbst sperren.", "error")
    else:
        get_db().execute("UPDATE users SET approved = 0 WHERE id = ?", (user_id,))
        get_db().commit()
        flash("Nutzer gesperrt.", "ok")
    return redirect(url_for("admin_users"))


@app.route("/admin/nutzer/<int:user_id>/rolle", methods=["POST"])
@admin_required
def toggle_role(user_id):
    if user_id == session["user_id"]:
        flash("Sie können die eigene Rolle nicht ändern.", "error")
    else:
        db = get_db()
        row = db.execute("SELECT role FROM users WHERE id = ?", (user_id,)).fetchone()
        if row:
            neue_rolle = "admin" if row["role"] != "admin" else "user"
            db.execute("UPDATE users SET role = ? WHERE id = ?", (neue_rolle, user_id))
            db.commit()
            flash(f"Rolle geändert zu {neue_rolle}.", "ok")
    return redirect(url_for("admin_users"))


@app.template_filter("euro")
def euro(value):
    try:
        return f"{float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " €"
    except (TypeError, ValueError):
        return "0,00 €"


@app.template_filter("stunden_fmt")
def stunden_fmt(value):
    try:
        s = f"{float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return s.rstrip("0").rstrip(",").replace(",", ",") + " h"
    except (TypeError, ValueError):
        return "0 h"


if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000)), debug=False)
