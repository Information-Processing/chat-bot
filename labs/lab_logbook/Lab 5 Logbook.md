# Lab 5 Logbook: Building a Relational Database with SQLite

**Information Processing — Lab 5**

---
  - Lab completed in full. All sections (SQLite installation, Chinook database setup, database inspection, remote query server and client, API-based queries) completed successfully.
  - This logbook documents the procedures and outcomes as performed on an EC2 instance (eu-north-1) and locally (WSL).

---

## Lab Objectives

This lab introduced the workflow for:

- Installing a simple RDBMS (SQLite) on an EC2 instance
- Creating a relational database and populating it with data (Chinook sample database)
- Running SQL queries from the shell on the EC2 instance
- Writing Python scripts to query the database on EC2 remotely, collect responses, and process them locally (first via a generic `/query` endpoint, then via specific API endpoints)

I used the same EC2 instance and SSH setup as in Lab 4 (Ubuntu, key-based login).

---

## Section 1: SQLite as RDBMS and Chinook Setup

### 1.1 SQLite and Why It Was Used

**SQLite** is a lightweight, serverless relational database management system. Data is stored in a single file; no separate server process is required. It is fast, easy to install, and needs minimal setup, which made it suitable for this lab and for learning SQL without dealing with server configuration.

### 1.2 Installing SQLite on the EC2 Instance

I logged into the EC2 instance via SSH (as in Lab 4). I then ran:

1. **Updated the package list:** `sudo apt update`
2. **Installed SQLite:** `sudo apt install sqlite3 -y`  
3. **Verified the installation:** `sqlite3 --version`  
   The reported version was **3.45.1** (2024-01-30).

After these steps, I could run the `sqlite3` command and create or open databases on the instance.

### 1.3 Setting Up the Chinook Sample Database

The **Chinook** database is a sample relational database that models a digital music store. It is useful for practising SQL with joins, grouping, and aggregation.

**Main tables:** Artist, Album, Track, MediaType, Genre, Playlist, PlaylistTrack, Employee, Customer, Invoice, InvoiceLine.

**Steps I performed:**

1. **Downloaded the Chinook SQL script on the EC2 instance.**  
   The lab manual uses `wget -O chinook.sql` (capital **O** for “output file”). I first typed `wget -0` (digit zero) and got “invalid option”; I then used `wget -O chinook.sql` with the correct GitHub URL and the file saved successfully (e.g. ~582 KB).

2. **Confirmed the file:** `ls` showed `chinook.sql` in my home directory.

3. **Created the database file:**  
   `sqlite3 chinook.db < chinook.sql`  
   This executed the script and created `chinook.db` in the current directory.

4. **Opened the database:** `sqlite3 chinook.db`

5. **Verified the tables:** At the `sqlite>` prompt I ran `.tables` and saw:  
   Album, Artist, Customer, Employee, Genre, Invoice, InvoiceLine, MediaType, Playlist, PlaylistTrack, Track.

I could then run SQL queries on `chinook.db` for the rest of the lab.

---

## Section 1.4 Inspecting the Database (Section 1.3 Tasks)

I ran the following inside `sqlite3 chinook.db` to inspect structure, contents, and relationships.

| Task | What I ran | Outcome / note |
|------|------------|------------------|
| List tables | `.tables` | All 11 tables listed as above. |
| Customer schema | `.schema Customer` | Saw columns (CustomerId, FirstName, LastName, Company, Address, City, State, Country, PostalCode, Phone, Fax, Email, SupportRepId) and primary/foreign key definitions. |
| Preview customers | `SELECT * FROM Customer LIMIT 5;` | First five customer rows. |
| Preview artists | `SELECT * FROM Artist LIMIT 5;` | First five artists (e.g. AC/DC, Accept, Aerosmith, Alanis Morissette, Alice In Chains). |
| Albums with artist names | JOIN query | I had a typo: `SELET` instead of `SELECT`, then `Artist.Artist.ID` instead of `Artist.ArtistId`. After correcting to `SELECT Album.Title, Artist.Name FROM Album JOIN Artist ON Album.ArtistId = Artist.ArtistId LIMIT 5;` the query returned album titles with artist names (e.g. “For Those About To Rock We Salute You” | AC/DC). |
| Count tracks | `SELECT COUNT(*) FROM Track;` | **3503** tracks. |
| Invoices | `SELECT InvoiceId, CustomerId, Total FROM Invoice LIMIT 5;` | Sample invoice rows. |
| Largest invoice | `SELECT MAX(Total) FROM Invoice;` | Maximum purchase amount. |
| Tracks per album | `SELECT AlbumId, COUNT(*) AS NumTracks FROM Track GROUP BY AlbumId LIMIT 5;` | Counts per album (e.g. AlbumId 1 had 10 tracks). |
| Playlists and track counts | JOIN + GROUP BY on Playlist and PlaylistTrack | Number of tracks per playlist. |

