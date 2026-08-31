# Session Handoff — Product Analytics Dashboard

Context dump for a new Claude session (new account) picking this project back
up. This is a working log, not user-facing docs — see `README.md` for that.
Read `CLAUDE.md` too; its rules govern how work here should be done.

## What this project is

RetailRocket e-commerce clickstream (2.7M real events, git-ignored `data/`)
turned into a Streamlit dashboard: conversion funnel, cohort retention, KPIs,
item analytics, and an interactive churn (return-prediction) model with a
predictor UI. Deployed live at
**p-analytics-dashboard.streamlit.app**, repo
**github.com/Ayush05G/product-analytics-dashboard** (public, branch `main`).

## Accounts / auth (important — this trips often)

- GitHub: repo is owned by **Ayush05G**. `gh auth status` shows two logged-in
  accounts (Ayush05G, AyushG-Bachatt) and the *active* one drifts back to
  AyushG-Bachatt between sessions/turns for reasons never fully pinned down.
  **Reconfirmed just now, writing this update: `AyushG-Bachatt` is still the
  active account.** **Before any push, run `gh auth switch --user Ayush05G`
  and verify with `gh api user --jq .login`** — a push while the wrong
  account is active gets a 403. (Plain `git push` over the configured remote
  has been working regardless — this mainly bites `gh` subcommands, e.g.
  `gh pr create`, `gh api` mutations. Read-only `gh api` GETs against a
  public repo are unaffected by which account is active.)
- Git identity on commits: `Ayush Gupta <ayush2425.rk@gmail.com>` (matches the
  Ayush05G account's public email so GitHub attributes commits correctly).
  Set via local `git config user.name` / `user.email` in this repo already —
  should persist, but verify if commits show the wrong author.
- Streamlit Cloud: deployed under Ayush's account, watching this repo's
  `main` branch. Pushes to `main` auto-redeploy.

## Repo history at a glance (oldest → newest)

1. **Phase 0–1**: scaffolding, `.gitignore`, `src/data_load.py` (load/clean/
   validate), `src/metrics.py` (`funnel`, `cohort_retention`, `kpis`) — pure,
   UI-free, each verified against real data via `python src/<file>.py`.
2. **Phase 2**: Streamlit `app.py` — Overview/Funnel/Retention tabs, sidebar
   date-range filter.
3. **Stretch**: `src/churn.py` — return-prediction churn model (30-day obs /
   30-day horizon, no leakage), logistic regression + gradient boosting.
4. **Deploy-readiness**: `resolve_data_path()` in `data_load.py` — falls back
   to downloading `events.csv` from an `EVENTS_URL` (env var / Streamlit
   secret) when the local file is absent, since `data/` can't be committed.
   Dataset hosted as a GitHub Release asset (see Deployment below).
5. **Public launch**: repo pushed to GitHub, README written, screenshot
   added, deployed to Streamlit Cloud, live-demo link added to README.
6. **Git history rewrite**: original commits were authored under a different
   account with a `Co-Authored-By: Claude` trailer. Rewrote all commits via
   `git filter-branch` to single-author (`Ayush Gupta`), stripped the
   trailer, force-pushed. GitHub's contributors sidebar cache lagged behind
   this for a while (was cosmetic only — `/contributors` API was already
   correct); it eventually caught up.
7. **Bigger feature push** ("make it a full product"): added
   `.github/workflows/tests.yml` CI, a pytest suite (`tests/`), and the
   **interactive churn predictor** — `score_visitors`, `predict_one`,
   `at_risk_visitors` in `src/churn.py`, wired into a "Predict" section on
   the Churn tab (visitor lookup + gauge, what-if sliders, at-risk CSV
   export). Also added: Items tab (`top_items`), daily-active trend chart
   (`daily_active`), retention decay curve, int32 downcast on
   `visitorid`/`itemid` for free-tier RAM.
8. **Growth case study** (`case-study.md`, `scripts/funnel_analysis.py`,
   `results/funnel_numbers.md`) — a PM/growth artifact diagnosing the funnel
   drop-off and designing an experiment, backed entirely by computed
   figures. Also exported `case-study.docx` (Word version).
9. **Funnel correction**: `funnel()` gained a *progression-based* step
   conversion (`step_conversion_progressed`) alongside the original
   stage-count rate, because ~9–10% of buyers/cart-adders skip the previous
   stage in the raw event log (tracking gaps), which inflates the naive
   `stage / previous stage` rate. Both figures are now surfaced; the case
   study uses the progression rate as the honest experiment baseline.
10. **Perf**: cut `funnel()` peak memory 173 MB → 66 MB.
11. **Production incident + fix** (see "Known footgun" below): a live
    `KeyError` on the deployed Funnel tab from a stale `st.cache_data` entry
    after `funnel()`'s output shape changed. Fixed by adding a
    `# cache-schema: N` comment convention to every cached wrapper in
    `app.py`, and bumping the relevant one. Also cleaned up the case study
    (removed placeholder/appendix sections).

Full commit list: run `git log --oneline` in the repo — **27 commits** as of
this update (`git rev-list --count HEAD`), all on `main`, all clean
single-author (`Ayush Gupta <ayush2425.rk@gmail.com>`), local `main` ==
`origin/main`.

## Known footgun — read before touching `app.py`'s `@st.cache_data` wrappers

`st.cache_data`'s cache key comes from the **wrapper function's own source**
(via `inspect.getsource`) plus the arguments passed — **not** from the `src/`
function it calls, and not from default argument values. So if you change a
`src/metrics.py` or `src/churn.py` function's **output shape** (new column,
rename, dtype change) without touching the `app.py` wrapper's text, Streamlit
keeps serving the old cached shape — including on the already-deployed app,
with no error until something in the UI accesses the now-missing/renamed
field. This already broke production once (`KeyError:
'step_conversion_progressed'`), and pytest passed the whole time because no
unit test exercises Streamlit's cache.

