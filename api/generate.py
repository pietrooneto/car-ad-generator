import os, json, requests

def handler(request):
    if request.method != "POST":
        return {"statusCode": 405, "headers": {}, "body": "Method Not Allowed"}

    try:
        data = request.get_json() or {}
    except Exception:
        try:
            data = json.loads(request.body.decode("utf-8"))
        except Exception:
            data = {}

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

    GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
    MODEL = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")
    if not GROQ_API_KEY:
        return {
            "statusCode": 500,
            "headers": { "Content-Type": "application/json" },
            "body": json.dumps({"error": "GROQ_API_KEY non configurata"})
        }

    try:
        resp = requests.post(
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
                "max_tokens": 600,
            },
            timeout=30,
        )
        if resp.status_code == 429:
            return {
                "statusCode": 429,
                "headers": { "Content-Type": "application/json" },
                "body": json.dumps({"error": "Rate limit superato"})
            }
        if resp.status_code >= 400:
            return {
                "statusCode": 500,
                "headers": { "Content-Type": "application/json" },
                "body": json.dumps({"error": f"Groq error {resp.status_code}", "details": resp.text})
            }
        j = resp.json()
        text = (j.get("choices") or [{}])[0].get("message", {}).get("content", "")
        return {
            "statusCode": 200,
            "headers": { "Content-Type": "application/json" },
            "body": json.dumps({"text": text})
        }
    except requests.RequestException as e:
        return {
            "statusCode": 500,
            "headers": { "Content-Type": "application/json" },
            "body": json.dumps({"error": "Errore rete", "details": str(e)})
        }
