# CV Tailor Agent

Paste a job ad + your CV → get a **rewritten, ATS-optimised CV**, a **cover letter**, and a **gap report**.

Runs entirely on your own machine with [Ollama](https://ollama.com). No API key, no subscription,
no cloud. Your CV never leaves your laptop.

---

## Cost: €0

| Piece | What it costs |
|---|---|
| LLM (Ollama + Llama 3.1 8B) | Free, runs locally, unlimited use |
| Web UI (Flask) | Free |
| PDF/DOCX parsing (pypdf, python-docx) | Free |
| ATS keyword engine | Free — pure Python, no model needed |

Hardware: an 8B model needs roughly **8 GB of RAM**. On 16 GB you can run `llama3.1:8b` or
`qwen2.5:14b` comfortably. On 8 GB use `llama3.2:3b` or `phi3.5`.

---

## Setup (5 minutes)

```bash
# 1. Install Ollama — https://ollama.com/download  (macOS, Windows, Linux)
curl -fsSL https://ollama.com/install.sh | sh        # Linux/macOS

# 2. Pull a model
ollama pull llama3.1:8b        # best all-rounder, ~4.7 GB
# ollama pull qwen2.5:14b      # better writing, needs ~16 GB RAM
# ollama pull llama3.2:3b      # low-RAM fallback

# 3. Start the model server (leave it running)
#    Linux/macOS:   ollama serve
#    Windows:       nothing to do — Ollama runs in the system tray automatically
ollama serve

# 4. Run the app
python -m pip install -r requirements.txt      # Windows: use this form
python app.py

# Full click-by-click walkthrough for Windows: see SETUP-WINDOWS.md
```

Open **http://localhost:8000**.

The header shows a green dot when Ollama is connected. Without it the app still runs in
**demo mode**: the deterministic ATS scanner works fully, the LLM rewrites don't.

### Config

| Env var | Default | Meaning |
|---|---|---|
| `OLLAMA_HOST` | `http://localhost:11434` | Where Ollama listens |
| `OLLAMA_MODEL` | `llama3.1:8b` | Default model |
| `OLLAMA_TIMEOUT` | `600` | Seconds per LLM call |
| `PORT` | `8000` | Web UI port |

```bash
OLLAMA_MODEL=qwen2.5:14b PORT=9000 python app.py
```

---

## How the agent works

It's not one big prompt — it's a **chain of specialised steps**, each one grounded in the
previous step's output. That is what makes the result reliable instead of generic.

```
                 ┌───────────────────────────────────┐
  CV file ──────▶│ 1. parse   PDF/DOCX/TXT → text    │
                 └───────────────┬───────────────────┘
  Job ad ────┐                   │
             ▼                   ▼
   ┌──────────────────┐  ┌──────────────────┐
   │ 2. LLM: analyse  │  │ 3. LLM: parse CV │
   │    the job ad    │  │    → JSON profile│
   │    → JSON criteria│ └────────┬─────────┘
   └────────┬─────────┘           │
            │      ┌──────────────┴──────────┐
            │      ▼                         │
            │ ┌──────────────────────────┐   │
            └▶│ 4. TOOL: ATS keyword     │◀──┘
              │    match (deterministic) │
              └────────────┬─────────────┘
                           ▼
              ┌──────────────────────────┐
              │ 5. LLM: gap analysis     │
              │    strengths / gaps /    │
              │    keywords to add       │
              └────────────┬─────────────┘
                           ▼
              ┌──────────────────────────┐
              │ 6. LLM: rewrite the CV   │
              └────────────┬─────────────┘
                           ▼
              ┌──────────────────────────┐
              │ 7. LLM: FACT-CHECK the   │
              │    draft vs original CV  │
              └────────────┬─────────────┘
                    issues?│yes → 8. LLM: revise ──┐
                           │no                     │
                           ▼◀──────────────────────┘
              ┌──────────────────────────┐
              │ 9. LLM: cover letter     │
              │10. TOOL: re-score ATS    │
              └────────────┬─────────────┘
                           ▼
              CV.docx · CoverLetter.docx · fit-report.json
```

### The two design decisions that matter

**1. The score is computed, not generated.** `agent/ats.py` does keyword extraction and
matching in plain Python. An LLM asked "rate this CV out of 100" will just make a number up.
This one is reproducible and you can see exactly which keywords drove it.

**2. There's a fact-checking pass with a repair loop.** The single biggest danger in CV
automation is a model inventing a job, a tool or a metric — that gets you caught in an
interview. Step 7 audits the rewrite against your original CV; if it finds unsupported
claims, step 8 rewrites with those corrections. This is the "agentic" part: the system
critiques and fixes its own work before showing it to you.

---

## Files

```
cv-agent/
├── app.py                 Flask server, SSE progress stream, downloads
├── requirements.txt
├── agent/
│   ├── parse.py           PDF / DOCX / TXT → clean text
│   ├── llm.py             Ollama client (chat + JSON mode)
│   ├── ats.py             Deterministic keyword engine + hygiene checks
│   ├── prompts.py         All prompts — tune the agent here, no code changes
│   ├── pipeline.py        The agent loop (steps 1–10)
│   └── export.py          Markdown → ATS-safe .docx
└── templates/index.html   Single-file UI
```

**To change the agent's behaviour, edit `agent/prompts.py`.** Want a German-only CV? A
one-page hard limit? A different bullet formula? It's all plain English in that one file.

---

## Using it well

1. **Paste the whole job ad**, not a summary. Requirements sections are what the keyword
   engine weights most heavily.
2. **Check the extracted CV text.** If your PDF is a scan, extraction returns nothing —
   paste your CV as text instead. If the ATS can't read it, neither can a real one.
3. **Hit "Quick ATS scan" first.** It's instant and LLM-free — good for deciding whether a
   job is even worth applying to.
4. **Read the Fit & gaps tab.** Blocking gaps are the ones you should address in the cover
   letter or reconsider applying for.
5. **Always proof-read.** The fact-checker is good, not perfect. You're the last check.

---

## Extending it

- **Swap in a cloud model for free:** `agent/llm.py` is ~60 lines. Google Gemini
  (`aistudio.google.com`) and Groq both have free tiers with OpenAI-compatible endpoints —
  point `chat()` at them and everything else keeps working.
- **Batch mode:** import `pipeline.run(cv_text, jd_text)` in a script and loop over a folder
  of job ads.
- **Persistence:** results live in an in-memory dict (`JOBS` in `app.py`); swap in SQLite to
  keep an application history.
- **Better PDF output:** the app exports `.docx`; open it in Word/LibreOffice and "Save as
  PDF". Or add WeasyPrint if you want direct PDF.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Red dot, "Ollama offline" | Make sure Ollama is running (Windows: llama icon in the system tray; Linux/macOS: run `ollama serve`) and reload the page |
| "Model not found" | `ollama pull llama3.1:8b` |
| Very slow (>5 min) | Use a smaller model: `OLLAMA_MODEL=llama3.2:3b python app.py` |
| "Model did not return valid JSON" | Small models struggle with JSON — use an 8B+ model |
| Empty CV text after upload | Your PDF is image-based; paste the text manually |
| Download says "Job not found" | Server restarted — re-run the agent |
