from dm import *
def dbox(ax, x, y, w, h, t, fc=YEL, fs=7.5):          # cylinder-ish
    box(ax, x, y, w, h, t, fc=fc, ec="#7F6000", fs=fs, rounding=0.18)
    ax.plot([x + 0.04, x + w - 0.04], [y + h - 0.13, y + h - 0.13], color="#7F6000", lw=0.7, zorder=4)

# ===== Alternative A: modular monolith (7.4 x 5.2) =====
f, ax = fig(7.4, 5.3)
box(ax, 1.7, 4.6, 4.0, 0.5, "React storefront + staff consoles (no authority; display only)", fc=GREY, ec="#555", fs=7.5)
cluster(ax, 0.2, 1.55, 7.0, 2.85, "Alternative A – one FastAPI modular monolith (2 identical instances)")
mods = ["Identity &\nAccess", "Catalogue &\nCart", "Order &\nCheckout", "Inventory", "Payment\nIntegration", "Fulfilment\n(pick / dispatch)", "Returns &\nRefunds", "Audit &\nReporting"]
bx = {}
for i, m in enumerate(mods):
    r, c = divmod(i, 4); bx[i] = box(ax, 0.4 + c * 1.72, 3.2 - r * 0.85 + 0.0, 1.5, 0.65, m, fs=7.3)
box(ax, 0.4, 1.7, 3.2, 0.5, "Background worker (same codebase):\noutbox relay · reservation-expiry sweeper", fc=GREEN, ec="#2E7D32", fs=7)
arrow(ax, (3.35, 4.6), (3.35, 4.4), color="#555")
ax.text(5.1, 2.05, "in-process calls;\nreserve stock + order insert\nin ONE ACID transaction", fontsize=7, ha="center", style="italic", color="#444")
dbox(ax, 1.5, 0.25, 4.4, 0.8, "PostgreSQL – one database, one schema per module\nUNIQUE(gateway_event_id) · conditional UPDATE for stock\nCHECK(reserved ≤ on_hand) · append-only audit")
arrow(ax, (3.7, 1.55), (3.7, 1.05), color="#555", both=True)
box(ax, 5.95, 0.25, 1.3, 0.8, "Payment gateway\nCourier API", fc=YEL, ec="#7F6000", fs=7, ls="--"); arrow(ax, (6.6, 1.05), (6.6, 1.55), both=True, color="#7F6000")
save(f, "alt_a")

# ===== Alternative B: event-driven microservices (7.4 x 6.4) =====
f, ax = fig(7.4, 6.4)
box(ax, 1.2, 5.75, 2.2, 0.5, "React storefront + staff consoles", fc=GREY, ec="#555", fs=7.3)
box(ax, 4.0, 5.75, 2.2, 0.5, "API gateway + auth service", fc=BLUEF, fs=7.3); arrow(ax, (3.4, 6.0), (4.0, 6.0), color="#555")
box(ax, 0.3, 3.55, 6.8, 0.5, "Message broker (Kafka / RabbitMQ) – at-least-once delivery\nevents: OrderPlaced · StockReserved · PaymentConfirmed · ShipmentCreated · RefundApproved", fc=GREEN, ec="#2E7D32", fs=6.6)
svc = ["Order\nservice", "Inventory\nservice", "Payment\nservice", "Shipping\nservice", "Refund\nservice", "Reporting\nservice"]
for i, t in enumerate(svc):
    x = 0.3 + i * 1.15
    b = box(ax, x, 4.45, 1.0, 0.7, t, fs=7.2); arrow(ax, (x + 0.5, 5.15), (x + 0.5, 5.15), color="#555")
    arrow(ax, (x + 0.5, 4.45), (x + 0.5, 4.05), both=True, color="#2E7D32")
    dbox(ax, x, 2.5, 1.0, 0.62, f"DB {i + 1}", fs=7); arrow(ax, (x + 0.5, 3.55), (x + 0.5, 3.12), color="#555")
