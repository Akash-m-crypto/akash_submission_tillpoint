# NOTES

Fill in every field below before you submit. We read this file first: a submission with an empty field is not graded.
Write in your own words. If you did not fix something, set Status to `not fixed` and say what you found and tried; that still counts.
Status is one of: `fixed`, `partly fixed`, `not fixed`. Commits: the short hashes of the commits for this item, or `none`.

I worked on this together with Claude (chat, claude.ai app). Claude helped me read the code, find causes and write the fixes and tests; I decided the scope, chose what to do about the open question (report 6), and I run `python3 -m unittest discover -s tests` myself. Details are in the Session logs section at the bottom.

## 1. Report

> Finance says that on some days the revenue in the daily report is higher than what the payment provider paid out, and a few orders show more money received than their total.

**Status:** fixed

**What I saw:** The README says the payment provider keeps retrying a webhook until it gets a 2xx. When I sent the same `payment.succeeded` event (same event id) two or three times, the `payments` table got one row per delivery, so an order showed 2x or 3x its total as received and the daily revenue went up by the same amount. That matches Finance's complaint: revenue above the payout, and some orders with more money received than their total.

**Root cause:** `payments.event_id` had no uniqueness and `handle_event` always did a plain `INSERT`. Nothing recognised a retry as the same payment. The handler also read the order outside a transaction, so a concurrent cancel or payment could change it between the read and the write.

**Fix and why:** I made the database enforce it: a unique index on `payments(event_id)`, and the insert is now `INSERT OR IGNORE`. If nothing was inserted (`rowcount == 0`) the event was already seen, so the handler returns the order's current status and adds nothing. The provider still gets its 2xx and stops retrying. I did the check in the database and not with a "does it exist?" query in Python, because two workers could both pass that query at the same time. The whole handler now runs in one `BEGIN IMMEDIATE` transaction with the order read inside it. Two different event ids are still both recorded, because real partial payments exist.

**How I verified it:** `tests/test_payment_retries.py`. The retry test fails on the original code (the order shows 3600 received instead of 1200) and passes after the fix. A second test checks that two different event ids are both recorded, and a third checks that a retry still reports the order as `paid`. One limit: the unique index cannot be created on a database that already contains duplicate event ids, so a real deployment would need a one-off cleanup first.

**Commits:** 972be17

## 2. Report

> Products show as sold out, or nearly, while the shelf is full. Staff say it gets worse on days when many customers abandon checkout.

**Status:** fixed

**What I saw:** Stock is taken (`reserve`) when an order is created, not when it is paid. When I created an order and then cancelled it while it was still `pending` (an abandoned checkout), the product's stock stayed lowered. Many abandoned checkouts therefore made the shelf look empty.

**Root cause:** In `Orders.cancel`, stock was only released `if order["status"] == "paid"`. A pending order holds stock just like a paid one, but its stock was never given back.

**Fix and why:** I removed the `paid`-only condition. Cancelled and shipped orders already return earlier in `cancel`, so every order that reaches the release loop (pending or paid) is holding stock and gets it back. The real rule is "an order holds stock until it ships or is cancelled", and the code now says that.

**How I verified it:** `tests/test_cancel_restock.py`: cancelling a pending order puts the stock back (fails on the old code: stock stays at 3 instead of 5), and cancelling twice only restocks once.

**Commits:** e6b1c75

## 3. Report

> Customers in taxed regions who used a coupon say the tax on their receipt is too high. Receipts without a coupon are right.

**Status:** fixed

**What I saw:** With a 10% coupon on a 10,000 cent item in CA, the order's tax was 725 (7.25% of the full price) instead of 653 (7.25% of the discounted 9,000). Without a coupon the tax was correct, as the report says.

**Root cause:** `pricing.price_order` calculated `tax_for(sub, region)` on the subtotal before the discount was applied.

**Fix and why:** Calculate the discount first, then `tax_for(sub - discount, region)`. The customer should pay tax only on what they actually pay for the goods.

