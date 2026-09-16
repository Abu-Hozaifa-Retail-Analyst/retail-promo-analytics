# Promotion & Profitability Analysis — Summary

**Data analyzed:** 119,153 valid transaction lines across 500 SKUs, 20 stores,
and 5,000 customers (2024–2025).

## Headline finding

**Promotions are not paying for themselves.** Zero of the 500 SKUs analyzed
generated more profit during their promotional periods than their own
non-promotional baseline would have produced over the same number of days.
On average, gross margin drops 7.3–8.2 percentage points during promotions
(from ~27% to ~19%), and for 443 of 500 SKUs (88.6%), even *revenue* was
lower during promotional periods than during non-promotional periods for
that same product.

## Business impact

Across the full dataset: **~20.2 million SAR in lost profit** relative to
what non-promotional baseline days would have generated, against **~39
million SAR in discounts given out** — roughly every 2 SAR of discount
bought back only 1 SAR of it in extra sales. This represents **12.2% of
total realized profit** (166M SAR) — a material, not marginal, impact.

## What we found, by analysis

**Promo lift** — Whether a promotion drives more revenue depends heavily on
which product you look at. At the individual-product level, most SKUs
(88.6%) actually saw *lower* revenue during their promotional periods than
their own non-promotional baseline. (An earlier, category-level view of
this same question showed the opposite — positive lift everywhere — but we
traced that to a measurement artifact: pooling many different products
together each day made it look like promotions were working when, product
by product, most weren't. The individual-product view is the reliable one.)

**Margin erosion** — Gross margin fell by 7–8 percentage points during
promotions in every product category, consistently. This is the primary
driver of the profitability gap.

**Best/worst promotions** — We ranked every SKU by net profit impact. Not
one was profitable. Even the *least bad* promotions lost a few thousand SAR
versus baseline; the worst individual product lost approximately 259,000
SAR. The gap between "best" and "worst" is about *how much* was lost, not
whether anything was gained.

**Price elasticity** — We attempted to estimate how sensitive demand is to
price, per product. This could not be done reliably for the large majority
of products: only 2% of SKUs showed a statistically meaningful
price-demand relationship, and even those explained very little of the
variation in sales. This is a data limitation — most products only have two
effective price points in this dataset (list price and one discounted
price), which isn't enough to reliably estimate how demand responds to
price. **We recommend not using any elasticity number from this dataset for
pricing decisions.**

**Returns** — Return rates are low (0.19–0.32% of units) and do not
meaningfully affect the findings above.

## Recommended next steps

1. **Review discount depth on a sample of high-loss SKUs first.** Rather
   than changing promotional strategy company-wide, pick the 10–15 SKUs
   with the largest losses and trial a shallower discount for one cycle.
   This tells us directly whether the problem is "discounts are too deep"
   or something more fundamental about which products get promoted.
2. **Run a real price test to get a usable elasticity read.** The current
   data can't answer "how would demand respond to a price change" — that
   needs a deliberate small-scale test (a few price points, held for a few
   weeks each, on a sample of products) rather than relying on existing
   promotional patterns.
3. **Re-run this analysis once more data is available**, controlling for
   seasonality (holidays, day-of-week), since the current results don't
   yet separate "the promotion worked" from "the promotion happened to run
   during a naturally busy period."

*Full methodology, data quality handling, and reproducible code:
see the project README and `src/` — [https://github.com/Abu-Hozaifa-Retail-Analyst/retail-promo-analytics].*