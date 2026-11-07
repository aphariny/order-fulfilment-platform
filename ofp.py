"""Order Fulfilment Platform - validation prototype (modular-monolith core).
Synthetic data only. SQLite stands in for PostgreSQL; gateway and courier are test doubles.
Purpose: demonstrate that invariants are enforceable by transactions + constraints.
It is NOT a production-capacity or secure-payment claim."""
import sqlite3, hmac, hashlib, time, uuid
from contextlib import contextmanager

SECRET = b"synthetic-test-secret"
MAX_COURIER_ATTEMPTS = 5
MAX_REFUND_ATTEMPTS = 3
DISPATCH_SLA = 24 * 3600   # dispatch within 24 h of payment (planning assumption A-05)
RESERVATION_TTL = 900   # 15 minutes (planning assumption A-04)

def sign(event_id, order_id, amount):
    return hmac.new(SECRET, f"{event_id}|{order_id}|{amount}".encode(), hashlib.sha256).hexdigest()

class GatewayError(Exception): pass
class CourierError(Exception): pass
class StockError(Exception): pass

class Gateway:                       # controlled test interface (status: SIMULATED)
    def __init__(self): self.fail_refunds = 0; self.refunded = {}; self.calls = 0
    def refund(self, key, amount):
        self.calls += 1
        if self.fail_refunds > 0:
            self.fail_refunds -= 1; raise GatewayError("gateway timeout")
        self.refunded.setdefault(key, amount)        # idempotent on key
        return "gw-" + key

class Courier:                       # controlled test interface (status: SIMULATED)
    def __init__(self): self.down_regions = set(); self.created = {}; self.calls = 0
    def create_shipment(self, key, region):
        self.calls += 1
        if region in self.down_regions: raise CourierError("courier API unavailable")
        return self.created.setdefault(key, "CR-" + key[:8])

SCHEMA = """
CREATE TABLE users(id TEXT PRIMARY KEY, name TEXT, role TEXT, region TEXT);
CREATE TABLE sessions(token TEXT PRIMARY KEY, user_id TEXT REFERENCES users(id));
CREATE TABLE region_rules(region TEXT PRIMARY KEY, tax_bp INTEGER, shipping INTEGER, refund_limit INTEGER);
CREATE TABLE products(sku TEXT PRIMARY KEY, price INTEGER CHECK(price>0));
CREATE TABLE stock(sku TEXT PRIMARY KEY REFERENCES products(sku), on_hand INTEGER, reserved INTEGER DEFAULT 0,
                   CHECK(reserved>=0), CHECK(reserved<=on_hand));
CREATE TABLE orders(id TEXT PRIMARY KEY, customer_id TEXT, region TEXT, status TEXT, subtotal INTEGER, tax INTEGER,
                    shipping INTEGER, total INTEGER, created_at REAL, reserve_expires_at REAL, paid_at REAL, picked INTEGER DEFAULT 0);
CREATE TABLE order_items(order_id TEXT, sku TEXT, qty INTEGER, unit_price INTEGER);
CREATE TABLE payments(id TEXT PRIMARY KEY, order_id TEXT, gateway_event_id TEXT UNIQUE, amount INTEGER, applied INTEGER, created_at REAL);
CREATE UNIQUE INDEX one_applied_payment ON payments(order_id) WHERE applied=1;
CREATE TABLE shipments(id TEXT PRIMARY KEY, order_id TEXT UNIQUE, courier_ref TEXT, sync_status TEXT);
CREATE TABLE outbox(id TEXT PRIMARY KEY, shipment_id TEXT, region TEXT, status TEXT, attempts INTEGER, next_attempt REAL);
CREATE TABLE scan_events(event_id TEXT PRIMARY KEY, kind TEXT, order_id TEXT, sku TEXT, qty INTEGER, result TEXT);
CREATE TABLE stock_corrections(id TEXT PRIMARY KEY, sku TEXT, delta INTEGER, status TEXT, event_id TEXT);
CREATE TABLE refunds(id TEXT PRIMARY KEY, order_id TEXT, amount INTEGER, status TEXT, requested_by TEXT, approved_by TEXT,
                     reason TEXT, attempts INTEGER DEFAULT 0, region TEXT);
CREATE TABLE audit(id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, actor TEXT, action TEXT, entity TEXT, detail TEXT);
"""
ACTIVE_REFUND = ("REQUESTED", "APPROVED", "EXECUTING", "RETRY_PENDING", "EXECUTED")

