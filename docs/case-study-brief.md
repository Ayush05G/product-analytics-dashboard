# Growth Case Study — Funnel Drop-off Analysis (companion to the dashboard)

## What this is
A PM/APM-style growth case study built on the SAME RetailRocket clickstream that
powers my existing product analytics dashboard. The dashboard surfaces the funnel
drop-off; this case study diagnoses it and designs growth experiments to fix it.
The deliverable is a written document (case-study.md), NOT a new app. The only
CODE work here is small analysis scripts that compute the real numbers the
document needs.

## Context you need
- The Streamlit product-analytics dashboard already exists and works. Do not
  rebuild it. Reuse its data and, where possible, its existing metric functions
  (e.g. src/metrics.py) rather than re-deriving logic.
- Data: RetailRocket events.csv (columns: timestamp, visitorid, event
  [view | addtocart | transaction], itemid) in data/. REAL data — never
  synthetic. Timestamps are Unix epoch milliseconds.
- A draft case study document already exists (case-study.md) with placeholder
  figures marked [from dashboard]. The job is to compute the real figures and
  fill them in — not to invent numbers.

## Goal (do these in order, verifying each before moving on)
1. Compute the visitor-LEVEL funnel from events.csv (count unique visitors who
   viewed, who added to cart, who purchased). Report: view→cart %,
   cart→purchase %, overall view→purchase %, and the raw transaction count over
   the period. Visitor-level, not event-level.
2. Compute segment cuts of cart→purchase conversion, to find the actionable
   pocket (not just the average):
   - new vs returning visitors
   - single-item vs multi-item carts
   - (if item price is available) by price band
   Report each as a small table, and flag the segment with the worst conversion.
3. Print all numbers clearly to the console AND save them to a results file
   (results/funnel_numbers.md) so they can be pasted into the case study.
4. Fill case-study.md: replace every [from dashboard] marker with the real
   figures from steps 1–2. Add the absolute revenue translation in the
   "Expected impact" section using the real transaction count.
5. Sanity-review the illustrative parts of case-study.md against the real data:
   adjust the RICE hypothesis scores and the MDE so they're consistent with the
   actual baseline conversion. Do not fabricate precision — if a number can't be
   derived from the data, say so in the doc rather than inventing it.

## Key constraints
- Correctness first: sanity-check totals (row count, unique visitors, event-type
  counts, date range) before trusting any funnel number. Print these.
- Visitor-level funnel: a funnel counts PEOPLE who progressed, not raw events —
  one visitor viewing 20 items must not inflate the top of the funnel.
- Keep analysis scripts small and in src/ or scripts/, separate from any UI.
- Do NOT commit data/. Ensure .gitignore already excludes it.
- Integrity: the whole point is real numbers. Never replace a computed figure
  with a made-up one; leave a clear TODO if something can't be computed.

## What NOT to do
- Do not rebuild or restyle the existing dashboard.
- Do not add new dashboard features, models, or pages.
- Do not touch the "How to present in an interview" section except to leave it
  in place (the user deletes it manually before publishing).

## Conventions
- Type hints on functions. Small, single-purpose functions.
- Commit at logical checkpoints with clear messages.

## Workflow notes
- Read case-study.md first so you understand exactly which numbers it needs.
- If a segment or figure the document expects can't be computed from the data,
  ask me before proceeding rather than guessing.
