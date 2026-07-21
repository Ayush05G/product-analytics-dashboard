# Diagnosing and Fixing Funnel Drop-off: A Growth Case Study
### E-commerce conversion funnel · RetailRocket clickstream data

> **Format note:** This is a product/growth case study — a PM thinking artifact,
> not a coded deliverable. It is the companion to my Product Analytics Dashboard
> project: the dashboard *surfaces* the funnel drop-off; this document *reasons
> about how to fix it*. Every figure below is computed from the real RetailRocket
> clickstream by `scripts/funnel_analysis.py`; the full output, including segment
> definitions and cross-checks, is in `results/funnel_numbers.md`.

---

## TL;DR (Executive summary)

The funnel loses **97.6%** of users at the **view → add-to-cart** step, and a
further **72.0%** of those who do add to cart never purchase. Only **0.83%** of
viewers buy. But the two drops are not equally actionable: the view→cart drop is
dominated by low-intent browsing, while the cart→purchase drop happens *after*
intent is demonstrated and is therefore the higher-leverage place to intervene.

My recommendation is to **prioritize the add-to-cart → purchase step first**
(highest intent, most fixable), with a specific bet on reducing checkout
friction, while running a lighter-weight test on the view→cart step. If the
lead experiment lifts cart→purchase conversion by a modest relative amount, the
downstream revenue impact is meaningful because it acts on already-intent-rich
traffic.

**Two findings from the data changed this plan rather than confirming it**, and
both are carried through below:
1. **Larger carts convert *better*, not worse** (36.9% vs 25.8% same-day). The
   intuitive "cost shock on big baskets" story is not what the data shows, so
   cost transparency is demoted from lead bet to third priority, and the lead
   becomes **first-time-buyer checkout friction** — new visitors convert 11
   points below returning ones and are 85% of all cart-adders. The actionable
   pocket is the **new visitor with a single-item cart** (23.9%, and 65% of all
   cart activity).
2. **A 5% relative MDE is not testable here.** At the observed ~1,894
   cart-adders/week it needs ~17 weeks per the sizing table in §4 — not the
   1–2 weeks originally assumed. The experiment is re-specified around a
   detectable effect instead.

---

## 1. Context & the funnel

**Product:** an e-commerce store. **Data:** RetailRocket clickstream — real
user-event data (view / add-to-cart / transaction) from 2015-05-03 to
2015-09-18 (137 days, ~4.5 months): **2,755,641 events across 1,407,580
visitors**, of which 22,457 are transaction events comprising **17,672 distinct
orders**.

**The funnel (visitor-level):**

| Stage | Visitors | Step conv. (stage-count) | Step conv. (progression) | Cumulative |
|---|---:|---:|---:|---:|
| Viewed a product | 1,404,179 | — | — | 100% |
| Added to cart | 37,722 | 2.69% | **2.45%** | 2.69% |
| Purchased | 11,719 | 31.07% | **28.04%** | 0.83% |

Two rates per step, because they answer different questions — see the
measurement note below. **This document uses the progression column
throughout**, since that is the rate an intervention on a step can actually
move.

The shape: view→cart is a brutally steep 2.45%, while cart→purchase is a
comparatively healthy 28.04%. Nearly all raw loss is at the top; nearly all
*recoverable intent* is at the bottom.

**Why visitor-level, not event-level:** a funnel should count *people who
progressed*, not raw events — otherwise a single user viewing 20 items inflates
the top of the funnel and distorts the conversion rate. (This is itself a small
signal of rigor worth stating explicitly.)

**One measurement subtlety worth being explicit about — it affects both steps.**
Not everyone at a stage passed through the stage recorded before it:

- **1,143 of 11,719 buyers (9.8%) have no add-to-cart event at all.**
- **3,321 of 37,722 cart-adders (8.8%) have no view event at all.**

Either a tracking gap, or a real path that skips the step (a direct link into a
cart, a re-order). Dividing *all* buyers by cart-adders puts the first group in
the numerator when they were never in the denominator, inflating cart→purchase
to 31.07%; the same arithmetic inflates view→cart to 2.69%. The progression
column instead counts only visitors who reached **both** the stage and the one
before it — 10,576 buyers who also carted (28.04%), and 34,401 cart-adders who
also viewed (2.45%).

Worth stating plainly: an earlier draft of this document reported the gap as
"3,401 visitors (0.24%) have no view event." That is true of the visitor base
but misleading about the funnel — measured against the population the step
actually operates on, cart-adders, it is 8.8%, not 0.24%.

