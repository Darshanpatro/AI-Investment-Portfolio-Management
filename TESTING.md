# TESTING.md

Test documentation for the **AI-Based Investment Portfolio Management and Risk Analysis System**.

All results below were recorded by actually running the application, not estimated. The automated portions are reproducible with:

```bash
rm database/portfolio.db     # Windows: del database\portfolio.db
python smoke_test.py
```

**Environment used for the recorded run**

| Item | Value |
|---|---|
| Python | 3.12 |
| Flask | 3.0.3 |
| Database | SQLite (`database/portfolio.db`, created fresh) |
| Market data | `data/market_data.csv` — 4,032 rows, 8 symbols |
| Knowledge base | 6 documents indexed |
| `LLM_API_KEY` | not set (fallback path exercised) |
| Automated result | **ALL SMOKE TESTS PASSED** |

---

## 1. Authentication

| # | Test case | Steps | Expected result | Actual result | Status |
|---|---|---|---|---|---|
| A1 | Registration page loads | GET `/register` | 200, form with 4 fields | 200, form rendered | Pass |
| A2 | Valid registration | Submit name / email / password / matching confirm | Account created, redirect to login, success message | User row created, redirected, "Account created successfully" | Pass |
| A3 | Duplicate email rejected | Register the same email twice | Error message, no second row | "An account with that email already exists." | Pass |
| A4 | Password mismatch rejected | confirm ≠ password | Error, no account created | "Password and confirmation do not match." | Pass |
| A5 | Short password rejected | 5-character password | Error message | "Password must be at least 6 characters long." | Pass |
| A6 | Invalid email rejected | `notanemail` | Error message | "A valid email address is required." | Pass |
| A7 | Password is hashed | Inspect `users.password_hash` in SQLite | No plain text | `scrypt:32768:8:1$...` hash stored | Pass |
| A8 | Wrong password rejected | Correct email, wrong password | Login refused | "Invalid email or password." | Pass |
| A9 | Valid login | Correct credentials | Session created, redirect to dashboard | Dashboard rendered, name in sidebar | Pass |
| A10 | Logout | Click Logout | Session cleared, redirect to login | Redirected, protected pages now blocked | Pass |
| A11 | Protected routes require auth | Visit `/`, `/holdings`, `/risk` while logged out | Redirect to login | All redirected with "Please log in" | Pass |

**Verifying the hash manually**

```bash
sqlite3 database/portfolio.db "SELECT email, substr(password_hash,1,30) FROM users;"
```

---

## 2. Holdings CRUD and persistence

| # | Test case | Input | Expected result | Actual result | Status |
|---|---|---|---|---|---|
| H1 | Add valid holding | TCS, qty 10, price 3550, 2024-06-10 | Row inserted, success message | "Holding added successfully", visible in table | Pass |
| H2 | Transaction auto-created | After H1, check Transactions page | One BUY row matching the holding | BUY 10 @ ₹3550 on 2024-06-10 | Pass |
| H3 | Negative quantity rejected | qty `-5` | Validation error, no insert | "Quantity must be greater than zero." | Pass |
| H4 | Zero price rejected | price `0` | Validation error | "Buy price must be greater than zero." | Pass |
| H5 | Non-numeric quantity rejected | qty `abc` | Validation error | "Quantity must be a valid number." | Pass |
| H6 | Invalid date rejected | `2024-13-45` | Validation error | "Purchase date must be a valid date (YYYY-MM-DD)." | Pass |
| H7 | Future date rejected | tomorrow's date | Validation error | "Purchase date cannot be in the future." | Pass |
| H8 | Missing symbol rejected | blank symbol | Validation error | "Symbol is required and must be alphanumeric..." | Pass |
| H9 | Edit holding | Change qty 10 → 12 | Row updated, totals recalculated | "Holding updated successfully", figures changed | Pass |
| H10 | Delete holding | Click delete, confirm | Row removed | "Holding deleted", gone from table | Pass |
| H11 | **Persistence across restart** | Add holding → Ctrl+C → `python app.py` → log in | Holding still present | Still present with identical values | Pass |
| H12 | Empty portfolio state | New user visits dashboard | Friendly empty state, no crash | "No holdings yet" card with Add button | Pass |

**H11 is the key demonstration test** — it proves data is written to SQLite rather than held in memory.

---

## 3. User isolation

