"""CV Tailor Agent — free, local, private.

Run:  python app.py     ->  http://localhost:8000
"""
from __future__ import annotations

import io
import json
import os
import queue
import re
import threading
import uuid
import zipfile

from flask import (Flask, Response, jsonify, render_template, request,
                   send_file, stream_with_context)

from agent import ats, export, llm, parse, pipeline

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 12 * 1024 * 1024  # 12 MB uploads

JOBS: dict[str, dict] = {}          # in-memory results, keyed by job id
MAX_JOBS = 40


def _remember(job_id: str, payload: dict) -> None:
    JOBS[job_id] = payload
    if len(JOBS) > MAX_JOBS:
        for k in list(JOBS)[:-MAX_JOBS]:
            JOBS.pop(k, None)


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/status")
def status():
    up = llm.available()
    return jsonify({
        "ollama": up,
        "host": llm.OLLAMA_HOST,
        "models": llm.list_models() if up else [],
        "default_model": llm.DEFAULT_MODEL,
    })


@app.post("/api/extract")
def extract():
    """Upload a CV file -> plain text, so the user can see/edit what the ATS sees."""
    f = request.files.get("file")
    if not f:
        return jsonify({"error": "No file uploaded."}), 400
    try:
        text = parse.load(f.filename, f.read())
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    if len(text.strip()) < 50:
        return jsonify({
            "text": text,
            "warning": "Almost no text extracted — this PDF is probably a scan/image. "
                       "Paste your CV text manually instead."
        })
    return jsonify({"text": text})


@app.post("/api/analyze")
def analyze():
    """Fast, LLM-free ATS scan — instant feedback while you type."""
    data = request.get_json(force=True)
    cv, jd = data.get("cv", ""), data.get("jd", "")
    if not cv.strip() or not jd.strip():
        return jsonify({"error": "Both CV and job description are required."}), 400
    m = ats.match(cv, jd)
    m["hygiene"] = ats.readability_flags(cv)
    return jsonify(m)


@app.post("/api/run")
def run():
    """Kick off the full agent pipeline, streaming progress via SSE."""
    data = request.get_json(force=True)
    cv, jd = data.get("cv", ""), data.get("jd", "")
    model = data.get("model") or None
    tone = data.get("tone") or "professional"
    if not cv.strip() or not jd.strip():
        return jsonify({"error": "Both CV and job description are required."}), 400

    job_id = uuid.uuid4().hex[:12]

    def generate():
        q: "queue.Queue[dict]" = queue.Queue()
        box: dict = {}

        def emit(stage, st, extra=None):
            q.put({"stage": stage, "status": st, **(extra or {})})

        def worker():
            try:
                box["result"] = pipeline.run(cv, jd, model=model, tone=tone, emit=emit)
            except Exception as e:                      # noqa: BLE001
                box["error"] = str(e)
            finally:
                q.put({"stage": "__end__", "status": "done"})

        threading.Thread(target=worker, daemon=True).start()
        yield _sse({"stage": "start", "status": "start", "job_id": job_id})

        while True:
            try:
                ev = q.get(timeout=15)
            except queue.Empty:
                yield ": keep-alive\n\n"
                continue
            if ev.get("stage") == "__end__":
                break
            yield _sse(ev)

        if "error" in box:
            yield _sse({"stage": "error", "status": "error", "message": box["error"]})
            return
        res = box.get("result", {})
        res["job_id"] = job_id
        _remember(job_id, res)
        yield _sse({"stage": "result", "status": "done", "result": res})

    return Response(stream_with_context(generate()),
                    mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


def _slug(s: str) -> str:
    s = re.sub(r"[^\w\s-]", "", s or "").strip().lower()
    return re.sub(r"[\s_-]+", "-", s)[:40] or "application"


@app.get("/api/download/<job_id>/<kind>")
def download(job_id: str, kind: str):
    job = JOBS.get(job_id)
    if not job:
        return jsonify({"error": "Job not found (server restarted?). Re-run the agent."}), 404

    jd = job.get("jd") or {}
    base = _slug(f"{jd.get('job_title','')}-{jd.get('company','')}") or "application"
    cv_md = job.get("cv_markdown", "")
    letter_md = job.get("cover_letter", "")

    if kind == "cv.docx":
        return _send(export.markdown_to_docx(cv_md), f"CV-{base}.docx",
                     "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    if kind == "letter.docx":
        return _send(export.markdown_to_docx(letter_md), f"CoverLetter-{base}.docx",
                     "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    if kind == "cv.md":
        return _send(cv_md.encode(), f"CV-{base}.md", "text/markdown")
    if kind == "letter.md":
        return _send(letter_md.encode(), f"CoverLetter-{base}.md", "text/markdown")
    if kind == "bundle.zip":
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr(f"CV-{base}.md", cv_md)
            z.writestr(f"CV-{base}.docx", export.markdown_to_docx(cv_md))
            z.writestr(f"CoverLetter-{base}.md", letter_md)
            z.writestr(f"CoverLetter-{base}.docx", export.markdown_to_docx(letter_md))
            z.writestr("fit-report.json", json.dumps({
                "ats_before": job.get("ats_before"),
                "ats_after": job.get("ats_after"),
                "gaps": job.get("gaps"),
                "audit": job.get("audit"),
                "hygiene": job.get("hygiene"),
            }, ensure_ascii=False, indent=2))
        return _send(buf.getvalue(), f"application-{base}.zip", "application/zip")
    return jsonify({"error": "Unknown download type."}), 404


def _send(data: bytes, name: str, mime: str):
    return send_file(io.BytesIO(data), mimetype=mime,
                     as_attachment=True, download_name=name)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
