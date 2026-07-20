# Diagnosing and Fixing Funnel Drop-off: A Growth Case Study
### E-commerce conversion funnel · RetailRocket clickstream data

> **Format note:** This is a product/growth case study — a PM thinking artifact,
> not a coded deliverable. It is the companion to my Product Analytics Dashboard
> project: the dashboard *surfaces* the funnel drop-off; this document *reasons
> about how to fix it*. Figures marked `[from dashboard]` are computed in that
> project — replace the representative values below with your exact numbers.

---

## TL;DR (Executive summary)

The funnel loses the vast majority of users at the **view → add-to-cart** step
and roughly two-thirds of the remainder at **add-to-cart → purchase**. But the
two drops are not equally actionable: the view→cart drop is dominated by
low-intent browsing, while the cart→purchase drop happens *after* intent is
demonstrated and is therefore the higher-leverage place to intervene.

My recommendation is to **prioritize the add-to-cart → purchase step first**
(highest intent, most fixable), with a specific bet on reducing checkout
friction, while running a lighter-weight test on the view→cart step. If the
lead experiment lifts cart→purchase conversion by a modest relative amount, the
downstream revenue impact is meaningful because it acts on already-intent-rich
traffic.

---

## 1. Context & the funnel

**Product:** an e-commerce store. **Data:** RetailRocket clickstream — real
user-event data (view / add-to-cart / transaction) over ~4.5 months, ~2.7M
events across ~1.4M visitors.

**The funnel (visitor-level):**

| Stage | Visitors | Step conversion | Cumulative |
|---|---|---|---|
| Viewed a product | `[from dashboard]` | — | 100% |
| Added to cart | `[from dashboard]` | ~X% | ~X% |
| Purchased | `[from dashboard]` | ~Y% | ~Z% |

*Representative shape from this dataset: view→cart is a very steep drop (single-digit %),
cart→purchase is a much healthier ~30–35%. Confirm exact figures from the dashboard's
funnel view before finalizing.*

**Why visitor-level, not event-level:** a funnel should count *people who
progressed*, not raw events — otherwise a single user viewing 20 items inflates
the top of the funnel and distorts the conversion rate. (This is itself a small
signal of rigor worth stating explicitly.)

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

**Segmentation to sharpen the diagnosis** (the cuts to run on the data):
- New vs returning visitors — does cart abandonment concentrate in first-time users?
- Single-item vs multi-item carts — is drop-off worse for larger carts (cost shock)?
- Time-of-day / day-of-week — capacity or context effects?

*(Note: item price band is not analyzable here — the dataset's item price
property is hashed/normalized, not real currency — so that cut is deliberately
excluded.)*

Segmentation matters because an *average* conversion rate hides the pocket where
the fix actually lives. "Cart→purchase is 32% overall but 12% for new users with
multi-item carts" is a far more actionable finding than the headline number.

---

## 3. Hypotheses (prioritized with RICE)

Candidate explanations for the add-to-cart → purchase drop, scored on
**Reach × Impact × Confidence ÷ Effort** (illustrative scores — tune to your
read of the data):

| # | Hypothesis | Reach | Impact | Conf. | Effort | RICE | Priority |
|---|---|---|---|---|---|---|---|
| H1 | Unexpected costs (shipping/fees) shown late cause abandonment | High | High | Med | Low | **High** | 1 |
| H2 | Checkout is too long / forces account creation | High | High | Med | Med | High | 2 |
| H3 | Payment step friction (limited options / failures) | Med | High | Med | Med | Med | 3 |
| H4 | No urgency or reassurance (stock, returns, trust signals) | High | Med | Low | Low | Med | 4 |
| H5 | Cart isn't persisted across sessions (users lose carts) | Med | Med | Med | Med | Med | 5 |

**Lead hypothesis: H1 — cost transparency.** Showing total cost (incl. shipping)
*early* rather than at the final step is a classic, well-evidenced driver of cart
abandonment, low-effort to test, and high-reach. That makes it the first experiment.

---

## 4. Experiment design

### Experiment 1 — Early cost transparency (tests H1)

- **Hypothesis:** Displaying all-in cost (product + shipping + fees) on the cart
  page, rather than revealing it at final checkout, reduces surprise-driven
  abandonment and lifts cart→purchase conversion.
- **Change:** Variant shows a full cost breakdown on the cart page; control keeps
  costs revealed at the final step.
