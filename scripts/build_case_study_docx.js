// Build case-study.docx — the presentable version of case-study.md.
//
// The .md stays the source of truth; this renders it as a Word document for
// sharing with people who won't read markdown on GitHub. Content is kept in
// sync by hand: if you edit case-study.md, mirror the change here and re-run.
//
// Deliberately EXCLUDES the "How to present this in an interview" section —
// those are private prep notes, not part of the deliverable.
//
// Requires the `docx` npm package (installed globally here, not a repo dep):
//   npm install -g docx
//   NODE_PATH="$(npm root -g)" node scripts/build_case_study_docx.js case-study.docx
//
// Layout note: US Letter with 1" margins => 9360 DXA of content width. Every
// table's columnWidths must sum to exactly that; the script throws if not.

const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle,
  Footer, PageNumber, LevelFormat, convertInchesToTwip,
} = require("docx");

const OUT = process.argv[2] || "case-study.docx";

// US Letter, 1" margins -> content width 9360 DXA
const CONTENT_W = 9360;

const NAVY = "1F3864";
const SLATE = "44546A";
const HDR_BG = "DEE6F1";
const ZEBRA = "F4F6FA";
const BODY = "Calibri";

// ---------- inline markdown (**bold**, *italic*, `code`) ----------
function runs(text, opts = {}) {
  const base = { font: BODY, size: opts.size || 21, color: opts.color };
  const out = [];
  const re = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g;
  let last = 0, m;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push(new TextRun({ ...base, text: text.slice(last, m.index) }));
    const tok = m[0];
    if (tok.startsWith("**")) out.push(new TextRun({ ...base, text: tok.slice(2, -2), bold: true }));
    else if (tok.startsWith("`")) out.push(new TextRun({ ...base, text: tok.slice(1, -1), font: "Consolas", size: (opts.size || 21) - 2 }));
    else out.push(new TextRun({ ...base, text: tok.slice(1, -1), italics: true }));
    last = m.index + tok.length;
  }
  if (last < text.length) out.push(new TextRun({ ...base, text: text.slice(last) }));
  return out;
}

const P = (text, opts = {}) => new Paragraph({
  children: runs(text, opts),
  spacing: { after: opts.after === undefined ? 140 : opts.after, line: 276 },
  alignment: opts.align,
  indent: opts.indent,
});

const H1 = (text) => new Paragraph({
  children: [new TextRun({ text, font: BODY, size: 30, bold: true, color: NAVY })],
  heading: HeadingLevel.HEADING_1,
  spacing: { before: 340, after: 160 },
});

const H2 = (text) => new Paragraph({
  children: [new TextRun({ text, font: BODY, size: 24, bold: true, color: SLATE })],
  heading: HeadingLevel.HEADING_2,
  spacing: { before: 240, after: 120 },
});

const BULLET = (text, level = 0) => new Paragraph({
  children: runs(text),
  numbering: { reference: "bullets", level },
  spacing: { after: 90, line: 276 },
});

const NUM = (text) => new Paragraph({
  children: runs(text),
  numbering: { reference: "nums", level: 0 },
  spacing: { after: 90, line: 276 },
});

const RULE = () => new Paragraph({
  text: "",
  spacing: { before: 60, after: 180 },
  border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "C9D2E0" } },
});

