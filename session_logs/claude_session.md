buddy i want submission in this format, its not fix but its kind of template for submission thing, help me with this too, ill fill the notes.md later and find another fixes you can and give in the template , help me buddy

Next: money-input validation, free orders stuck in pending, and a ship-vs-cancel race.

Akash submission
ZIP

I hhave solved bugs from my side, check if there's any more bugs need to be solved and after that tell me in detail that in each time, what bugs you fixed, your approach, why did you choose that approach and how you implemented it and also check my approach on it.

The second pass found one more real bug: create() accepts fractional or boolean quantities, so an order of 1.5 units would leave fractional stock. I'll fix that with a test, then rebuild the zip.

I found one more bug on the second pass (quantity validation) and fixed it. The updated akash_submission.zip has 10 fix commits and 32 passing tests. Below, for each fix: the bug, how I found the cause, why I chose that fix, and how it's built.

For every fix I wrote a test first and watched it fail on the code as sent. It was committed together with the fix.

The five reported bugs

1. Duplicate payments from webhook retries (972be17)

Cause: the provider resends a webhook until it gets a 2xx. The payments table had no uniqueness on event_id, so every retry added another row. Revenue and "received" amounts then ran higher than the real payout.
Approach: make the database enforce "one event, one payment", not just the Python code. A check in Python alone ("does this event exist? no, insert") breaks when two workers check at the same moment.
Implementation:
Added a unique index on payments(event_id).
The insert is now INSERT OR IGNORE, and rowcount == 0 means "already seen". A retry returns the order's current status and adds nothing, so the provider still gets its 2xx and stops retrying.
The whole handler runs in one BEGIN IMMEDIATE transaction, with the order read inside it.
Caveat: the index fails to build on a database that already contains duplicates. Put that in NOTES.md.

2. Stock leak on cancelled orders (e6b1c75)

Cause: stock is taken when the order is created, but cancel() only gave it back if the status was paid. Abandoned checkouts are cancelled while pending, so their stock never came back.
Approach: the real rule is "an order holds stock until it ships or is cancelled". So I stopped checking for paid and restock every order that reaches that point.
Implementation: I removed the if status == "paid" condition. Cancelled and shipped orders already return earlier in the function, so only pending and paid orders get there.

3. Tax too high with coupons (513a12c)

Cause: price_order computed tax on the subtotal before the discount.
Approach: the customer pays tax only on what they actually pay for the goods.
Implementation: compute the discount first, then tax_for(sub - discount, region). The tests use hand-calculated values: a 10% coupon on 10,000 cents in CA gives tax 653, and a fixed 500-cent coupon in TX gives tax 594.

4. Daily report on the wrong day (c2c32fe)

Cause: day_bounds_utc added the UTC offset. For a shop at UTC+5:30, local midnight is 18:30Z the evening before, so the offset must be subtracted. Sales near the day boundary landed on the wrong day.
Approach: fix the one sign and test both sides of UTC, because a sign error hides easily if you only test one direction.
Implementation: start -= timedelta(minutes=offset). I added tests for both a positive offset (IST) and a negative one (UTC-5), plus a morning sale and a late-evening sale in IST.

5. Overselling with two workers (9ad19ce)

Cause: there were three connected problems.
Each worker process kept its own product cache. Worker A could hold "stock = 1" after worker B had sold that unit, then sell it again. The same cache also served stale prices.
The stock check and the decrement were two separate steps.
cancel() read the order's status before taking the write lock, so two workers cancelling the same order could both restock it.
Approach: SQLite is the only source of truth. A per-process cache can't be correct with several processes, and the lookups are cheap. So I removed the cache rather than trying to invalidate it.
Implementation:
Deleted the cache.
reserve is now one statement, UPDATE ... SET stock = stock - ? WHERE sku = ? AND stock >= ?. If rowcount is 0, it raises OutOfStock.
cancel() starts BEGIN IMMEDIATE first and reads the status inside the lock.
The tests use two App objects on one database file. The cancel-race test makes worker A cancel in the gap just before worker B takes its lock. All three tests fail on the original code.
The extra fixes

6. Server crash on bad JSON (fc0fb15)

Cause: json.loads ran outside any error handling in server.py, so malformed input dropped the connection.
Fix: catch ValueError (which covers JSONDecodeError and a bad Content-Length) and answer 400. A body that isn't a JSON object also gets a 400. The test starts a real HTTPServer on a free port.

