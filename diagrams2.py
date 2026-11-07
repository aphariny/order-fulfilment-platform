from dm import *

def lifelines(ax, xs, names, ytop, ybot, w=1.05, fc=BLUEF, fs=7.5):
    for x, n in zip(xs, names):
        box(ax, x - w / 2, ytop, w, 0.5, n, fc=fc, fs=fs, bold=True)
        ax.plot([x, x], [ytop, ybot], color="#777", lw=0.8, ls=(0, (4, 3)), zorder=1)
def msg(ax, xs, i, j, y, text, dashed=False, fs=6.7, dy=0.075, align="mid"):
    x1, x2 = xs[i], xs[j]
    arrow(ax, (x1, y), (x2, y), ls="--" if dashed else "-", lw=0.9, style="->" if dashed else "-|>", color="#222")
    ax.text((x1 + x2) / 2, y + dy, text, ha="center", va="bottom", fontsize=fs, zorder=6, linespacing=1.12, bbox=dict(fc="white", ec="none", pad=0.8, alpha=0.92))
def selfmsg(ax, xs, i, y, text, fs=6.7):
    x = xs[i]; ax.plot([x, x + 0.32, x + 0.32], [y, y, y - 0.17], color="#222", lw=0.9, zorder=3); arrow(ax, (x + 0.32, y - 0.17), (x, y - 0.17), lw=0.9, color="#222")
    ax.text(x + 0.38, y - 0.08, text, ha="left", va="center", fontsize=fs, zorder=6)
def frame(ax, x1, x2, ytop, ybot, tag, cond, fc="none"):
    ax.add_patch(Rectangle((x1, ybot), x2 - x1, ytop - ybot, fc=fc, ec="#555", lw=1.0, zorder=0.5))
    ax.add_patch(Polygon([[x1, ytop], [x1 + 0.55, ytop], [x1 + 0.55, ytop - 0.1], [x1 + 0.45, ytop - 0.2], [x1, ytop - 0.2]], closed=True, fc="#EEEEEE", ec="#555", lw=0.9, zorder=0.6))
    ax.text(x1 + 0.05, ytop - 0.1, tag, fontsize=7, fontweight="bold", va="center"); ax.text(x1 + 0.62, ytop - 0.1, cond, fontsize=6.8, va="center", style="italic")
def band(ax, x1, x2, y, text):
    ax.plot([x1, x2], [y, y], color="#999", lw=0.8, ls=(0, (2, 2))); ax.text((x1 + x2) / 2, y + 0.03, text, ha="center", va="bottom", fontsize=7, style="italic", color="#555", bbox=dict(fc="white", ec="none", pad=1))

