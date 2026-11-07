# FIX MY CITY – Spot it. Report it. Fix it smarter.

AI-powered urban incident management platform for the Smart City Hackathon Pforzheim 2026.

Citizens upload a photo and mark the location. A real vision AI model recognizes the incident, a transparent algorithm calculates the priority, a rule-based table suggests the department, and city staff review everything in an administration dashboard.

---

## 1. Start the app (macOS / Linux)

You need Python 3.9 or newer. Open a terminal in this folder (`fix-my-city`):

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # Windows: copy .env.example .env
```

Open `.env` in a text editor:

- `ANTHROPIC_API_KEY` – your API key for real AI image recognition. Leave empty to run in **simulated demo mode**.
- `ADMIN_EMAIL` / `ADMIN_PASSWORD` – the administrator login that is created on first start. **Change the password.**

Start the server:

```bash
uvicorn main:app --app-dir backend --reload
```

Open **http://127.0.0.1:8000** in your browser.

To show it on a phone in the same Wi-Fi: `uvicorn main:app --app-dir backend --host 0.0.0.0` and open `http://<your-laptop-IP>:8000`. Note: phones only allow device location on HTTPS or localhost, so use the map to pick the location there.

To reset all data, stop the server and delete the `data/` folder.

---

## Languages and design

The website is bilingual: use the **DE | EN** switch in the header. The choice is remembered in the browser. AI analyses are generated in the language that is active when the photo is submitted. All interface texts are in `frontend/js/i18n.js`.

The design follows Pforzheim’s identity: navy for civic trust, gold for the Goldstadt (jewelry and watches since 1767), and turquoise/sky blue for the three rivers Enz, Nagold and Würm.

---

## 2. Live demo script for the jury (about 3 minutes)

1. **Home** – show the live statistics (they come from the database; demo records are labeled).
2. **Report an Issue** – upload a photo (e.g. a pothole), add a short description, click the map, tick “I confirm the location”, click **Analyze my report**.
3. **Analysis page** – show the AI result with its “AI-generated analysis – Subject to administrative verification” label, the priority score with its factor breakdown, the provisional department and the recommended actions. Click **Confirm and submit report** and show the tracking code.
4. **Login** with the admin account → **City Dashboard** – show the statistics and charts, sort by priority, open the new report.
5. **Correct the AI**: change the priority level or category, write a reason, save. Show the entry under “Corrections of AI results” and in the **Correction log** tab.
6. Change the **status** (e.g. Assigned → In Progress).
7. **Live City Map** – show the report with its colored marker and updated status.

Test this full flow once before the pitch with 2–3 real photos.

---

## 3. Architecture

```
Browser (HTML/CSS/JS, Leaflet, Chart.js)
        │  REST/JSON, image upload (multipart)
        ▼
FastAPI backend (Python)  ──►  Anthropic Messages API (vision)   ← API key only here
        │
        ▼
SQLite database (data/fixmycity.db) + image files (data/uploads/)
```

| Folder / file | Purpose |
|---|---|
| `backend/main.py` | API routes, authentication, roles, upload validation, admin functions |
| `backend/ai_vision.py` | Real AI image recognition; clearly labeled simulated mode without a key |
| `backend/engine.py` | Priority formula, escalation rules, department mapping, duplicate detection |
| `backend/database.py` | Database schema (all tables from the brief) and reference data |
| `backend/seed.py` | 10 fictional, clearly labeled demonstration incidents |
| `frontend/` | The website: `index.html`, `css/styles.css`, `js/app.js`, local copies of Leaflet and Chart.js |

**Why not React + Supabase?** For a 48-hour hackathon this stack runs on any laptop in two minutes with no accounts or build step. The API is cleanly separated, so the frontend can later be rebuilt in React/Next.js and SQLite can be replaced by PostgreSQL/Supabase (the SQL is standard; change `database.py`).

---

## 4. How the AI image recognition works

1. The browser sends the photo, description, chosen category and coordinates to `POST /api/reports`.
2. The backend checks the file type by its content (JPG, PNG, WEBP only) and the size limit.
3. The backend sends the image to a vision-capable Claude model with a strict instruction: analyze only what is visible, return a fixed JSON structure, and say so when the image is unclear instead of forcing a category.
4. The answer is validated (allowed categories and levels only). If the AI fails, nothing is saved and the user sees an error and can retry.
5. The priority engine and the department table run on the result. The report is saved as a draft and becomes public only after the citizen confirms it.

**Confidence:** the model does not return a calibrated confidence value, so the app shows none (as required by the brief).

**Simulated mode:** without an API key the app returns predefined sample values, labeled “Simulated output – this is NOT a real AI analysis” everywhere they appear, and a banner says demo mode is active.

---

## 5. Priority engine

`Priority = 0.40 × Severity + 0.25 × Location sensitivity + 0.20 × Public exposure + 0.15 × Urgency` (each 0–100)

- Severity, urgency and public exposure are AI estimates, converted with fixed tables in `engine.py`. Public exposure is an estimate from the photo, never an invented number of people.
- Location sensitivity needs a verified dataset of sensitive locations (schools etc.) from an approved source. **None is connected yet**, so it shows “Data unavailable” and the remaining weights are rescaled to 100%. This is shown in every breakdown.
- Levels: 0–30 Low, 31–60 Medium, 61–85 High, 86–100 Critical.
- A safety-critical AI finding always raises the score to at least 86 (Critical) and requires human review. A low score can never hide a safety warning.
- If the image could not be analyzed, no score is calculated and manual review is required.

---

## 6. Open data – status

The six approved platforms are registered in the `open_data_sources` table: Statistik BW, Daten BW, MobiData BW, GovData, Zensus 2022, Pforzheim Analyseumgebung.

**No direct dataset links have been provided yet, so no dataset is integrated.** Nothing is imported from any other source, and the app shows “Data unavailable” where official data would be needed.

To add a dataset once the team has the exact link, insert a row into `dataset_metadata` (name, source platform, URL, description, retrieval date, relevant fields, usage). It then appears automatically on the “How It Works” page. The most useful datasets would be:

1. Verified locations of schools, kindergartens, hospitals or other sensitive sites → location sensitivity in the priority score (implement the proximity check in `engine.location_sensitivity`).
2. Population distribution (e.g. Zensus 2022 grid data) → a data-based public exposure value instead of the AI estimate.
3. Mobility data (MobiData BW) → higher exposure for busy routes or stops.

---

## 7. Security

- API key stored only in `.env` on the server; never sent to the browser.
- Passwords hashed with PBKDF2-SHA256 (200,000 iterations, random salt). Session tokens expire after 7 days.
- Role-based access: citizens cannot call any `/api/admin/...` endpoint (HTTP 403).
- Image validation by file content, size limit, random file names, path-traversal protection.
- The public map and tracking page expose no personal data (no names, emails or user IDs).

**Before real public use** (beyond the hackathon): serve over HTTPS, add rate limiting and email verification, strip photo metadata (EXIF/GPS), define data retention and a privacy notice (GDPR), and move to PostgreSQL.

---

## 8. Known limitations (honest list for the jury)

- Location sensitivity is unavailable until an approved dataset link is provided.
- Duplicate detection uses category, distance (75 m) and time (14 days); image similarity is not implemented. Merging is always manual.
- Corrections are stored for future evaluation; the model does **not** retrain automatically.
- Department names are provisional suggestions from the brief, editable in the dashboard, not verified official responsibilities.
- Map tiles and the AI need an internet connection.
- This is a prototype, not an official service of the City of Pforzheim, and it does not replace emergency services (112).