for x in (0.3, 1.45, 2.6, 4.9): arrow(ax, (5.1, 5.75), (x + 0.5, 5.15), color="#bbb", lw=0.7)
box(ax, 0.3, 1.2, 3.3, 1.0, "Saga for checkout (choreography):\nOrderPlaced → reserve stock → StockReserved →\nauthorise payment → PaymentConfirmed → create shipment.\nCompensation: release stock if payment fails.", fc=YEL, ec="#7F6000", fs=6.8)
box(ax, 3.9, 1.2, 3.2, 1.0, "Extra platform to run:\nKubernetes or ECS · broker cluster · schema\nregistry · distributed tracing · 6 CI pipelines\n· 6 databases to back up and migrate", fc=RED, ec="#A94442", fs=6.8)
box(ax, 0.3, 0.2, 6.8, 0.7, "Consistency across services is eventual: the 'last unit' needs a synchronous reserve call or a saga with compensation;\nreports must be assembled from events; the support console needs data from several services.", fc=GREY, ec="#555", fs=6.8)
save(f, "alt_b")

# ===== Selected component diagram (7.4 x 7.0) =====
f, ax = fig(7.4, 7.0)
box(ax, 1.6, 6.4, 4.6, 0.45, "«component» React SPA (customer · picker · support · finance · admin views)", fc=GREY, ec="#555", fs=7)
cluster(ax, 1.45, 1.95, 4.85, 4.2, "«component» Order Fulfilment API (FastAPI modular monolith)")
M = {}
spec = [("auth", "Identity & Access\nsessions · RBAC · field filter", 1.6, 4.95), ("ord", "Order & Checkout\npricing · reservation · rules", 4.0, 4.95),
        ("pay", "Payment Integration\nsigned callbacks · idempotency", 1.6, 3.95), ("inv", "Inventory\nreserve / release · corrections", 4.0, 3.95),
        ("ful", "Fulfilment\npick lists · scans · dispatch", 1.6, 2.95), ("ref", "Returns & Refunds\napproval workflow", 4.0, 2.95),
        ("aud", "Audit\nappend-only log", 1.6, 2.1), ("rep", "Reporting\nread-only aggregates", 4.0, 2.1)]
for k, t, x, y in spec: M[k] = box(ax, x, y, 2.15, 0.62, t, fs=6.7)
box(ax, 0.05, 3.85, 1.2, 0.8, "«external»\nPayment gateway", fc=YEL, ec="#7F6000", fs=6.8, ls="--")
box(ax, 6.2, 1.05, 1.15, 0.8, "«external»\nCourier API", fc=YEL, ec="#7F6000", fs=6.8, ls="--")
box(ax, 0.1, 0.95, 2.3, 0.85, "«component» Background worker\noutbox relay · expiry sweeper\n(same codebase)", fc=GREEN, ec="#2E7D32", fs=6.6)
dbox(ax, 2.6, 0.1, 3.0, 0.7, "«database» PostgreSQL\nschemas per module · constraints", fs=6.6)
arrow(ax, (2.7, 6.4), (2.7, 5.57), "HTTPS / JSON", fs=6.4, loff=(-0.6, 0.1))
arrow(ax, (3.75, 5.26), (4.0, 5.26), color="#555")
arrow(ax, (5.07, 4.95), (5.07, 4.57), "reserve()", fs=6.3, loff=(0.4, 0))
arrow(ax, (1.25, 4.25), (1.6, 4.25), "callbacks", fs=6.3, loff=(0.0, 0.14))
arrow(ax, (3.2, 4.57), (4.4, 4.95), "applyPayment()", fs=6.3, loff=(-0.35, 0.0))
arrow(ax, (4.0, 3.5), (3.4, 3.95), "refund()", fs=6.3, ls="--", loff=(0.45, -0.05))
arrow(ax, (4.0, 2.95), (3.75, 2.72), "audit", fs=6.3, ls="--", loff=(0.3, 0.05))
arrow(ax, (2.4, 1.38), (6.2, 1.38), "createShipment (idempotency key)", fs=6.4, loff=(0, 0.13), both=True, color="#2E7D32")
arrow(ax, (4.1, 1.95), (4.1, 0.8), color="#777", both=True)
arrow(ax, (1.3, 0.95), (2.6, 0.45), color="#2E7D32")
save(f, "component")