**Nothing downstream in this document changes as a result.** The experiment
sizing, the segment cuts, and the revenue translation are all built on
cart→purchase and the cart-adder population, which the view-step gap does not
touch. The correction matters for honesty and for anyone reusing these figures,
not for the recommendation.

---

## 2. Diagnosis — where is the *real* leak?

Two drops stand out. The instinct is to attack the biggest number (view→cart),
but the right question is **which drop represents fixable lost intent**, not
which is largest.

**Drop A — view → add-to-cart (largest, but partly expected).**
A product view is weak intent: browsing, comparison-shopping, accidental
clicks, or re-visits all count. A large fraction of viewers were never going to
buy on this session. So while this drop is huge, a big chunk of it is *normal
e-commerce behavior*, not a broken experience. Improving it is possible but the
"true addressable" portion is smaller than the raw number suggests.

**Drop B — add-to-cart → purchase (smaller, higher-intent, more fixable).**
Adding to cart is a strong intent signal. When a user does that and *still*
doesn't buy, something in the path — cost surprises (shipping/fees), a clunky
checkout, forced account creation, payment friction, or simple hesitation —
plausibly got in the way. This is where a fix most directly recovers lost,
*genuine* demand.

**Prioritization call:** lead with Drop B. It has the best ratio of
addressable-intent to effort. Drop A is worth a lighter parallel test but is a
secondary bet.

**Segmentation to sharpen the diagnosis** — two cuts were run on the data.

**Cut 1 — new vs returning** (visitor grain). "Returning" = had activity on a
calendar day strictly *before* their first add-to-cart day. Status is judged at
the moment of intent on purpose: the simpler "active on 2+ days overall"
definition has lookahead bias, because purchasing itself generates later
activity and would mechanically inflate the returning group.

| Segment | Cart visitors | Purchasers | Cart→purchase |
|---|---:|---:|---:|
| New | 32,106 | 8,476 | **26.40%** |
| Returning | 5,616 | 2,100 | 37.39% |

**Cut 2 — single-item vs multi-item carts** (visitor-day grain). The data has no
session or cart ID, so a "cart" is approximated by the visitor-day; multi-item =
≥2 distinct items added that day. Primary conversion is same-day, with a 7-day
window as a robustness check.

| Segment | Cart-days | Cart→purchase (same-day) | (within 7 days) |
|---|---:|---:|---:|
| Single-item | 33,991 | **25.76%** | 27.28% |
| Multi-item | 7,638 | 36.93% | 40.64% |

**Crossed — the actionable pocket:**

| Status | Cart size | Cart-days | Cart→purchase |
|---|---|---:|---:|
| New | Single-item | 27,266 | **23.86%** |
| New | Multi-item | 4,840 | 29.67% |
| Returning | Single-item | 6,725 | 33.44% |
| Returning | Multi-item | 2,798 | 49.50% |

**The data contradicted my prior, and that changes the recommendation.** I
expected larger carts to convert *worse* (cost shock on a bigger basket). The
opposite is true at both the marginal and crossed level: multi-item carts
convert ~11 points better, and the effect holds within both new and returning
visitors. Basket size here is behaving as an *intent proxy*, not a price-pain
proxy — someone adding three items is more committed, not more likely to balk.
This meaningfully weakens the "unexpected costs" story as the lead explanation
(see §3).

So the actionable pocket is **new visitors with single-item carts: 23.86%
against a 28.04% baseline, across 27,266 cart-days — 65% of all cart activity.**
That is the opposite of a niche: it is the modal cart, converting worst. An
*average* conversion rate hid it entirely.

*(Two cuts named in the original plan were not run: item price band is not
analyzable — the dataset's price property is hashed/normalized, not real
currency — and time-of-day / day-of-week was scoped out. Neither is claimed
below.)*

---

## 3. Hypotheses (prioritized with RICE)

Candidate explanations for the add-to-cart → purchase drop, scored on
**Reach × Impact × Confidence ÷ Effort**.

*Scoring honesty: **Reach is data-derived** — sized from the real segment
populations in §2. **Impact, Confidence and Effort are judgment calls**, informed
by the segment evidence but not measurable from a clickstream that contains no
checkout, pricing, or payment instrumentation. They are labelled as estimates
rather than dressed up as findings.*