// ---------- tables ----------
function table(cols, headers, rows, opts = {}) {
  const fs_ = opts.size || 18;
  const total = cols.reduce((a, b) => a + b, 0);
  if (total !== CONTENT_W) throw new Error(`columns sum ${total} != ${CONTENT_W}`);

  const cell = (txt, i, isHead, rowIdx) => new TableCell({
    width: { size: cols[i], type: WidthType.DXA },
    shading: { type: ShadingType.CLEAR, fill: isHead ? HDR_BG : (rowIdx % 2 ? ZEBRA : "FFFFFF") },
    margins: { top: 70, bottom: 70, left: 100, right: 100 },
    children: [new Paragraph({
      children: runs(String(txt), { size: fs_ }).map(r => r),
      alignment: (opts.right || []).includes(i) ? AlignmentType.RIGHT : AlignmentType.LEFT,
      spacing: { after: 0, line: 240 },
    })],
  });

  const headRow = new TableRow({
    tableHeader: true,
    children: headers.map((h, i) => new TableCell({
      width: { size: cols[i], type: WidthType.DXA },
      shading: { type: ShadingType.CLEAR, fill: HDR_BG },
      margins: { top: 70, bottom: 70, left: 100, right: 100 },
      children: [new Paragraph({
        children: [new TextRun({ text: h, font: BODY, size: fs_, bold: true, color: NAVY })],
        alignment: (opts.right || []).includes(i) ? AlignmentType.RIGHT : AlignmentType.LEFT,
        spacing: { after: 0, line: 240 },
      })],
    })),
  });

  return new Table({
    columnWidths: cols,
    width: { size: CONTENT_W, type: WidthType.DXA },
    borders: {
      top: { style: BorderStyle.SINGLE, size: 4, color: "AAB6C8" },
      bottom: { style: BorderStyle.SINGLE, size: 4, color: "AAB6C8" },
      left: { style: BorderStyle.NONE }, right: { style: BorderStyle.NONE },
      insideHorizontal: { style: BorderStyle.SINGLE, size: 2, color: "D6DDE8" },
      insideVertical: { style: BorderStyle.NONE },
    },
    rows: [headRow, ...rows.map((r, ri) => new TableRow({
      children: r.map((c, i) => cell(c, i, false, ri)),
    }))],
  });
}

const SPACER = (n = 120) => new Paragraph({ text: "", spacing: { after: n } });

// ================= CONTENT =================
const kids = [];

// --- Title block ---
kids.push(new Paragraph({
  children: [new TextRun({ text: "Diagnosing and Fixing Funnel Drop-off", font: BODY, size: 44, bold: true, color: NAVY })],
  spacing: { after: 60 },
}));
kids.push(new Paragraph({
  children: [new TextRun({ text: "A Growth Case Study — E-commerce conversion funnel, RetailRocket clickstream", font: BODY, size: 24, color: SLATE })],
  spacing: { after: 60 },
}));
kids.push(new Paragraph({
  children: [new TextRun({ text: "Ayush Gupta", font: BODY, size: 21, bold: true, color: SLATE })],
  spacing: { after: 200 },
  border: { bottom: { style: BorderStyle.SINGLE, size: 12, color: NAVY } },
}));
kids.push(SPACER(160));

kids.push(P("Companion to my Product Analytics Dashboard: the dashboard *surfaces* the funnel drop-off, this document *diagnoses it and designs the experiments to fix it*. Every figure here is computed from the real RetailRocket clickstream — 2,755,641 events over 137 days — by a reproducible analysis script. None are illustrative.", { color: SLATE }));

kids.push(RULE());

// --- TL;DR ---
kids.push(H1("TL;DR"));
kids.push(P("The funnel loses **97.6%** of users at the **view → add-to-cart** step, and a further **72.0%** of those who do add to cart never purchase. Only **0.83%** of viewers buy. But the two drops are not equally actionable: the view→cart drop is dominated by low-intent browsing, while the cart→purchase drop happens *after* intent is demonstrated — the higher-leverage place to intervene."));
kids.push(P("My recommendation is to **prioritise the add-to-cart → purchase step first**, with a specific bet on reducing first-time-buyer checkout friction, and to treat the view→cart step as a secondary bet."));
kids.push(P("**Two findings from the data changed this plan rather than confirming it**, and both are carried through below:"));
kids.push(NUM("**Larger carts convert better, not worse** (36.9% vs 25.8% same-day). The intuitive “cost shock on big baskets” story is not what the data shows, so cost transparency is demoted from lead bet to third priority. The lead becomes **first-time-buyer checkout friction** — new visitors convert 11 points below returning ones and are 85% of all cart-adders. The actionable pocket is the **new visitor with a single-item cart** (23.9%, and 65% of all cart activity)."));
kids.push(NUM("**A 5% relative MDE is not testable here.** At ~1,894 cart-adders/week it needs ~17 weeks — not the 1–2 weeks originally assumed. The experiment is re-specified around an effect this traffic can actually resolve."));

kids.push(RULE());