# ===== Baseline deployment (7.4 x 6.2) =====
f, ax = fig(7.4, 6.2)
box(ax, 2.3, 5.55, 3.2, 0.5, "«device» browser / warehouse tablet", fc=GREY, ec="#555", fs=7.5)
cluster(ax, 1.55, 1.0, 4.55, 4.2, "«execution environment» 1 cloud region · 2 availability zones")
box(ax, 2.5, 4.4, 2.6, 0.5, "«node» load balancer + TLS", fs=7.3)
box(ax, 1.7, 3.15, 2.0, 0.75, "«node» api-1 (AZ-a)\nFastAPI container", fs=7); box(ax, 3.95, 3.15, 2.0, 0.75, "«node» api-2 (AZ-b)\nFastAPI container", fs=7)
dbox(ax, 1.7, 1.35, 2.2, 1.0, "«node» PostgreSQL primary\n(managed, AZ-a)\nstandby in AZ-b", fs=6.8)
box(ax, 4.2, 1.35, 1.75, 1.0, "«node» worker\noutbox relay +\nexpiry sweeper", fc=GREEN, ec="#2E7D32", fs=6.8)
box(ax, 1.7, 0.1, 2.2, 0.6, "«artifact» nightly backup + WAL\narchive (RPO ≤ 5 min)", fc="#FFFFFF", ec="#555", fs=6.5)
box(ax, 0.05, 3.2, 1.25, 0.65, "GitHub\n(source control)", fc=GREY, ec="#555", fs=6.8)
box(ax, 6.25, 4.35, 1.1, 0.7, "Payment\ngateway\n(external)", fc=YEL, ec="#7F6000", fs=6.8, ls="--")
box(ax, 6.25, 1.5, 1.1, 0.7, "Courier API\n(external)", fc=YEL, ec="#7F6000", fs=6.8, ls="--")
arrow(ax, (3.8, 5.55), (3.8, 4.9), "HTTPS", fs=6.4, loff=(0.3, 0))
arrow(ax, (3.3, 4.4), (2.7, 3.9), color="#555"); arrow(ax, (4.3, 4.4), (4.95, 3.9), color="#555")
arrow(ax, (2.7, 3.15), (2.7, 2.35), color="#555"); arrow(ax, (4.95, 3.15), (3.9, 2.2), color="#555"); arrow(ax, (4.2, 1.85), (3.9, 1.85), color="#555")
arrow(ax, (2.8, 1.35), (2.8, 0.7), color="#555")
arrow(ax, (1.3, 3.52), (1.7, 3.52), "release", fs=6.3, loff=(0, 0.14), ls="--", color="#777")
arrow(ax, (6.25, 4.7), (5.1, 4.65), "signed callbacks", fs=6.2, loff=(0.1, 0.14), both=True, color="#7F6000")
arrow(ax, (5.95, 1.85), (6.25, 1.85), color="#7F6000", both=True)
save(f, "deployment")

# ===== Revised deployment (Q6) (7.4 x 7.8) =====
f, ax = fig(7.4, 7.9)
cluster(ax, 0.15, 6.2, 7.1, 1.55, "12 regions – warehouses, stores, customers", ec="#777")
box(ax, 0.35, 6.35, 3.2, 0.95, "«node» scanner / approval terminal ×12 regions\nEdge Sync Agent + local queue\n(eventId · deviceId · seq)", fc=GREY, ec="#555", fs=7)
box(ax, 3.85, 6.35, 3.2, 0.95, "«device» customer browsers (all regions)\nstatic assets via CDN", fc=GREY, ec="#555", fs=7)
cluster(ax, 0.15, 0.95, 7.1, 4.95, "«execution environment» primary cloud region · 2 availability zones")
box(ax, 1.9, 5.05, 3.5, 0.55, "«node» load balancer + TLS + rate limits", fs=7.3)
box(ax, 0.4, 3.85, 3.1, 0.75, "«node» api × 3 (autoscale 2–4)\nFastAPI containers", fs=7.2)
box(ax, 3.85, 3.85, 3.1, 0.75, "«node» sync-worker × 1–2\ninbox apply · outbox relay · expiry", fc=GREEN, ec="#2E7D32", fs=7.0)
box(ax, 0.9, 2.95, 2.3, 0.5, "«node» PgBouncer (pool)", fc="#FFFFFF", ec="#555", fs=7)
dbox(ax, 0.4, 1.15, 3.1, 1.05, "«node» PostgreSQL primary\norders · stock · refunds · inbox · rules\n(synchronous standby, AZ-b)", fs=6.8)
dbox(ax, 3.85, 1.15, 3.1, 1.05, "«node» PostgreSQL read replica\nregion_daily aggregates\nused only by reports", fs=6.8)
box(ax, 4.05, 2.45, 2.9, 0.55, "«node» report job (every 5 min)", fc=GREEN, ec="#2E7D32", fs=6.8)
box(ax, 0.2, 0.1, 6.9, 0.6, "Payment gateway · Courier API (external): callbacks enter through the load balancer; shipments leave through the sync-worker", fc=YEL, ec="#7F6000", fs=6.6, ls="--")
arrow(ax, (1.95, 6.35), (3.0, 5.6), "batched, signed,\nidempotent sync", fs=6.3, loff=(-0.45, 0.0)); arrow(ax, (5.4, 6.35), (4.5, 5.6), "via CDN", fs=6.3, loff=(0.4, 0.0))
arrow(ax, (3.1, 5.05), (1.95, 4.6), color="#555"); arrow(ax, (4.3, 5.05), (5.4, 4.6), color="#555", lw=0.1)
arrow(ax, (1.95, 3.85), (2.0, 3.45), color="#555"); arrow(ax, (5.4, 3.85), (3.2, 3.3), color="#555")
arrow(ax, (2.0, 2.95), (2.0, 2.2), color="#555"); arrow(ax, (5.4, 2.45), (5.4, 2.2), "read", fs=6.3, loff=(0.25, 0), color="#555")
arrow(ax, (3.5, 1.65), (3.85, 1.65), "replication", fs=6.2, loff=(0, 0.17), ls="--", color="#555")
save(f, "deployment_rev")