| # | Hypothesis | Reach (from data) | Impact | Conf. | Effort | RICE | Priority |
|---|---|---|---|---|---|---|---|
| H2 | Checkout friction / forced account creation deters first-time buyers | **High** — 32,106 of 37,722 cart visitors (85%) are new | High | **Med-High** ↑ | Med | **High** | 1 |
| H4 | No reassurance for first-timers (trust signals, returns policy, stock) | **High** — same 85% new-visitor base | Med | Med ↑ | Low | **High** | 2 |
| H1 | Unexpected costs (shipping/fees) shown late cause abandonment | **High** — all 41,629 cart-days | High | **Low-Med** ↓ | Low | Med | 3 |
| H5 | Cart isn't persisted across sessions (users lose carts) | **Low** — 5,616 returning cart visitors (15%), and they already convert best | Med | Low ↓ | Med | Low | 4 |
| H3 | Payment step friction (limited options / failures) | **Unsizable** — no payment events in this dataset | High | Low | Med | n/a | Defer |

↑/↓ mark scores moved *by the segment evidence* from my pre-analysis priors.

**Lead hypothesis: H2 — first-time-buyer checkout friction.** The single largest
signal in the data is that new visitors convert at 26.40% vs 37.39% for
returning — an 11-point gap, concentrated in the 85% of cart-adders who are new.
Forced account creation and a long checkout penalise exactly that group: a
returning visitor has already paid the account-setup cost, a first-timer hasn't.
The hypothesis predicts the gap we actually observe, which is why it leads.

**Why H1 was demoted from lead.** Cost transparency remains a well-evidenced
lever in e-commerce generally, so it stays on the list — but the specific
prediction it makes *here* fails. If late cost disclosure drove abandonment,
larger baskets (higher absolute shipping/fee shock) should convert worse. They
convert **better** (36.93% vs 25.76%). That is evidence against cost shock being
the dominant mechanism in this dataset, so its Confidence drops. It is cheap to
test and worth running second, but leading with it would mean ignoring the
clearest signal available.

**Why H3 is deferred, not scored.** The dataset has no payment or checkout-step
events, so its Reach cannot be estimated at all. Assigning it a RICE score would
be inventing precision. It needs instrumentation before it can be ranked.

---

## 4. Experiment design

### Sizing reality check (do this *before* choosing an MDE)

Assignment is per visitor, so the binding constraint is **~1,894 distinct
cart-adders per week**. Against the 28.04% baseline, at 95% two-sided confidence
and 80% power:

| Relative lift (MDE) | Visitors per arm | Total | Weeks at observed traffic |
|---|---:|---:|---:|
| +5% | 16,356 | 32,712 | **17.3** |
| +10% | 4,147 | 8,294 | 4.4 |
| +15% | 1,868 | 3,736 | 2.0 |
| +20% | 1,064 | 2,128 | 1.1 |

**This kills the original ~5% MDE.** Detecting a 5% relative lift needs ~17
weeks of continuous traffic — well over a quarter, and long enough that
seasonality and site changes would contaminate the read. The plan is therefore
re-specified around **+10% relative as the MDE, ~4.5 weeks**, which is the
smallest effect this traffic volume can honestly resolve in a sane window.

The trade-off must be stated plainly: a +10% MDE means the test is **blind to a
real +6% improvement** — a lift worth shipping would come back "not
significant." That is a limitation of the available traffic, not evidence of no
effect, and it should be pre-registered as such so a null result isn't
over-read.

### Experiment 1 — Guest checkout for first-time buyers (tests H2)

- **Hypothesis:** Removing forced account creation and cutting checkout steps
  lifts cart→purchase most for new visitors — the 85% of cart-adders currently
  converting 11 points below returning visitors.
- **Change:** Variant offers guest checkout with post-purchase optional account
  creation; control keeps account-required checkout.
- **Unit of assignment:** visitor (not session) — avoids the same user seeing both.
- **Primary metric:** cart→purchase conversion (progression-based, per §1).
- **Pre-registered segment:** new visitors, single-item carts. Powering the test
  on this pocket alone (23.86% baseline, ~1,393 cart-days/week) needs ~7.4 weeks
  at +10%, so the test runs on the full population with the segment as a
  **pre-declared secondary** — not a post-hoc slice fished for significance.
- **Guardrails:** revenue per visitor, AOV, refund/return rate, and
  account-creation rate (guest checkout must not gut the signup base).
