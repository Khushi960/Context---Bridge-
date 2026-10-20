# Context Bridge

Write a project's state once, then paste a handoff into Claude, ChatGPT or Gemini and continue without re-explaining.

- **frontend/**  React + TypeScript (Vite). warm paper-style form page, autosave, live handoff preview, one-click copy per tool.
- **backend/**   FastAPI + SQLite. Stores packets, formats handoffs, and calls an LLM (Anthropic API) to fill a packet from a pasted chat or to condense a long transcript.
- **frontend/dist/**  A prebuilt copy of the frontend. The backend serves it, so you do not need Node to run the app.

## Run (Python only)

    cd backend
    python3 -m pip install -r requirements.txt
    cp .env.example .env          # then paste ONE key into .env: ANTHROPIC_API_KEY (Claude) or GEMINI_API_KEY (Gemini)
    python3 -m uvicorn app.main:app --reload

Open http://127.0.0.1:8000 . You will see the login page. Click **Create account**, pick a unique username and a password (8+ characters), and tick the academic-integrity promise.

The app works without an API key. Only "Fill from chat", "Condense with AI" and "Double-check with AI" need one. If both keys are set, Claude is used unless `CONTEXT_BRIDGE_PROVIDER=gemini`. If Google retires the Gemini model (HTTP 404), the app asks Google which models your key can use, switches to a current Flash model and retries. You can still pin one with `CONTEXT_BRIDGE_GEMINI_MODEL`.

## Develop the frontend (needs Node 18+)

    cd frontend
    npm install
    npm run dev                    # http://localhost:5173, proxies /api to port 8000
    npm run build                  # rebuilds frontend/dist

## API (docs at /docs)

| Method | Path | What it does |
|---|---|---|
| GET | /api/health | Server status and whether an API key is set (no login needed) |
| POST | /api/auth/register | Create an account (unique username, password 8+ characters) and log in |
| POST | /api/auth/login | Log in. Sets an HttpOnly session cookie |
| POST | /api/auth/logout | Log out and delete the session |
| GET | /api/auth/me | The logged-in user, or 401 |
| GET, POST | /api/packets | List or create **your** packets |
| GET, PUT, DELETE | /api/packets/{id} | Read, save or delete one packet |
| POST | /api/extract | LLM reads a chat transcript and returns packet fields |
| POST | /api/integrity | Academic-integrity check on a packet (`deep: true` lets the LLM re-read the flagged line) |
| POST | /api/handoff | Formats a packet for claude, chatgpt or gemini within a token limit. `summarize: true` has the LLM write a clean briefing from the notes (and recent chat) instead of copying them as typed. Returns `blocked: true` and no text if the integrity check is unanswered |

Every route except `/api/health` and `/api/auth/*` needs a login. A request without one gets `401`.

## Login (one private space per user)

`backend/app/auth.py` and the `users` and `sessions` tables in `contextbridge.db`.

- **Unique users.** Usernames are unique, ignoring capital letters (`Asha` and `asha` are the same name).
- **Private packets.** Each packet stores its owner. A user can only list, open, save or delete their own packets. Asking for someone else's packet id returns 404, as if it did not exist.
- **Passwords are never stored.** Only a salted PBKDF2-SHA256 hash (200,000 rounds, Python standard library).
- **Sessions.** Logging in sets a random token in an HttpOnly cookie (JavaScript cannot read it) for 30 days. The database keeps only a SHA-256 hash of the token. Log out deletes it. When serving over https, set `CONTEXT_BRIDGE_SECURE_COOKIE=1` in `.env`.
- **Wrong passwords.** After 5 wrong tries for a username, that username is locked for 15 minutes. The error never says whether the username exists.
- **AI routes need a login** (`/extract`, `/integrity`, `/handoff`), so nobody else on the network can spend your API key.
- **Old data.** Packets saved before login existed are given to the first account created.
- **Frontend.** `frontend/public/login.html` is the login and sign-up page. `frontend/public/session.js` runs before the app: it sends you to the login page when you are not logged in or your session ends, and adds "Signed in as ..." and **Log out** at the bottom of the sidebar. Both are plain files with no build step, and are already copied into `frontend/dist`.
- **Integrity at sign-up.** Creating an account requires ticking "I will not use it to get answers while a test or exam is going on". The login page also explains the warning and lock described below.

## How it works

1. A packet holds goal, status, decisions, constraints, facts, open questions, answer style and recent chat.
2. `formatting.py` renders it per tool: XML tags for Claude, Markdown for ChatGPT, plain sections for Gemini.
3. Tokens are estimated as characters / 4. If the chat is too long it is trimmed from the top, or the LLM condenses it.
4. `llm.py` holds every model call, for Claude (Anthropic SDK) or Gemini (plain REST, key sent in a header). Set CONTEXT_BRIDGE_MODEL or CONTEXT_BRIDGE_GEMINI_MODEL in .env to change the model.

## AI summary (the main button)

With an API key set, the "AI summary" switch in the top bar is on. Clicking **Copy for Claude / ChatGPT / Gemini** sends your notes (and recent chat) to the model, which writes a short, clean briefing in that tool's style. It is wrapped, given the integrity note if one applies, and copied. The raw chat is not copied, only what the next AI needs. If the model call fails, the plain structured handoff is copied instead and the toast says why. With the switch off, or with no key, the notes are copied as typed.

## Academic-integrity guard

`backend/app/ethics.py` reads the packet (fields and recent chat) and gives one of three levels:

| Level | Example | What happens |
|---|---|---|
| allow | "Explain how SQLite stores JSON", "check my answer to the practice paper" | Nothing |
| ask | "Solve this quiz for me and give me the answers" | The handoff is locked until the student says it is practice (not graded) or that the instructor allows AI |
| ask | "give answers to these questions" (a plain request for ready-made answers) | Same: the student is asked if a test may be going on |
| warn | "Give me the answers, the test is live right now", "make sure the teacher can't detect it" | Same lock, with a stronger warning |
| warn | Goal "give answers to these questions" + constraint "1hr left" | The whole packet is read together: an answer request in one field plus time pressure in another (hours, minutes, "time is running out", "hurry", "asap") means a test may be on |

- **Long chats:** phrase rules cannot see an exam question that has no trigger words. So the AI also reads the notes and the whole chat (`ethics.deep_check`, prompt `INTEGRITY_SYSTEM` in `llm.py`) and looks for exam-style wording, marks, repeated requests for "another answer", time pressure and plans to submit. It runs automatically when you press Copy with AI summary on, after "Fill from chat", and on the "Check this chat" link. A red or amber banner appears at the top of the page until the student answers. The AI verdict can raise the level but never lowers a rule hit, and it is cached by content, so repeats cost nothing. If the model is unreachable, only the rules run.
- The student's answer is stored in the packet and tied to the flagged text, so changing the text asks again.
- Once answered, one line about it is added to the handoff for Claude, ChatGPT and Gemini, so the flag travels with the packet.
- The rules are plain regular expressions (readable, testable). "Double-check with AI" in the dialog asks the model to re-read only the flagged line, and its verdict is cached. A model can lower a warn to ask, never to allow.
- It is a nudge, not enforcement: it cannot know whether a test is really live, and rules will miss some phrasings and flag some honest ones. Nothing is logged or sent anywhere by the guard itself.

Test and measure it (from `backend/`):

    python3 -m pip install httpx           # only needed for the login tests (tests/test_auth.py)
    python3 -m unittest discover -s tests -v
    python3 eval/run_eval.py                # confusion matrix, precision and recall on eval/prompts.jsonl

The 15 bundled prompts are only a starter set written by the developer. For a paper, build a larger set labelled by other people.
