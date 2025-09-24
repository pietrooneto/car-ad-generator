import os, requests
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.get("/health")
def health():
    return jsonify({"ok": True})

@app.post("/")
def generate():
    GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
    MODEL = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")
    if not GROQ_API_KEY:
        return jsonify({"error": "GROQ_API_KEY non configurata"}), 500

    data = request.get_json(silent=True) or {}
    marca   = (data.get("marca") or "").strip()
    modello = (data.get("modello") or "").strip()
    anno    = (data.get("anno") or "").strip()
    km      = (data.get("km") or "").strip()
    optional= (data.get("optional") or "").strip()
    stile   = (data.get("stile") or "professionale").strip()

    prompt = f"""Scrivi una descrizione breve ma convincente (5-7 frasi) per un annuncio auto.

Dati:
- Marca: {marca}
- Modello: {modello}
- Anno: {anno}
- Chilometri: {km}
- Optional/Note: {optional}

Requisiti:
- Tono {stile}
- Includi 3-5 bullet con punti di forza
- Chiudi con una call-to-action breve.
Scrivi in italiano naturale."""

    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": "Sei un copywriter automotive, scrivi in italiano."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.7,
                "max_tokens": 600
            },
            timeout=30
        )
        if r.status_code == 429:
            return jsonify({"error": "Rate limit superato"}), 429
        if r.status_code >= 400:
            return jsonify({"error": f"Groq error {r.status_code}", "details": r.text}), 500

        j = r.json()
        text = (j.get("choices") or [{}])[0].get("message", {}).get("content", "")
        return jsonify({"text": text or "Nessuna risposta."})
    except requests.RequestException as e:
        return jsonify({"error": "Errore rete", "details": str(e)}), 500
