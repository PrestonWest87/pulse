import json
import uvicorn
from fastapi import FastAPI, Request, HTTPException
from datetime import datetime

from src.database import SessionLocal, init_db, Monitor, MonitorCheck, Alert
from src.monitors import get_monitor
from src.alert_engine import evaluate_and_alert

init_db()
app = FastAPI(title="Pulse Webhook Gateway")


def log(msg):
    print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] [WEBHOOK] {msg}")


@app.get("/health")
def health():
    return {"status": "ok", "service": "pulse-webhook", "timestamp": datetime.utcnow().isoformat()}


@app.post("/webhook/{monitor_name}")
async def receive_webhook(monitor_name: str, request: Request):
    """
    Generic inbound webhook receiver.
    Create a monitor with type 'webhook_in' and matching name,
    then POST here with any payload.
    """
    try:
        payload = await request.json()
    except Exception:
        payload = {"raw": await request.body()}

    with SessionLocal() as db:
        mon = db.query(Monitor).filter(
            Monitor.name == monitor_name,
            Monitor.monitor_type == "webhook_in",
            Monitor.enabled == True
        ).first()

        if not mon:
            raise HTTPException(status_code=404, detail=f"No active webhook_in monitor named '{monitor_name}'")

        # Save the check
        check = MonitorCheck(
            monitor_id=mon.id,
            status="up",
            response_summary=f"Webhook received ({len(json.dumps(payload))} bytes)",
            raw_data=payload,
        )
        db.add(check)
        db.commit()
        db.refresh(check)

        mon.last_check_at = datetime.utcnow()
        mon.last_status = "up"
        db.commit()

        evaluate_and_alert(mon, check, None)

        return {"status": "ok", "monitor": monitor_name, "check_id": check.id}


if __name__ == "__main__":
    log("Pulse Webhook Gateway starting on port 8100...")
    uvicorn.run(app, host="0.0.0.0", port=8100)
