import os, json, sys, traceback
from http.server import BaseHTTPRequestHandler
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

def _mask(k: str) -> str:
    if not k: return ""
    return (k[:4] + "..." + k[-4:]) if len(k) > 8 else "****"

def _post_json(url: str, payload: dict, headers: dict, timeout: int = 30) -> tuple[int, str]:
    data = json.dumps(payload).encode("utf-8")
    req = Request(url, data=data, headers=headers, method="POST")
    try:
        with urlopen(req, timeout=timeout) as resp:
            return resp.getcode(), resp.read().decode("utf-8", "replace")
    except HTTPError as e:
        try:
            body = e.read().decode("utf-8", "replace")
        except Exception:
            body = str(e)
        return e.code, body
    except URLError as e:
        return 0, str(e)

class handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: dict, ctype="application/json; charset=utf-8"):
        raw = json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        # Health endpoint: /api/generate (GET)
        self._send(200, {"ok": True, "runtime": "BaseHTTPRequestHandler", "py": sys.version})

    def do_POST(self):
        # ---- Read body safely ----
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length > 0 else b""
        try:
            data = json.loads(raw.decode("utf-8")) if raw else {}
        except Exception:
            data = {}

        # ---- Env ----
        api_key = os.environ.get("GROQ_API_KEY", "")
        model   = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")

        # ---- Debug log (goes to Vercel Function Logs) ----
        print("== /api/generate POST ==")
        print("Headers:", dict(self.headers))
        print("Body:", (raw[:500]).decode("utf-8", "replace"))
        print("Env GROQ_API_KEY set?:", bool(api_key), "masked:", _mask(api_key), "MODEL:", model, flush=True)

        if not api_key:
            self._send(500, {"error": "GROQ_API_KEY non configurata"})
            return

        marca    = (data.get("marca") or "").strip()
        modello  = (data.get("modello") or "").strip()
        anno     = (data.get("anno") or "").strip()
        km       = (data.get("km") or "").strip()
        optional = (data.get("optional") or "").strip()
        stile    = (data.get("stile") or "professionale").strip()

        if not marca or not modello:
            self._send(400, {"error": "Parametri mancanti: 'marca' e 'modello' obbligatori"})
            return

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

        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "Sei un copywriter automotive, scrivi in italiano."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
            "max_tokens": 600
        }

        try:
            status, body = _post_json(url, payload, headers)
            print("Groq status:", status)
            print("Groq body preview:", (body or "")[:600].replace("\n", "\\n"), flush=True)

            if status == 429:
                self._send(429, {"error": "Rate limit superato"})
                return
            if status >= 400 or status == 0:
                self._send(500, {"error": f"Groq error {status}", "details": body})
                return

            try:
                j = json.loads(body)
                text = (j.get("choices") or [{}])[0].get("message", {}).get("content", "")
            except Exception as e:
                self._send(500, {"error": "Risposta non JSON da Groq", "details": str(e), "raw": body[:1000]})
                return

            self._send(200, {"text": text or "Nessuna risposta."})

        except Exception as e:
            trace = traceback.format_exc()
            print("UNEXPECTED ERROR:", repr(e), "\n", trace, flush=True)
            self._send(500, {"error": "Errore inatteso", "details": str(e), "trace": trace})