**How I verified it:** `tests/test_tax_with_coupon.py` with hand-calculated expected values: percent coupon in CA gives tax 653 and total 9,653; fixed 500 cent coupon in TX gives tax 594 and total 10,094; and an order with no coupon keeps tax 725. The coupon tests fail on the old code.

**Commits:** 513a12c

## 4. Report

> Our shop in India (UTC+5:30) says sales taken in the morning do not appear in that day's report and turn up under the day before.

**Status:** fixed

**What I saw:** `day_bounds_utc("2025-03-10", 330)` returned 05:30Z on the 10th to 05:30Z on the 11th. But a day that starts at local midnight in India starts at 18:30Z on the 9th. So a sale at 08:00 IST (02:30Z on the 10th) fell outside the window for the 10th.

**Root cause:** `day_bounds_utc` added the UTC offset to local midnight. For a zone east of Greenwich, local midnight happens earlier in UTC, so the offset must be subtracted.

**Fix and why:** One line: `start -= timedelta(minutes=utc_offset_minutes)`. I tested both directions around UTC, because a sign error can look right if you only test one side.

**How I verified it:** `tests/test_report_timezone.py`: exact window for UTC+5:30 (18:30Z to 18:30Z), exact window for UTC-5, a morning sale in India landing on its own day (fails on old code), and a late-evening sale landing on its own local day.

**Commits:** c2c32fe

## 5. Report

> Ever since we started running two server workers, we have sold more units of an item than we had, and its stock went negative.

**Status:** fixed

**What I saw:** I simulated two workers as two `App` objects (each with its own connection and cache) on one database file. Worker A looked at a product with stock 1 (so it cached it), worker B sold that last unit, and then worker A sold it again, because it still believed stock was 1.

**Root cause:** Three connected problems. (1) `Catalog` kept a per-process cache of products, so with several processes one worker's view of stock (and price) goes stale and nothing tells it. (2) `reserve` was check-then-update in two steps, using that cached number. (3) `cancel` read the order's status before taking the write lock, so two workers cancelling the same order could both see "not cancelled" and both give the stock back.

**Fix and why:** I removed the cache: SQLite is the only source of truth, and the lookups are cheap, so invalidating a cache across processes is not worth the risk. `reserve` is now one atomic statement, `UPDATE products SET stock = stock - ? WHERE sku = ? AND stock >= ?`, and if no row changed it raises `OutOfStock`. `cancel` now starts `BEGIN IMMEDIATE` first and reads the status inside the lock.

**How I verified it:** `tests/test_multiworker_stock.py` has three tests, all failing on the original code: the oversell (last unit sold twice), a price change on one worker being seen by the other, and a deterministic race where worker A cancels in the gap just before worker B takes its lock (stock must come back once, not twice). Limit: I tested with two `App` objects on one file and not with two real server processes under load.

**Commits:** 9ad19ce

## 6. Open question

> Open question from support, no single right answer: sometimes a customer really does pay twice for one order (two separate payments, not a retry of the same one). Today the system records both and says nothing. Decide what should happen, build the smallest version of your decision, and explain what it costs in `NOTES.md`.

**My decision:** Option A now: keep recording both payments, and flag the order as overpaid with the extra amount, so support can refund it by hand. Option C (automatic refund) is the later step, not built now.

**Why:** A costs little to build and does not depend on anything outside this code. Both payments stay in our records, so our ledger still matches what the provider really took from the customer (which is also what Finance complained about in report 1). I did not choose rejecting the second payment because the provider has already taken the money, so rejecting it would make our records disagree with the payout, and a non-2xx answer would make the provider retry for ever. I did not build C because this code has no connection to the provider's refund API, and adding one brings new failure cases (a refund that fails, or is sent twice) and is far from the smallest version.

**What it costs:** No money moves by itself: someone has to look at the flag and refund manually, and nothing alerts them, so they have to check the report. The daily revenue report still counts the second payment as money received. An order that was paid and then cancelled is not flagged, even though the customer is owed money back.

