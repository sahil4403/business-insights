# Project Instructions & Long-Term Memory

## CRITICAL RULE — NO REPEATED-MESSAGE LOOP (最高重要)
- NEVER repeat phrases like "Bhai, ab main ... karta hu" multiple times without making a tool call.
- The user has repeatedly reported that the agent got stuck emitting repeated text with NO tool calls. This is the #1 most important bug. DO NOT let it happen again.
- ALWAYS pair a thought with an actual `bash`/`read`/`edit`/`write`/`todowrite` tool call in the SAME message. Never emit a paragraph of "I will now do X" without immediately doing X.
- If you catch yourself about to type a second "Bhai, ab main X karta hu" line with no tool call attached, STOP and just issue the tool call directly instead.
- Keep narration to a single short line max, then call the tool.

## Project
- Django 6.1, SQLite, `.venv` in project dir (path has a space): `/Users/sahilwaghmare/Desktop/Business Insights Production Open Code`
- Virtual env python: `.venv/bin/python -m pip install <pkg>`
- Server: port 8000. Phone test: `http://192.168.1.4:8000/labour/` (hard refresh / cache clear needed).
- LSP errors are pre-existing (django type-stub objects/values_list, openpyxl BytesIO false positives). Ignore them; `manage.py check` must pass (0 issues).
- Labour categories: Tractor, Hyva Driver, JCB Operator, Mistri.

## Rozi (daily wages) feature — Labour module
- Each labourer has a `base_daily_rate` (full-day rozi). Day-type multipliers: Full = 1.0, One & Half = 1.5, Half = 0.5.
- Model: `Labour.base_daily_rate` + `LabourRozi` (labour, date, day_type, amount computed on save).
- Form: `LabourRoziForm` (labour, date, day_type, note). View: `rozi_create`. Template: `rozi_form.html`. Route uses name `rozi_create` (pending URL wiring).
- Rozi is aggregated into `extra_amount` in `_day_aggregates_for_labour` so it shows as salary in detail + statement (confirmed with user: "Sirf Rozi add karo, statement me salary me add hoga").
