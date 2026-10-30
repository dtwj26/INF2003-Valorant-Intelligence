# INF2003 Team 30 — Connect Neon PostgreSQL to pgAdmin 4

**Project:** Valorant Competitive Intelligence System  
**Shared Neon project:** `INF2003-Valorant-Intelligence`  
**Neon organization:** `INF2003-Team30`  
**Branch:** `production`  
**PostgreSQL database:** `valorant_dev`  
**Purpose:** Connect to the **existing shared cloud database**. Do **not** recreate the database or re-import the datasets.

> **Security:** This README does not contain a database password or a full connection string. Never paste passwords, full `DATABASE_URL` values, screenshots showing passwords, or `.env` contents into GitHub, Teams, Discord, or the report.

## 1. Get project access

1. Check your email for a Neon invitation to the `INF2003-Team30` organization. Register/sign in with the **same invited email** and accept the invitation.
2. The project owner should grant you **Project → Settings → Project permissions → Editor** for `INF2003-Valorant-Intelligence` (your organization role can be **Collaborator**).
3. Visit <https://console.neon.tech>, select organization **INF2003-Team30**, and open project **INF2003-Valorant-Intelligence**.
4. Project-level Editor access allows you to manage the selected Neon project. **PostgreSQL SQL permissions depend on the database role used for your connection**; the Neon project permission is not itself a separate PostgreSQL login.

If you cannot see the project, ask the project owner to check your invitation acceptance **and** the project-level Editor grant.

## 2. Get the connection details (in Neon)

1. Open the project, select branch `production`, then click **Connect**.
2. Under **Postgres database**, select:
   - **Database:** `valorant_dev`
   - **Role:** the database role provided for you by the project owner (the original database-owner role is `valorant_dev_owner`)
   - **Connection pooling:** **OFF** (direct connection), suitable for pgAdmin.
3. Read the generated connection string. It follows this **illustrative** format:

   ```text
   postgresql://<DB_USER>:<PASSWORD>@<HOST>.neon.tech/valorant_dev?sslmode=require&channel_binding=require
   ```

4. Extract the **host**, **database username**, and **password**. Use your own project's current connection details; do not copy the example literally.
5. If you do not have a working database password, ask the owner to arrange access securely. Do **not** reset the shared owner's password yourself: that would break other people's connections until they update their `.env`/pgAdmin credentials.

**How to read the URI:**

| URI part | What to put in pgAdmin |
|---|---|
| Text after `@` and before `/valorant_dev` | **Host name/address** (hostname only, without `postgresql://` or `https://`) |
| Text after `postgresql://` and before `:` | **Username** |
| Password portion (between first `:` and `@`, decoded if necessary) | **Password** |
| `valorant_dev` | **Maintenance database** |
| `sslmode=require` | **SSL mode = Require** |
| PostgreSQL standard | **Port = 5432** |

> Some passwords can contain reserved URL characters (`@`, `:`, `%`). The console's provided connection string is URL-encoded; for pgAdmin's separate Password field, use the actual password, not its percent-encoded text. If unsure, use the **Show password** control in Neon's Connect dialog. Do not reveal it in screenshots.

## 3. Register the shared database in pgAdmin 4

You need **pgAdmin 4**, but you do **not** need to install PostgreSQL locally or create a local `valorant_dev` database.

1. Open **pgAdmin 4**.
2. In **Object Explorer**, right-click **Servers → Register → Server…** (or **Register → Server…** from the toolbar/menu).
3. In **General**:
   - **Name:** `Neon - Valorant Cloud` (a local display label; any clear name is fine)
4. In **Connection**:
   - **Host name/address:** the **direct** Neon hostname from the Connect dialog
   - **Port:** `5432`
   - **Maintenance database:** `valorant_dev`
   - **Username:** your assigned Neon PostgreSQL role
   - **Password:** corresponding database password
   - **Save password?:** optional; only on a trusted personal computer
5. In **Parameters / SSL** (the name varies slightly by pgAdmin version), set **SSL mode = Require**.
6. Click **Save**.
7. Expand **Servers → Neon - Valorant Cloud → Databases → valorant_dev → Schemas → public → Tables**.

**Do not select a hostname ending in `-pooler` for pgAdmin** when the direct connection is available.

## 4. Verify the shared database (safe, read-only queries)

Right-click the **cloud** `valorant_dev` database → **Query Tool**. Make sure the editor title says **Neon - Valorant Cloud**, not a local PostgreSQL server.

### A. Confirm you are in the right database

