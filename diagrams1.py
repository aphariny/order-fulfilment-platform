from dm import *

# ============ Context diagram (portrait 7.4 x 6.2) ============
f, ax = fig(7.4, 6.0)
box(ax, 2.2, 2.05, 3.0, 1.7, "Order Fulfilment Platform\n\ncheckout · stock reservation · payment\nconfirmation · picking · dispatch · tracking\nreturns & refunds · audit · reporting", fc=BLUEF, fs=8.5, bold=False)
cluster(ax, 1.9, 1.75, 3.6, 2.3, "System boundary", fs=8)
tops = [("Customer", 1.2), ("Picker", 3.7), ("Support agent", 6.2)]
bots = [("Store manager", 1.2), ("Finance reviewer", 3.7), ("Administrator", 6.2)]
for n, x in tops:
    b = box(ax, x - 0.8, 4.85, 1.6, 0.6, n, fc=GREY, ec="#555", fs=8.5); arrow(ax, side(b, "b", 0.5), (min(max(x, 2.6), 4.8), 4.05), style="-|>", color="#555")
for n, x in bots:
    b = box(ax, x - 0.8, 0.55, 1.6, 0.6, n, fc=GREY, ec="#555", fs=8.5); arrow(ax, side(b, "t", 0.5), (min(max(x, 2.6), 4.8), 1.75), style="-|>", color="#555")
g = box(ax, 0.05, 2.4, 1.4, 1.0, "Payment gateway\n(external;\nhosted card page)", fc=YEL, ec="#7F6000", fs=7.5, ls="--")
c = box(ax, 5.95, 2.4, 1.4, 1.0, "Courier API\n(external)", fc=YEL, ec="#7F6000", fs=7.5, ls="--")
arrow(ax, (1.45, 2.9), (1.9, 2.9), "signed\ncallbacks", both=True, fs=6.5, loff=(0, 0.25)); arrow(ax, (5.5, 2.9), (5.95, 2.9), "shipments /\ntracking", both=True, fs=6.5, loff=(0, 0.25))
box(ax, 0.3, 0.02, 6.8, 0.38, "OUT OF SCOPE: card-data handling (gateway-hosted) · accounting ledger · marketing · ML demand forecasting · courier routing · supplier purchasing", fc=RED, ec="#A94442", fs=6.8)
ax.text(3.7, 5.75, "Figure 1 – Context diagram and system boundary", ha="center", fontsize=0.1, color="white")
save(f, "context")

# ============ Use case diagram (landscape 10 x 6.7) ============
f, ax = fig(10, 6.7)
ax.add_patch(Rectangle((1.75, 0.12), 6.5, 6.5, fc="#FBFDFF", ec=BLUE, lw=1.3, zorder=0)); ax.text(5.0, 6.45, "Omnichannel Order Fulfilment Platform", ha="center", va="center", fontsize=9.5, color=BLUE, fontweight="bold")
L = 3.35; R = 6.65
ucs = {}
for k, y, t in [("order", 5.7, "Place order"), ("track", 4.9, "Track order and delivery"), ("reqref", 4.1, "Request return / refund"), ("viewst", 3.3, "View order and refund status\n(no payment data)"),
                ("pick", 2.5, "Confirm pick"), ("sync", 1.7, "Synchronise buffered scan events"), ("disp", 0.9, "Dispatch order\n(paid, picked, label present)")]:
    ucs[k] = uc(ax, L, y, t, w=2.8, h=0.54, fs=8.2)
ucs["reserve"] = uc(ax, 5.6, 6.0, "Reserve stock\n(15-min hold)", w=1.7, h=0.48, fs=7.5)
for k, y, t in [("pay", 5.25, "Confirm payment callback"), ("ship", 4.6, "Create / track courier shipment"), ("appr", 3.95, "Approve or reject refund"), ("exec", 3.3, "Execute approved refund"),
                ("audit", 2.65, "View refund audit and reports"), ("corr", 2.0, "Approve stock correction"), ("overdue", 1.35, "Review overdue dispatches"), ("admin", 0.7, "Manage users and regional rules")]:
    ucs[k] = uc(ax, R, y, t, w=2.8, h=0.5, fs=8.2)