# ============ Sequence 1: payment callback -> order confirmation -> shipment -> courier sync (retry) ============
W, H = 7.4, 10.3
f, ax = fig(W, H)
xs = [0.65, 1.9, 3.1, 4.3, 5.5, 6.7]
names = ["Payment\nGateway", "Callback\nAPI", "Order\nModule", "PostgreSQL", "Outbox\nWorker", "Courier\nAPI"]
lifelines(ax, xs, names, H - 0.6, 0.15)
y = H - 1.0; st = 0.36
msg(ax, xs, 0, 1, y, "1 POST /callback\n{eventId, orderId, amount, signature}", dy=0.04); y -= 0.5
selfmsg(ax, xs, 1, y, "2 verify HMAC signature"); y -= 0.36
msg(ax, xs, 1, 2, y, "3 applyPayment(eventId, orderId, amount)"); y -= 0.36
msg(ax, xs, 2, 3, y, "4 one transaction: INSERT payment (eventId UNIQUE)\nUPDATE order → PAID · INSERT shipment · INSERT outbox", dy=0.06); y -= 0.45
msg(ax, xs, 3, 2, y, "5 commit OK", dashed=True); y -= 0.32
msg(ax, xs, 2, 1, y, "6 APPLIED", dashed=True); y -= 0.32
msg(ax, xs, 1, 0, y, "7 200 OK", dashed=True); y -= 0.3
ytop = y; y -= 0.33
msg(ax, xs, 0, 1, y, "8 POST /callback (same eventId, repeated)"); y -= 0.32
msg(ax, xs, 1, 3, y, "9 INSERT payment … eventId already stored", dy=0.07); y -= 0.32
msg(ax, xs, 3, 1, y, "10 no change (unique constraint)", dashed=True); y -= 0.32
msg(ax, xs, 1, 0, y, "11 200 DUPLICATE_IGNORED", dashed=True); y -= 0.22
frame(ax, 0.22, 7.2, ytop, y, "alt", "[duplicate delivery of the same gateway eventId]", fc="#FFFDF2"); y -= 0.3
band(ax, 0.22, 7.2, y, "asynchronous outbox relay (separate worker process)"); y -= 0.36
msg(ax, xs, 4, 3, y, "12 SELECT outbox WHERE status = PENDING\nAND next_attempt ≤ now", dy=0.06); y -= 0.5
msg(ax, xs, 4, 5, y, "13 createShipment\n(idempotency key = shipmentId)", dy=0.04); y -= 0.36
ytop = y; y -= 0.34
msg(ax, xs, 5, 4, y, "14 error / timeout", dashed=True); y -= 0.32
msg(ax, xs, 4, 3, y, "15 attempts + 1 · next_attempt = now + 2^n s", dy=0.07); y -= 0.3
ybot = y - 0.05
frame(ax, 0.22, 7.2, ytop, ybot, "alt", "[courier unavailable]  (order stays PAID; local record intact)", fc="#FFF5F5"); y -= 0.33
ytop2 = y; y -= 0.34
msg(ax, xs, 4, 5, y, "16 createShipment(same key)  – retry"); y -= 0.32
msg(ax, xs, 5, 4, y, "17 courierRef\n(idempotent: no duplicate shipment)", dashed=True, dy=0.04); y -= 0.46
msg(ax, xs, 4, 3, y, "18 shipment → SYNCED · outbox → DONE", dy=0.07); y -= 0.3
frame(ax, 0.22, 7.2, ytop2, y, "loop", "[retry while attempts < 5, exponential back-off]", fc="#F5FFF5"); y -= 0.3
box(ax, 0.3, y - 0.45, 6.8, 0.46, "After the 5th failure: shipment → SYNC_FAILED, alert to support console; the paid order is never rolled back.", fc=YEL, ec="#7F6000", fs=7)
save(f, "seq_callback")