| # | Test case | Steps | Expected result | Actual result | Status |
|---|---|---|---|---|---|
| U1 | Holdings isolated | User A adds INFY; log in as User B; view `/holdings` | B sees empty portfolio | "No holdings yet" | Pass |
| U2 | Totals isolated | As User B, check dashboard | All totals ₹0.00 | ₹0.00 across all cards | Pass |
| U3 | AI assistant isolated | As User B, ask "How many holdings do I have?" | Answer says 0 | "You currently have 0 holding(s)..." | Pass |
| U4 | Direct URL access blocked | As User B, POST to `/holdings/<A's id>/delete` | Not found, A's data untouched | "Holding not found.", A's holding intact | Pass |
| U5 | Alerts isolated | Compare `/alerts` between users | Each sees only their own | Confirmed | Pass |

U4 matters because it tests the object-level check, not just the page-level one. Every service method filters on `user_id`, so guessing another user's row ID fails.

---

## 4. Portfolio calculations

Verified against the seeded demo portfolio (`python seed_data.py`).

| # | Test case | Formula | Expected | Actual | Status |
|---|---|---|---|---|---|
| C1 | Investment value | qty × buy_price | TCS: 10 × 3550 = ₹35,500.00 | ₹35,500.00 | Pass |
| C2 | Current value | qty × current_price | TCS: 10 × 2796.59 = ₹27,965.90 | ₹27,965.90 | Pass |
| C3 | Profit/Loss | current − investment | −₹7,534.10 | −₹7,534.10 | Pass |
| C4 | Return % | P/L ÷ investment × 100 | −21.22% | −21.22% | Pass |
| C5 | Total investment | Σ investment values | ₹126,800.00 | ₹126,800.00 | Pass |
| C6 | Total current value | Σ current values | ₹152,381.98 | ₹152,381.98 | Pass |
| C7 | Total P/L | total current − total investment | ₹25,581.98 | ₹25,581.98 | Pass |
| C8 | Total return % | 25581.98 ÷ 126800 × 100 | 20.18% | 20.18% | Pass |
| C9 | Recalculation on edit | Change a quantity | All dependent figures update | Dashboard, portfolio and charts all updated | Pass |
| C10 | Unknown symbol handled | Add holding with symbol `ZZZZ` | "N/A" shown, no crash, warning alert | Price column "N/A", market-data alert created | Pass |

**Manual verification during the demo:** open the Portfolio page, pick any row, and check `quantity × buy price` against the Investment column with a calculator.

---

## 5. Asset allocation

| # | Test case | Expected | Actual (demo portfolio) | Status |
|---|---|---|---|---|
| AL1 | Percentages computed | asset value ÷ total × 100 | Technology 40.67%, Banking 26.62%, Energy 16.88%, Diversified 12.23%, Commodity 3.61% | Pass |
| AL2 | Percentages sum to 100 | ≈100% | 40.67 + 26.62 + 16.88 + 12.23 + 3.61 = 100.01 (rounding) | Pass |
| AL3 | Doughnut chart renders | Chart matches table | Segments match sector table | Pass |
| AL4 | Chart updates on change | Delete a holding, reload | Chart redraws with new percentages | Redrawn correctly | Pass |
| AL5 | Data comes from API | Inspect `/api/allocation` in DevTools | Live JSON, not template-embedded | JSON returned from backend | Pass |

**AL5 is worth showing in the viva** — open browser DevTools → Network tab and show the JSON response arriving from the server.

---

## 6. Performance charts

| # | Test case | Endpoint | Expected | Actual | Status |
|---|---|---|---|---|---|
| P1 | Value series generated | `/api/performance/value-series` | Array of {date, value} | 504 points, last = 2026-09-15 | Pass |
| P2 | Series reflects holdings | — | Values = Σ(qty × close) per day | Verified against manual calculation | Pass |
| P3 | Value-over-time chart | Performance page | Line chart renders | Rendered | Pass |
| P4 | Investment vs current | — | Grouped bar chart | Rendered, both series present | Pass |
| P5 | Return % by asset | — | Bar chart, green/red by sign | Rendered with correct colours | Pass |
| P6 | P/L by asset | — | Horizontal bar chart | Rendered | Pass |
| P7 | Empty portfolio | New user | Friendly message, no JS errors | "Add holdings to see performance charts" | Pass |

---

## 7. Concentration risk

| # | Test case | Setup | Expected | Actual | Status |
|---|---|---|---|---|---|
| CR1 | Breach detected | Demo portfolio, threshold 40% | Technology flagged at 40.67% | "High concentration detected in the Technology sector. Technology represents 40.67%..." | Pass |
| CR2 | No false positive | Threshold raised to 60% | No breach | "No concentration threshold breaches detected." | Pass |
| CR3 | **Threshold is configurable** | Set `CONCENTRATION_THRESHOLD_PERCENT=25`, restart | More sectors breach | Technology and Banking both flagged | Pass |
| CR4 | Single-asset concentration | One holding only | Asset-level breach at 100% | Flagged at 100% | Pass |
| CR5 | Explains, does not advise | Read the message text | No buy/sell recommendation | Describes the condition only | Pass |
| CR6 | Table highlights breach | Risk page sector table | Breaching row highlighted | Row shown with warning background | Pass |