# ===== Revised component (Q6) (7.4 x 6.2) =====
f, ax = fig(7.4, 6.2)
box(ax, 0.2, 5.15, 3.6, 0.8, "«component» Edge Sync Agent\nlocal queue {eventId, deviceId, seq}\nlocal approvals shown as PENDING_SERVER_VALIDATION", fc=GREY, ec="#555", fs=6.8)
cluster(ax, 0.2, 1.3, 7.0, 3.5, "«component» Order Fulfilment API – revision 2.0 (changed or new modules shaded orange)")
box(ax, 0.4, 3.75, 2.2, 0.7, "NEW  Sync Inbox\ndedup by eventId · per-device seq\nholds events ≤ 72 h", fc=ORG, ec="#C55A11", fs=6.5)
box(ax, 2.85, 3.75, 2.0, 0.7, "NEW  Regional Rules\nversioned tax · shipping ·\nrefund limit (two-person change)", fc=ORG, ec="#C55A11", fs=6.5)
box(ax, 5.1, 3.75, 1.95, 0.7, "CHANGED  Reporting\nreplica aggregates ·\nas-of time + pending events", fc=ORG, ec="#C55A11", fs=6.5)
box(ax, 0.4, 2.55, 1.55, 0.65, "Fulfilment", fs=7); box(ax, 2.1, 2.55, 1.55, 0.65, "Inventory", fs=7); box(ax, 3.8, 2.55, 1.55, 0.65, "Order & Checkout", fs=7); box(ax, 5.5, 2.55, 1.55, 0.65, "Returns & Refunds\n(server-validated)", fs=6.5)
box(ax, 0.4, 1.5, 6.65, 0.6, "Audit (append-only) · Identity & Access (unchanged: server-side RBAC, field filter)", fs=6.8)
dbox(ax, 0.3, 0.2, 3.0, 0.7, "PostgreSQL primary", fs=7.3); dbox(ax, 4.2, 0.2, 3.0, 0.7, "Read replica", fs=7.3)
arrow(ax, (2.0, 5.15), (1.5, 4.45), "idempotent batch sync", fs=6.4, loff=(0.85, 0.12))
arrow(ax, (1.0, 3.75), (1.2, 3.2), color="#555"); arrow(ax, (2.0, 3.75), (2.8, 3.2), color="#555")
arrow(ax, (3.6, 3.75), (4.3, 3.2), "reads rule\nversion", fs=6.0, loff=(-0.5, 0.0), color="#555"); arrow(ax, (4.5, 3.75), (6.1, 3.2), color="#555")
arrow(ax, (3.3, 0.55), (4.2, 0.55), "replication", fs=6.2, loff=(0, 0.14), ls="--", color="#555")
arrow(ax, (1.8, 1.5), (1.8, 0.9), color="#555")
save(f, "component_rev")
print("part3 ok")
