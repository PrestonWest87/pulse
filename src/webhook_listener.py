import json
import uvicorn
from fastapi import FastAPI, Request, HTTPException
from datetime import datetime
from src.database import SessionLocal, init_db, Source, CollectedItem
from src.alert_engine import evaluate_items

init_db()
app = FastAPI(title="Pulse Webhook — Inbound Data Gateway")


def log(msg):
    print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] [WEBHOOK] {msg}")


@app.get("/health")
def health():
    return {"status": "ok", "service": "pulse-webhook", "timestamp": datetime.utcnow().isoformat()}


@app.post("/ingest/{source_name}")
async def receive_data(source_name: str, request: Request):
    """Receive data from external sources. Matches to a source by name."""
    try:
        payload = await request.json()
    except Exception:
        payload = {"raw": (await request.body()).decode("utf-8", errors="replace")}

    with SessionLocal() as db:
        src = db.query(Source).filter(
            Source.name == source_name,
            Source.collector_type == "webhook_in",
            Source.enabled == True
        ).first()

        if not src:
            raise HTTPException(status_code=404, detail=f"No active webhook_in source named '{source_name}'")

        item = CollectedItem(
            source_id=src.id, source_name=src.name, source_type="webhook_in",
            title=payload.get("title", payload.get("event", "Webhook data")),
            content=json.dumps(payload, indent=2)[:100000],
            url=payload.get("url", ""),
            published_at=datetime.utcnow(),
            raw_data=payload,
        )
        db.add(item)
        db.commit()
        db.refresh(item)

        evaluate_items(src, [item])

        return {"status": "ok", "source": source_name, "item_id": item.id}


if __name__ == "__main__":
    log("Pulse webhook gateway starting on port 8100...")
    uvicorn.run(app, host="0.0.0.0", port=8100)
