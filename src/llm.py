import requests
import json
from datetime import datetime
from src.database import SessionLocal, SystemConfig


def get_llm_config():
    with SessionLocal() as session:
        config = session.query(SystemConfig).first()
        if config and config.llm_endpoint:
            return config
    return None


def call_llm(messages, config=None, temperature=0.1, timeout=120):
    if config is None:
        config = get_llm_config()
    if not config or not config.llm_endpoint:
        return None

    headers = {"Content-Type": "application/json"}
    if config.llm_api_key:
        headers["Authorization"] = f"Bearer {config.llm_api_key}"

    payload = {
        "model": config.llm_model_name or "gpt-3.5-turbo",
        "messages": messages,
        "temperature": temperature
    }

    url = config.llm_endpoint.rstrip('/') + "/chat/completions"

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=timeout)
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
    except requests.exceptions.Timeout:
        return "[WARN] LLM request timed out"
    except requests.exceptions.ConnectionError:
        return "[WARN] LLM connection refused"
    except Exception as e:
        return f"[WARN] LLM error: {e}"


def chunk_list(data, size):
    for i in range(0, len(data), size):
        yield data[i:i + size]


def generate_alert_summary(alerts):
    config = get_llm_config()
    if not config or not alerts:
        return None

    context = "\n".join([
        f"- [{a.get('severity', '?').upper()}] {a.get('title', '?')}: {a.get('message', '')[:200]}"
        for a in alerts[:15]
    ])

    if not context:
        return None

    response = call_llm([
        {"role": "system", "content": "You are a monitoring operations manager. Summarize the recent alerts into a concise 2-3 paragraph briefing. Group related alerts. Highlight the most critical items first."},
        {"role": "user", "content": f"Recent alerts:\n{context}"}
    ], config, temperature=0.2)

    return response.strip() if response and "[WARN]" not in response else None
