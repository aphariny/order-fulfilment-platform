def check_invariants(p):
    """Executable versions of invariants I1-I8. Returns {id: (passed, detail)}."""
    out = {}
    with p.tx() as c:
        q = lambda s, *a: c.execute(s, a).fetchall()
        dup = q("SELECT gateway_event_id, COUNT(*) n FROM payments GROUP BY 1 HAVING n>1")
        multi = q("SELECT order_id, COUNT(*) n FROM payments WHERE applied=1 GROUP BY 1 HAVING n>1")
        out["I1 one payment per gateway event / one applied payment per order"] = (not dup and not multi, f"dup_events={len(dup)} multi_paid_orders={len(multi)}")
        bad = q("SELECT sku FROM stock WHERE reserved<0 OR reserved>on_hand")
        out["I2 0 <= reserved <= on_hand for every SKU"] = (not bad, f"violations={len(bad)}")
        bad = q("""SELECT o.id FROM orders o WHERE o.status IN ('PAID','PACKED','DISPATCHED','DELIVERED','CLOSED')
                   AND (SELECT COUNT(*) FROM payments p WHERE p.order_id=o.id AND p.applied=1 AND p.amount=o.total)!=1""")
        out["I3 PAID-or-later order has exactly one applied payment equal to its total"] = (not bad, f"violations={len(bad)}")
        bad = q("""SELECT o.id FROM orders o JOIN shipments s ON s.order_id=o.id
                   WHERE o.status IN ('DISPATCHED','DELIVERED') AND (s.courier_ref IS NULL OR o.picked=0)""")
        out["I4 DISPATCHED/DELIVERED order is picked and has a courier reference"] = (not bad, f"violations={len(bad)}")
        bad = q("""SELECT r.id FROM refunds r LEFT JOIN users u ON u.id=r.approved_by
                   WHERE r.status IN ('EXECUTING','EXECUTED') AND (r.approved_by IS NULL OR r.approved_by=r.requested_by
                   OR u.role NOT IN ('store_manager','finance_reviewer'))""")
        out["I5 executed refund has a distinct, authorised approver"] = (not bad, f"violations={len(bad)}")
        bad = q("""SELECT o.id FROM orders o WHERE (SELECT COALESCE(SUM(amount),0) FROM refunds r WHERE r.order_id=o.id
                   AND r.status IN ('REQUESTED','APPROVED','EXECUTING','RETRY_PENDING','EXECUTED'))
                   > (SELECT COALESCE(SUM(amount),0) FROM payments p WHERE p.order_id=o.id AND p.applied=1)""")
        out["I6 active refunds never exceed amount paid"] = (not bad, f"violations={len(bad)}")
        bad = q("""SELECT r.id FROM refunds r WHERE r.status!='REQUESTED' AND
                   (SELECT COUNT(*) FROM audit a WHERE a.entity=r.id AND a.action LIKE 'REFUND_%')<2""")
        out["I7 every refund state change is audited"] = (not bad, f"violations={len(bad)}")
        bad = q("""SELECT s.sku FROM stock s WHERE s.reserved != COALESCE((SELECT SUM(i.qty) FROM order_items i JOIN orders o ON o.id=i.order_id
                   WHERE i.sku=s.sku AND o.status IN ('PLACED','PAID','PACKED')),0)""")
        out["I8 reserved units == units on live (PLACED/PAID/PACKED) orders"] = (not bad, f"violations={len(bad)} {[b[0] for b in bad]}")
    return out
