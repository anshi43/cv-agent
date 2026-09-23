# 🪟 CV Tailor Agent — Exact Windows Setup Guide

**No experience needed.** Every step below is either a double-click or a copy-paste.
Total one-time setup: ~30 minutes (most of it is two downloads running in the background).

---

## What you will install (all free)

| # | What | Why | Size | Time |
|---|------|-----|------|------|
| 1 | **Ollama** | Runs the AI brain on your PC (offline, private) | ~200 MB | 2 min |
| 2 | **Python** | Runs the web app itself | ~30 MB | 2 min |
| 3 | **The AI model** (`llama3.1:8b`) | The actual intelligence, downloaded once | ~5 GB | 10–30 min depending on internet |
| 4 | **App extras** (4 small libraries) | One command does it | ~5 MB | 1 min |

Your CV and the job ad **never leave your computer** — everything runs locally.

---

## PART 1 — Install Ollama (the AI engine)

1. Open your browser and go to: **https://ollama.com/download**
2. Click the big **Download for Windows** button.
3. When the download finishes, double-click **OllamaSetup.exe** (it lands in your `Downloads` folder).
   - ⚠️ If a blue popup says *"Windows protected your PC"*, click **More info → Run anyway**. (This is normal for new apps.)
4. Click **Install**. Wait ~1 minute. Done.
5. ✅ **Check:** Look at the bottom-right corner of your screen near the clock. Click the little **^** arrow — you should see a **llama 🦙 icon**. That means Ollama is running. It starts automatically every time Windows starts, so you never have to think about it again.

> ℹ️ On Windows you do **NOT** need to type `ollama serve` (the tray icon already does that job).

---

## PART 2 — Install Python (runs the app)

1. Go to: **https://www.python.org/downloads/**
2. Click the big yellow button: **Download Python 3.x.x**.
3. Double-click the downloaded file (e.g. `python-3.13.x-amd64.exe`).
4. ⚠️ **THE MOST IMPORTANT STEP IN THIS WHOLE GUIDE:**
   On the first screen, at the bottom, **tick the checkbox that says `Add python.exe to PATH`** before clicking anything else.
5. Now click **Install Now** → wait → **Close**.
6. ✅ **Check:** Press the **Windows key**, type `powershell`, press **Enter**. A blue window opens. Type the following and press Enter:
   ```powershell
   python --version
   ```
   You should see something like `Python 3.13.1`. If instead a **Microsoft Store window** opens, Python wasn't added to PATH — run the installer again and make sure the checkbox in step 4 is ticked.

---

## PART 3 — Get the app (1 download, no typing)

1. In this chat, open the file list and click **`cv-agent.zip`** to download it (it lands in `Downloads`).
2. Right-click `cv-agent.zip` → **Extract All…** → click **Extract**.
3. A folder called `cv-agent` opens. Keep it somewhere you'll find it again, e.g. leave it in `Downloads` or drag it to your Desktop.
4. ✅ **Check:** Opening the folder, you should see `app.py`, `README.md`, `requirements.txt`, `SETUP-WINDOWS.md` (this file), `sample_cv.txt`, `sample_job.txt`, and two subfolders (`agent`, `templates`).

---

## PART 4 — Install the app's extras (one command)

1. Open the `cv-agent` folder in File Explorer.
2. **Trick to open a terminal exactly in this folder:** click once into the **address bar** at the top of the File Explorer window (where the folder path is shown), type `powershell` and press **Enter**.
   → A blue terminal window opens, already pointed at the right folder.
3. Copy-paste this line and press Enter:
   ```powershell
   python -m pip install -r requirements.txt
   ```
4. ✅ **Check:** The last line should say something like `Successfully installed flask-… pypdf-… python-docx-… requests-…`.

---

## PART 5 — Download the AI model (the big 5 GB one-time download)

1. In the same blue terminal window, copy-paste:
   ```powershell
   ollama pull llama3.1:8b
   ```
2. Wait. You'll see a progress bar. On a normal connection this takes 10–30 minutes. ☕
3. ✅ **Check:** When it's done, type:
   ```powershell
   ollama list
   ```
   You should see `llama3.1:8b` in the table.

> 💪 **Does your PC have less than 8 GB of RAM?** Use the smaller model instead:
> ```powershell
> ollama pull llama3.2:3b
> ```
> and when starting the app later (Part 6), use this start command instead:
> ```powershell
> $env:OLLAMA_MODEL="llama3.2:3b"; python app.py
> ```

---

## PART 6 — Start the app 🚀

1. In the `cv-agent` folder's blue terminal window (the address-bar trick from Part 4), type:
   ```powershell
   python app.py
   ```
2. ✅ **Check:** You should see a line like:
   ```
   * Running on http://0.0.0.0:8000
   ```
3. Open your browser (Chrome/Edge/Firefox) and go to: **http://localhost:8000**
4. The dot in the top-right corner of the page should be **green** = AI ready.
   - If it's red, refresh the page after 10 seconds (Ollama might still be waking up).
5. **Use it:**
   - Upload your CV (PDF, DOCX or TXT)
   - Paste the job advertisement into the big text box
   - Click **Run the agent** — watch the 7 steps light up (~2–5 min with the 8B model)
   - Download your **tailored CV (.docx)**, **cover letter (.docx)** and **fit report (.zip)**
   - Tip: try **Quick ATS scan** first — it scores your CV against the job ad in 1 second, no AI needed. Sample files are included: `sample_cv.txt` and `sample_job.txt`.

> 🔥 If a blue **Windows Firewall** popup appears, just click **Allow access**. (The app only talks to your own browser — it doesn't open anything to the internet.)

---

## PART 7 — Every other time you want to use it (30 seconds)

1. Make sure the **llama icon** is in the tray (bottom-right, near the clock). If not: press the Windows key → type `ollama` → open it.
2. Open the `cv-agent` folder → click the address bar → type `powershell` → Enter.
3. Type:  `python app.py`
4. Browser → **http://localhost:8000**

To **stop** the app: click on the blue terminal window and press **Ctrl + C**. To close the terminal: type `exit`.

---

## 🆘 Troubleshooting

| Problem | Fix |
|---|---|
| `python` is not recognized… (or Microsoft Store opens) | Re-run the Python installer from Part 2 and **tick "Add python.exe to PATH"**. Then close and reopen the terminal. |
| `pip` is not recognized | Use the long form: `python -m pip install -r requirements.txt` |
| The page shows a **red dot** / "demo mode" | Ollama isn't running. Check for the tray llama icon; if missing, start Ollama from the Start menu. Then refresh the page. |
| `ollama: command not found` after installing | Close the terminal window and open a new one (the terminal only learns about new programs on startup). |
| `model 'llama3.1:8b' not found` | You skipped Part 5. Run `ollama pull llama3.1:8b`. See what you have with `ollama list`. |
| Answers are very slow or the PC struggles | Your PC probably has < 8 GB RAM. Use the 3B model (see the box in Part 5). |
| `Address already in use` | The app is already running in another window. Close that window (Ctrl + C), or start on another port: `$env:PORT="8080"; python app.py` |
| "Run the agent" gives an error about connection | Same as red dot: Ollama isn't running. |
| I want it to stop talking… the download is huge | The 5 GB model download is one-time. After that everything is offline. |

---

## 🔒 Privacy

Everything — CV parsing, the AI, the ATS score — runs on your own PC. No account, no API key, no internet needed after setup, no data leaves your machine. Uninstalling is easy: uninstall *Ollama* and *Python* from Windows Settings → Apps whenever you want.

*Questions you can always ask me in this chat. Happy job hunting!* 🍀
