import os, sys, json, time, tempfile, threading, random, uuid
from concurrent.futures import ThreadPoolExecutor
from ofp import *
from edge import EdgeNode
from invariants import check_invariants

RESULTS = []
def new(regions=("R01","R02"), stock=None):
    d = tempfile.mkdtemp(); p = Platform(os.path.join(d, "t.db"), Gateway(), Courier())
    with p.tx() as c:
        for i, r in enumerate(regions):
            c.execute("INSERT INTO region_rules VALUES(?,?,?,?)", (r, 1800 if i % 2 == 0 else 1200, 40 + 10 * i, 2000 + 1000 * (i % 2)))
        c.execute("INSERT INTO products VALUES('SKU-A',1000),('SKU-LAST',2500),('SKU-B',300)")
        s = stock or {"SKU-A": 100, "SKU-LAST": 1, "SKU-B": 10000}
        for k, v in s.items(): c.execute("INSERT INTO stock(sku,on_hand) VALUES(?,?)", (k, v))
        users = [("cust1","customer","R01"),("cust2","customer","R01"),("picker1","picker","R01"),("support1","support_agent","R01"),
                 ("mgr1","store_manager","R01"),("mgr2","store_manager","R02"),("fin1","finance_reviewer","R01"),("admin1","administrator","R01"),
                 ("courier","courier_system","R01")]
        for u, role, reg in users:
            c.execute("INSERT INTO users VALUES(?,?,?,?)", (u, u, role, reg)); c.execute("INSERT INTO sessions VALUES(?,?)", ("tok_" + u, u))
    return p
T = lambda u: "tok_" + u
def paid_order(p, cust="cust1", items=(("SKU-A",1),), region="R01"):
    o = p.place_order(T(cust), list(items), region); assert o["ok"], o
    eid = "gw-" + uuid.uuid4().hex[:8]
    r = p.payment_callback(eid, o["order_id"], o["total"], sign(eid, o["order_id"], o["total"])); assert r["ok"], r
    return o["order_id"], o["total"], eid
def packed_synced(p, **kw):
    oid, tot, eid = paid_order(p, **kw)
    p.ingest_event(T("picker1"), "pk-" + oid, "PICK_CONFIRM", order_id=oid); p.process_outbox(); return oid, tot
def delivered(p, **kw):
    oid, tot = packed_synced(p, **kw); assert p.dispatch(T("picker1"), oid)["ok"]
    assert p.ingest_event(T("courier"), "dl-" + oid, "DELIVERED", order_id=oid)["ok"]; return oid, tot
def record(sid, title, predicted, observed, passed, extra=None):
    inv = None
    RESULTS.append(dict(id=sid, title=title, predicted=predicted, observed=observed, passed=passed, **(extra or {})))
    print(f"[{'PASS' if passed else 'FAIL'}] {sid} {title}\n   predicted: {predicted}\n   observed : {observed}")

def inv_ok(p):
    r = check_invariants(p); return all(v[0] for v in r.values()), r

# ---------------- Q5 scenarios ----------------
def v1():
    wins = []; ok_all = True
    for t in range(20):
        p = new(); res = {}
        b = threading.Barrier(2)
        def go(u):
            b.wait(); res[u] = p.place_order(T(u), [("SKU-LAST", 1)], "R01")
        th = [threading.Thread(target=go, args=(u,)) for u in ("cust1","cust2")]
        [x.start() for x in th]; [x.join() for x in th]
        n_ok = sum(r["ok"] for r in res.values()); n_oos = sum(r.get("code") == "OUT_OF_STOCK" for r in res.values())
        with p.tx() as c: rs = c.execute("SELECT reserved FROM stock WHERE sku='SKU-LAST'").fetchone()[0]
        okinv, _ = inv_ok(p)
        wins.append((n_ok, n_oos, rs)); ok_all &= (n_ok == 1 and n_oos == 1 and rs == 1 and okinv)
    record("V1", "Two customers buy the last unit (20 repeated trials)", "Exactly one order is created, the other receives OUT_OF_STOCK, reserved=1, invariants hold in every trial",
           f"{sum(w==(1,1,1) for w in wins)}/20 trials gave (1 order, 1 OUT_OF_STOCK, reserved=1); invariants I1-I8 held in all trials", ok_all)
