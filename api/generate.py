import os
import json
import sys
import traceback
import requests
from flask import Flask, request, jsonify

# ========= LOGGING / DEBUG =========
def _mask_key(k: str) -> str:
    if not k: return ""
    if len(k) <= 8: return "****"
    return f"{k[:4]}...{k[-4:]}"

def _log(*args):
    # stampa su stdout (visibile nei Function Logs di Vercel)
    print(*args, flush=True)

_log("== Booting generate.py ==")
_log("Python:", sys.version)
try:
    import flask
    _log("Flask version:", flask.__version__)
except Exception as e:
    _log("Flask import issue:", repr(e))

# ========= FLASK APP =========
app = Flask(__name__)
app.url_map.strict_slashes = False  # niente redirect tra / e // finale

@app.get("/health")
def health():
    return jsonify({"ok": True, "runtime": "flask", "py": sys.version})

@app.route("/", methods=["POST", "GET"])
def generate():
    # ---- ENV ----
    GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
    MODEL = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")
    _log("Incoming request:", request.method, request.path)
    _log("Env present? GROQ_API_KEY:", bool(GROQ_API_KEY), "masked:", _mask_key(GROQ_API_KEY), "MODEL:", MODEL)

    if request.method != "POST":
        return jsonify({"error": "Method Not Allowed", "hint": "Use POST JSON to this endpoint"}), 405

    if not GROQ_API_KEY:
        _log("ERROR: GROQ_API_KEY missing")
        return jsonify({"error": "GROQ_API_KEY non configurata"}), 500

    # ---- BODY PARSE ----
    try:
        payload = request.get_json(silent=True)
    except Exception:
        payload = None

    if payload is None:
        try:
            payload = json.loads(request.data.decode("utf-8") or "{}")
        except Exception:
            payload = {}

    _log("Request JSON:", json.dumps(payload)[:500])

    marca    = (payload.get("marca") or "").strip()
    modello  = (payload.get("modello") or "").strip()
    anno     = (payload.get("anno") or "").strip()
    km       = (payload.get("km") or "").strip()
    optional = (payload.get("optional") or "").strip()
    stile    = (payload.get("stile") or "professionale").strip()

    if not marca or not modello:
        _log("Validation error: missing marca/modello")
        return jsonify({"error": "Parametri mancanti: 'marca' e 'modello' sono obbligatori"}), 400

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

    # ---- CALL GROQ ----
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "Sei un copywriter automotive, scrivi in italiano."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.7,
        "max_tokens": 600
    }

    _log("Calling Groq:", url, "model:", MODEL)
    try:
        resp = requests.post(url, headers=headers, json=body, timeout=30)
        _log("Groq status:", resp.status_code)
        # log solo anteprima body
        preview = (resp.text or "")[:600].replace("\n", "\\n")
        _log("Groq body preview:", preview)

        if resp.status_code == 429:
            return jsonify({"error": "Rate limit superato"}), 429
        if resp.status_code >= 400:
            return jsonify({"error": f"Groq error {resp.status_code}", "details": resp.text}), 500

        try:
            j = resp.json()
        except Exception as e:
            _log("JSON parse error:", repr(e))
            return jsonify({"error": "Risposta non JSON da Groq", "raw": resp.text[:1000]}), 500

        text = (j.get("choices") or [{}])[0].get("message", {}).get("content", "")
        return jsonify({"text": text or "Nessuna risposta."})

    except requests.RequestException as e:
        _log("Network error:", repr(e))
        return jsonify({"error": "Errore rete verso Groq", "details": str(e)}), 500
    except Exception as e:
        trace = traceback.format_exc()
        _log("Unexpected error:", repr(e), "\n", trace)
        # includo traccia anche nella risposta per debug (rimuovi in prod)
        return jsonify({"error": "Errore inatteso", "details": str(e), "trace": trace}), 500
