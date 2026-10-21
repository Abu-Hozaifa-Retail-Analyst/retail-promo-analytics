# Store test: does a 10% discount cap hurt traffic?

## Why a test

The analysis shows that customers buy the same quantity per sale at every discount level, so the
discounts look like margin given away. What the data cannot show is whether discounts bring in extra
**customers** (more sales, not bigger sales). Only a live comparison can answer that. A 10% cap would add
about 5.9M SAR (+3.5%) to profit if customers do not react, so the question is how many transactions the
cap could lose before it stops paying.

**Break-even.** Losing 3.5% of transactions, at average profit per transaction, cancels the 3.5% gain.
That is the line the test must stay above.

## Design

| Item | Choice | Reason |
|---|---|---|
| Unit | Store | The cap is a store-level price rule; customers see one policy per store |
| Stores | All 20: 10 with the cap, 10 as controls | Smaller samples cannot detect a 3.5% change |
| Matching | 10 pairs, matched on region then store type | Similar stores are compared with each other |
| Assignment | Random inside each pair, fixed seed, recorded before launch | Fair and auditable (`assign_stores`) |
| Cap rule | Any discount above 10% is set to 10%. Discounts at or below 10% are untouched | Same rule as the simulation |
| Duration | **16 weeks** (plus 4 weeks of history for a balance check) | See precision table |
| Start | Not at the start of a known peak period (Ramadan, Eid, White Friday) | Keeps the first weeks representative |

## How precise will it be?

Weekly traffic is about 57 transactions per store (profit about 80,000 SAR per store), and it varies from
week to week by roughly 14%. Using the 103 weeks of history, we replayed the planned analysis 1,500 times
on random 10-versus-10 splits and measured how wide the 95% interval is, as a share of normal traffic:

| Test length | Transactions (interval ±) | Profit per store-week (interval ±) |
|---|---|---|
| 8 weeks | 4.4% | 6.2% |
| 12 weeks | 3.6% | 4.9% |
| **16 weeks** | **3.1%** | **4.3%** |
| 26 weeks | 2.4% | 3.1% |
| 40 weeks | 2.0% | 2.4% |

- **At 16 weeks the transaction interval (±3.1%) is narrower than the break-even loss (3.5%).** If the cap
  does no harm, the test can show it. At 12 weeks it cannot.
- **Profit is too noisy to be the deciding measure.** The expected gain (+3.5%) is smaller than the profit
  interval (±4.3%). The gain per sale is arithmetic (the price rises), so the test only has to show that
  traffic did not fall by more than the break-even amount.

## Measures

1. **Primary: transactions per store-week**, capped stores versus their matched controls.
2. **Secondary: profit per store-week**, same comparison. Report it, but do not decide on it alone.
3. **Compliance: share of sales discounted above 10%.** It should be about 0% in capped stores and about
   12% in controls. If capped stores still show discounts above 10%, the test did not run as designed.

## Decision rules (agree these before launch)

Using the 95% interval for the change in transactions (capped versus control):

| Result | Decision |
|---|---|
| Interval stays above −3.5% and compliance holds | **Roll out the cap.** Traffic loss, if any, is smaller than the gain |
| Interval sits entirely below −3.5% | **Stop.** The cap loses more than it earns |
| Interval crosses −3.5% | **Inconclusive.** Extend by 8 weeks or test a softer cap (15%) |

## Risks and how to handle them

| Risk | Handling |
|---|---|
| **Shoppers switch stores.** Four pairs have both stores in the same city, so customers could move from a capped store to its control. This makes the cap look worse than it is | The bias is conservative: a "safe" result is trustworthy. If the result is "harmful", compare same-city pairs with other pairs before deciding |
| Staff or systems override the cap | Check compliance weekly from the sales data |
| Promotions, stock-outs or store closures in one arm | Keep a log of events per store; exclude a pair if one of its stores is affected |
| Regular customers notice and complain | Count complaints and loyalty-member transactions per arm |
| Results differ in peak periods | Report by month; do not assume the result holds for Ramadan or White Friday without checking |
| Choosing the answer after seeing the data | Fix the decision rules and the seed before launch; look at results only at the planned end, except for compliance |

## Before launch

1. Run `assign_stores(store, seed=...)` once, save the table, and share it with store operations.
2. Confirm the system can apply the cap by store, and confirm the start date.
3. Pull the last 4 weeks and check that capped and control stores had similar traffic and discount share.
4. Write the decision rules above into the project plan and get sign-off.

## Analysis at the end

```python
from src.analysis.store_test import analyze_store_test, store_week_table

weeks = store_week_table(analysis)  # analysis = table from build_sales_analysis_table
test_weeks = weeks[(weeks["week"] >= start) & (weeks["week"] < end)]
result = analyze_store_test(test_weeks, assignment)  # assignment = the saved table from assign_stores
```

The result holds the percentage change in transactions and in profit with 95% intervals, the share of sales
above the cap in each arm, and the verdict (`safe`, `harmful` or `inconclusive`).

As a dry run, the same function applied to 16 weeks of history, with a random assignment and no real cap,
returned a change of +0.5% with an interval of −2.9% to +3.9%: close to zero, as it should be.

## What the test will and will not tell you

It will tell you whether a 10% cap changes the number of transactions by more than the break-even amount.
It will not tell you the effect on other products, on loyalty over a longer period, or on competitors'
reactions, and the rollout should keep monitoring traffic after launch.