// --- 1 ---
kids.push(H1("1. Context & the funnel"));
kids.push(P("**Product:** an e-commerce store. **Data:** RetailRocket clickstream — real user-event data (view / add-to-cart / transaction) from 2015-05-03 to 2015-09-18 (137 days): **2,755,641 events across 1,407,580 visitors**, of which 22,457 are transaction events comprising **17,672 distinct orders**."));
kids.push(H2("The funnel (visitor-level)"));
kids.push(table(
  [2200, 1500, 2100, 2100, 1460],
  ["Stage", "Visitors", "Step conv. (stage-count)", "Step conv. (progression)", "Cumulative"],
  [
    ["Viewed a product", "1,404,179", "—", "—", "100%"],
    ["Added to cart", "37,722", "2.69%", "**2.45%**", "2.69%"],
    ["Purchased", "11,719", "31.07%", "**28.04%**", "0.83%"],
  ],
  { right: [1, 2, 3, 4] }
));
kids.push(SPACER(140));
kids.push(P("Two rates per step, because they answer different questions. **This document uses the progression column throughout**, since that is the rate an intervention on a step can actually move."));
kids.push(P("The shape: view→cart is a brutally steep 2.45%, while cart→purchase is a comparatively healthy 28.04%. Nearly all raw loss is at the top; nearly all *recoverable intent* is at the bottom."));
kids.push(P("**Why visitor-level, not event-level:** a funnel should count *people who progressed*, not raw events — otherwise a single user viewing 20 items inflates the top of the funnel and distorts the conversion rate."));

kids.push(H2("A measurement subtlety that affects both steps"));
kids.push(P("Not everyone at a stage passed through the stage recorded before it:"));
kids.push(BULLET("**1,143 of 11,719 buyers (9.8%) have no add-to-cart event at all.**"));
kids.push(BULLET("**3,321 of 37,722 cart-adders (8.8%) have no view event at all.**"));
kids.push(P("Either a tracking gap, or a real path that skips the step (a direct link into a cart, a re-order). Dividing *all* buyers by cart-adders puts the first group in the numerator when they were never in the denominator, inflating cart→purchase to 31.07%; the same arithmetic inflates view→cart to 2.69%. The progression column instead counts only visitors who reached **both** the stage and the one before it — 10,576 buyers who also carted (28.04%), and 34,401 cart-adders who also viewed (2.45%)."));
kids.push(P("**Nothing downstream in this document changes as a result.** The experiment sizing, the segment cuts, and the revenue translation are all built on cart→purchase and the cart-adder population, which the view-step gap does not touch. The correction matters for honesty and for anyone reusing these figures, not for the recommendation."));

kids.push(RULE());

// --- 2 ---
kids.push(H1("2. Diagnosis — where is the real leak?"));
kids.push(P("Two drops stand out. The instinct is to attack the biggest number (view→cart), but the right question is **which drop represents fixable lost intent**, not which is largest."));
kids.push(P("**Drop A — view → add-to-cart (largest, but partly expected).** A product view is weak intent: browsing, comparison-shopping, accidental clicks. A large fraction of viewers were never going to buy. This drop is huge, but much of it is *normal e-commerce behaviour*, not a broken experience — the truly addressable portion is smaller than the raw number suggests."));
kids.push(P("**Drop B — add-to-cart → purchase (smaller, higher-intent, more fixable).** Adding to cart is a strong intent signal. When a user does that and *still* doesn't buy, something in the path — cost surprises, a clunky checkout, forced account creation, payment friction — plausibly got in the way. This is where a fix most directly recovers lost, *genuine* demand."));
kids.push(P("**Prioritisation call:** lead with Drop B. Best ratio of addressable intent to effort."));

kids.push(H2("Cut 1 — New vs returning (visitor grain)"));
kids.push(P("“Returning” = had activity on a calendar day strictly *before* their first add-to-cart day. Status is judged at the moment of intent on purpose: the simpler “active on 2+ days overall” definition has lookahead bias, because purchasing itself generates later activity and would mechanically inflate the returning group.", { size: 19 }));
kids.push(table(
  [3360, 2000, 2000, 2000],
  ["Segment", "Cart visitors", "Purchasers", "Cart→purchase"],
  [["New", "32,106", "8,476", "**26.40%**"], ["Returning", "5,616", "2,100", "37.39%"]],
  { right: [1, 2, 3] }
));
kids.push(SPACER(140));

kids.push(H2("Cut 2 — Single-item vs multi-item carts (visitor-day grain)"));
kids.push(P("The data has no session or cart ID, so a “cart” is approximated by the visitor-day; multi-item = ≥2 distinct items added that day. Primary conversion is same-day, with a 7-day window as a robustness check.", { size: 19 }));
kids.push(table(
  [3360, 2000, 2200, 1800],
  ["Segment", "Cart-days", "Cart→purchase (same-day)", "Within 7 days"],
  [["Single-item", "33,991", "**25.76%**", "27.28%"], ["Multi-item", "7,638", "36.93%", "40.64%"]],
  { right: [1, 2, 3] }
));
kids.push(SPACER(140));

