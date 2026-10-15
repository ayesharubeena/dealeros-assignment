# DECISIONS

Each entry: the decision, the alternative I rejected, and the one line that separated them.

## 1. Compute disagreements at import time and store them
**Decision:** `import_data` runs `compare()` and writes a `Disagreement` table; the API just reads it.
**Rejected:** computing on every request.
**Why:** the data only changes on import, and a stored result is one place to look when someone asks "why is this row flagged?".

## 2. `compare()` is a pure function with no database
**Decision:** it takes plain dataclasses and returns plain findings (`recon/compare.py`).
**Rejected:** writing the logic as ORM queries.
**Why:** the brief says to test where disagreements are decided, and a pure function can be tested with three lines of setup per case.

## 3. A split entry is not a disagreement (REC-1055)
**Decision:** if a record has several B entries and their values sum exactly to A's total, I do not flag it. REC-1055's entries (71,950.93 + 107,926.39) sum to A's 179,877.32 exactly, and the second entry is labelled "part 2 of 2". Other duplicates (REC-1042: two identical entries) are flagged as `duplicate_entry`.
**Rejected:** flagging every record with more than one entry, which is the literal reading of "entered twice".
**Why:** the numbers prove the two entries are one amount split in two, so flagging it would be a false alarm that teaches people to ignore the screen.

## 4. Money is `Decimal`, compared exactly at cent precision; commas are thousands separators only
**Decision:** `"1,25,400.00"` (Indian grouping) parses to 125400.00, and that is *still* a mismatch against A's 183,244.16. `"1,5"` and `"N/A"` are unreadable: kept as raw text, flagged `value_unreadable`.
**Rejected:** floats with a tolerance, and guessing that `"1,5"` means 1.5.
**Why:** this is money, so equal means equal to the cent, and an importer that guesses is worse than one that says "I can't read this".

## 5. Reference cleanup is deterministic, and unreadable refs become orphans
**Decision:** strip whitespace, upper-case, optional `REC` prefix and dash, then `REC-<digits>`. `rec1034`, `1112` and ` REC - 1070 ` all resolve and match their A record cleanly. A ref that can't be read at all is reported as `orphan_entry`, with the raw text in the detail.
**Rejected:** fuzzy matching (e.g. nearest id).
**Why:** a wrong match silently hides a real disagreement, while a flagged orphan is merely noisy.

## 6. Which fields are compared: total, location, date. Not `state`
**Decision:** A's `total_value` is compared to B's `value` (not `base_value`). Location and date are compared too (this finds REC-1009, where B's `recorded_on` is two days after A's `event_date`). A's `state` (REC-1019 is VOIDED) is *not* flagged because B has no state field to disagree with.
**Rejected:** flagging VOIDED-in-A as a disagreement.
**Why:** the brief defines disagreement as the systems *reporting different values*, and there is no B-side value here. This is the call I'm least sure about, and each reason is its own filter, so reversing it is a small change. Worth asking the team.

## 7. The tenant boundary is one function, and a cross-org row shows each org only its own half
**Decision:** `views.visible_to(org)` is the only way the API reads disagreements. REC-1077 sits at LOC-102 (ORG-A) in System A but LOC-201 (ORG-B) in System B, so both orgs see the row, and `serialise()` blanks the other org's side (record id, entry id, location, value) and the detail text.
**Rejected:** (a) assigning the row to just one org, which would hide a real problem from the other; (b) showing both halves to both, which is the leak the brief warns about.
**Why:** each org needs to know something is wrong, and neither needs to know anything about the other's data.

## 8. `org` is a required query parameter, there is no "all orgs" view, and an unknown owner means nobody sees it
**Decision:** a missing org is a 400 and an unknown org a 404. A finding whose locations belong to no known org is visible to no tenant, and the import command prints how many there are (0 here).
**Rejected:** an "ALL" option for convenience, and a default org.
**Why:** a default is exactly how data crosses a boundary, and the brief says to skip authentication, so an explicit parameter is the honest stand-in.

## 9. Store raw text beside every parsed value, and refuse to drop rows
**Decision:** `raw_ref`, `raw_value` and `raw_total_value` are kept; `record_id` / `entry_id` are not unique; the importer raises if rows stored != rows read; a repeated `record_id` in A becomes a `duplicate_record_in_a` finding instead of overwriting.
**Rejected:** unique constraints and "skip the bad row and log it".
**Why:** a unique constraint turns dirty data into a crash, and a skipped row is exactly the silent drop the brief forbids.

## 10. Re-importing replaces everything; plain `JsonResponse` instead of DRF
**Decision:** each import wipes and reloads inside one transaction, and the API is two small views with no REST framework.
**Rejected:** incremental upserts, and Django REST Framework.
**Why:** both are bigger than the problem (120 rows, read-only API), and less code means less to defend on the call.
