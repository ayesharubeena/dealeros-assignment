# System A vs System B: disagreement finder

Two systems record the same events across multiple tenants (orgs). This app imports both exports, finds where they disagree, and shows those rows in a table, without ever showing one org another org's data.

Stack: Django (SQLite) + React (Vite). No auth, per the brief.

## How to run

Needs Python 3.10+ and Node 18+.

```bash
# 1. Backend
cd backend
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r ../requirements.txt
python manage.py migrate
python manage.py import_data          # loads ../data/*.csv and computes disagreements
python manage.py runserver            # http://127.0.0.1:8000

# 2. Frontend (second terminal)
cd frontend
npm install
npm run dev                           # http://localhost:5173  (proxies /api to Django)

# 3. Tests
cd backend && python manage.py test
```

`import_data` prints what it did, e.g. `system B: read 121, stored 121`, and fails loudly if the two numbers differ. Re-running it replaces the data, so it is safe to repeat.

## What I built

- **Importer** (`recon/importer.py`, `recon/parsing.py`): every CSV row is stored, with the raw text kept next to each parsed value. Dirty refs (`rec1034`, `1112`, ` REC - 1070 `), the blank value, and `1,25,400.00` are all handled without dropping a row.
- **Comparison** (`recon/compare.py`): a pure function that produces these reasons: missing in B, orphan B entry, duplicate B entry, value differs, value blank/unreadable, location differs, date differs (plus duplicate record id in A).
- **Tenant boundary** (`recon/views.py`): `org` is required; one `visible_to()` function scopes every query; a row that spans two orgs (REC-1077) shows each org only its own half.
- **Screen**: a plain table with an org picker, a filter by reason, and a sortable value column.
- **Tests**: 31 tests. Each kind of disagreement has a test that proves it is caught, there are tests for the cases that must *not* be flagged, and there are tenant-leak tests that check the other org's locations never appear anywhere in the response. I also broke the code on purpose in four ways to confirm the tests fail.

Result on the supplied data: 11 disagreements: 2 missing in B, 1 orphan, 1 duplicate, 4 value mismatches, 1 blank value, 1 location mismatch, 1 date mismatch.

## What I deliberately did not build

- Authentication or real per-user tenancy: `?org=` stands in for it. In production the org must come from the logged-in user, never from the URL.
- Pagination, performance work, or CSV upload from the UI (120 rows; import is a command).
- Fuzzy matching of references (see DECISIONS #5).
- Flagging VOIDED-in-A (DECISIONS #6).
- Incremental or historical imports; each import replaces the last.
- Styling beyond a plain table.

See `DECISIONS.md` for the reasoning behind the main calls.

## How I worked with the agent

> **I used Claude (an AI assistant) to help build this project. First I gave it the assignment document and the dataset. It read the data and found the problems in it(blank value, messy references, a split entry, a record that crosses two orgs).Claude wrote the code and the tests. I ran the project on my computer, checked the screen with both orgs, and ran the tests.**

## Questions

**a. Name one thing the AI agent got wrong. How did you notice?**

> **While building, the AI made a mistake in a test: it used a wrong file path to the data folder, so the tests failed with a "file not found" error. It noticed this when it ran the tests, and it fixed the path. Also, in its first version of the API, one rule could show a record's data to the wrong org if a location was unknown. It found this while reviewing the output for each org and made the rule stricter.**

**b. Which part of your submission are you least confident about, and why?**

> **I am least confident about two decisions. First, I did not flag record REC-1019 (VOIDED in System A) as a disagreement, because System B has no "state" field to compare. A reviewer may think it should be flagged. Second, I flagged REC-1009 because the date in System B is two days different from System A, but this could be a normal delay between the event date and the recorded date. Both are written in DECISIONS.md,and each reason has its own filter, so they are easy to change.**

**c. If you had a second day, what would you fix first?**

> **First, I would replace the "?org=" in the URL with real login, so the org comes from the logged-in user. Right now anyone can type another org name. Second, I would ask the team about the VOIDED record and the date difference. Third, I would add a page-by-page list (pagination) and a CSV upload from the screen, so it works with larger data.**