def v2():
    p = new(); oid = p.place_order(T("cust1"), [("SKU-A", 2)], "R01"); eid = "gw-DUP1"
    sig = sign(eid, oid["order_id"], oid["total"]); p.hook_in_callback = lambda: time.sleep(0.3)   # keeps original in-flight
    out = []; th = [threading.Thread(target=lambda: out.append(p.payment_callback(eid, oid["order_id"], oid["total"], sig))) for _ in range(8)]
    [x.start() for x in th]; [x.join() for x in th]; p.hook_in_callback = None
    codes = sorted(r["code"] for r in out)
    with p.tx() as c:
        n = [c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("payments", "shipments", "outbox")]
        na = c.execute("SELECT COUNT(*) FROM audit WHERE action='PAYMENT_APPLIED'").fetchone()[0]
    okinv, _ = inv_ok(p)
    record("V2", "Same payment callback delivered 8 times while the first is still processing",
           "1 APPLIED + 7 DUPLICATE_IGNORED; exactly 1 payment, 1 shipment, 1 outbox message, 1 audit entry",
           f"{codes.count('APPLIED')} APPLIED + {codes.count('DUPLICATE_IGNORED')} DUPLICATE_IGNORED; payments={n[0]}, shipments={n[1]}, outbox={n[2]}, PAYMENT_APPLIED audit rows={na}",
           codes.count("APPLIED") == 1 and codes.count("DUPLICATE_IGNORED") == 7 and n == [1,1,1] and na == 1 and okinv)
def v3():
    p = new(); oid, tot = delivered(p, items=(("SKU-A", 4),))
    r = p.request_refund(T("support1"), oid, 1500, "damaged"); rid = r["refund_id"]
    pre = p.execute_refund(T("fin1"), rid); calls0 = p.gw.calls            # not yet approved
    p.approve_refund(T("mgr1"), rid); p.gw.fail_refunds = 1
    f1 = p.execute_refund(T("fin1"), rid); f2 = p.execute_refund(T("fin1"), rid)
    keys = len(p.gw.refunded)
    # rollback path
    r2 = p.request_refund(T("support1"), oid, 1000, "second"); rid2 = r2["refund_id"]
    p.approve_refund(T("fin1"), rid2); p.gw.fail_refunds = 3
    g = [p.execute_refund(T("fin1"), rid2)["code"] for _ in range(3)]
    with p.tx() as c: refundable = p.refundable(c, oid)
    okinv, _ = inv_ok(p)
    ok = (pre["code"] == "NOT_APPROVED" and calls0 == 0 and f1["code"] == "RETRY_PENDING" and f2["code"] == "EXECUTED" and keys == 1
          and g == ["RETRY_PENDING", "RETRY_PENDING", "ROLLED_BACK"] and refundable == tot - 1500 and okinv)
    record("V3", "Refund: execute before approval; approved refund fails at gateway; retry; repeated failure",
           "Pre-approval execution denied with 0 gateway calls; 1st failure -> RETRY_PENDING, retry -> EXECUTED with 1 gateway refund; 3 straight failures -> ROLLED_BACK and refundable amount restored",
           f"pre-approval={pre['code']} (gateway calls={calls0}); first attempt={f1['code']}, retry={f2['code']}, distinct gateway refunds={keys}; 3 failures={g}; refundable after rollback={refundable} (total {tot} - executed 1500)", ok)
def v4():
    p = new(); oid = p.place_order(T("cust1"), [("SKU-A", 1)], "R01")["order_id"]
    a = p.dispatch(T("picker1"), oid)
    eid = "gw-4"; o = p.place_order(T("cust1"), [("SKU-A", 1)], "R01"); oid2 = o["order_id"]
    p.payment_callback(eid, oid2, o["total"], sign(eid, oid2, o["total"]))
    b = p.dispatch(T("picker1"), oid2)
    p.ingest_event(T("picker1"), "pk4", "PICK_CONFIRM", order_id=oid2)
    c_ = p.dispatch(T("picker1"), oid2)                           # courier not yet synced
    p.process_outbox(); d = p.dispatch(T("picker1"), oid2)
    pk = p.ingest_event(T("picker1"), "pk4b", "PICK_CONFIRM", order_id=oid)   # pick for unpaid order
    okinv, _ = inv_ok(p)
    codes = (a["code"], b["code"], c_["code"], d["code"], pk["code"])
    record("V4", "Dispatch without confirmed payment / without pick confirmation / without courier label",
           "unpaid -> NOT_PAID; paid but not picked -> NOT_PICKED; picked but no label -> NO_COURIER_LABEL; all met -> DISPATCHED; pick scan for unpaid order rejected",
           "dispatch results: " + ", ".join(codes[:4]) + f"; pick scan on unpaid order -> {codes[4]}",
           codes == ("NOT_PAID","NOT_PICKED","NO_COURIER_LABEL","DISPATCHED","REJECTED_NOT_PAID") and okinv)