**The convention now in place**: every `@st.cache_data`-wrapped function in
`app.py` has a `# cache-schema: N` comment above its body. **Whenever you
change the shape of what a wrapped `src/` function returns, bump that
wrapper's `cache-schema` number** (see `app.py` around line 86 onward for the
existing ones). Bumping changes the wrapper's source text → changes the cache
key → drops stale entries, and this self-heals the deployed app on redeploy
with zero manual reboot needed.

**Also**: verify changes by actually running the app (`streamlit run app.py`
or the `.claude/launch.json` `dashboard` config) and clicking the affected
tab — not just `pytest` — before pushing. This is the check that would have
caught the incident above.

## Deployment specifics

- Dataset is NOT committed (`data/` git-ignored, ~90 MB raw). Hosted as a
  **GitHub Release asset**: tag `data-v1`, file `events.csv.gz` (~33 MB
  gzipped). URL:
  `https://github.com/Ayush05G/product-analytics-dashboard/releases/download/data-v1/events.csv.gz`
- `src/data_load.py:resolve_data_path()` resolution order: local
  `data/events.csv` → `EVENTS_URL` (env var, downloads + decompresses `.gz`
  automatically) → actionable `FileNotFoundError`.
- On Streamlit Cloud, `EVENTS_URL` is set via the app's **Settings → Secrets**
  (see `.streamlit/secrets.toml.example` for the local-dev equivalent).
  `app.py` bridges `st.secrets["EVENTS_URL"]` → `os.environ` before calling
  `load_events()`.
- **I (the assistant) cannot verify a live deploy myself** —
  `p-analytics-dashboard.streamlit.app` redirects to a login-gated URL for
  both curl and browser tooling. Any claim that a redeploy is "confirmed
  working" needs the human to actually check it. Don't assert it's fine
  without that; ask instead.