- **Unit of assignment:** visitor (not session) — avoids the same user seeing both.
- **Primary metric:** cart→purchase conversion rate.
- **Guardrail metrics:** overall revenue per visitor, average order value,
  refund/return rate. *(Prevents a false win — e.g. lifting conversion while
  quietly lowering AOV or spiking returns.)*
- **Minimum Detectable Effect (MDE):** target a relative lift of, say, ~5%; state
  it explicitly because it drives the sample size.
- **Sample size / duration:** compute from baseline conversion, chosen MDE, 80%
  power, 95% confidence; run at least 1–2 full weeks to cover weekly seasonality
  and avoid day-of-week bias. Note the practical point that lower baseline
  conversion → larger sample needed.
- **Decision rule:** ship if the primary metric clears significance *and* no
  guardrail regresses beyond a pre-set threshold.

### Experiment 2 — Streamlined / guest checkout (tests H2)

- **Hypothesis:** Removing forced account creation (offering guest checkout) and
  cutting checkout steps reduces friction and lifts cart→purchase.
- **Metric / guardrails:** same primary metric; guardrail on account-creation
  rate (don't destroy account signups entirely) and repeat-purchase rate.
- Same assignment, power, and duration discipline as above.

### (Parallel, lighter) Experiment 3 — view → cart nudge (tests Drop A)

- **Hypothesis:** Clearer add-to-cart affordance / social proof on the product
  page lifts view→cart for the *addressable* segment.
- Kept deliberately smaller — Drop A is the secondary bet.

**Cross-experiment discipline:** watch for novelty effects (early bumps that
fade), don't peek-and-stop (fixed horizon or a proper sequential test), and
segment results the same way as the diagnosis so a null *average* doesn't hide a
real segment win.

---

## 5. Expected impact (quantified)

Frame the upside in revenue, not just rate points — this is what a PM is
accountable for.

Illustrative sensitivity (plug in your baseline):

| Lead experiment result | Cart→purchase | Downstream effect |
|---|---|---|
| No effect | baseline | none |
| +5% relative | baseline ×1.05 | ~5% more purchases from existing cart-adders |
| +10% relative | baseline ×1.10 | ~10% more purchases from the same intent-rich traffic |

Because this acts on **already-high-intent** users (cart-adders), a given
relative lift here converts to real revenue more reliably than the same lift at
the top of the funnel. Translate to absolute terms using the dashboard's
transaction count over the period: *"a 5% lift on ~N monthly purchasers ≈ ~M
additional orders/month."*

State the honest ceiling too: the view→cart drop caps total funnel conversion,
so cart-step wins are meaningful but bounded — the bigger long-term prize is
top-of-funnel *quality* (attracting higher-intent traffic), which is a
marketing/product-discovery problem beyond a single checkout experiment.

---

## 6. Measurement plan & guardrails

- **Primary:** cart→purchase conversion (per assigned visitor).
- **Guardrails:** revenue per visitor, AOV, return/refund rate, account-signup rate.
- **Segments monitored:** new vs returning, cart size.
- **Integrity:** pre-registered MDE and duration; no early stopping; sanity-check
  that assignment is balanced (A/A check if possible).

---

## 7. Risks, assumptions & next steps

**Assumptions:** the dataset's event definitions map cleanly to funnel stages;
add-to-cart reliably signals intent; the period is representative (no atypical
seasonal distortion).

**Risks:** low baseline conversion means experiments need real traffic/time to
reach significance; a cart-step win may be partially offset if it pulls forward
low-quality orders (hence the return-rate guardrail).

**Next steps:** (1) confirm exact funnel + segment numbers from the dashboard;
(2) run Experiment 1; (3) based on result, proceed to Experiment 2 or iterate;
(4) revisit top-of-funnel traffic quality as the larger structural lever.

---

## Appendix — how the numbers were produced

All funnel and segment figures come from my **Product Analytics Dashboard**
project (RetailRocket clickstream, pandas + Streamlit). Funnel = visitor-level
progression through view → add-to-cart → transaction; conversion rates and
segment cuts are computed there and read into this case study. *(Link the repo /
live dashboard here.)*

---

### How to present this in an interview (delete before publishing)
- Lead with the *prioritization insight* (biggest drop ≠ most fixable drop) —
  that's the part that signals judgment.
- Be ready to defend the RICE scores and the choice of primary vs guardrail metrics.
- Know your sample-size logic well enough to explain *why* low baseline
  conversion needs more traffic.
- Tie it back to the dashboard: "the tool found it, this is how I'd act on it."
