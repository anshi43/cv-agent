"""The agent loop.

Steps (each one is a tool call or an LLM call, results feed the next step):

  1. analyse_jd     LLM  -> structured hiring criteria
  2. parse_cv       LLM  -> structured candidate profile
  3. ats_match      tool -> deterministic keyword score (no hallucination possible)
  4. gap_analysis   LLM  -> strengths / gaps / keywords to weave in
  5. write_cv       LLM  -> tailored CV in Markdown
  6. fact_check     LLM  -> audits step 5 against the ORIGINAL CV
  7. revise         LLM  -> only runs if the auditor found issues  (the "agentic" bit)
  8. write_letter   LLM  -> cover letter grounded in the same evidence
  9. rescore        tool -> ATS score of the tailored CV, before/after delta

If Ollama is not reachable the pipeline runs in DEMO mode: steps 3, 9 and a
heuristic version of 4 still work, so you can see the mechanics end to end.
"""
from __future__ import annotations

import json
import time
from typing import Callable

from . import ats, llm, prompts

Emit = Callable[[str, str, dict | None], None]


def _noop(stage: str, status: str, data: dict | None = None) -> None:
    pass


def _truncate(text: str, limit: int = 12000) -> str:
    return text if len(text) <= limit else text[:limit] + "\n…[truncated]"


def run(cv_text: str, jd_text: str, model: str | None = None,
        tone: str = "professional", emit: Emit = _noop) -> dict:
    t0 = time.time()
    result: dict = {"demo_mode": False, "steps": []}

    def step(name, fn, **kw):
        emit(name, "start", None)
        try:
            out = fn(**kw)
            emit(name, "done", None)
            result["steps"].append({"name": name, "ok": True})
            return out
        except Exception as e:
            emit(name, "error", {"message": str(e)})
            result["steps"].append({"name": name, "ok": False, "error": str(e)})
            raise

    # ---- 3. deterministic ATS match (always available) --------------------
    before = ats.match(cv_text, jd_text)
    result["ats_before"] = before
    result["hygiene"] = ats.readability_flags(cv_text)

    if not llm.available():
        result["demo_mode"] = True
        result.update(_demo(cv_text, jd_text, before))
        result["elapsed"] = round(time.time() - t0, 1)
        emit("done", "done", None)
        return result

    # ---- 1. JD analysis ---------------------------------------------------
    jd = step("analyse_jd", llm.chat_json,
              system=prompts.JD_ANALYST,
              user=f"JOB ADVERTISEMENT:\n\n{_truncate(jd_text)}",
              model=model)
    result["jd"] = jd

    # ---- 2. CV parsing ----------------------------------------------------
    profile = step("parse_cv", llm.chat_json,
                   system=prompts.CV_PARSER,
                   user=f"RAW CV:\n\n{_truncate(cv_text)}",
                   model=model)
    result["profile"] = profile

    # ---- 4. gap analysis --------------------------------------------------
    gaps = step("gap_analysis", llm.chat_json,
                system=prompts.GAP_ANALYST,
                user=(
                    f"JOB CRITERIA (JSON):\n{json.dumps(jd, ensure_ascii=False)}\n\n"
                    f"CANDIDATE PROFILE (JSON):\n{json.dumps(profile, ensure_ascii=False)}\n\n"
                    f"KEYWORDS THE ATS SCAN FOUND MISSING: {', '.join(before['missing'][:25])}"
                ),
                model=model)
    result["gaps"] = gaps

    evidence = (
        f"JOB CRITERIA:\n{json.dumps(jd, ensure_ascii=False, indent=1)}\n\n"
        f"CANDIDATE PROFILE:\n{json.dumps(profile, ensure_ascii=False, indent=1)}\n\n"
        f"FIT ANALYSIS:\n{json.dumps(gaps, ensure_ascii=False, indent=1)}\n\n"
        f"ORIGINAL CV (source of truth):\n{_truncate(cv_text, 9000)}\n\n"
        f"TONE: {tone}"
    )

    # ---- 5. write tailored CV --------------------------------------------
    cv_md = step("write_cv", llm.chat,
                 system=prompts.CV_WRITER, user=evidence,
                 model=model, temperature=0.35)
    cv_md = _strip_fences(cv_md)

    # ---- 6/7. fact check + self-repair loop -------------------------------
    audit = step("fact_check", llm.chat_json,
                 system=prompts.FACT_CHECKER,
                 user=f"ORIGINAL CV:\n{_truncate(cv_text, 9000)}\n\nREWRITTEN CV:\n{cv_md}",
                 model=model)
    result["audit"] = audit

    if not audit.get("ok", True) and audit.get("issues"):
        cv_md = _strip_fences(step(
            "revise_cv", llm.chat,
            system=prompts.CV_WRITER,
            user=(evidence + "\n\nPREVIOUS DRAFT:\n" + cv_md +
                  "\n\nThe fact-checker flagged these unsupported claims. Rewrite the CV "
                  "applying every fix and removing anything unsupported:\n" +
                  json.dumps(audit["issues"], ensure_ascii=False)),
            model=model, temperature=0.2))
        result["revised"] = True

    result["cv_markdown"] = cv_md

    # ---- 8. cover letter --------------------------------------------------
    result["cover_letter"] = _strip_fences(step(
        "write_letter", llm.chat,
        system=prompts.LETTER_WRITER, user=evidence,
        model=model, temperature=0.5))

    # ---- 9. rescore -------------------------------------------------------
    after = ats.match(cv_md, jd_text)
    result["ats_after"] = after
    result["delta"] = after["score"] - before["score"]
    result["elapsed"] = round(time.time() - t0, 1)
    emit("done", "done", None)
    return result


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    return t.strip()


