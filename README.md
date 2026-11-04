# Parting Pal

Parting Pal is an AI exit-interview assistant. HR invites a departing employee, the employee has a short chat (or uses voice input) with Parting Pal, and HR gets a summary, the reasons for leaving sorted into fixed categories, a sentiment score and reports.

- **Backend:** Python 3.11, FastAPI, SQLAlchemy (Postgres or SQLite)
- **Frontend:** React 18, TypeScript, Vite
- **Models:** OpenAI, Google Gemini, or any open-source model behind an OpenAI-compatible API (Qwen or Llama via Ollama, vLLM, LM Studio or DashScope). HR picks the provider and model for each interview.

## How the interview avoids loops

The model writes the wording of each message, but the code decides what to ask next. The logic is in [backend/app/interview/flow.py](backend/app/interview/flow.py).

1. **Fixed topic order.** There are 8 topics in [topics.py](backend/app/interview/topics.py). Each is asked once, with at most `MAX_FOLLOWUPS_PER_TOPIC` follow-ups, then the interview moves on.
2. **Classifier after each reply.** A small JSON call ([engine.py](backend/app/interview/engine.py)) labels the employee's reply as *answered*, *declined*, *wants to end*, or *also covered topic X*.
   - A declined topic is skipped for good.
   - A topic the employee already discussed in passing is marked covered and not asked.
   - If the classifier fails, the interview moves on rather than repeating the question.
3. **Progress in the prompt.** The covered, declined and upcoming topics, plus a single task for this message, go into the system prompt every turn ([prompts.py](backend/app/interview/prompts.py)). The instruction never says "begin the interview". The start is sent as a hidden first user message.
4. **Memory comes from the database.** The full transcript is loaded from the database on every turn. A page refresh, server restart or a different server instance always continues the same conversation.
5. **Repeat guard.** If a generated question is about 85% or more similar to an earlier one, it is regenerated with a correction.
6. **The interview ends in code.**
   - After the last topic there is a recap and "anything else?", then the close.
   - `MAX_USER_TURNS` (default 20) is a hard limit; wrap-up starts one turn before it.
   - The employee can end the interview at any time.
   - `[INTERVIEW_COMPLETE]` is requested in the closing message and stripped before display. The code ends the interview whether or not the model includes it.
7. **Summary afterwards.** The summary runs in the background after completion.
   - The output is validated JSON with reasons mapped to fixed categories, so reports aggregate cleanly.
   - Failures are stored on the interview so HR can retry with **Regenerate summary**.

## Running locally

```bash
# Backend
cd backend
python -m venv .venv && .venv/Scripts/activate      # or: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # set at least one provider; for a quick start use
                        # DATABASE_URL=sqlite:///./partingpal.db and AUTH_DISABLED=true
uvicorn app.main:app --reload --port 8000
pytest                  # flow and API tests using a scripted fake model

# Frontend (separate terminal)
cd frontend
npm install
cp .env.example .env    # set VITE_GOOGLE_CLIENT_ID, or leave it empty for dev mode
npm run dev             # http://localhost:5173 (proxies /api to :8000)
```

### Using Qwen locally with Ollama

```bash
ollama pull qwen2.5:7b-instruct
# backend/.env
OSS_BASE_URL=http://localhost:11434/v1
OSS_MODELS=qwen2.5:7b-instruct,qwen3:8b
```

Qwen3's `<think>` blocks are removed automatically. Smaller local models handle the classifier's JSON less reliably. If one makes a mistake, the interview moves on; it doesn't loop.

### Docker

```bash
cp backend/.env.example backend/.env    # fill in keys and the admin allowlist
docker compose up --build               # http://localhost:8080
```

## HR sign-in

The dashboard uses Google Sign-In.
- The backend verifies the Google ID token on every request.
- It only allows accounts listed in `ADMIN_ALLOWED_EMAILS` or `ADMIN_ALLOWED_DOMAINS`. If both are empty, nobody can sign in.
- `AUTH_DISABLED=true` turns sign-in off. Use it only for local development.

To set up Google Sign-In:
1. Create an OAuth client of type "Web application" in Google Cloud Console.
2. Add your frontend URL as an authorised JavaScript origin.
3. Set `GOOGLE_CLIENT_ID` (backend) and `VITE_GOOGLE_CLIENT_ID` (frontend) to the same client id.

## Employee links

- Each link holds a random 32-byte token and expires after `LINK_VALID_DAYS`. HR can extend it.
- After an interview is completed, its link no longer shows the transcript.
- Voice recordings are converted to 16 kHz WAV in the browser and transcribed with OpenAI or Gemini.
  - The employee reviews and edits the text before sending.
  - Audio is never stored.

## Configuration

See [backend/.env.example](backend/.env.example) for every setting. The ones you will most often change:

| Setting | Default | Purpose |
|---|---|---|
| `DEFAULT_PROVIDER` | `gemini` | Provider preselected in the invite form |
| `*_MODELS` | see file | Models HR can choose from; the first one is the default |
| `MAX_USER_TURNS` | 20 | Hard limit on employee replies |
| `MAX_FOLLOWUPS_PER_TOPIC` | 1 | Follow-ups before moving to the next topic |
| `TRANSCRIPTION_PROVIDER` | auto | `openai` or `gemini`, used for voice input |
| `SMTP_*` | unset | Send invitation emails; otherwise HR copies the link |

## Notes for production

- Tables are created on startup. Add Alembic before changing the schema.
- The interview endpoints are protected by the link token but have no rate limiting. Add it at the proxy if links could leak.
- Logs contain interview ids and errors only, never conversation text.