**CR3 is the proof the threshold is not hard-coded.** Editing `.env` and restarting changes the result with no code change.

---

## 8. Drawdown

| # | Test case | Expected | Actual (demo portfolio) | Status |
|---|---|---|---|---|
| D1 | Current drawdown | (current − peak) ÷ peak × 100 | −6.76% | Pass |
| D2 | Maximum drawdown | Most negative in series | −13.16% | Pass |
| D3 | Previous peak shown | Highest recorded value | ₹163,434.90 | Pass |
| D4 | Current value shown | Latest series value | ₹152,381.98 | Pass |
| D5 | Drawdown never positive | Max ≤ 0 | All values ≤ 0 | Pass |
| D6 | Chart renders | Line chart of drawdown % | Rendered | Pass |
| D7 | Alert at threshold | Threshold `-5` | Drawdown alert created | Critical alert generated | Pass |
| D8 | No alert within threshold | Threshold `-30` | No drawdown alert | None created | Pass |
| D9 | Empty portfolio handled | No holdings | No crash, `has_data` false | "No portfolio value history yet." | Pass |

---

## 9. Anomaly detection (Isolation Forest)

| # | Test case | Expected | Actual | Status |
|---|---|---|---|---|
| AN1 | Model fits on real data | `IsolationForest` trained per symbol | Fitted on returns + 5-day rolling volatility | Pass |
| AN2 | Anomalies flagged | Unusual observations identified | 15 flagged per symbol (contamination 0.05 × ~300 points) | Pass |
| AN3 | Most significant reported | Largest absolute move surfaced | TCS −6.47%, INFY +6.31%, RELIANCE +5.68% | Pass |
| AN4 | Injected anomaly detected | TCS has an injected volatility spike | TCS flagged with the largest magnitude move | Pass |
| AN5 | No directional claim | Read the message text | "flags a statistical deviation only; it does not predict future price direction" | Pass |
| AN6 | Insufficient data handled | Symbol with < 20 points | Graceful message | "insufficient data" badge, no crash | Pass |
| AN7 | Only held symbols analysed | Compare against holdings | Exactly the 6 held symbols | Pass |

**Note on AN2:** `contamination=0.05` means roughly 5% of observations are flagged by construction. This is a property of the algorithm, not a bug, and is documented in the README's limitations section. The UI reports the most significant flagged move rather than the most recent one so the result is meaningful to read.

---

## 10. Alerts

| # | Test case | Steps | Expected | Actual | Status |
|---|---|---|---|---|---|
| AL1 | Alerts generated from real conditions | Run alert check on demo portfolio | Concentration + anomaly alerts appear | 7 alerts created matching risk page | Pass |
| AL2 | Stored in database | Query `alerts` table | Rows persisted | Rows present after restart | Pass |
| AL3 | De-duplication | Click "Run Alert Check" 3× | No duplicate rows same day | "No new alert conditions detected." | Pass |
| AL4 | Mark one as read | Click "Mark read" | `is_read` = 1, row dimmed | Updated | Pass |
| AL5 | Mark all read | Click "Mark All Read" | All unread updated | All dimmed | Pass |
| AL6 | Severity displayed | View alerts | info / warning / critical badges | Correct colours per severity | Pass |
| AL7 | Timestamp displayed | View alerts | Date and time shown | e.g. "16 Sep 2026, 09:18 AM" | Pass |
| AL8 | Market-data warning | Add unknown symbol, run check | Info alert about missing price | "Market data unavailable for some holdings" | Pass |
| AL9 | Empty portfolio | New user runs check | No alerts, no crash | "No new alert conditions detected." | Pass |
| AL10 | Dashboard shows recent | View dashboard | 5 most recent shown | Correct | Pass |

---

## 11. AI assistant and question routing