A = lambda x, y, n, ext=False: actor(ax, x, y, n, ext=ext)
cust, supp, pick = (0.75, 4.75, ), (0.75, 3.35), (0.75, 1.6)
A(*cust, "Customer"); A(*supp, "Support\nagent"); A(*pick, "Picker")
gw, co, fin, mg, adm = (9.25, 5.15), (9.25, 4.15), (9.25, 3.0), (9.25, 1.75), (9.25, 0.5)
A(*gw, "Payment\ngateway", True); A(*co, "Courier\nAPI", True); A(*fin, "Finance\nreviewer"); A(*mg, "Store\nmanager"); A(*adm, "Administrator")
ln = lambda p, q, **k: ax.plot([p[0], q[0]], [p[1], q[1]], color="#333", lw=0.9, zorder=2, **k)
lc = lambda a, k: ((a[0] + 0.17, a[1] + 0.25), (ucs[k][0] - ucs[k][2] / 2 + 0.02, ucs[k][1]))
for k in ("order", "track", "reqref"): ln(*lc(cust, k))
for k in ("reqref", "viewst"): ln(*lc(supp, k))
for k in ("pick", "sync", "disp"): ln(*lc(pick, k))
rc = lambda a, k: ((a[0] - 0.17, a[1] + 0.25), (ucs[k][0] + ucs[k][2] / 2 - 0.02, ucs[k][1]))
for a, ks in [(gw, ["pay"]), (co, ["ship"]), (fin, ["appr", "exec", "audit"]), (mg, ["appr", "audit", "corr", "overdue"]), (adm, ["admin"])]:
    for k in ks: ln(*rc(a, k))
arrow(ax, (L + 1.0, 5.85), (5.6 - 0.85, 6.0), "«include»", ls="--", fs=7, loff=(0, 0.15))
ax.text(5.0, 0.22, "Administrator cannot approve refunds (separation of duties); store manager approval is limited to the regional refund limit.", ha="center", fontsize=7, style="italic", color="#444")
save(f, "usecase")

# ============ Class diagram (landscape 10 x 6.6) ============
f, ax = fig(10, 6.6)
def cls(x, yt, name, attrs, ops=(), w=1.65, fc=BLUEF):
    lh = 0.152; h = 0.28 + lh * len(attrs) + (0.08 + lh * len(ops) if ops else 0.06)
    y = yt - h; ax.add_patch(Rectangle((x, y), w, h, fc="white", ec=BLUE, lw=1.1, zorder=2)); ax.add_patch(Rectangle((x, yt - 0.26), w, 0.26, fc=fc, ec=BLUE, lw=1.1, zorder=2))
    ax.text(x + w / 2, yt - 0.13, name, ha="center", va="center", fontsize=7.8, fontweight="bold", zorder=3)
    for i, a in enumerate(attrs): ax.text(x + 0.06, yt - 0.26 - 0.03 - lh * (i + 0.5), a, fontsize=6.4, va="center", zorder=3)
    if ops:
        ya = yt - 0.26 - 0.03 - lh * len(attrs) - 0.02; ax.plot([x, x + w], [ya, ya], color=BLUE, lw=0.8, zorder=3)
        for i, o in enumerate(ops): ax.text(x + 0.06, ya - 0.05 - lh * (i + 0.5), o, fontsize=6.4, va="center", zorder=3)
    return (x, y, w, h)
