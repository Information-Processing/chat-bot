from flask import Flask, request, jsonify
import sqlite3

app = Flask(__name__)
DB_PATH = "project.db"

def run_query(sql, params=()):
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.execute(sql, params)
        con.commit()
        return cur.fetchall()

@app.route("/chat", methods=["POST"])
def add_chat():
    data = request.json
    client_msg = data.get("client input")
    system_msg = data.get("system response")

    if not client_msg or not system_msg:
        return jsonify({"error": "Payload must include 'client input' and 'system response'"}), 400

    # Insert both as separate rows so the 'memory' GET call can read them in order
    query = "INSERT INTO ChatHistory (sender, message) VALUES (?, ?)"
    run_query(query, ("User", client_msg))
    run_query(query, ("System", system_msg))

    return jsonify({"status": "Success", "message": "Interaction saved"}), 201

@app.route("/chat", methods=["GET"])
def get_chat():
    # We fetch ALL messages so you can send them to OpenAI for context/memory
    # ASC order ensures the oldest context comes first, newest last
    rows = run_query("SELECT sender, message, timestamp FROM ChatHistory ORDER BY id ASC")
    return jsonify([{"role": r[0], "content": r[1], "time": r[2]} for r in rows])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