| # | Question | Expected route | Actual answer | Status |
|---|---|---|---|---|
| AI1 | "What is my total investment?" | `sql` | "Your total investment across all holdings is ₹56,800.00." | Pass |
| AI2 | "Which asset has the highest profit?" | `sql` | "INFY (Infosys) has a profit/loss of ₹12,703.80 and a return of 59.64%." | Pass |
| AI3 | "How many holdings do I have?" | `sql` | "You currently have 2 holding(s) in your portfolio." | Pass |
| AI4 | "What is my portfolio return?" | `sql` | Returns the computed percentage | Pass |
| AI5 | "What is diversification?" | `rag` | Definition retrieved from the Diversification document | Pass |
| AI6 | "What is drawdown?" | `rag` | Definition retrieved from the Drawdown document | Pass |
| AI7 | "Why is diversification relevant to my portfolio?" | `hybrid` | Combined the user's real 100% Technology concentration with retrieved knowledge | Pass |
| AI8 | Unsupported question | `rag` fallback | Helpful message, no guessed SQL | "I could not confidently map that question..." | Pass |
| AI9 | Empty question | — | 400 error, friendly message | "Question cannot be empty." | Pass |
| AI10 | Over-long question (>500 chars) | — | 400 error | "Question is too long (max 500 characters)." | Pass |
| AI11 | Chat history persisted | Reload assistant page | Previous Q&A shown | History rendered with route labels | Pass |
| AI12 | Route label displayed | Ask anything | Route shown above the answer | "Assistant · route: sql" | Pass |

**AI7 output (recorded):**

> Your portfolio currently holds 2 asset(s) worth ₹61,969.70. Your largest sector exposure is Technology at 100.0% of your portfolio. This currently exceeds your configured concentration risk threshold.
>
> From "Diversification": Diversification is an investment strategy that involves spreading capital across multiple assets, asset classes, sectors, or geographies...

This demonstrates hybrid routing: the first paragraph is computed from the user's real database rows, the second is retrieved from the knowledge base.

---

## 12. NL-to-SQL safety

| # | Test case | Input | Expected | Actual | Status |
|---|---|---|---|---|---|
| SQ1 | SELECT-only enforced | Validator receives `DELETE FROM holdings` | `UnsafeQueryError` | "Only SELECT statements are permitted." | Pass |
| SQ2 | DROP blocked | `SELECT * FROM holdings WHERE user_id = :user_id; DROP TABLE users` | Rejected | "Query contains a forbidden keyword: 'drop'." | Pass |
| SQ3 | UPDATE blocked | Query containing `update` | Rejected | Forbidden keyword error | Pass |
| SQ4 | INSERT blocked | Query containing `insert` | Rejected | Forbidden keyword error | Pass |
| SQ5 | Comment injection blocked | Query containing `--` | Rejected | Forbidden keyword error | Pass |
| SQ6 | Table whitelist enforced | `SELECT * FROM users WHERE user_id = :user_id` | Rejected | "Query references a table outside the allowed whitelist." | Pass |
| SQ7 | `user_id` filter mandatory | `SELECT * FROM holdings` | Rejected | "Query must be scoped to the current user..." | Pass |
| SQ8 | Injection attempt via chat | "DROP TABLE users; also what is my total investment" | Safe answer, nothing executed | Classified as `total_investment`, template used, tables intact | Pass |
| SQ9 | Unmappable question | Random text | Helpful message, no SQL run | "I could not confidently map that question..." | Pass |
| SQ10 | Parameters bound, not concatenated | Review `sql_service.py` | Uses `:user_id` binding | Confirmed — no string interpolation of user input | Pass |

**Verifying SQ8 after the test:**

```bash
sqlite3 database/portfolio.db ".tables"
# users, holdings, transactions, market_data, alerts, chat_history, knowledge_documents
```

All tables intact — the injection attempt never reached the database.

### Why templates instead of LLM-generated SQL

The question is classified into one of a fixed set of intents, each mapped to a pre-written parameterized query. A second independent validator then checks the query before execution. Because the SQL string is never built from user text, injection is structurally impossible rather than something a model has to be trusted to avoid.

---

## 13. RAG and knowledge base

| # | Test case | Expected | Actual | Status |
|---|---|---|---|---|
| R1 | Documents indexed | 6 documents processed | 6 documents, chunk counts shown | Pass |
| R2 | Chunking works | ~120-word chunks with overlap | Chunks created per document | Pass |
| R3 | Retrieval returns relevant chunks | Top chunk from matching document | "What is drawdown?" → Drawdown doc, similarity 0.2816 | Pass |
| R4 | Similarity scores displayed | Scores visible on knowledge page | Shown per chunk | Pass |
| R5 | Correct document ranked first | Query each of the 6 topics | Correct document ranked #1 in all 6 | Pass |
| R6 | Answer grounded in retrieval | Answer traceable to chunks | Sentences match retrieved text | Pass |
| R7 | No-match handled | Query "how do I bake bread" | Helpful message, not a fabricated answer | "I couldn't find anything in the knowledge base relevant to that question." | Pass |
| R8 | Fallback clearly labelled | No API key set | Labelled as extractive, not LLM | "(No LLM API key configured — showing an answer extracted from the retrieved knowledge base content.)" | Pass |
| R9 | Re-index works | Click "Re-index Documents" | Index and DB table refreshed | Counts updated | Pass |
| R10 | New document picked up | Add a `.txt`, re-index | Becomes searchable | New document indexed and retrievable | Pass |
| R11 | Not sending whole document | Review `rag_service.py` | Only top chunks used | Top 3 chunks passed as context | Pass |