**Key takeaway:** Inspecting the database and fixing small syntax errors (e.g. `Artist.ArtistId`) reinforced how the Chinook schema is structured and how joins and grouping work.

---

## Section 2: Remote Query Server and Client

The goal was to run a **Flask** server on the EC2 instance that accepts an SQL query (as JSON), executes it against `chinook.db`, and returns the results as JSON. A **client** on my local machine would send the query and display the response.

### 2.1 Python Virtual Environment and Flask on EC2

On the EC2 instance I:

1. **Installed the venv package:** `sudo apt install python3-venv`.
2. **Created a virtual environment:** `python3 -m venv venv`
3. **Activated it:** `source venv/bin/activate` (prompt then showed `(venv)`).
4. **Installed Flask:** I ran `pip install flask`. Flask and its dependencies installed successfully.

### 2.2 Creating and Running the Server (`db_server.py`)

I created `db_server.py` on the EC2 instance with:

- **Flask app** and **sqlite3** connection to `chinook.db` (path `DB_PATH = "chinook.db"`).
- **POST `/query`** endpoint: reads `sql` from `request.json`, connects to the database, uses `row_factory = sqlite3.Row`, executes the query, converts rows to dictionaries, and returns `jsonify(rows)`.

I ensured `chinook.db` was in the same directory as `db_server.py`, then started the server with:

```bash
python3 db_server.py
```

The server ran on **0.0.0.0:5000** (all interfaces, port 5000). I left this terminal running and made sure the EC2 security group allowed inbound traffic on port 5000 (or “allow all” as in Lab 4) so my local client could reach it.

### 2.3 Running the Client Locally

On my local machine (WSL), in the `lab5_information` folder, I had a client script `db_client.py` that:

- Set the server URL to `http://<EC2_PUBLIC_IP>:5000/query` (e.g. `13.60.40.103` or `13.60.38.68` from my sessions).
- Sent a **POST** request with `json={"sql": "SELECT Name FROM Artist LIMIT 5"}`.
- Printed the JSON response.

I ran `python3 db_client.py`. The server responded with JSON and the client printed the five artist records (e.g. AC/DC, Accept, Aerosmith, Alanis Morissette, Alice In Chains). This confirmed that the remote query server and client were working end-to-end.

---

## Section 3: API-Based Queries

The next step was to move from “client sends raw SQL” to **API-based** access: the client calls specific endpoints with simple parameters (e.g. `limit`, `artist`, `q`, `email`), and the **server** builds and runs the SQL and returns JSON. This matches a typical application design where the server owns the database logic.

### 3.1 Tasks i and ii Implemented

I implemented and tested the following on the server and client:

- **Task i — Artists with configurable limit**  
  - **Server:** `GET /artists` with query parameter `limit` (default 5).  
  - SQL: `SELECT Name FROM Artist LIMIT ?` with the limit passed as a parameter.  
  - Response: JSON list of artist names (e.g. `["AC/DC", "Accept", "Aerosmith"]`).  
- **Task ii — Albums for a given artist (exact match)**  
  - **Server:** `GET /albums` with query parameter `artist`.  
  - SQL: `SELECT Album.Title FROM Album JOIN Artist ON Album.ArtistId = Artist.ArtistId WHERE Artist.Name = ?`  
  - Response: JSON list of album titles (e.g. for `artist=AC/DC`: `["For Those About To Rock We Salute You", "Let There Be Rock"]`).