def v5():
    p = new(); p.courier.down_regions.add("R01"); oid, tot, _ = paid_order(p)
    r1 = p.process_outbox()
    with p.tx() as c:
        st1 = c.execute("SELECT status FROM orders WHERE id=?", (oid,)).fetchone()[0]
        ob = c.execute("SELECT attempts,status FROM outbox").fetchone(); sh = c.execute("SELECT sync_status FROM shipments").fetchone()[0]
    p.courier.down_regions.clear(); t0 = p.now; p.now = lambda: t0() + 60
    r2 = p.process_outbox(); r3 = p.process_outbox()
    with p.tx() as c: sh2 = c.execute("SELECT sync_status, courier_ref FROM shipments").fetchone()
    # exhaustion path
    q = new(); q.courier.down_regions.add("R01"); paid_order(q); base = q.now
    for i in range(6): q.now = (lambda i=i: base() + 1000 * (i + 1)); q.process_outbox()
    with q.tx() as c: ob2 = c.execute("SELECT attempts,status FROM outbox").fetchone(); sh3 = c.execute("SELECT sync_status FROM shipments").fetchone()[0]
    ok = (r1["failed"] == 1 and st1 == "PAID" and ob[0] == 1 and sh == "PENDING_SYNC" and r2["done"] == 1 and r3["done"] == 0 and sh2[0] == "SYNCED"
          and len(p.courier.created) == 1 and ob2[1] == "FAILED_ALERT" and sh3 == "SYNC_FAILED")
    record("V5", "Courier synchronisation fails after the order is stored, then is retried",
           "Order stays PAID with local record intact; outbox attempt=1; after recovery exactly one courier shipment is created; after 5 failures an alert state is raised",
           f"first run failed={r1['failed']}, order status={st1}, outbox attempts={ob[0]}, shipment={sh}; after recovery done={r2['done']}, second worker pass done={r3['done']}, courier shipments created={len(p.courier.created)}, final={sh2[0]}; after 6 outage passes outbox={ob2[1]} (attempts={ob2[0]}), shipment={sh3}", ok)
def v6():
    p = new(); oid, tot = delivered(p); rid = p.request_refund(T("cust1"), oid, 500, "return")["refund_id"]
    a = p.approve_refund(T("support1"), rid, claimed_role="finance_reviewer"); b = p.approve_refund(T("cust1"), rid)
    c_ = p.approve_refund(T("admin1"), rid); d = p.view_order(T("cust2"), oid); e = p.view_order(T("support1"), oid, claimed_role="finance_reviewer")
    f = p.view_order(T("fin1"), oid); g = p.view_order(T("mgr2"), oid)
    with p.tx() as c: st = c.execute("SELECT status FROM refunds WHERE id=?", (rid,)).fetchone()[0]; nd = c.execute("SELECT COUNT(*) FROM audit WHERE action LIKE 'DENIED:%'").fetchone()[0]
    okinv, _ = inv_ok(p)
    ok = (a["code"] == b["code"] == c_["code"] == "FORBIDDEN" and not d["ok"] and e["ok"] and "payment_events" not in e["view"] and f["ok"] and "payment_events" in f["view"]
          and not g["ok"] and st == "REQUESTED" and nd == 5 and okinv)
    record("V6", "Privilege and ownership attacks (role spoofing, customer/support/admin approving, cross-customer and cross-region access)",
           "Support (even claiming finance role), customer and admin approvals FORBIDDEN; other customer and other-region manager cannot read the order; support sees status but no payment data; finance sees payment data; refund still REQUESTED; each denial audited",
           f"support+claimed finance={a['code']}, customer={b['code']}, admin={c_['code']}; other customer view ok={d['ok']}; other-region manager ok={g['ok']}; support view has payment data={'payment_events' in e['view']}; finance view has payment data={'payment_events' in f['view']}; refund status={st}; DENIED audit rows={nd}", ok)
