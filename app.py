from flask import Flask, request, jsonify, render_template
import datetime
import os
import sqlite3

from dotenv import load_dotenv
import psycopg

load_dotenv()

app = Flask(__name__)

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "1234")
DELETE_PASSWORD = os.getenv("DELETE_PASSWORD", "ORELSOREK!")
DATABASE_URL = os.getenv("DATABASE_URL")

DB_TYPE = "postgres" if DATABASE_URL else "sqlite"
PLACEHOLDER = "%s" if DB_TYPE == "postgres" else "?"


def get_db_conn():
    if DB_TYPE == "postgres":
        return psycopg.connect(DATABASE_URL, sslmode="require")
    return sqlite3.connect("locations.db")


def init_db():
    conn = get_db_conn()
    cur = conn.cursor()

    if DB_TYPE == "postgres":
        cur.execute("""
        CREATE TABLE IF NOT EXISTS locations(
            id SERIAL PRIMARY KEY,
            username TEXT,
            lat DOUBLE PRECISION,
            lon DOUBLE PRECISION,
            time TIMESTAMPTZ
        )
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS deleted_users(
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE,
            deleted_at TIMESTAMPTZ
        )
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS bets(
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE,
            bet TEXT,
            updated_at TIMESTAMPTZ
        )
        """)
    else:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS locations(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            lat REAL,
            lon REAL,
            time TEXT
        )
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS deleted_users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            deleted_at TEXT
        )
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS bets(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            bet TEXT,
            updated_at TEXT
        )
        """)

    conn.commit()
    conn.close()


init_db()


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/admin")
def admin():
    password = request.args.get("password")

    if password != ADMIN_PASSWORD:
        return "Access denied"

    return render_template("admin.html")


@app.route("/update_location", methods=["POST"])
def update_location():

    data = request.get_json(silent=True) or {}

    username = data.get("username")
    lat = data.get("lat")
    lon = data.get("lon")

    if not username or lat is None or lon is None:
        return jsonify({"status": "error", "message": "missing fields"}), 400

    conn = get_db_conn()
    cur = conn.cursor()

    cur.execute(
        f"SELECT 1 FROM deleted_users WHERE username={PLACEHOLDER} LIMIT 1",
        (username,)
    )
    if cur.fetchone():
        conn.close()
        return jsonify({"status": "ok"})

    cur.execute(
        f"INSERT INTO locations (username,lat,lon,time) VALUES ({PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER})",
        (username, lat, lon, datetime.datetime.now(datetime.timezone.utc))
    )

    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})


@app.route("/admin_locations")
def admin_locations():

    password = request.args.get("password")

    if password != ADMIN_PASSWORD:
        return jsonify([])

    conn = get_db_conn()
    cur = conn.cursor()

    cur.execute("""
    SELECT l1.username,l1.lat,l1.lon,l1.time
    FROM locations l1
    INNER JOIN (
        SELECT username, MAX(time) AS max_time
        FROM locations
        GROUP BY username
    ) l2
    ON l1.username=l2.username AND l1.time=l2.max_time
    """)

    rows = cur.fetchall()
    conn.close()

    data = []

    for r in rows:
        data.append({
            "username": r[0],
            "lat": r[1],
            "lon": r[2],
            "time": r[3]
        })

    return jsonify(data)

@app.route("/submit_bet", methods=["POST"])
def submit_bet():

    data = request.get_json(silent=True) or {}

    username = data.get("username")
    bet = data.get("bet")

    if not username or not bet:
        return jsonify({"status": "error", "message": "missing fields"}), 400

    updated_at = datetime.datetime.now(datetime.timezone.utc)
    if DB_TYPE == "sqlite":
        updated_at = updated_at.isoformat()

    conn = get_db_conn()
    cur = conn.cursor()

    cur.execute(
        f"""
        INSERT INTO bets (username, bet, updated_at)
        VALUES ({PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER})
        ON CONFLICT (username)
        DO UPDATE SET
            bet=EXCLUDED.bet,
            updated_at=EXCLUDED.updated_at
        """,
        (username, bet, updated_at)
    )

    conn.commit()
    conn.close()

    return jsonify({"status": "ok"})

@app.route("/bets")
def get_bets():

    conn = get_db_conn()
    cur = conn.cursor()

    cur.execute("SELECT username, bet, updated_at FROM bets ORDER BY updated_at DESC")

    rows = cur.fetchall()
    conn.close()

    data = []

    for r in rows:
        bet_time = r[2]
        if hasattr(bet_time, "isoformat"):
            bet_time = bet_time.isoformat()
        data.append({
            "username": r[0],
            "bet": r[1],
            "time": bet_time
        })

    return jsonify(data)

@app.route("/delete_user", methods=["POST"])
def delete_user():

    data = request.json

    username = data.get("username")
    password = data.get("password")

    if password != DELETE_PASSWORD:
        return jsonify({"status":"error","message":"wrong password"}),403

    conn = get_db_conn()
    cur = conn.cursor()

    if not username:
        return jsonify({"status": "error", "message": "missing username"}), 400

    cur.execute(
        f"DELETE FROM locations WHERE username={PLACEHOLDER}",
        (username,)
    )

    cur.execute(
        f"DELETE FROM bets WHERE username={PLACEHOLDER}",
        (username,)
    )

    deleted_at = datetime.datetime.now(datetime.timezone.utc)
    if DB_TYPE == "sqlite":
        deleted_at = deleted_at.isoformat()

    cur.execute(
        f"""
        INSERT INTO deleted_users (username, deleted_at)
        VALUES ({PLACEHOLDER}, {PLACEHOLDER})
        ON CONFLICT (username)
        DO UPDATE SET
            deleted_at=EXCLUDED.deleted_at
        """,
        (username, deleted_at)
    )

    conn.commit()
    conn.close()

    return jsonify({"status":"ok"})

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5050"))
    app.run(host="0.0.0.0", port=port, debug=True)