- **MDE / duration:** +10% relative, ~4.5 weeks — from the table above, covering
  four-plus full weekly cycles to absorb day-of-week effects.
- **Decision rule:** ship if the primary metric clears significance *and* no
  guardrail regresses beyond a pre-set threshold.

### Experiment 2 — Early cost transparency (tests H1)

- **Hypothesis:** Displaying all-in cost (product + shipping + fees) on the cart
  page rather than at final checkout reduces surprise-driven abandonment.
- **Why second:** the basket-size evidence in §2 argues against cost shock being
  the dominant mechanism here. It is cheap to build and worth resolving, but it
  is now a *test of a weakened prior* rather than the lead bet.
- **Specific falsifier to watch:** if H1 is right, the lift should concentrate in
  multi-item carts. Given those already convert best, a flat result there is the
  expected outcome and should retire the hypothesis rather than prompt a retest.
- Same assignment, metrics, guardrails, and sizing discipline as above.

### (Parallel, lighter) Experiment 3 — view → cart nudge (tests Drop A)

- **Hypothesis:** Clearer add-to-cart affordance / social proof on the product
  page lifts view→cart for the *addressable* segment.
- Kept deliberately smaller — Drop A is the secondary bet.
- **Power is not the constraint here.** Unlike the cart-step tests, this one
  draws on ~1.4M viewers, so it can resolve much smaller effects in the same
  window. The 2.45% baseline is low, which raises the required sample, but
  traffic at this stage is abundant enough to absorb it.

**Running Experiment 3 alongside Experiment 1 — what it does and doesn't do.**
Randomised independently, Exp 3 does *not* bias Exp 1: its exposure is balanced
across Exp 1's arms in expectation, so the guest-checkout comparison stays
internally valid. Two real effects remain, and both should be pre-declared:
1. **Dilution.** A successful view→cart nudge pulls *marginal, lower-intent*
   users into the cart stage — exactly the population that converts worst
   (§2). Exp 1's measured lift can shrink even if the checkout change is
   working, because the mix of who reaches checkout has shifted.
2. **Interaction.** The two changes may not be additive. Log Exp 3 assignment
   as a covariate and test the interaction rather than assuming independence.

Given the cart step already needs ~4.5 weeks at the minimum detectable effect,
the cleaner sequencing is to run Exp 1 alone first and start Exp 3 after it
reads out. "Parallel" is a scheduling convenience, not a free lunch.

**Cross-experiment discipline:** watch for novelty effects (early bumps that
fade), don't peek-and-stop (fixed horizon or a proper sequential test), and
segment results the same way as the diagnosis so a null *average* doesn't hide a
real segment win.

---

## 5. Expected impact (quantified)

Frame the upside in revenue, not just rate points — this is what a PM is
accountable for.

**Monthly baseline, from the real data** (17,672 orders over 137 days):

| Quantity | Per month |
|---|---:|
| Cart-days (add-to-cart occasions) | 9,237 |
| Purchases from cart-adders | 2,347 |
| Distinct orders (all paths) | 3,921 |

Sensitivity on the 28.04% baseline:

| Lead experiment result | Cart→purchase | Additional purchases/month |
|---|---:|---:|
| No effect | 28.04% | — |
| +5% relative | 29.44% (+1.40pp) | **~130** |
| +10% relative (the MDE) | 30.84% (+2.80pp) | **~259** |
| +20% relative | 33.65% (+5.61pp) | **~518** |

So the realistic win — a detectable +10% — is roughly **259 additional orders
per month, ~6.6% on top of the 3,921 the store does today.** Because it acts on
already-high-intent users, that lift converts to revenue more reliably than the
same relative lift at the top of the funnel.

**Deliberately not quantified in currency.** The dataset has no price or order
value, so revenue per order cannot be derived. Multiplying by an assumed AOV
would manufacture a number the data does not support; the orders figure is where
the evidence honestly stops. Anyone with real AOV can complete the arithmetic in
one step.

**The honest ceiling.** Even a +20% cart-step win moves overall view→purchase
from 0.83% to roughly 0.99% — the 2.45% view→cart rate caps total funnel
conversion no matter how good checkout gets. Cart-step wins are real but
bounded. The structurally bigger prize is top-of-funnel *quality*: 97.6% of
viewers never cart, and shifting that is a traffic-and-discovery problem, not a
checkout one.

---

## 6. Measurement plan & guardrails