# --------------------------------------------------------------------------
# DEMO MODE — no LLM. Shows the deterministic half of the agent working.
# --------------------------------------------------------------------------
def _demo(cv_text: str, jd_text: str, before: dict) -> dict:
    kws = before["keywords"][:12]
    missing = before["missing"][:10]
    title_guess = ""
    for line in jd_text.strip().split("\n")[:6]:
        s = line.strip(" #*-")
        if 3 < len(s) < 80:
            title_guess = s
            break

    cv_md = (
        "> **DEMO MODE — Ollama is not running.** The deterministic ATS engine below is "
        "real output. The rewritten CV and cover letter require a local model: run "
        "`ollama serve` and `ollama pull llama3.1:8b`, then re-run.\n\n"
        f"# Tailored CV — target role: {title_guess or 'see job ad'}\n\n"
        "## What the agent would do with an LLM attached\n"
        f"- Rewrite your summary around: **{', '.join(kws[:6]) or 'the ad’s core terms'}**\n"
        f"- Weave in these missing ATS keywords wherever you genuinely have the skill: "
        f"**{', '.join(missing) or '— none, good coverage'}**\n"
        "- Re-order and re-weight bullets so the most job-relevant role leads\n"
        "- Fact-check every claim back against your original CV, then self-revise\n\n"
        "## Your CV as parsed (first 1500 characters)\n\n```\n"
        + cv_text[:1500] + "\n```\n"
    )
    letter = (
        "**DEMO MODE** — start Ollama to generate a real, evidence-grounded letter.\n\n"
        "Dear Hiring Team,\n\n"
        f"[The agent will open with a specific hook for *{title_guess or 'this role'}*, then "
        "build two proof paragraphs from real achievements in your CV that map to the ad's "
        f"top requirements — currently detected as: {', '.join(kws[:5])} — and close with a "
        "first-90-days statement.]\n\nKind regards,\n"
    )
    return {"cv_markdown": cv_md, "cover_letter": letter,
            "ats_after": before, "delta": 0,
            "gaps": {"verdict": "n/a (demo mode)",
                     "strengths": [], "gaps": [],
                     "keywords_to_add": missing, "reorder_advice": []}}