class Platform:
    def __init__(self, path, gateway, courier):
        self.path = path; self.gw = gateway; self.courier = courier
        self.now = time.time; self.hook_in_callback = None
        c = self._conn(); c.executescript(SCHEMA); c.execute("PRAGMA journal_mode=WAL"); c.close()

    def _conn(self):
        c = sqlite3.connect(self.path, timeout=120, isolation_level=None)
        c.row_factory = sqlite3.Row; c.execute("PRAGMA foreign_keys=ON"); return c

    @contextmanager
    def tx(self):
        c = self._conn()
        try:
            c.execute("BEGIN IMMEDIATE"); yield c; c.execute("COMMIT")
        except BaseException:
            try: c.execute("ROLLBACK")
            except Exception: pass
            raise
        finally: c.close()

    # ---------- helpers ----------
    def audit(self, c, actor, action, entity, detail=""):
        c.execute("INSERT INTO audit(ts,actor,action,entity,detail) VALUES(?,?,?,?,?)",
                  (self.now(), actor, action, entity, detail))
    def actor(self, c, token):                      # identity comes from the SERVER session, never from the request
        return c.execute("SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=?", (token,)).fetchone()
    def deny(self, c, a, action, entity, code):
        self.audit(c, a["id"] if a else "anonymous", "DENIED:" + action, entity, code)
        return {"ok": False, "code": code}
    def refundable(self, c, order_id):
        paid = c.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE order_id=? AND applied=1", (order_id,)).fetchone()[0]
        used = c.execute("SELECT COALESCE(SUM(amount),0) FROM refunds WHERE order_id=? AND status IN (%s)"
                         % ",".join("?" * len(ACTIVE_REFUND)), (order_id, *ACTIVE_REFUND)).fetchone()[0]
        return paid - used

    # ---------- checkout ----------
    def place_order(self, token, items, region, client_total=None):
        try:
            with self.tx() as c:
                a = self.actor(c, token)
                if not a or a["role"] != "customer": return self.deny(c, a, "place_order", "-", "FORBIDDEN")
                rule = c.execute("SELECT * FROM region_rules WHERE region=?", (region,)).fetchone()
                if not rule: return {"ok": False, "code": "UNKNOWN_REGION"}
                subtotal = 0
                for sku, qty in items:
                    p = c.execute("SELECT price FROM products WHERE sku=?", (sku,)).fetchone()   # server-side price
                    n = c.execute("UPDATE stock SET reserved=reserved+? WHERE sku=? AND on_hand-reserved>=?", (qty, sku, qty)).rowcount
                    if n == 0: raise StockError(sku)
                    subtotal += p["price"] * qty
                tax = (subtotal * rule["tax_bp"] + 5000) // 10000
                total = subtotal + tax + rule["shipping"]
                oid = "O-" + uuid.uuid4().hex[:8]
                c.execute("INSERT INTO orders(id,customer_id,region,status,subtotal,tax,shipping,total,created_at,reserve_expires_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                          (oid, a["id"], region, "PLACED", subtotal, tax, rule["shipping"], total, self.now(), self.now() + RESERVATION_TTL))
                for sku, qty in items:
                    pr = c.execute("SELECT price FROM products WHERE sku=?", (sku,)).fetchone()["price"]
                    c.execute("INSERT INTO order_items VALUES(?,?,?,?)", (oid, sku, qty, pr))
                note = "" if client_total in (None, total) else f"client_total {client_total} ignored"
                self.audit(c, a["id"], "ORDER_PLACED", oid, f"total={total} {note}")
                return {"ok": True, "order_id": oid, "total": total}
        except StockError as e:
            return {"ok": False, "code": "OUT_OF_STOCK", "sku": str(e)}


    # ---------- reservation expiry (added in v2 after validation scenario V7 failed) ----------
    def expire_reservations(self):
        n = 0
        with self.tx() as c:
            for o in c.execute("SELECT id FROM orders WHERE status='PLACED' AND reserve_expires_at<?", (self.now(),)).fetchall():
                c.execute("UPDATE orders SET status='CANCELLED' WHERE id=?", (o["id"],))
                for it in c.execute("SELECT * FROM order_items WHERE order_id=?", (o["id"],)).fetchall():
                    c.execute("UPDATE stock SET reserved=reserved-? WHERE sku=?", (it["qty"], it["sku"]))
                self.audit(c, "system", "RESERVATION_EXPIRED", o["id"]); n += 1
        return n

    # ---------- payment callback (idempotent) ----------
    def payment_callback(self, event_id, order_id, amount, signature):
        with self.tx() as c:
            if not hmac.compare_digest(signature, sign(event_id, order_id, amount)):
                self.audit(c, "gateway", "BAD_SIGNATURE", order_id, event_id); return {"ok": False, "code": "BAD_SIGNATURE"}
            if c.execute("SELECT 1 FROM payments WHERE gateway_event_id=?", (event_id,)).fetchone():
                return {"ok": True, "code": "DUPLICATE_IGNORED"}
            o = c.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
            if not o: return {"ok": False, "code": "UNKNOWN_ORDER"}
            if amount != o["total"]:
                self.audit(c, "gateway", "AMOUNT_MISMATCH", order_id, f"{amount}!={o['total']}")
                return {"ok": False, "code": "AMOUNT_MISMATCH"}
            if o["status"] != "PLACED":
                return self._late_payment(c, o, event_id, amount)
            c.execute("INSERT INTO payments VALUES(?,?,?,?,1,?)", (uuid.uuid4().hex, order_id, event_id, amount, self.now()))
            if self.hook_in_callback: self.hook_in_callback()
            c.execute("UPDATE orders SET status='PAID', paid_at=? WHERE id=?", (self.now(), order_id))
            sid = "S-" + uuid.uuid4().hex[:8]
            c.execute("INSERT INTO shipments VALUES(?,?,NULL,'PENDING_SYNC')", (sid, order_id))
            c.execute("INSERT INTO outbox VALUES(?,?,?,'PENDING',0,0)", (uuid.uuid4().hex, sid, o["region"]))
            self.audit(c, "gateway", "PAYMENT_APPLIED", order_id, event_id)
            return {"ok": True, "code": "APPLIED"}

    def _late_payment(self, c, o, event_id, amount):   # payment for a non-PLACED order is never silently kept
        c.execute("INSERT INTO payments VALUES(?,?,?,?,0,?)", (uuid.uuid4().hex, o["id"], event_id, amount, self.now()))
        self.audit(c, "gateway", "LATE_PAYMENT", o["id"], f"status={o['status']}")
        return {"ok": False, "code": "ORDER_NOT_PAYABLE"}

    # ---------- courier synchronisation via outbox ----------
    def process_outbox(self):
        with self.tx() as c:
            rows = c.execute("SELECT * FROM outbox WHERE status='PENDING' AND next_attempt<=?", (self.now(),)).fetchall()
        done = failed = 0
        for r in rows:
            try:
                ref = self.courier.create_shipment(r["shipment_id"], r["region"])   # idempotency key = shipment id
                with self.tx() as c:
                    c.execute("UPDATE shipments SET courier_ref=?, sync_status='SYNCED' WHERE id=?", (ref, r["shipment_id"]))
                    c.execute("UPDATE outbox SET status='DONE' WHERE id=?", (r["id"],)); done += 1
            except CourierError:
                with self.tx() as c:
                    att = r["attempts"] + 1
                    st = "FAILED_ALERT" if att >= MAX_COURIER_ATTEMPTS else "PENDING"
                    c.execute("UPDATE outbox SET attempts=?, status=?, next_attempt=? WHERE id=?",
                              (att, st, self.now() + 2 ** att, r["id"]))
                    if st != "PENDING":
                        c.execute("UPDATE shipments SET sync_status='SYNC_FAILED' WHERE id=?", (r["shipment_id"],))
                        self.audit(c, "system", "COURIER_SYNC_ALERT", r["shipment_id"])
                failed += 1
        return {"done": done, "failed": failed}

    # ---------- warehouse events (idempotent) ----------
    def ingest_event(self, token, event_id, kind, order_id=None, sku=None, qty=0):
        with self.tx() as c:
            a = self.actor(c, token)
            allowed = {"PICK_CONFIRM": ("picker",), "STOCK_DELTA": ("picker", "store_manager"), "DELIVERED": ("courier_system",)}
            if not a or a["role"] not in allowed.get(kind, ()): return self.deny(c, a, "ingest_" + kind, order_id or sku, "FORBIDDEN")
            if c.execute("SELECT 1 FROM scan_events WHERE event_id=?", (event_id,)).fetchone():
                return {"ok": True, "code": "DUPLICATE_IGNORED"}
            result = "APPLIED"
            if kind == "PICK_CONFIRM":
                o = c.execute("SELECT status FROM orders WHERE id=?", (order_id,)).fetchone()
                if o and o["status"] == "PAID":
                    c.execute("UPDATE orders SET status='PACKED', picked=1 WHERE id=?", (order_id,))
                elif o and o["status"] in ("PACKED", "DISPATCHED", "DELIVERED", "CLOSED"): result = "NOOP"
                else: result = "REJECTED_NOT_PAID"
            elif kind == "STOCK_DELTA":
                if qty >= 0:
                    c.execute("UPDATE stock SET on_hand=on_hand+? WHERE sku=?", (qty, sku))
                else:                                    # negative corrections need a human decision
                    c.execute("INSERT INTO stock_corrections VALUES(?,?,?,'PENDING',?)", (uuid.uuid4().hex, sku, qty, event_id))
                    result = "PENDING_MANAGER_APPROVAL"
            elif kind == "DELIVERED":
                n = c.execute("UPDATE orders SET status='DELIVERED' WHERE id=? AND status='DISPATCHED'", (order_id,)).rowcount
                result = "APPLIED" if n else "REJECTED_NOT_DISPATCHED"
            c.execute("INSERT INTO scan_events VALUES(?,?,?,?,?,?)", (event_id, kind, order_id, sku, qty, result))
            return {"ok": result in ("APPLIED", "NOOP", "PENDING_MANAGER_APPROVAL"), "code": result}

    def dispatch(self, token, order_id):
        with self.tx() as c:
            a = self.actor(c, token)
            if not a or a["role"] != "picker": return self.deny(c, a, "dispatch", order_id, "FORBIDDEN")
            o = c.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
            if not o: return {"ok": False, "code": "UNKNOWN_ORDER"}
            paid = c.execute("SELECT 1 FROM payments WHERE order_id=? AND applied=1", (order_id,)).fetchone()
            if not paid or o["status"] == "PLACED": return self.deny(c, a, "dispatch", order_id, "NOT_PAID")
            if o["status"] != "PACKED" or not o["picked"]: return self.deny(c, a, "dispatch", order_id, "NOT_PICKED")
            s = c.execute("SELECT courier_ref FROM shipments WHERE order_id=?", (order_id,)).fetchone()
            if not s or not s["courier_ref"]: return self.deny(c, a, "dispatch", order_id, "NO_COURIER_LABEL")
            for it in c.execute("SELECT * FROM order_items WHERE order_id=?", (order_id,)).fetchall():
                c.execute("UPDATE stock SET on_hand=on_hand-?, reserved=reserved-? WHERE sku=?", (it["qty"], it["qty"], it["sku"]))
            c.execute("UPDATE orders SET status='DISPATCHED' WHERE id=?", (order_id,))
            self.audit(c, a["id"], "DISPATCHED", order_id)
            return {"ok": True, "code": "DISPATCHED"}

    def approve_stock_correction(self, token, cid):
        with self.tx() as c:
            a = self.actor(c, token)
            if not a or a["role"] != "store_manager": return self.deny(c, a, "approve_stock_correction", cid, "FORBIDDEN")
            r = c.execute("SELECT * FROM stock_corrections WHERE id=? AND status='PENDING'", (cid,)).fetchone()
            if not r: return {"ok": False, "code": "NOT_PENDING"}
            s = c.execute("SELECT * FROM stock WHERE sku=?", (r["sku"],)).fetchone()
            if s["on_hand"] + r["delta"] < s["reserved"]:
                return {"ok": False, "code": "WOULD_BREAK_RESERVATIONS"}
            c.execute("UPDATE stock SET on_hand=on_hand+? WHERE sku=?", (r["delta"], r["sku"]))
            c.execute("UPDATE stock_corrections SET status='APPROVED' WHERE id=?", (cid,))
            self.audit(c, a["id"], "STOCK_CORRECTION_APPROVED", cid)
            return {"ok": True, "code": "APPROVED"}

    # ---------- access-controlled order view ----------
    def view_order(self, token, order_id, claimed_role=None):      # claimed_role is deliberately ignored
        with self.tx() as c:
            a = self.actor(c, token)
            o = c.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
            if not a or not o: return self.deny(c, a, "view_order", order_id, "NOT_FOUND_OR_FORBIDDEN")
            if a["role"] == "customer" and o["customer_id"] != a["id"]:
                return self.deny(c, a, "view_order", order_id, "NOT_FOUND_OR_FORBIDDEN")
            if a["role"] == "store_manager" and o["region"] != a["region"]:
                return self.deny(c, a, "view_order", order_id, "NOT_FOUND_OR_FORBIDDEN")
            if a["role"] not in ("customer", "support_agent", "finance_reviewer", "store_manager", "picker", "administrator"):
                return self.deny(c, a, "view_order", order_id, "NOT_FOUND_OR_FORBIDDEN")
            v = {"id": o["id"], "status": o["status"], "total": o["total"], "region": o["region"]}
            if a["role"] in ("customer", "finance_reviewer"):
                v["payment_events"] = [r[0] for r in c.execute("SELECT gateway_event_id FROM payments WHERE order_id=?", (order_id,))]
            return {"ok": True, "view": v}

    # ---------- refunds ----------
    def request_refund(self, token, order_id, amount, reason):
        with self.tx() as c:
            a = self.actor(c, token)
            o = c.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
            if not a or not o or a["role"] not in ("customer", "support_agent"): return self.deny(c, a, "request_refund", order_id, "FORBIDDEN")
            if a["role"] == "customer" and o["customer_id"] != a["id"]: return self.deny(c, a, "request_refund", order_id, "FORBIDDEN")
            if o["status"] not in ("PAID", "DELIVERED"): return {"ok": False, "code": "STATUS_NOT_REFUNDABLE"}
            if amount <= 0 or amount > self.refundable(c, order_id): return {"ok": False, "code": "EXCEEDS_REFUNDABLE"}
            rid = "R-" + uuid.uuid4().hex[:8]
            c.execute("INSERT INTO refunds(id,order_id,amount,status,requested_by,reason,region) VALUES(?,?,?,?,?,?,?)",
                      (rid, order_id, amount, "REQUESTED", a["id"], reason, o["region"]))
            self.audit(c, a["id"], "REFUND_REQUESTED", rid, f"amount={amount}")
            return {"ok": True, "refund_id": rid}

    def approve_refund(self, token, refund_id, approve=True, claimed_role=None):   # claimed_role ignored
        with self.tx() as c:
            a = self.actor(c, token)
            r = c.execute("SELECT * FROM refunds WHERE id=?", (refund_id,)).fetchone()
            if not a or not r or a["role"] not in ("store_manager", "finance_reviewer"):
                return self.deny(c, a, "approve_refund", refund_id, "FORBIDDEN")
            if a["id"] == r["requested_by"]: return self.deny(c, a, "approve_refund", refund_id, "SELF_APPROVAL")
            rule = c.execute("SELECT refund_limit FROM region_rules WHERE region=?", (r["region"],)).fetchone()
            if a["role"] == "store_manager" and (a["region"] != r["region"] or r["amount"] > rule["refund_limit"]):
                return self.deny(c, a, "approve_refund", refund_id, "ABOVE_APPROVER_LIMIT")
            if r["status"] != "REQUESTED": return {"ok": False, "code": "NOT_PENDING"}
            st = "APPROVED" if approve else "REJECTED"
            c.execute("UPDATE refunds SET status=?, approved_by=? WHERE id=?", (st, a["id"], refund_id))
            self.audit(c, a["id"], "REFUND_" + st, refund_id)
            return {"ok": True, "code": st}

    def execute_refund(self, token, refund_id):
        with self.tx() as c:
            a = self.actor(c, token)
            if not a or a["role"] != "finance_reviewer": return self.deny(c, a, "execute_refund", refund_id, "FORBIDDEN")
            n = c.execute("UPDATE refunds SET status='EXECUTING' WHERE id=? AND status IN ('APPROVED','RETRY_PENDING') AND approved_by IS NOT NULL",
                          (refund_id,)).rowcount
            if n == 0: return self.deny(c, a, "execute_refund", refund_id, "NOT_APPROVED")
            r = c.execute("SELECT * FROM refunds WHERE id=?", (refund_id,)).fetchone()
        try:
            self.gw.refund(refund_id, r["amount"])                       # idempotency key = refund id
            with self.tx() as c:
                c.execute("UPDATE refunds SET status='EXECUTED' WHERE id=?", (refund_id,))
                o = c.execute("SELECT * FROM orders WHERE id=?", (r["order_id"],)).fetchone()
                paid = c.execute("SELECT SUM(amount) FROM payments WHERE order_id=? AND applied=1", (r["order_id"],)).fetchone()[0]
                done = c.execute("SELECT SUM(amount) FROM refunds WHERE order_id=? AND status='EXECUTED'", (r["order_id"],)).fetchone()[0]
                if done == paid:
                    if o["status"] == "PAID":
                        c.execute("UPDATE orders SET status='CANCELLED' WHERE id=?", (o["id"],))
                        for it in c.execute("SELECT * FROM order_items WHERE order_id=?", (o["id"],)).fetchall():
                            c.execute("UPDATE stock SET reserved=reserved-? WHERE sku=?", (it["qty"], it["sku"]))
                    elif o["status"] == "DELIVERED":
                        c.execute("UPDATE orders SET status='CLOSED' WHERE id=?", (o["id"],))
                self.audit(c, a["id"], "REFUND_EXECUTED", refund_id)
            return {"ok": True, "code": "EXECUTED"}
        except GatewayError:
            with self.tx() as c:
                att = r["attempts"] + 1
                st = "ROLLED_BACK" if att >= MAX_REFUND_ATTEMPTS else "RETRY_PENDING"
                c.execute("UPDATE refunds SET status=?, attempts=? WHERE id=?", (st, att, refund_id))
                self.audit(c, a["id"], "REFUND_" + st, refund_id, f"attempt {att}")
            return {"ok": False, "code": st}

    def overdue_dispatches(self):
        with self.tx() as c:
            return [r["id"] for r in c.execute("SELECT id FROM orders WHERE status IN ('PAID','PACKED') AND paid_at<?", (self.now() - DISPATCH_SLA,))]

    # ---------- reporting ----------
    def report(self):
        with self.tx() as c:
            rows = {}
            for r in c.execute("SELECT region FROM region_rules"): rows[r[0]] = {"sales": 0, "refunds_executed": 0, "pending_events": 0, "unapplied_payments": 0}
            for r in c.execute("SELECT o.region, SUM(p.amount) s FROM payments p JOIN orders o ON o.id=p.order_id WHERE p.applied=1 GROUP BY o.region"):
                rows[r["region"]]["sales"] = r["s"]
            for r in c.execute("SELECT region, SUM(amount) s FROM refunds WHERE status='EXECUTED' GROUP BY region"):
                rows[r["region"]]["refunds_executed"] = r["s"]
            for r in c.execute("SELECT region, COUNT(*) n FROM outbox WHERE status!='DONE' GROUP BY region"):
                rows[r["region"]]["pending_events"] = r["n"]
            for r in c.execute("SELECT o.region, COUNT(*) n FROM payments p JOIN orders o ON o.id=p.order_id WHERE p.applied=0 GROUP BY o.region"):
                rows[r["region"]]["unapplied_payments"] = r["n"]
            return rows
