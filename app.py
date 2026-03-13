from flask import Flask, request, jsonify, render_template
import datetime
import os
import sqlite3

from dotenv import load_dotenv
import psycopg2

load_dotenv()

app = Flask(__name__)

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "1234")
DELETE_PASSWORD = os.getenv("DELETE_PASSWORD", "ORELSOREK!")
DATABASE_URL = os.getenv("DATABASE_URL")

DB_TYPE = "postgres" if DATABASE_URL else "sqlite"
PLACEHOLDER = "%s" if DB_TYPE == "postgres" else "?"


def get_db_conn():
    if DB_TYPE == "postgres":
        return psycopg2.connect(DATABASE_URL, sslmode="require")
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

    conn.commit()
    conn.close()

    return jsonify({"status":"ok"})

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5050"))
    app.run(host="0.0.0.0", port=port, debug=True)