**What I built:** Each order now has `paid_cents` and `overpaid_cents` (money received minus the order total, never below zero), calculated from the payments table each time so it cannot drift out of sync. I also added `GET /reports/overpaid`, which lists the overpaid orders, because a flag that support has to hunt for order by order is not much of a flag. The rule is "paid more than the total", not "has two payments", because two partial payments that add up (500 + 700 on 1,200) are legitimate.

**How I verified it:** `tests/test_overpayment.py` (6 tests, all failing on the old code): exact payment is not overpaid, partial payments that add up are not overpaid, paying twice keeps both payments and shows the excess of 1,200, a retry of the second payment does not grow the excess, the report lists only the overpaid order, and the report works over the API.

**Commits:** 673a654

## Other things I noticed

Fixed after the reports, each with a cause, a fix and a test that fails on the old code:

- **Server dropped the connection on malformed JSON** (`server.py`). `json.loads` ran outside any error handling, so bad input crashed the request. Now invalid JSON, a body that is not a JSON object, or a bad `Content-Length` returns 400. Test: `tests/test_server_bad_input.py` (starts a real `HTTPServer`). Commit: fc0fb15.
- **Money inputs were not validated** (`payments.py`, `catalog.py`). A negative payment would reduce what is recorded as paid, and `price_cents: 99.5` was stored as a fraction in an integer column. Now amounts must be positive whole cents and prices non-negative whole cents. I check `type(x) is int` because `True` counts as an `int` in Python. Test: `tests/test_money_validation.py`. Commit: 9de6704.
- **Free orders stayed `pending` for ever** (`orders.py`). With a 100% coupon the total is 0, so no payment ever arrives and the order can never be paid or shipped. `create` now marks a zero-total order `paid`. Test: `tests/test_free_orders.py`. Commit: 51e9cca.
- **`ship` could overwrite a concurrent cancel** (`orders.py`). It checked that the order was `paid` and then updated it without checking again, so a cancel (which also restocks) landing in between left a cancelled order marked `shipped`. The update is now `... WHERE id = ? AND status = 'paid'` and fails if no row changed. Test: `tests/test_ship_cancel_race.py`. Commit: 9e1583f.
- **Fractional and boolean quantities were accepted** (`orders.py`). `qty` only had to be above 0, so `1.5` could leave fractional stock. Quantities must now be positive whole numbers. Test: `tests/test_quantity_validation.py`. Commit: 66c84c1.

Noticed and **not fixed**:

- A payment for an already-cancelled order is rejected with a 409, so the provider retries for ever and the money it took is never recorded. What to do with it is a policy decision (similar to report 6), so I left it.
- The daily revenue report counts payments for orders that were later cancelled, so it is gross of cancellations. There is no refund model to subtract against.
- An order that was paid and then cancelled has its stock restocked, but nothing records that a refund is owed.
- Pending orders never expire, so abandoned checkouts hold stock until someone cancels them (a scheduled job would be needed).
- `OrderError` is mapped to 404 even for conflicts such as "a shipped order cannot be cancelled" or "only a paid order can ship", and invalid quantities also get 404. I did not change status codes because API clients may rely on them.
- The report uses a fixed UTC offset, so a day when daylight saving changes is not really 24 hours long. Also, `GET /reports/daily` reads the offset from a request body, which is unusual for a GET.
- An unexpected error such as SQLite `database is locked` under heavy load is not caught by the server, so the connection is dropped instead of answering 503. Turning on WAL mode and a busy timeout would help with two workers.
- `list_for` does not validate `page` and `per_page` (a negative `per_page` means no limit in SQLite). It is not exposed through the API, so I left it.
- The unique index on `payments(event_id)` cannot be created on a database that already has duplicate event ids; a one-off cleanup of existing data is needed before deploying.

## Session logs

AI tool used: Claude (claude.ai mobile app), in one long conversation covering everything in this file: reading the code, reproducing the reports, the fixes and tests, the open question, and writing these notes (Claude drafted this file from the work we did together, and I reviewed it).

- `session_logs/claude_session_1.md`: full export of that conversation, unedited.