```sql
SELECT current_database() AS database_name,
       current_user AS connected_as;
```

Expected database name: **`valorant_dev`**. `connected_as` will show your assigned database role.

### B. Check the eight application tables

```sql
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_type = 'BASE TABLE'
ORDER BY table_name;
```

Expected: `agent_selections`, `agents`, `map_games`, `match_participants`, `match_series`, `players`, `teams`, `tournaments` (**8 rows**).

### C. Check imported match data

```sql
SELECT COUNT(*) AS total_matches FROM match_series;
```

Expected at the time of the team's 29 October 2026 validation: **12,677**. If the team has since imported or edited data, this may change.

### D. Optional: confirm foreign keys

```sql
SELECT conname AS constraint_name,
       conrelid::regclass AS table_name
FROM pg_constraint
WHERE contype = 'f'
  AND connamespace = 'public'::regnamespace
ORDER BY table_name, constraint_name;
```

Expected at baseline: **8 foreign-key constraints**.

## 5. Connecting the Streamlit app (optional)

After pulling the latest `main` branch:

1. Open the repository root (the directory containing `requirements.txt`).
2. Install dependencies using your preferred Python environment:

   ```powershell
   python -m pip install -r requirements.txt
   ```

3. Create a local file **`.env`** at repository root, with **your own securely obtained connection URI**:

   ```dotenv
   DATABASE_URL="postgresql://<DB_USER>:<PASSWORD>@<HOST>/valorant_dev?sslmode=require&channel_binding=require"
   ```

4. Confirm `.env` is Git-ignored:

   ```powershell
   git check-ignore -v .env
   ```

5. Start the app from repository root:

   ```powershell
   python -m streamlit run frontend/app.py
   ```

6. Open <http://localhost:8501>. The Homepage should show six selectable seasons (2021–2026) and live PostgreSQL statistics.

**Important:** The `.env` is for the application. pgAdmin's saved server connection is configured separately.

## 6. Working safely as a team

- **Shared data:** Your edits to Neon `production` are immediately visible to everyone. There is **no need to run the six-season import scripts** on your machine just to query the project.
- **Schema changes:** Coordinate before `ALTER TABLE`, `DROP TABLE`, bulk `UPDATE` or `DELETE`. Prefer a separate Neon development branch for experiments.
- **Version control:** Save agreed schema changes as versioned `.sql` migration files in `database/postgresql/schema/` and commit to GitHub; changing only the live database is not reproducible.
- **Backup:** The project owner retains a tested pgAdmin Custom-format backup of the initial PostgreSQL dataset. Make another backup before major destructive changes.
- **Secrets:** Never commit `.env`, credentials, tokens or backups containing sensitive information. Share credentials only using an approved secure channel. Rotate a database password if exposed.

## 7. Troubleshooting

| Problem | Check / solution |
|---|---|
| Project does not appear in Neon | Accept the organization invitation; owner must also grant project **Editor** permissions |
| `password authentication failed` | Incorrect password/role, or password was reset. Obtain current role credentials securely |
| `could not translate host name` | Paste the hostname **only**, no `postgresql://`, port, URL path or question mark |
| SSL error | Set pgAdmin **SSL mode: Require**; use a current pgAdmin version |
| No tables in pgAdmin | Expand `Databases → valorant_dev → Schemas → public → Tables`; right-click **Refresh** |
| Wrong counts or missing `match_series` | Check whether you connected to **Neon cloud** and database **`valorant_dev`**, not local `postgres` |
| Connection takes a little longer initially | Neon may have suspended idle compute; the next connection automatically wakes it |
| Permission denied for `CREATE TABLE` | Neon project Editor rights do not guarantee this particular database user's SQL privileges; ask the owner to check the **PostgreSQL role** |
| App fails while pgAdmin works | Check local `.env` (do not share it); install `psycopg2-binary` and `python-dotenv`; run from repository root |

## 8. Verification snapshot and references

Baseline on **29 October 2026**: 8 application tables, 8 foreign keys, 12,677 matches, 27,448 map games, 24,924 team-participation rows, and 267,214 agent-selection rows. Counts are a snapshot, not immutable targets after future development.

- Neon console: <https://console.neon.tech>
- Neon project permissions: <https://neon.com/blog/neon-now-has-per-project-permissions>
- Neon SSL requirement: <https://neon.com/blog/oops-proof-your-vibe-code-with-neon-because-mistakes-happen>

**Team onboarding done when:** you can see the eight cloud tables, execute the read-only queries, and run the Streamlit Homepage against Neon without exposing the connection string.