kids.push(H2("Crossed — the actionable pocket"));
kids.push(table(
  [2360, 2200, 2400, 2400],
  ["Status", "Cart size", "Cart-days", "Cart→purchase"],
  [
    ["New", "Single-item", "27,266", "**23.86%**"],
    ["New", "Multi-item", "4,840", "29.67%"],
    ["Returning", "Single-item", "6,725", "33.44%"],
    ["Returning", "Multi-item", "2,798", "49.50%"],
  ],
  { right: [2, 3] }
));
kids.push(SPACER(160));

kids.push(P("**The data contradicted my prior, and that changes the recommendation.** I expected larger carts to convert *worse* (cost shock on a bigger basket). The opposite is true at both the marginal and crossed level: multi-item carts convert ~11 points better, and the effect holds within both new and returning visitors. Basket size here is behaving as an *intent proxy*, not a price-pain proxy — someone adding three items is more committed, not more likely to balk. This meaningfully weakens the “unexpected costs” story as the lead explanation."));
kids.push(P("So the actionable pocket is **new visitors with single-item carts: 23.86% against a 28.04% baseline, across 27,266 cart-days — 65% of all cart activity.** That is the opposite of a niche: it is the modal cart, converting worst. An *average* conversion rate hid it entirely."));
kids.push(P("*Two cuts named in the original plan were not run: item price band is not analysable — the dataset's price property is hashed/normalised, not real currency — and time-of-day / day-of-week was scoped out. Neither is claimed below.*", { size: 19, color: SLATE }));

kids.push(RULE());

// --- 3 ---
kids.push(H1("3. Hypotheses (prioritised with RICE)"));
kids.push(P("Candidate explanations for the add-to-cart → purchase drop, scored on **Reach × Impact × Confidence ÷ Effort**."));
kids.push(P("*Scoring honesty: **Reach is data-derived** — sized from the real segment populations in §2. **Impact, Confidence and Effort are judgment calls**, informed by the segment evidence but not measurable from a clickstream that contains no checkout, pricing, or payment instrumentation. They are labelled as estimates rather than dressed up as findings.*", { size: 19, color: SLATE }));
kids.push(table(
  [450, 2500, 2500, 750, 1000, 750, 700, 710],
  ["#", "Hypothesis", "Reach (from data)", "Imp.", "Conf.", "Eff.", "RICE", "Pri."],
  [
    ["H2", "Checkout friction / forced account creation deters first-time buyers", "**High** — 32,106 of 37,722 cart visitors (85%) are new", "High", "**Med-High** ↑", "Med", "**High**", "1"],
    ["H4", "No reassurance for first-timers (trust signals, returns, stock)", "**High** — same 85% new-visitor base", "Med", "Med ↑", "Low", "**High**", "2"],
    ["H1", "Unexpected costs (shipping/fees) shown late cause abandonment", "**High** — all 41,629 cart-days", "High", "**Low-Med** ↓", "Low", "Med", "3"],
    ["H5", "Cart isn't persisted across sessions", "**Low** — 5,616 returning cart visitors (15%), and they already convert best", "Med", "Low ↓", "Med", "Low", "4"],
    ["H3", "Payment step friction (limited options / failures)", "**Unsizable** — no payment events in this dataset", "High", "Low", "Med", "n/a", "Defer"],
  ],
  { size: 16 }
));
kids.push(SPACER(120));
kids.push(P("↑/↓ mark scores moved *by the segment evidence* from my pre-analysis priors.", { size: 18, color: SLATE }));

kids.push(P("**Lead hypothesis: H2 — first-time-buyer checkout friction.** The single largest signal in the data is that new visitors convert at 26.40% vs 37.39% for returning — an 11-point gap, concentrated in the 85% of cart-adders who are new. Forced account creation and a long checkout penalise exactly that group: a returning visitor has already paid the account-setup cost, a first-timer hasn't. The hypothesis predicts the gap we actually observe, which is why it leads."));
kids.push(P("**Why H1 was demoted from lead.** Cost transparency remains a well-evidenced lever in e-commerce generally, so it stays on the list — but the specific prediction it makes *here* fails. If late cost disclosure drove abandonment, larger baskets should convert worse. They convert **better** (36.93% vs 25.76%). That is evidence against cost shock being the dominant mechanism in this dataset, so its Confidence drops."));
kids.push(P("**Why H3 is deferred, not scored.** The dataset has no payment or checkout-step events, so its Reach cannot be estimated at all. Assigning it a RICE score would be inventing precision."));