7. Money inputs not validated (9de6704)

Cause: a negative payment could reduce what was recorded as paid, and price_cents: 99.5 was stored as a float in an integer column.
Fix: require a positive whole number of cents for payments and a non-negative one for prices. I used type(x) is int because True counts as an int in Python and would pass isinstance.

8. Free orders stuck pending (51e9cca)

Cause: with a 100% coupon the total is 0, so no payment ever arrives and the order can never become paid or ship.
Fix: create() sets the status to paid when total_cents == 0.

9. Ship overwriting a cancel (9e1583f)

Cause: ship() read the order, checked it was paid, then updated it unconditionally. A cancel landing in between turned a cancelled and restocked order into shipped.
Fix: the update is now ... WHERE id = ? AND status = 'paid', and rowcount == 0 raises an error. The check and the write happen in one atomic statement.

10. Fractional quantities (66c84c1, found on the second pass)

Cause: create() only checked qty <= 0, so 1.5 or True got through and left fractional stock.
Fix: exact-type check for a positive whole number.
Not fixed, and why
Report 6 (a second payment for the same order): this is your decision, and it's scored. See the three options in my earlier message.
Payment for a cancelled order: the 409 makes the provider retry forever and the money is never recorded. The right behavior is a policy choice that overlaps Report 6.
Revenue is gross of cancellations: daily_sales counts payments for orders that were later cancelled. There's no refund model to subtract against.
Status codes: OrderError maps to 404 even for conflicts like "already shipped". I left it alone because changing API status codes could break clients.
Smaller items:
Pending orders never expire.
The timezone offset is fixed, so a daylight-saving day isn't 24 hours.
An unexpected exception such as database is locked still drops the connection.
What you still have to do
Fill in NOTES.md in your own words. Use the commit hashes above and the "How I verified" line for each (the test file and "failed before, passes after").
Put real session logs in session_logs/. The example's logs are made-up. Yours should be this conversation and any other AI sessions, unedited.
Decide Report 6.
Set your own git name and email, and rename the folder to <yourname>_submission.

Do you want to go through Report 6 now? Or I can walk you through any fix above so you can explain it in your interview.

Akash submission
ZIP

Yes let's go through report 6.

Report 6 is the one decision in this assignment that's explicitly yours, and the graders score your reasoning on it. I'll lay out the facts and the options, and you make the call.

What the system does today: a first payment that covers the total marks the order paid. A second payment with a different event ID is still inserted, the status stays paid, and nothing marks the order as overpaid. Finance only finds out when the totals disagree. That's the same symptom as Report 1, except this time the money really did arrive.

One trap in the wording: "paid twice" isn't the same as "has two payments". Two partial payments (500 + 700 on a 1,200 order) are legitimate. So the rule has to be paid_cents > total_cents, not payment count > 1.

The options:

A. Record it and flag it. Keep both payments and show how much was overpaid on the order. This needs no schema change and no outside systems.
Cost: no money moves. A person must read the flag and refund by hand, and nothing alerts them.
B. Reject the second payment. Don't record it.
Cost: the provider has already taken the customer's money. Your ledger then disagrees with the provider's payout, which is exactly what Finance complained about in Report 1. It also returns a non-2xx, so the provider retries forever.
C. Record it and refund it automatically.
Cost: it needs the provider's refund API, which this code doesn't have, plus handling for failed or repeated refunds. That's far from "the smallest version".

Your wording in NOTES.md should also address two follow-ups:

Should the flag show up in the daily report, or only on the order?
Is the second payment still revenue? It's cash received, but it isn't a sale.

Which option do you pick, and in one or two sentences, why? Type it in your own words, since that's what gets scored. If you want a variant, such as A now with a note that C is the real fix later, say so. Once you've decided, I'll build the smallest version with tests: exact payment shows no overpayment, partial payments that add up show none, a real double payment shows the overpaid amount, and a retried webhook doesn't change it.

I would choose the either option A and C because in option A, we're not having too much cost for implementation from ourselves, and it'll flag and manually return the money that's extra paid and doesn't reflect in the ledger and C because it is automated and not required any human intervention until special cases but I'll keep the C option as future or another possible implementation, why we're not implementing it now is because it may fail if we change the api which code doesn't have and as a previous enginners principle is if something is working somehow correctly, don't interfere it, so yeah. That's my interpretation.

Understood: A now, C as a documented future step. I'll build A as the smallest version that still lets someone find the flagged orders.