- Free-tier RAM (~1 GB) mitigations already applied: `visitorid`/`itemid`
  downcast to int32 in `data_load.py`; churn model cached with
  `st.cache_resource` (trains once per instance, ~30–60s on first Churn-tab
  visit, not re-pickled per access like `st.cache_data` would). If it still
  OOMs on the free tier, the next lever is lazy-loading the churn dataset
  build (don't build it until the Churn tab is opened).

## Project structure

```
app.py                    Streamlit UI only — imports from src/, no logic of its own
src/
  data_load.py            load_events(), resolve_data_path(), sanity_report()
  metrics.py              funnel(), cohort_retention(), kpis(), daily_active(),
                          top_items() — all pure pandas, no Streamlit imports
  churn.py                make_churn_dataset(), train_churn_models(),
                          score_visitors(), predict_one(), at_risk_visitors(),
                          churn_insight(), best_model_name()
tests/                    pytest, synthetic-fixture based (no dataset needed)
.github/workflows/        tests.yml — pytest on every push/PR
scripts/
  funnel_analysis.py      funnel + segment cuts backing the case study
  build_case_study_docx.js
case-study.md             growth case study (funnel diagnosis, experiment design)
case-study.docx           Word export of the above
docs/
  case-study-brief.md     the brief case-study.md was written against
  dashboard.png / churn_predictor.png   README screenshots
results/
  funnel_numbers.md       figures the case study cites, all computed
data/                     raw data — git-ignored, never commit
.streamlit/secrets.toml.example
requirements.txt / requirements-dev.txt (adds pytest)
```

**Filesystem gotcha**: `case-study.md` and `docs/case-study-brief.md` must
never be renamed to something differing only by capitalization — this repo
is developed on a case-insensitive filesystem (Windows), where e.g.
`CASE-STUDY.md` and `case-study.md` would collide into one file. **This
already happened once**: the original brief (a file named `CASE-STUDY.md`)
was silently overwritten by the case-study draft before either reached git,
because they're the same path on this filesystem. `docs/case-study-brief.md`
was reconstructed afterward from an earlier session's own context (i.e.
from having read the original, not from disk or git) — it should be
verbatim, but the user has never explicitly confirmed that. **Treat it as
lower-trust than everything else in this repo until they do.**