# ============ Sequence 2: offline scanner synchronisation ============
W, H = 7.4, 7.9
f, ax = fig(W, H)
xs = [0.7, 2.1, 3.55, 5.0, 6.5]
names = ["Picker /\nManager", "Edge Sync\nAgent", "Sync API\n(inbox)", "Domain\nmodules", "PostgreSQL"]
lifelines(ax, xs, names, H - 0.6, 0.15, w=1.15)
y = H - 0.98
band(ax, 0.2, 7.2, y, "connection lost – work continues locally"); y -= 0.4
msg(ax, xs, 0, 1, y, "1 scan PICK_CONFIRM(order)"); y -= 0.36
msg(ax, xs, 1, 1, y, "") if False else None
selfmsg(ax, xs, 1, y, "2 queue {eventId, deviceId, seq}"); y -= 0.38
msg(ax, xs, 1, 0, y, "3 BUFFERED_LOCALLY", dashed=True); y -= 0.36
msg(ax, xs, 0, 1, y, "4 approve refund R-17 (finance login)"); y -= 0.36
msg(ax, xs, 1, 0, y, "5 shows PENDING_SERVER_VALIDATION\n(never 'Approved')", dashed=True, dy=0.05); y -= 0.52
band(ax, 0.2, 7.2, y, "connection restored"); y -= 0.42
msg(ax, xs, 1, 2, y, "6 POST /sync [events, approval intents]"); y -= 0.38
msg(ax, xs, 2, 4, y, "7 INSERT inbox(eventId) ON CONFLICT DO NOTHING", dy=0.07); y -= 0.38
ytop = y; y -= 0.32
msg(ax, xs, 2, 3, y, "8 apply once: confirm pick / validate approval\n(identity, role, regional limit, status, age ≤ 24 h)", dy=0.05); y -= 0.52
msg(ax, xs, 3, 4, y, "9 UPDATE with guards + audit row"); y -= 0.3
ax.text(0.3, y - 0.12, "[eventId already present] → result DUPLICATE_IGNORED, no side effect", fontsize=6.6, style="italic", va="center", color="#555")
frame(ax, 0.2, 7.2, ytop, y - 0.25, "alt", "[eventId new]", fc="#FFFDF2"); y -= 0.6
msg(ax, xs, 2, 1, y, "10 per-event results: APPLIED / DUPLICATE_IGNORED /\nREJECTED(reason) / PENDING_MANAGER_APPROVAL", dashed=True, dy=0.05); y -= 0.52
selfmsg(ax, xs, 1, y, "11 delete acknowledged events;\nlocal approval → SERVER_ACCEPTED or SERVER_REJECTED"); y -= 0.56
box(ax, 0.3, y - 0.5, 6.8, 0.55, "If acknowledgement (10) is lost, the agent resends the same events and step 7 absorbs them.\nRefund execution happens only on the server, after a server-side APPROVED.", fc=YEL, ec="#7F6000", fs=6.8)
save(f, "seq_sync")

# ============ Order state machine (portrait 7.4 x 3.9) ============
f, ax = fig(7.4, 4.0)
def st_box(x, y, t, fc=BLUEF, w=1.2, h=0.5): return box(ax, x, y, w, h, t, fc=fc, fs=8.5, bold=True, rounding=0.12)
ax.add_patch(Circle((0.25, 3.05), 0.09, fc="black", zorder=3))
P = st_box(0.6, 2.8, "Placed"); Pd = st_box(2.55, 2.8, "Paid"); Pk = st_box(4.5, 2.8, "Packed"); Di = st_box(6.1, 1.65, "Dispatched", w=1.25)
De = st_box(4.5, 1.0, "Delivered"); Cl = st_box(2.55, 1.0, "Closed", fc=GREEN); Ca = st_box(0.6, 1.0, "Cancelled", fc=RED)
ax.add_patch(Circle((3.15, 0.22), 0.1, fc="white", ec="black", lw=1.2, zorder=3)); ax.add_patch(Circle((3.15, 0.22), 0.055, fc="black", zorder=4))
ax.add_patch(Circle((1.2, 0.22), 0.1, fc="white", ec="black", lw=1.2, zorder=3)); ax.add_patch(Circle((1.2, 0.22), 0.055, fc="black", zorder=4))
arrow(ax, (0.34, 3.05), (0.6, 3.05), fs=6.5)
arrow(ax, side(P, "r"), side(Pd, "l"), "payment callback applied\n[amount = total, eventId new]", fs=6.3, loff=(0, 0.5))
arrow(ax, side(Pd, "r"), side(Pk, "l"), "pick confirmed", fs=6.3, loff=(0, 0.45))
arrow(ax, side(Pk, "r"), (6.7, 2.15), "dispatch\n[paid ∧ picked ∧ courierRef]", fs=6.3, rad=-0.35, loff=(0.55, 0.32))
arrow(ax, (6.7, 1.65), (5.7, 1.25), "courier DELIVERED\nevent", fs=6.3, loff=(0.7, 0.05))
arrow(ax, side(De, "l"), side(Cl, "r"), "return window ends /\nfull refund executed", fs=6.3, loff=(0, 0.32))
arrow(ax, side(P, "b", 0.5), side(Ca, "t", 0.5), "reservation expired (15 min)\nor customer cancels", fs=6.3, loff=(-0.02, 0), rad=0.0)
arrow(ax, (3.0, 2.8), (1.7, 1.5), "full refund executed\n(before packing)", fs=6.3, loff=(0.95, 0.15))
arrow(ax, side(Cl, "b", 0.5), (3.15, 0.32)); arrow(ax, side(Ca, "b", 0.5), (1.2, 0.32))
ax.text(5.0, 0.35, "Terminal states: Closed, Cancelled.\nCancelled is not reachable after packing.", fontsize=6.8, style="italic", color="#444", ha="left")
save(f, "order_state")