X = [0.08, 2.1, 4.12, 6.3, 8.27]; W = 1.65
User = cls(X[0], 6.5, "User", ["id", "name", "role : Role", "region"], ["authenticate()"])
Reg = cls(X[1], 6.5, "RegionRule", ["region", "version", "taxBp", "shippingFee", "refundLimit", "effectiveFrom"])
Scan = cls(X[2], 6.5, "ScanEvent", ["eventId {unique}", "deviceId", "seq", "kind", "result"], ["apply()"])
SC = cls(X[4], 6.5, "StockCorrection", ["id", "sku", "delta", "status"], ["approve()"])
Ref = cls(X[0], 4.55, "Refund", ["id", "amount", "status : RefundStatus", "requestedBy", "approvedBy", "attempts", "reason"], ["request()", "approve() / reject()", "execute()", "rollback()"])
Ord = cls(X[1], 4.55, "Order", ["id", "status : OrderStatus", "subtotal, tax, shipping", "total", "reserveExpiresAt", "paidAt", "picked : bool", "ruleVersion"], ["place()", "applyPayment(evt)", "confirmPick()", "dispatch()", "cancel()"])
Pay = cls(X[2], 4.55, "Payment", ["id", "gatewayEventId {unique}", "amount", "applied : bool"])
Shp = cls(X[2], 3.1, "Shipment", ["id", "courierRef", "syncStatus"])
Out = cls(X[3], 3.1, "OutboxMessage", ["id", "attempts", "nextAttempt", "status"], ["retry()"])
Aud = cls(X[0], 1.75, "AuditEntry", ["id", "ts", "actor", "action", "entity", "detail"])
OL = cls(X[1], 1.75, "OrderLine", ["sku", "qty", "unitPrice"])
Prod = cls(X[3], 1.75, "Product", ["sku", "price : Money"])
SI = cls(X[4], 1.75, "StockItem", ["sku", "onHand : int", "reserved : int"], ["reserve(qty)", "release(qty)"])
line = lambda p, q, **k: arrow(ax, p, q, style="-", **k)
def mult(p, t, dx=0, dy=0): ax.text(p[0] + dx, p[1] + dy, t, fontsize=6.6, ha="center", va="center", zorder=6)
def end_l(p, t, up): mult(p, t, 0.17, 0.09 if up else -0.09)
def end_r(p, t, up): mult(p, t, -0.17, 0.09 if up else -0.09)
# User - Order (places)
p, q = (X[0] + 1.3, User[1]), (X[1] + 0.3, Ord[1] + Ord[3]); line(p, q, label="places", fs=6.6, loff=(-0.4, 0.03)); mult(p, "1", 0.1, -0.12); mult(q, "0..*", -0.1, 0.13)
# User -> Refund
p, q = (X[0] + 0.5, User[1]), (X[0] + 0.5, Ref[1] + Ref[3]); arrow(ax, p, q, "requests /\napproves", ls="--", fs=6.2, loff=(0.5, 0), style="->")
# Order - Refund
y = 3.35; line((X[0] + W, y), (X[1], y)); end_l((X[0] + W, y), "0..*", False); end_r((X[1], y), "1", True)
# Order - Payment
y = 4.1; line((X[1] + W, y), (X[2], y)); end_l((X[1] + W, y), "1", True); end_r((X[2], y), "0..*", False)
# Order - Shipment
y = 2.95; line((X[1] + W, y), (X[2], y)); end_l((X[1] + W, y), "1", True); end_r((X[2], y), "0..1", False)
# Shipment - Outbox
y = 2.65; line((X[2] + W, y), (X[3], y)); end_l((X[2] + W, y), "1", True); end_r((X[3], y), "0..*", False)
# Order <>-- OrderLine (composition, diamond at Order)
p, q = (X[1] + 0.8, Ord[1]), (X[1] + 0.8, OL[1] + OL[3]); line(p, q); ax.add_patch(Polygon([[p[0], p[1]], [p[0] - 0.07, p[1] - 0.12], [p[0], p[1] - 0.24], [p[0] + 0.07, p[1] - 0.12]], closed=True, fc=BLUE, ec=BLUE, zorder=6)); mult(q, "1..*", 0.25, 0.12)
# Order ..> RegionRule
p, q = (X[1] + 0.8, Ord[1] + Ord[3]), (X[1] + 0.8, Reg[1]); arrow(ax, p, q, "snapshots\nrule version", ls="--", style="->", fs=6.2, loff=(0.5, 0))
# ScanEvent ..> Order
p, q = (X[2] + 0.3, Scan[1]), (X[1] + 1.4, Ord[1] + Ord[3]); arrow(ax, p, q, "confirms pick", ls="--", style="->", fs=6.2, loff=(0.6, 0.03))
# ScanEvent ..> StockCorrection
p, q = (X[2] + W, 5.95), (X[4], 5.95); arrow(ax, p, q, "may raise (negative delta)", ls="--", style="->", fs=6.2, loff=(0, 0.13))
# StockCorrection ..> StockItem
p, q = (X[4] + 0.8, SC[1]), (X[4] + 0.8, SI[1] + SI[3]); arrow(ax, p, q, "adjusts after\nmanager approval", ls="--", style="->", fs=6.2, loff=(-0.02, 0))
# OrderLine -> Product ; Product - StockItem
y = 1.3; arrow(ax, (X[1] + W, y), (X[3], y), style="->"); mult((X[3], y), "1", -0.12, 0.1)
line((X[3] + W, y), (X[4], y)); end_l((X[3] + W, y), "1", True); end_r((X[4], y), "1", False)
# Refund ..> Audit
p, q = (X[0] + 0.8, Ref[1]), (X[0] + 0.8, Aud[1] + Aud[3]); arrow(ax, p, q, "every change", ls="--", style="->", fs=6.2, loff=(0.5, 0))
save(f, "class")
print("part1 ok")