On the server I added a small **helper** `run_query(sql, params=())` to open the DB, execute the query with parameters, and return rows, and used it in both `/artists` and `/albums` so that all user input was passed as parameters (safe from SQL injection). By using `?` as a placeholder and passing values separately in `cur.execute(sql, params)`, the client could never send a malicious string that would be executed as SQL—for example, a command that could delete the database. This is a major security improvement over the Section 2 approach, where the client sent raw SQL in the POST body and the server executed it directly. The original **POST `/query`** endpoint was left in place for the earlier client.

### 3.2 Troubleshooting While Implementing the API

While testing the new endpoints from the local client I saw:

1. **404 on GET /artists**  
   The first time I called `GET /artists?limit=3`, the server returned 404. The Flask app did not yet have the `/artists` route; I had only just added the code. I saved the updated `db_server.py`, restarted the server on EC2, and tried again.

2. **SyntaxError: unterminated string literal (line 48)**  
   After editing `db_server.py` I had left a string unclosed (e.g. `app.run(host="0.0.0.0`). The server failed to start. I fixed the string in `app.run(...)`, saved, and restarted the server.

3. **JSONDecodeError on the client**  
   In an earlier run, the client called an endpoint that was not yet implemented or returned non-JSON (e.g. 404 HTML). The client called `.json()` on the response and raised `JSONDecodeError: Expecting value`. Once the server returned 200 with valid JSON, the client printed the lists of artist names and album titles correctly.

### 3.3 Verification

After fixing the server code and restarting:

- `GET /artists?limit=3` returned **200** and the client printed: `['AC/DC', 'Accept', 'Aerosmith']`.
- `GET /albums?artist=AC/DC` returned **200** and the client printed: `['For Those About To Rock We Salute You', 'Let There Be Rock']`.

The lab manual also describes further endpoints (e.g. **Task iii:** `GET /tracks/search?q=...&limit=...` for partial track name match; **Task iv:** `GET /customer/invoices?email=...` for invoices by customer email; **Task v:** `GET /reports/top-customers?limit=...` for top customers by total spending). The same pattern applies: the client sends only simple parameters; the server constructs the SQL (using parameterised queries), runs it, and returns JSON. In production, this communication should use **HTTPS (TLS)** to protect requests and responses over the network.

---

## Summary Table: Lab 5 Components

| Section | Component | What I did / outcome |
|---------|------------|----------------------|
| 1.1–1.2 | SQLite on EC2 | `sudo apt update`, `sudo apt install sqlite3 -y`, `sqlite3 --version` → 3.45.1 |
| 1.3 | Chinook DB | `wget -O chinook.sql` (fixing `-0` typo), `sqlite3 chinook.db < chinook.sql`, `.tables` to verify |
| 1.4 | Inspection | `.tables`, `.schema Customer`, sample SELECTs, JOIN (Artist/Album), COUNT, GROUP BY, etc.; fixed SELET and Artist.ArtistId typos |
| 2 | Remote server | Python venv, `pip install flask`, `db_server.py` with POST `/query`, server on 0.0.0.0:5000 |
| 2 | Remote client | `db_client.py` POST to `/query` with JSON `{"sql": "..."}`; ran locally, received artist list |
| 3 | API endpoints | GET `/artists?limit=`, GET `/albums?artist=`; parameterised SQL; fixed 404 and syntax error; verified 200 and JSON output |

---

## Key Takeaways

- **SQLite** on EC2 was installed with `apt`; the Chinook database was created from the official SQL script using `wget -O` and `sqlite3 chinook.db < chinook.sql`. Small command-line typos (`sudp`, `-0`, `SELET`, `Artist.Artist.ID`) were corrected during the session.
- **Remote access** was achieved with a Flask app exposing **POST /query** and a local client sending SQL in JSON; the server executed the query and returned rows as JSON. The Flask app was run inside a virtual environment and bound to 0.0.0.0:5000, with the security group allowing inbound traffic on port 5000.
- **API-based design** was introduced with **GET /artists** and **GET /albums**. The server builds SQL from query parameters and uses parameterised queries; the client only sends simple parameters. Implementing these routes required adding the handlers, fixing an unterminated string in `app.run()`, and restarting the server; after that, the client received correct JSON lists for artists (with limit) and albums (by artist name).