kids.push(RULE());

// --- 4 ---
kids.push(H1("4. Experiment design"));
kids.push(H2("Sizing reality check (do this before choosing an MDE)"));
kids.push(P("Assignment is per visitor, so the binding constraint is **~1,894 distinct cart-adders per week**. Against the 28.04% baseline, at 95% two-sided confidence and 80% power:"));
kids.push(table(
  [2760, 2200, 2200, 2200],
  ["Relative lift (MDE)", "Visitors per arm", "Total", "Weeks at observed traffic"],
  [
    ["+5%", "16,356", "32,712", "**17.3**"],
    ["+10%", "4,147", "8,294", "4.4"],
    ["+15%", "1,868", "3,736", "2.0"],
    ["+20%", "1,064", "2,128", "1.1"],
  ],
  { right: [1, 2, 3] }
));
kids.push(SPACER(150));
kids.push(P("**This kills the original ~5% MDE.** Detecting a 5% relative lift needs ~17 weeks of continuous traffic — well over a quarter, and long enough that seasonality and site changes would contaminate the read. The plan is therefore re-specified around **+10% relative as the MDE, ~4.5 weeks**, the smallest effect this traffic volume can honestly resolve in a sane window."));
kids.push(P("The trade-off must be stated plainly: a +10% MDE means the test is **blind to a real +6% improvement** — a lift worth shipping would come back “not significant.” That is a limitation of the available traffic, not evidence of no effect, and it should be pre-registered as such so a null result isn't over-read."));

kids.push(H2("Experiment 1 — Guest checkout for first-time buyers (tests H2)"));
kids.push(BULLET("**Hypothesis:** Removing forced account creation and cutting checkout steps lifts cart→purchase most for new visitors — the 85% of cart-adders converting 11 points below returning visitors."));
kids.push(BULLET("**Change:** Variant offers guest checkout with post-purchase optional account creation; control keeps account-required checkout."));
kids.push(BULLET("**Unit of assignment:** visitor (not session) — avoids the same user seeing both."));
kids.push(BULLET("**Primary metric:** cart→purchase conversion (progression-based, per §1)."));
kids.push(BULLET("**Pre-registered segment:** new visitors, single-item carts. Powering on this pocket alone (23.86% baseline, ~1,393 cart-days/week) needs ~7.4 weeks at +10%, so the test runs on the full population with the segment as a **pre-declared secondary** — not a post-hoc slice fished for significance."));
kids.push(BULLET("**Guardrails:** revenue per visitor, AOV, refund/return rate, and account-creation rate (guest checkout must not gut the signup base)."));
kids.push(BULLET("**MDE / duration:** +10% relative, ~4.5 weeks — covering four-plus full weekly cycles to absorb day-of-week effects."));
kids.push(BULLET("**Decision rule:** ship if the primary metric clears significance *and* no guardrail regresses beyond a pre-set threshold."));

kids.push(H2("Experiment 2 — Early cost transparency (tests H1)"));
kids.push(BULLET("**Hypothesis:** Displaying all-in cost (product + shipping + fees) on the cart page rather than at final checkout reduces surprise-driven abandonment."));
kids.push(BULLET("**Why second:** the basket-size evidence in §2 argues against cost shock being the dominant mechanism here. Cheap to build and worth resolving, but now a *test of a weakened prior* rather than the lead bet."));
kids.push(BULLET("**Specific falsifier to watch:** if H1 is right, the lift should concentrate in multi-item carts. Given those already convert best, a flat result there is the expected outcome and should retire the hypothesis rather than prompt a retest."));

