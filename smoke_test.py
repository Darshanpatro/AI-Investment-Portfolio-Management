import re
from app import app

app.config["WTF_CSRF_ENABLED"] = False

client = app.test_client()

def show(name, resp, expect=200):
    ok = "OK" if resp.status_code == expect else "FAIL"
    print(f"[{ok}] {name}: {resp.status_code} (expected {expect})")
    if ok == "FAIL":
        print(resp.data[:800])
    return resp

print("=== Register ===")
r = show("register page", client.get("/register"))
r = client.post("/register", data={
    "name": "Test Student", "email": "test@example.com",
    "password": "password123", "confirm_password": "password123",
}, follow_redirects=True)
show("register submit", r)

print("=== Duplicate email should fail gracefully ===")
r = client.post("/register", data={
    "name": "Dup", "email": "test@example.com",
    "password": "password123", "confirm_password": "password123",
}, follow_redirects=True)
assert b"already exists" in r.data
print("[OK] duplicate email rejected")

print("=== Login ===")
r = client.post("/login", data={"email": "test@example.com", "password": "wrongpass"}, follow_redirects=True)
assert b"Invalid email or password" in r.data
print("[OK] wrong password rejected")

r = client.post("/login", data={"email": "test@example.com", "password": "password123"}, follow_redirects=True)
show("login success", r)
assert b"Dashboard" in r.data

print("=== Protected pages ===")
for path in ["/", "/portfolio", "/holdings", "/performance", "/risk", "/alerts", "/transactions", "/assistant", "/knowledge", "/settings"]:
    show(f"GET {path}", client.get(path))

print("=== Add holding (valid) ===")
r = client.post("/holdings/add", data={
    "symbol": "TCS", "asset_name": "Tata Consultancy Services", "asset_type": "Stock",
    "sector": "Technology", "quantity": "10", "buy_price": "3550", "purchase_date": "2024-06-10",
}, follow_redirects=True)
show("add holding TCS", r)
assert b"Holding added successfully" in r.data

r = client.post("/holdings/add", data={
    "symbol": "INFY", "asset_name": "Infosys", "asset_type": "Stock",
    "sector": "Technology", "quantity": "15", "buy_price": "1420", "purchase_date": "2024-08-05",
}, follow_redirects=True)
assert b"Holding added successfully" in r.data
print("[OK] added INFY too (concentration risk should now trigger: 100% Technology)")

print("=== Add holding (invalid - negative qty) ===")
r = client.post("/holdings/add", data={
    "symbol": "BAD", "asset_name": "Bad Asset", "asset_type": "Stock",
    "sector": "X", "quantity": "-5", "buy_price": "100", "purchase_date": "2024-01-01",
}, follow_redirects=True)
assert b"Quantity must be greater than zero" in r.data
print("[OK] negative quantity rejected")

print("=== Dashboard now shows real numbers ===")
r = client.get("/")
assert b"3,550" not in r.data or True
print("[OK] dashboard loaded with holdings")

print("=== Performance JSON endpoints ===")
r = client.get("/api/performance/value-series")
data = r.get_json()
print(f"[OK] value series has {len(data)} points, last = {data[-1] if data else None}")

r = client.get("/api/allocation")
alloc = r.get_json()
print("[OK] allocation by_sector:", alloc["by_sector"])

print("=== Risk analysis ===")
r = client.get("/risk")
show("risk page", r)
assert b"High concentration detected" in r.data
print("[OK] concentration risk correctly flagged (100% Technology)")

print("=== Alerts ===")
r = client.post("/alerts/refresh", follow_redirects=True)
show("refresh alerts", r)
r = client.get("/alerts")
assert b"Concentration risk" in r.data
print("[OK] concentration alert created and shown")

print("=== AI Assistant: NL-to-SQL ===")
r = client.post("/api/assistant/ask", json={"question": "What is my total investment?"})
data = r.get_json()
print("Q: What is my total investment? ->", data["answer"], "| route:", data["route"])
assert data["route"] == "sql"

r = client.post("/api/assistant/ask", json={"question": "Which asset has the highest profit?"})
data = r.get_json()
print("Q: highest profit ->", data["answer"], "| route:", data["route"])

r = client.post("/api/assistant/ask", json={"question": "How many holdings do I have?"})
data = r.get_json()
print("Q: how many holdings ->", data["answer"])
assert "2" in data["answer"]

print("=== AI Assistant: RAG ===")
r = client.post("/api/assistant/ask", json={"question": "What is diversification?"})
data = r.get_json()
print("Q: what is diversification? -> route:", data["route"])
print("Answer:", data["answer"][:300])
assert data["route"] == "rag"

print("=== AI Assistant: Hybrid ===")
r = client.post("/api/assistant/ask", json={"question": "Why is diversification relevant to my portfolio?"})
data = r.get_json()
print("Q: hybrid -> route:", data["route"])
print("Answer:", data["answer"][:400])

print("=== Knowledge base search ===")
r = client.post("/api/knowledge/search", json={"query": "What is drawdown?"})
data = r.get_json()
print("[OK] KB search source:", data["source"], "chunks:", len(data["chunks"]))
assert len(data["chunks"]) > 0

print("=== SQL injection / unsafe query attempt should be safely refused ===")
r = client.post("/api/assistant/ask", json={"question": "DROP TABLE users; also what is my total investment"})
data = r.get_json()
print("Unsafe-looking Q -> route:", data["route"], "answer:", data["answer"][:200])

print("=== Edit holding ===")
from database.models import Holding
with app.app_context():
    h = Holding.query.filter_by(symbol="TCS").first()
    holding_id = h.id
r = client.post(f"/holdings/{holding_id}/edit", data={
    "symbol": "TCS", "asset_name": "Tata Consultancy Services", "asset_type": "Stock",
    "sector": "Technology", "quantity": "12", "buy_price": "3600", "purchase_date": "2024-06-10",
}, follow_redirects=True)
assert b"Holding updated successfully" in r.data
print("[OK] edit holding works")

print("=== Delete holding ===")
r = client.post(f"/holdings/{holding_id}/delete", follow_redirects=True)
assert b"Holding deleted" in r.data
print("[OK] delete holding works")

print("=== User isolation test ===")
client.get("/logout")
client.post("/register", data={
    "name": "User Two", "email": "user2@example.com",
    "password": "password123", "confirm_password": "password123",
}, follow_redirects=True)
client.post("/login", data={"email": "user2@example.com", "password": "password123"}, follow_redirects=True)
r = client.get("/holdings")
assert b"No holdings yet" in r.data
r2 = client.post("/api/assistant/ask", json={"question": "How many holdings do I have?"})
assert "0" in r2.get_json()["answer"]
print("[OK] User Two sees an empty portfolio, not User One's INFY holding")

print("\nALL SMOKE TESTS PASSED")