# ============ Refund state machine (portrait 7.4 x 3.9) ============
f, ax = fig(7.4, 4.1)
ax.add_patch(Circle((0.22, 3.15), 0.09, fc="black", zorder=3))
Rq = box(ax, 0.55, 2.9, 1.2, 0.5, "Requested", fc=BLUEF, fs=8.5, bold=True, rounding=0.12)
Ap = box(ax, 3.0, 2.9, 1.2, 0.5, "Approved", fc=GREEN, fs=8.5, bold=True, rounding=0.12)
Ex = box(ax, 5.8, 2.9, 1.2, 0.5, "Executing", fc=YEL, fs=8.5, bold=True, rounding=0.12)
Rj = box(ax, 0.55, 1.15, 1.2, 0.5, "Rejected", fc=RED, fs=8.5, bold=True, rounding=0.12)
Rp = box(ax, 5.8, 1.65, 1.2, 0.5, "RetryPending", fc=YEL, fs=8.5, bold=True, rounding=0.12)
Rb = box(ax, 5.8, 0.35, 1.2, 0.5, "RolledBack", fc=RED, fs=8.5, bold=True, rounding=0.12)
Ed = box(ax, 3.0, 1.15, 1.2, 0.5, "Executed", fc=GREEN, fs=8.5, bold=True, rounding=0.12)
arrow(ax, (0.31, 3.15), (0.55, 3.15))
arrow(ax, side(Rq, "r"), side(Ap, "l"), "approve\n[role ∈ {manager, finance}\n∧ approver ≠ requester\n∧ amount ≤ regional limit\nor finance]", fs=6.2, loff=(0, 0.5))
arrow(ax, side(Rq, "b", 0.5), side(Rj, "t", 0.5), "reject", fs=6.5, loff=(0.25, 0))
arrow(ax, side(Ap, "r"), side(Ex, "l"), "finance\nexecutes", fs=6.5, loff=(0, 0.27))
arrow(ax, (6.15, 2.9), (6.15, 2.15), "gateway error\n[attempts < 3]", fs=6.2, loff=(-0.55, 0.0))
arrow(ax, (6.65, 2.15), (6.65, 2.9), "retry\n(same key)", fs=6.2, loff=(0.38, 0.0))
arrow(ax, (5.8, 2.9), (4.2, 1.5), "gateway OK", fs=6.5, loff=(-0.45, -0.05))
arrow(ax, side(Rp, "b", 0.5), side(Rb, "t", 0.5), "attempts = 3: release refundable\namount, alert finance", fs=6.2, loff=(-0.95, 0))
ax.add_patch(Circle((3.6, 0.35), 0.1, fc="white", ec="black", lw=1.2, zorder=3)); ax.add_patch(Circle((3.6, 0.35), 0.055, fc="black", zorder=4))
arrow(ax, (3.6, 1.15), (3.6, 0.45))
ax.text(0.3, 0.6, "Invariant: Executing is entered only from\nApproved or RetryPending, with\napprovedBy ≠ null and ≠ requestedBy.", fontsize=6.6, style="italic", color="#444", va="center")
save(f, "refund_state")
print("part2 ok")