kids.push(H2("Experiment 3 — view → cart nudge (tests Drop A, lighter)"));
kids.push(BULLET("**Hypothesis:** Clearer add-to-cart affordance / social proof on the product page lifts view→cart for the *addressable* segment."));
kids.push(BULLET("**Power is not the constraint here.** Unlike the cart-step tests, this draws on ~1.4M viewers, so it can resolve much smaller effects in the same window."));
kids.push(P("**Running Experiment 3 alongside Experiment 1 — what it does and doesn't do.** Randomised independently, Exp 3 does *not* bias Exp 1: its exposure is balanced across Exp 1's arms in expectation, so the guest-checkout comparison stays internally valid. Two real effects remain, and both should be pre-declared:"));
kids.push(NUM("**Dilution.** A successful view→cart nudge pulls *marginal, lower-intent* users into the cart stage — exactly the population that converts worst. Exp 1's measured lift can shrink even if the checkout change is working, because the mix of who reaches checkout has shifted."));
kids.push(NUM("**Interaction.** The two changes may not be additive. Log Exp 3 assignment as a covariate and test the interaction rather than assuming independence."));
kids.push(P("Given the cart step already needs ~4.5 weeks, the cleaner sequencing is to run Exp 1 alone first and start Exp 3 after it reads out. “Parallel” is a scheduling convenience, not a free lunch."));
kids.push(P("**Cross-experiment discipline:** watch for novelty effects, don't peek-and-stop (fixed horizon or a proper sequential test), and segment results the same way as the diagnosis so a null *average* doesn't hide a real segment win."));

kids.push(RULE());

// --- 5 ---
kids.push(H1("5. Expected impact"));
kids.push(P("Frame the upside in orders, not just rate points — this is what a PM is accountable for."));
kids.push(P("**Monthly baseline, from the real data** (17,672 orders over 137 days):"));
kids.push(table(
  [6360, 3000],
  ["Quantity", "Per month"],
  [
    ["Cart-days (add-to-cart occasions)", "9,237"],
    ["Purchases from cart-adders", "2,347"],
    ["Distinct orders (all paths)", "3,921"],
  ],
  { right: [1] }
));
kids.push(SPACER(150));
kids.push(P("Sensitivity on the 28.04% baseline:"));
kids.push(table(
  [3360, 3000, 3000],
  ["Lead experiment result", "Cart→purchase", "Additional purchases/month"],
  [
    ["No effect", "28.04%", "—"],
    ["+5% relative", "29.44% (+1.40pp)", "**~130**"],
    ["+10% relative (the MDE)", "30.84% (+2.80pp)", "**~259**"],
    ["+20% relative", "33.65% (+5.61pp)", "**~518**"],
  ],
  { right: [1, 2] }
));
kids.push(SPACER(150));
kids.push(P("So the realistic win — a detectable +10% — is roughly **259 additional orders per month, ~6.6% on top of the 3,921 the store does today.** Because it acts on already-high-intent users, that lift converts to revenue more reliably than the same relative lift at the top of the funnel."));
kids.push(P("**Deliberately not quantified in currency.** The dataset has no price or order value, so revenue per order cannot be derived. Multiplying by an assumed AOV would manufacture a number the data does not support; the orders figure is where the evidence honestly stops. Anyone with real AOV can complete the arithmetic in one step."));
kids.push(P("**The honest ceiling.** Even a +20% cart-step win moves overall view→purchase from 0.83% to roughly 0.99% — the 2.45% view→cart rate caps total funnel conversion no matter how good checkout gets. Cart-step wins are real but bounded. The structurally bigger prize is top-of-funnel *quality*: 97.6% of viewers never cart, and shifting that is a traffic-and-discovery problem, not a checkout one."));

kids.push(RULE());

// --- 6 ---
kids.push(H1("6. Measurement plan & guardrails"));
kids.push(BULLET("**Primary:** cart→purchase conversion (per assigned visitor), progression-based — buyers who also carted ÷ cart-adders. Worth fixing in the metric layer, not just here: the naive variant reads 3 points higher and would flatter any experiment measured against it."));
kids.push(BULLET("**Guardrails:** revenue per visitor, AOV, return/refund rate, account-signup rate."));
kids.push(BULLET("**Segments monitored:** new vs returning, cart size — both pre-declared, with the new/single-item pocket as the named secondary."));
kids.push(BULLET("**Integrity:** MDE (+10% relative) and duration (~4.5 weeks) pre-registered; no early stopping; A/A check that assignment is balanced. A null result at this MDE means “no effect ≥10%”, **not** “no effect” — a distinction the write-up must preserve."));

kids.push(RULE());