def v7():
    p = new(); first = p.place_order(T("cust1"), [("SKU-LAST", 1)], "R01")             # reserved, never paid
    t0 = p.now; p.now = lambda: t0() + 3600                                            # one hour later
    if hasattr(p, "expire_reservations"): n = p.expire_reservations()
    else: n = "no expiry mechanism"
    second = p.place_order(T("cust2"), [("SKU-LAST", 1)], "R01")
    okinv, inv = inv_ok(p)
    record("V7", "Abandoned unpaid checkout holds the last unit for one hour (reservation expiry, TTL 15 min)",
           "After the 15-minute reservation window the first order is cancelled, stock is released, and the second customer can buy the unit",
           f"expiry sweep result={n}; second customer's order -> {second.get('code', 'ORDER_CREATED')}", second["ok"] and okinv)
def v8():
    p = new(); o = p.place_order(T("cust1"), [("SKU-A", 2), ("SKU-B", 3)], "R01", client_total=1)
    expected_total = 2 * 1000 + 3 * 300; tax = (expected_total * 1800 + 5000) // 10000; exp = expected_total + tax + 40
    eid = "gw-8"; oid = o["order_id"]
    bad_sig = p.payment_callback(eid, oid, o["total"], "00" * 32); short = p.payment_callback(eid, oid, o["total"] - 100, sign(eid, oid, o["total"] - 100))
    good = p.payment_callback(eid, oid, o["total"], sign(eid, oid, o["total"]))
    with p.tx() as c: st = c.execute("SELECT status FROM orders WHERE id=?", (oid,)).fetchone()[0]
    ok = o["total"] == exp and bad_sig["code"] == "BAD_SIGNATURE" and short["code"] == "AMOUNT_MISMATCH" and good["code"] == "APPLIED" and st == "PAID"
    record("V8", "Price/tax integrity and callback authenticity (client sends total=1; forged signature; short payment)",
           f"Server total = subtotal {expected_total} + tax 18% {tax} + shipping 40 = {exp}; forged signature rejected; short payment rejected; correct callback applied",
           f"stored total={o['total']} (client claimed 1, ignored); forged={bad_sig['code']}; short payment={short['code']}; valid={good['code']}; order status={st}", ok)
def v9():
    p = new(); first = p.place_order(T("cust1"), [("SKU-LAST", 1)], "R01"); oid, tot = first["order_id"], first["total"]
    t0 = p.now; p.now = lambda: t0() + 3600
    if hasattr(p, "expire_reservations"): p.expire_reservations()
    eid = "gw-9"; r = p.payment_callback(eid, oid, tot, sign(eid, oid, tot))
    with p.tx() as c:
        pay = c.execute("SELECT applied FROM payments WHERE gateway_event_id=?", (eid,)).fetchone(); st = c.execute("SELECT status FROM orders WHERE id=?", (oid,)).fetchone()[0]
    okinv, _ = inv_ok(p)
    record("V9", "Payment callback arrives after the reservation has expired (late payment)",
           "Order is not resurrected; the payment is stored as UNAPPLIED and flagged for finance reconciliation; invariants hold",
           f"callback result={r['code']}; payment row applied flag={None if not pay else pay[0]}; order status={st}",
           r["code"] == "ORDER_NOT_PAYABLE" and pay is not None and pay[0] == 0 and st == "CANCELLED" and okinv)


def v10():
    p = new(); oid, tot = packed_synced(p); late, _, _ = paid_order(p)
    t0 = p.now; p.now = lambda: t0() + 25 * 3600
    before = p.overdue_dispatches(); p.dispatch(T("picker1"), oid); after = p.overdue_dispatches()
    record("V10", "Dispatch deadline: paid orders not dispatched within 24 h are flagged",
           "Both paid orders are listed as overdue after 25 h; once one is dispatched only the other remains listed",
           f"overdue before dispatch={len(before)} ({sorted(before) == sorted([oid, late])}); after dispatching one={len(after)} (remaining is the undispatched order: {after == [late]})",
           sorted(before) == sorted([oid, late]) and after == [late])
