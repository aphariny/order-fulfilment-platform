"""Edge sync agent for a (possibly disconnected) warehouse scanner node / regional approval terminal."""
import uuid
class EdgeNode:
    def __init__(self, platform, token):
        self.p = platform; self.token = token; self.online = False
        self.queue = []; self.local_approvals = {}   # refund_id -> {"token":..,"state":..}
    def scan(self, kind, **kw):
        self.queue.append({"event_id": kw.pop("event_id", "EV-" + uuid.uuid4().hex[:10]), "kind": kind, **kw})
        return "BUFFERED_LOCALLY"
    def queue_approval(self, token, refund_id):
        self.local_approvals[refund_id] = {"token": token, "state": "PENDING_SERVER_VALIDATION"}
    def display_status(self, refund_id):             # a local approval is NEVER shown as approved
        if refund_id in self.local_approvals and self.local_approvals[refund_id]["state"] == "PENDING_SERVER_VALIDATION":
            return "PENDING_SERVER_VALIDATION"
        with self.p.tx() as c:
            r = c.execute("SELECT status FROM refunds WHERE id=?", (refund_id,)).fetchone()
        return ("SERVER:" + r["status"]) if r else "UNKNOWN"
    def sync(self, lose_acks=False):
        if not self.online: return {"sent": 0}
        sent, remaining, results = 0, [], []
        for ev in self.queue:
            r = self.p.ingest_event(ev.get("token", self.token), ev["event_id"], ev["kind"], ev.get("order_id"), ev.get("sku"), ev.get("qty", 0))
            sent += 1; results.append(r["code"])
            if lose_acks: remaining.append(ev)       # ack lost: keep event, will be resent -> dedup must absorb it
        self.queue = remaining
        for rid, a in self.local_approvals.items():
            if a["state"] == "PENDING_SERVER_VALIDATION":
                r = self.p.approve_refund(a["token"], rid)
                a["state"] = "SERVER_ACCEPTED" if r["ok"] else "SERVER_REJECTED:" + r["code"]
        return {"sent": sent, "results": results}