**`case-study.docx` has never been visually rendered.** It was built with the
`docx` npm library and its content/structure match `case-study.md` (minus the
"how to present in an interview" section, deliberately excluded — that's the
user's private prep notes, not part of the deliverable). But no
LibreOffice/pandoc were available in the environment that built it, so it's
never actually been converted to PDF/images and eyeballed. If this session's
environment has the tooling: `python scripts/office/soffice.py --headless
--convert-to pdf case-study.docx`, then `pdftoppm` and look at the pages —
especially the RICE table (8 columns, portrait orientation, check it doesn't
overflow). If not, say so rather than assuming someone already checked.

## Verifying changes (in order of cost)

```bash
python src/data_load.py     # sanity: row count, visitors, event mix, date range
python src/metrics.py       # funnel / retention / KPI / item numbers + assertions
python src/churn.py         # churn model metrics, scoring, insight + assertions
python scripts/funnel_analysis.py   # regenerates results/funnel_numbers.md
pytest                      # unit tests, synthetic fixtures, no dataset needed
streamlit run app.py        # or use .claude/launch.json's "dashboard" config —
                            # ALWAYS do this before pushing UI/cache-relevant changes
```

CI (`.github/workflows/tests.yml`) runs `pytest` on every push to `main` and
on PRs — badge in README. It does **not** run the app or catch cache-schema
issues (see footgun above), only unit-level logic.

**Local-machine quirk, found while writing this update — not a code
regression.** On this machine, right now, `pytest` fails to *collect*
`tests/test_churn.py`:
`ImportError: DLL load failed while importing _binning: An Application
Control policy has blocked this file` — a Windows security policy blocking a
native scikit-learn DLL. `src/churn.py` and `requirements.txt` haven't been
touched in a long time (predate this session's work entirely), and CI (which
runs on GitHub's Linux runners, not this machine) is green. The other 18
tests still pass fine: `pytest --ignore=tests/test_churn.py`. If a new
session/machine hits this same error, it's very likely machine-specific
(antivirus/EDR policy), not a code problem — check that before investigating
the code itself.

## Data & metric definitions (for a quick self-check, full detail in README)

- 2,755,641 events after dedup (460 exact dupes dropped), 1,407,580 unique
  visitors, view/addtocart/transaction mix 96.7% / 2.5% / 0.8%, date range
  2015-05-03 → 2015-09-18.
- Funnel: visitor "reaches" a stage on ≥1 occurrence of that event.
  `step_conversion` (stage/previous stage) vs `step_conversion_progressed`
  (visitors who reached this stage **and** the previous one, ÷ previous
  stage) — the two diverge because a meaningful fraction of visitors skip a
  stage in the raw log (no addtocart before a transaction, etc.). Use
  progression rate as the honest "what would an experiment move" baseline.
- Retention: weekly acquisition cohorts, "retained" = any event in that week;
  cohort_retention() emits a proper triangle (0.0 for observed-but-empty
  cells, NaN only for genuinely unobservable future cells — this was a real
  bug fixed earlier in the session, caught by a unit test).
- Churn: 30-day observation window → 30-day horizon, `churned=1` if no event
  in horizon. Features built from obs-window only (no leakage). ~95% base
  churn rate on this dataset; best model ROC-AUC ≈ 0.687 (gradient boosting).

## Style / workflow notes carried from CLAUDE.md + this session

- Metric/model logic must stay pure functions in `src/`, no Streamlit
  imports there; `app.py` is UI-only.
- Every dashboard section needs a plain-English, data-derived insight, not
  just a chart.
- Cache expensive aggregations with `@st.cache_data` (or `@st.cache_resource`
  for live objects like fitted sklearn models) — but respect the cache-schema
  footgun above.
- Sanity-check any new aggregate against known dataset totals before
  trusting it.
- Data quality issues (missing/duplicate/out-of-range rows) must be handled
  explicitly and logged, never silently dropped.
- Commit at logical checkpoints with clear messages; only commit/push when
  the user actually asks.
- When the user corrects a mistake or confirms a non-obvious approach,
  that's supposed to get added back to CLAUDE.md / memory — check both for
  anything that might have been missed if picking this up fresh.

## What's actually left to do (priority order)

1. **Ask the user to skim `docs/case-study-brief.md` once.** It's the only
   file in this repo that was reconstructed from memory rather than read off
   disk/git (see the filesystem-gotcha note above). Low effort, real
   uncertainty until confirmed.
2. **Render `case-study.docx` and look at it**, if this environment has
   LibreOffice/pandoc. Never done. Check the RICE table specifically.
3. **`gh auth status` still shows `AyushG-Bachatt` as active**, reconfirmed at
   the time of this update. Switch before any `gh`-mediated write action; not
   urgent for plain `git push`.
4. **`backup-before-rewrite` git tag (local only, never pushed)** holds the
   pre-history-rewrite state from item 6 above, alongside `refs/original/`
   from `filter-branch`. Safe to leave. Only delete
   (`git tag -d backup-before-rewrite`) once the user has explicitly
   confirmed the rewritten history on GitHub looks right — it's the only
   rollback path if the rewrite turns out to have missed something.
5. **Nothing is currently broken or blocking** as far as this session
   verified: CI green, live site confirmed recovered by the user via
   screenshot, contributor graph correct via GitHub's API, working tree
   clean and in sync with `origin/main`. The items above are due diligence,
   not open bugs.
6. **If the user asks for something new**: re-read CLAUDE.md's "Workflow
   notes" section first (ask before assuming on unclear requirements), and
   check whether it touches the cache-schema footgun above before shipping
   any `app.py`/`src/` change together.