def v11():
    p = new(); o = p.place_order(T("cust1"), [("SKU-LAST", 1)], "R01")
    neg1 = p.ingest_event(T("picker1"), "sc1", "STOCK_DELTA", sku="SKU-LAST", qty=-1); neg2 = p.ingest_event(T("picker1"), "sc2", "STOCK_DELTA", sku="SKU-B", qty=-4)
    with p.tx() as c: ids = {r["sku"]: r["id"] for r in c.execute("SELECT id,sku FROM stock_corrections")}
    a = p.approve_stock_correction(T("picker1"), ids["SKU-B"]); b = p.approve_stock_correction(T("mgr1"), ids["SKU-LAST"]); d = p.approve_stock_correction(T("mgr1"), ids["SKU-B"])
    with p.tx() as c: onh = c.execute("SELECT on_hand FROM stock WHERE sku='SKU-B'").fetchone()[0]
    okinv, _ = inv_ok(p)
    record("V11", "Stock correction is a human decision (negative scan adjustments)",
           "Negative adjustments wait as PENDING; picker cannot approve; manager approval that would drop stock below reserved units is refused; a safe correction is applied only after manager approval",
           f"scan results={neg1['code']}, {neg2['code']}; picker approval={a['code']}; manager approval breaking reservation={b['code']}; safe manager approval={d['code']} (SKU-B on_hand 10000 -> {onh})",
           a["code"] == "FORBIDDEN" and b["code"] == "WOULD_BREAK_RESERVATIONS" and d["code"] == "APPROVED" and onh == 9996 and okinv)

# ---------------- Q6 scenarios ----------------
REG = [f"R{i:02d}" for i in range(1, 13)]
def r1():
    p = new(regions=REG); orders_unpaid, orders_paid = [], []
    for i in range(450): orders_unpaid.append(p.place_order(T("cust1"), [("SKU-B", 1)], REG[i % 12]))
    for i in range(180):
        o = p.place_order(T("cust2"), [("SKU-B", 1)], REG[i % 12]); eid = f"pre-{i}"
        p.payment_callback(eid, o["order_id"], o["total"], sign(eid, o["order_id"], o["total"])); orders_paid.append(o)
    ev = []
    for i, o in enumerate(orders_unpaid):
        e = f"pay-{i}"; ev.append(("pay", e, o))
    ev += [("pay", f"pay-{i}", orders_unpaid[i]) for i in range(50)]                          # 50 duplicate callbacks
    ev += [("stk", f"stk-{i}", None) for i in range(270)] + [("stk", f"stk-{i}", None) for i in range(30)]   # 30 replays
    ev += [("pick", f"pick-{i}", orders_paid[i]) for i in range(180)] + [("pick", f"pick-{i}", orders_paid[i]) for i in range(20)]
    assert len(ev) == 1000; random.Random(7).shuffle(ev)
    def run(e):
        k, eid, o = e
        if k == "pay": return p.payment_callback(eid, o["order_id"], o["total"], sign(eid, o["order_id"], o["total"]))["code"]
        if k == "stk": return p.ingest_event(T("picker1"), eid, "STOCK_DELTA", sku="SKU-A", qty=1)["code"]
        return p.ingest_event(T("picker1"), eid, "PICK_CONFIRM", order_id=o["order_id"])["code"]
    t0 = time.perf_counter()
    with ThreadPoolExecutor(8) as ex: codes = list(ex.map(run, ev))
    dt = time.perf_counter() - t0
    with p.tx() as c:
        pay = c.execute("SELECT COUNT(*) FROM payments WHERE applied=1 AND gateway_event_id LIKE 'pay-%'").fetchone()[0]
        onhand = c.execute("SELECT on_hand FROM stock WHERE sku='SKU-A'").fetchone()[0]
        packed = c.execute("SELECT COUNT(*) FROM orders WHERE status='PACKED'").fetchone()[0]
        ob = c.execute("SELECT COUNT(*) FROM outbox").fetchone()[0]
    okinv, inv = inv_ok(p); dups = codes.count("DUPLICATE_IGNORED")
    rate = 1000 / dt
    ok = pay == 450 and onhand == 100 + 270 and packed == 180 and dups == 100 and okinv
    record("W1", "Load: 1,000 mixed events (500 payment callbacks, 300 stock events, 200 pick scans; 100 deliberate duplicates), 8 concurrent workers, 12 regions",
           "Exactly 450 unique payments applied once (no duplicates); 270 stock receipts applied once (on_hand 100 -> 370); 180 picks applied; 100 duplicates ignored; invariants hold; prototype processes >16.7 events/s (planning rate 1,000/min)",
           f"unique payments applied={pay}; duplicates ignored={dups}; on_hand={onhand}; PACKED orders={packed}; outbox messages={ob} (one per paid order, 630 expected); elapsed={dt:.1f}s => {rate:.0f} events/s on this sandbox (planning need 16.7/s); invariants I1-I8 all hold={okinv}",
           ok and ob == 630, {"elapsed": round(dt, 2), "rate": round(rate, 1)})