Option A is built and committed as 673a654. All 38 tests pass, and the six new ones fail on the old code. The updated akash_submission.zip has it.

What I built:

Every order now shows paid_cents and overpaid_cents. The overpaid amount is the money received minus the order total, and never below zero. It's calculated from the payments table each time, so it can't drift out of sync and a webhook retry can't inflate it.
GET /reports/overpaid lists every order that has received more than its total, with the amounts. Without it, someone would have to open every order to find the flagged ones.
It uses paid > total rather than "more than one payment", so two partial payments that add up to the total (500 + 700 on 1,200) are not flagged. There's a test for that.

One correction for NOTES.md: you wrote that the extra money "doesn't reflect in the ledger". Under option A it does reflect: both payments stay recorded. That's the reason to choose A over rejecting the payment, because your records keep matching what the provider actually took. What A doesn't do is move any money, since someone still refunds by hand.

What A costs (the points to put in your own words):

Refunds stay manual. Nobody is alerted, so someone has to check the report.
The daily revenue report still counts the second payment as money received.
An order that is paid and then cancelled isn't flagged, even though the customer is owed a refund. That's a related gap, so write it down as an extra rough edge.

Your reason for deferring C is sound, but sharpen it: the real blocker is that this codebase has no connection to the provider's refund API, and building one adds new failure cases (refunds that fail or get sent twice). Your "if it works, don't disturb it" point is also fair for a minimal first step.

Next you fill in NOTES.md and session_logs/ in your own words. Do you want to start on the NOTES.md sections, or have me quiz you on any of the fixes first?

Akash submission
ZIP

Yes please filling the notes.md consisting of everything we've done till now, initial bugs and bugs that we found out too, apart from suggested and write it in my pov that I am writing things in notes.md

NOTES.md is filled in with no TODO left, committed as f3b2dfd, and the updated akash_submission.zip has it. It's written in the first person and covers the five reports, your Report 6 decision, the five extra fixes, the issues I left unfixed, and the session-log section.

Make it honestly yours before you send it:

Disclosure: I wrote in the file that you worked with Claude and that Claude drafted the notes. The brief allows AI help but wants it disclosed. Keep those lines.
Two claims I wrote for you that you have to make true:
It says you run python3 -m unittest discover -s tests yourself. Run it now (expect 38 tests, all OK). Otherwise edit that line.
It says you reviewed the notes. Read all of it and change anything you wouldn't say.
Interview: whoever reads it may ask you why you removed the cache, or why INSERT OR IGNORE is safer than checking first in Python. If you can't explain a paragraph, ask me about it, or reword it to what you actually understand.

Still to do:

Session log: save this whole conversation as session_logs/claude_session_1.md, unedited, using exactly that filename since NOTES.md refers to it. If you used other AI tools, add one file for each and one line in the notes.
Git identity: my commits use the placeholder Akash <akash@example.com>. If you rewrite the author (the git rebase command I gave you earlier), the commit hashes change. Run git log --oneline afterward and update every **Commits:** line in NOTES.md.
Package it: rename the folder to <yourname>_submission, zip it with .git included, and email it as <yourname>_submission.zip.
Hand-checks: run git log (11 fix commits plus the notes commit on top of the initial one) and python3 server.py to make sure it starts, as the README says.

Do you want me to quiz you on the fixes now, one at a time, the way an interviewer would?

Akash submission
ZIP

Should I post it on git or in Google drive?

Neither. The brief says to submit one zip file, sent back by email, named <your-name>_submission.zip. It doesn't ask for a GitHub link or a Drive link.

Don't post it on GitHub. A public repo lets other candidates copy your solution, and many companies treat that as a problem. It also adds nothing, because they read the .git folder inside your zip.
Don't send a Google Drive link instead of the zip. Links can expire, need permission changes, or go to spam. Attach the zip itself. If it's too big for email (yours is about 100 KB, so it isn't), you could add a Drive link as a backup, but the attachment is what they asked for.

Before you send:

Rename the folder to <yourname>_submission, with your real name.
Zip it with the .git folder included, and name the zip <yourname>_submission.zip.
Unzip a copy somewhere else and check git log shows your commits and the tests pass.
Make sure session_logs/claude_session_1.md is in the folder.
Email the zip to the address in your assessment invite, and check the invite for a deadline or subject-line format.

I can't see where to send it. Do you want help writing the email?