- **Primary:** cart→purchase conversion (per assigned visitor), progression-based
  — buyers who also carted ÷ cart-adders, per the §1 definition. Worth fixing in
  the metric layer, not just here: the naive variant reads 3 points higher and
  would flatter any experiment measured against it.
- **Guardrails:** revenue per visitor, AOV, return/refund rate, account-signup rate.
- **Segments monitored:** new vs returning, cart size — both pre-declared, with
  the new/single-item pocket as the named secondary.
- **Integrity:** MDE (+10% relative) and duration (~4.5 weeks) pre-registered from
  the sizing table in §4; no early stopping; A/A check that assignment is
  balanced. A null result at this MDE means "no effect ≥10%", **not** "no
  effect" — a distinction the write-up must preserve.

---

## 7. Risks, assumptions & next steps

**Assumptions:** add-to-cart reliably signals intent; the 137-day window
(May–Sep 2015) is representative and not seasonally distorted. Two assumptions
are known to be imperfect and are handled explicitly rather than waved through:
9.8% of buyers have no cart event and 8.8% of cart-adders no view event, so event
definitions do *not* map perfectly onto funnel stages (§1); and "cart" is
approximated by visitor-day because the data has no session or cart ID, which
will merge genuinely separate same-day visits into one cart.

**Risks:**
- **Underpowered by construction.** ~2,127 cart-days/week means effects below
  +10% relative are undetectable in a reasonable window. The main risk is
  misreading a null as "no effect."
- **New/returning is inferred, not observed.** There is no login or user ID —
  "returning" means prior on-site activity in this dataset's window, so a
  visitor active before 2015-05-03, or on another device, is misclassified as
  new. The 11-point gap is directionally solid but the level is soft.
- **A cart-step win may pull forward low-quality orders** — hence the
  return-rate guardrail.
- **Basket size as intent proxy is correlational.** Multi-item carts converting
  better does not license "make people add more items"; that would likely
  manufacture the correlate without the underlying intent.

**Next steps:** (1) run Experiment 1 (guest checkout) at the +10% MDE for ~4
weeks; (2) based on the result, proceed to Experiment 2 or iterate on the
first-time-buyer thesis; (3) instrument checkout and payment steps — H3 cannot
even be ranked until then, and the current data cannot distinguish *where* in
checkout new visitors drop; (4) revisit top-of-funnel traffic quality as the
larger structural lever, given the 2.45% ceiling.

---

## Appendix — how the numbers were produced

All figures are computed from the real RetailRocket clickstream (2,755,641
events, 2015-05-03 → 2015-09-18) by **`scripts/funnel_analysis.py`**, which
reuses the metric layer of my **Product Analytics Dashboard** project (pandas +
Streamlit). Full output — including segment definitions, the 7-day robustness
variant, sample-size table, and cross-checks — is in
**`results/funnel_numbers.md`**. Reproduce with `python scripts/funnel_analysis.py`.

- **Live dashboard:** https://p-analytics-dashboard.streamlit.app/
- **Repo:** https://github.com/Ayush05G/product-analytics-dashboard

The dashboard's Funnel tab shows the same progression rates (2.45% and 28.04%)
with the tracking-gap caveat, so the tool and this document agree on screen.

Definitions used here, stated so they can be audited:
- **Funnel** — visitor-level progression through view → add-to-cart →
  transaction, counting distinct people per stage, not events.
- **Cart→purchase** — progression-based: buyers who *also* carted ÷ cart-adders
  (28.04%). The naive all-buyers ÷ cart-adders ratio reads 31.07%. The same
  correction applies to view→cart: 2.45% progressed vs 2.69% naive.
- **New vs returning** — judged at first-cart time (prior-day activity), not
  over the whole window, to avoid lookahead bias.
- **Cart size** — distinct items per visitor-day; no session/cart ID exists.

The script asserts internal consistency before reporting: funnel monotonicity,
segments summing to stage totals, all rates in [0,1], 7-day conversion ≥
same-day, and reconciliation of the two independent conversion-rate paths.

---

### How to present this in an interview (delete before publishing)
- Lead with the *prioritization insight* (biggest drop ≠ most fixable drop) —
  that's the part that signals judgment.
- Be ready to defend the RICE scores and the choice of primary vs guardrail metrics.
- Know your sample-size logic well enough to explain *why* low baseline
  conversion needs more traffic.
- Tie it back to the dashboard: "the tool found it, this is how I'd act on it."
