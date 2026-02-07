from flask import Flask, request, jsonify
import sqlite3

app = Flask(__name__)
DB_PATH = "chinook.db"

# Helper function to run queries and reduce repeated code
def run_query(sql, params=()):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(sql, params)
    rows = cur.fetchall()
    con.close()
    return rows

# The original generic query endpoint (from Section 2)
@app.post("/query")
def query_db():
    sql = request.json.get("sql", "")
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute(sql)
    rows = [dict(r) for r in cur.fetchall()]
    con.close()
    return jsonify(rows)

# Task i: Artists with limit
@app.get("/artists")
def artists():
    limit = request.args.get("limit", "5")
    rows = run_query("SELECT Name FROM Artist LIMIT ?", (limit,))
    return jsonify([row[0] for row in rows])

# Task ii: Albums by Artist
@app.get("/albums")
def albums():
    artist = request.args.get("artist", "")
    sql = """
    SELECT Album.Title 
    FROM Album JOIN Artist ON Album.ArtistId = Artist.ArtistId 
    WHERE Artist.Name = ?
    """
    rows = run_query(sql, (artist,))
    return jsonify([row[0] for row in rows])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