def r2():
    p = new(); ids = []
    for i in range(30):
        oid, _, _ = paid_order(p); ids.append(oid)
    unpaid = p.place_order(T("cust1"), [("SKU-B", 1)], "R01")["order_id"]
    node = EdgeNode(p, T("picker1")); node.online = False
    for i, oid in enumerate(ids): node.scan("PICK_CONFIRM", order_id=oid, event_id=f"scan-{i}")
    node.scan("PICK_CONFIRM", order_id=unpaid, event_id="scan-unpaid")
    node.scan("STOCK_DELTA", sku="SKU-B", qty=5, event_id="stk-pos"); node.scan("STOCK_DELTA", sku="SKU-B", qty=-4, event_id="stk-neg")
    dl, _ = delivered(p); rid = p.request_refund(T("support1"), dl, 800, "return")["refund_id"]; rid_b = p.request_refund(T("cust1"), dl, 100, "x")["refund_id"]
    node.queue_approval(T("fin1"), rid); node.queue_approval(T("support1"), rid_b)
    offline_status = (node.display_status(rid), node.display_status(rid_b))
    with p.tx() as c: server_while_off = c.execute("SELECT status FROM refunds WHERE id=?", (rid,)).fetchone()[0]; packed_off = c.execute("SELECT COUNT(*) FROM orders WHERE status='PACKED'").fetchone()[0]
    node.queue += [dict(e) for e in node.queue[:10]]                          # 10 retransmissions queued before reconnect
    node.online = True; s1 = node.sync(lose_acks=True); s2 = node.sync()      # first ack lost -> everything resent
    with p.tx() as c:
        packed = c.execute("SELECT COUNT(*) FROM orders WHERE status='PACKED'").fetchone()[0]
        onh = c.execute("SELECT on_hand FROM stock WHERE sku='SKU-B'").fetchone()[0]
        corr = c.execute("SELECT status FROM stock_corrections").fetchone()[0]; ev_n = c.execute("SELECT COUNT(*) FROM scan_events").fetchone()[0]
        rs = c.execute("SELECT status FROM refunds WHERE id=?", (rid,)).fetchone()[0]; rsb = c.execute("SELECT status FROM refunds WHERE id=?", (rid_b,)).fetchone()[0]
    after = (node.display_status(rid), node.display_status(rid_b)); okinv, _ = inv_ok(p)
    ok = (offline_status == ("PENDING_SERVER_VALIDATION",) * 2 and server_while_off == "REQUESTED" and packed_off == 0 and packed == 30 and onh == 10005 and corr == "PENDING"
          and ev_n == 35 and rs == "APPROVED" and rsb == "REQUESTED" and after[1].startswith("SERVER:") and okinv)
    record("W2", "Disconnected scanner: buffered events, retransmission after lost acknowledgement, offline refund approvals",
           "While offline both approvals display PENDING_SERVER_VALIDATION and the server is unchanged; after sync each unique event is applied once despite resends (30 picks applied, unpaid-order pick rejected, +5 stock applied, -4 held for manager, 0 packed before sync); finance approval accepted, support approval rejected by the server",
           f"offline display={offline_status}, server refund status while offline={server_while_off}; after two sync passes: PACKED orders={packed} (0 before sync), distinct events stored={ev_n} (33 sent by the node + 2 earlier), sent in sync pass 1={s1['sent']} (incl. resends), pass 2={s2['sent']}, SKU-B on_hand={onh} (10,000+5), negative correction={corr}; refund statuses on server: finance-queued={rs}, support-queued={rsb}; local state of support approval={node.local_approvals[rid_b]['state']}; invariants hold={okinv}", ok)