// --- 7 ---
kids.push(H1("7. Risks, assumptions & next steps"));
kids.push(P("**Assumptions:** add-to-cart reliably signals intent; the 137-day window (May–Sep 2015) is representative and not seasonally distorted. Two assumptions are known to be imperfect and are handled explicitly rather than waved through: 9.8% of buyers have no cart event and 8.8% of cart-adders no view event, so event definitions do *not* map perfectly onto funnel stages; and “cart” is approximated by visitor-day because the data has no session or cart ID."));
kids.push(P("**Risks:**"));
kids.push(BULLET("**Underpowered by construction.** ~2,127 cart-days/week means effects below +10% relative are undetectable in a reasonable window. The main risk is misreading a null as “no effect.”"));
kids.push(BULLET("**New/returning is inferred, not observed.** There is no login or user ID — “returning” means prior on-site activity in this dataset's window, so a visitor active before 2015-05-03, or on another device, is misclassified as new. The 11-point gap is directionally solid but the level is soft."));
kids.push(BULLET("**A cart-step win may pull forward low-quality orders** — hence the return-rate guardrail."));
kids.push(BULLET("**Basket size as intent proxy is correlational.** Multi-item carts converting better does not license “make people add more items”; that would manufacture the correlate without the underlying intent."));
kids.push(P("**Next steps:** (1) run Experiment 1 (guest checkout) at the +10% MDE for ~4.5 weeks; (2) based on the result, proceed to Experiment 2 or iterate on the first-time-buyer thesis; (3) instrument checkout and payment steps — H3 cannot even be ranked until then; (4) revisit top-of-funnel traffic quality as the larger structural lever, given the 2.45% ceiling."));

kids.push(RULE());

// --- Appendix ---
kids.push(H1("Appendix — how the numbers were produced"));
kids.push(P("All figures are computed from the real RetailRocket clickstream (2,755,641 events, 2015-05-03 → 2015-09-18) by `scripts/funnel_analysis.py`, which reuses the metric layer of my Product Analytics Dashboard project (pandas + Streamlit). Full output — segment definitions, the 7-day robustness variant, sample-size table, and cross-checks — is in `results/funnel_numbers.md`."));
kids.push(BULLET("**Live dashboard:** https://p-analytics-dashboard.streamlit.app/"));
kids.push(BULLET("**Repo:** https://github.com/Ayush05G/product-analytics-dashboard"));
kids.push(P("The dashboard's Funnel tab shows the same progression rates (2.45% and 28.04%) with the tracking-gap caveat, so the tool and this document agree on screen."));
kids.push(P("**Definitions used here, stated so they can be audited:**"));
kids.push(BULLET("**Funnel** — visitor-level progression through view → add-to-cart → transaction, counting distinct people per stage, not events."));
kids.push(BULLET("**Cart→purchase** — progression-based: buyers who *also* carted ÷ cart-adders (28.04%). The naive all-buyers ÷ cart-adders ratio reads 31.07%. The same correction applies to view→cart: 2.45% progressed vs 2.69% naive."));
kids.push(BULLET("**New vs returning** — judged at first-cart time (prior-day activity), not over the whole window, to avoid lookahead bias."));
kids.push(BULLET("**Cart size** — distinct items per visitor-day; no session/cart ID exists."));
kids.push(P("The script asserts internal consistency before reporting: funnel monotonicity, segments summing to stage totals, all rates in [0,1], 7-day conversion ≥ same-day, and reconciliation of the two independent conversion-rate paths."));

// ================= DOC =================
const doc = new Document({
  creator: "Ayush Gupta",
  title: "Diagnosing and Fixing Funnel Drop-off — A Growth Case Study",
  description: "Growth case study on e-commerce funnel drop-off using the RetailRocket clickstream.",
  numbering: {
    config: [
      { reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 360, hanging: 200 } } } }] },
      { reference: "nums", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 360, hanging: 200 } } } }] },
    ],
  },
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },
        margin: { top: 1080, bottom: 1080, left: 1440, right: 1440 },
      },
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [
            new TextRun({ text: "Funnel Drop-off Case Study · Ayush Gupta · ", font: BODY, size: 16, color: "8A94A6" }),
            new TextRun({ children: [PageNumber.CURRENT], font: BODY, size: 16, color: "8A94A6" }),
          ],
        })],
      }),
    },
    children: kids,
  }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(OUT, buf);
  console.log("wrote " + OUT + " (" + buf.length + " bytes)");
});