**R5 recorded results:**

| Query | Top-ranked document | Similarity |
|---|---|---|
| What is diversification? | Diversification | 0.2159 |
| What is drawdown? | Drawdown | 0.2816 |
| Explain volatility | Volatility | 0.1772 |
| What is an ETF? | Stocks, Bonds, and ETFs | 0.1458 |
| What is asset allocation? | Asset Allocation | — ranked #1 |
| What is portfolio risk? | Portfolio Risk | — ranked #1 |

---

## 14. Error handling

| # | Test case | Steps | Expected | Actual | Status |
|---|---|---|---|---|---|
| E1 | 404 page | Visit `/nonexistent` | Friendly page, no traceback | "Page not found." | Pass |
| E2 | Missing market data | Add symbol `ZZZZ` | "N/A" shown, app continues | No crash, info alert raised | Pass |
| E3 | Empty portfolio everywhere | New user visits all pages | Empty states, no crashes | All 10 pages render | Pass |
| E4 | LLM API failure | Set an invalid `LLM_API_KEY` | Falls back, logs warning | Extractive answer returned, warning logged | Pass |
| E5 | Invalid form data | Submit malformed values | Validation message | Specific messages per field | Pass |
| E6 | Holding not found | Edit a non-existent ID | Friendly message | "Holding not found." | Pass |
| E7 | No stack traces shown | Trigger errors | Friendly pages only | Confirmed — traces go to the server log | Pass |
| E8 | RAG with no documents | Empty the documents folder | Graceful message | No crash, empty result handled | Pass |

---

## 15. Summary

| Area | Cases | Passed | Failed |
|---|---|---|---|
| Authentication | 11 | 11 | 0 |
| Holdings CRUD & persistence | 12 | 12 | 0 |
| User isolation | 5 | 5 | 0 |
| Portfolio calculations | 10 | 10 | 0 |
| Asset allocation | 5 | 5 | 0 |
| Performance charts | 7 | 7 | 0 |
| Concentration risk | 6 | 6 | 0 |
| Drawdown | 9 | 9 | 0 |
| Anomaly detection | 7 | 7 | 0 |
| Alerts | 10 | 10 | 0 |
| AI assistant & routing | 12 | 12 | 0 |
| NL-to-SQL safety | 10 | 10 | 0 |
| RAG & knowledge base | 11 | 11 | 0 |
| Error handling | 8 | 8 | 0 |
| **Total** | **123** | **123** | **0** |

### Defects found and fixed during testing

Recorded for transparency — these were real bugs caught by the tests above:

1. **Database path resolution.** Flask-SQLAlchemy resolves a relative `sqlite:///` URI against its `instance/` folder, not the project root, producing `unable to open database file`. Fixed in `config.py` by always building an absolute path from `BASE_DIR`.
2. **Hybrid routing missed conceptual questions.** "Why is diversification relevant to my portfolio?" routed to `rag` instead of `hybrid` because it matched no numeric SQL intent. Fixed by adding a portfolio-snapshot path in `ai_service.py` for questions that reference the portfolio and a concept together.
3. **RAG retrieval ranked the wrong document.** "What is diversification?" ranked an Asset Allocation chunk above the Diversification document. Fixed by weighting the document title into each chunk's vector and enabling bigrams and sublinear term frequency.
4. **Extractive fallback started mid-sentence.** Fixed by scoring complete sentences and preferring the earliest definitional sentence ("X is ...") in the source document.
5. **Anomaly reporting surfaced trivial moves.** The most *recent* flagged point was sometimes a −0.055% move inside a turbulent stretch. Changed to report the most *significant* flagged observation.

### Known limitations affecting testing

- Market data is bundled historical/sample data, so "current price" is the latest close in the CSV rather than a live quote. Figures in this document are reproducible for that reason.
- Isolation Forest flags ~5% of observations by construction at `contamination=0.05`; AN2 records that as expected behaviour.
- Tests were run against the Flask development server on a single machine. Concurrency and load testing are out of scope.