def r3():
    p = new(regions=REG); p.courier.down_regions |= {"R03", "R07"}; rows = {}
    for reg in REG:
        oid, tot = None, None
        o = p.place_order(T("cust1"), [("SKU-A", 1)], reg); eid = "e-" + reg
        p.payment_callback(eid, o["order_id"], o["total"], sign(eid, o["order_id"], o["total"])); p.ingest_event(T("picker1"), "pk-" + reg, "PICK_CONFIRM", order_id=o["order_id"]); rows[reg] = o
    p.process_outbox(); disp = {reg: p.dispatch(T("picker1"), rows[reg]["order_id"])["code"] for reg in REG}
    rep1 = p.report(); expected_total = sum(o["total"] for o in rows.values()); rep_total = sum(v["sales"] for v in rep1.values())
    pend = sorted(r for r, v in rep1.items() if v["pending_events"])
    p.courier.down_regions.clear(); t0 = p.now; p.now = lambda: t0() + 60; p.process_outbox()
    disp2 = {reg: p.dispatch(T("picker1"), rows[reg]["order_id"])["code"] for reg in ("R03", "R07")}
    rep2 = p.report(); okinv, _ = inv_ok(p)
    n_ok = sum(v == "DISPATCHED" for v in disp.values())
    ok = (n_ok == 10 and disp["R03"] == disp["R07"] == "NO_COURIER_LABEL" and pend == ["R03", "R07"] and rep_total == expected_total
          and all(v == "DISPATCHED" for v in disp2.values()) and not any(v["pending_events"] for v in rep2.values()) and okinv)
    record("W3", "Partial failure: courier API down for 2 of 12 regions; consolidated report remains reconcilable",
           "10 regions dispatch normally; R03 and R07 orders stay PACKED (NO_COURIER_LABEL) with payment intact; report shows pending events only for R03/R07 and its sales total equals the sum of paid orders; after recovery both dispatch and pending count is 0",
           f"dispatched during outage={n_ok}/12; blocked={[r for r,v in disp.items() if v!='DISPATCHED']}; pending-event regions in report={pend}; report sales total={rep_total} vs independent sum {expected_total}; after recovery R03/R07 -> {list(disp2.values())}; pending events remaining={sum(v['pending_events'] for v in rep2.values())}", ok)
def r4():
    p = new()
    a = p.place_order(T("cust1"), [("SKU-A", 2)], "R01"); b = p.place_order(T("cust1"), [("SKU-A", 2)], "R02")
    oid, tot, _ = paid_order(p, items=(("SKU-A", 3),), region="R01"); 
    o2 = p.place_order(T("cust1"), [("SKU-A", 3)], "R02")["order_id"]; tot2 = p.place_order(T("cust1"), [("SKU-A", 1)], "R02")  # noqa
    # refund limits: R01 limit 2000, R02 limit 3000; refund 2500 in R01 needs finance, mgr1 cannot; 
    p.ingest_event(T("picker1"), "pkx", "PICK_CONFIRM", order_id=oid); p.process_outbox(); p.dispatch(T("picker1"), oid); p.ingest_event(T("courier"), "dlx", "DELIVERED", order_id=oid)
    rid = p.request_refund(T("support1"), oid, 2500, "return")["refund_id"]
    m = p.approve_refund(T("mgr1"), rid); mx = p.approve_refund(T("mgr2"), rid); f = p.approve_refund(T("fin1"), rid)
    ok = a["total"] != b["total"] and m["code"] == "ABOVE_APPROVER_LIMIT" and mx["code"] == "ABOVE_APPROVER_LIMIT" and f["code"] == "APPROVED"
    record("W4", "Regional rules: same basket in R01 vs R02; refund above the region's local approval limit",
           "Totals differ by region tax/shipping; manager approval above regional limit refused (home-region and foreign-region managers alike); finance approves",
           f"R01 total={a['total']}, R02 total={b['total']}; R01 manager={m['code']}, R02 manager={mx['code']}, finance={f['code']}", ok)

for f in (v1, v2, v3, v4, v5, v6, v7, v8, v9, v10, v11, r1, r2, r3, r4):
    try: f()
    except Exception as e:
        import traceback; traceback.print_exc(); record(f.__name__, "CRASH", "-", repr(e), False)
json.dump(RESULTS, open(sys.argv[1] if len(sys.argv) > 1 else "results.json", "w"), indent=1)
print("\nSUMMARY:", sum(r["passed"] for r in RESULTS), "/", len(RESULTS), "passed")
