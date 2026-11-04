import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { useParams } from "react-router-dom";
import { ApiError, interviewApi, type Message, type PublicState } from "../api";
import AudioRecorder from "../components/AudioRecorder";
import TopicProgressBar from "../components/TopicProgressBar";
import Brand from "../components/Brand";
import ThemeToggle from "../components/ThemeToggle";

export default function InterviewChat() {
  const { token = "" } = useParams();
  const [state, setState] = useState<PublicState | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState<string | null>(null); // message shown while waiting for the reply
  const [busy, setBusy] = useState(false);
  const bottom = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    interviewApi
      .get(token)
      .then(setState)
      .catch((err) => setLoadError(err instanceof ApiError ? err.message : "Couldn't load the interview."));
  }, [token]);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [state?.messages.length, pending]);

  async function run(action: () => Promise<PublicState>, onError?: () => void) {
    setBusy(true);
    setError(null);
    try {
      setState(await action());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
      onError?.();
    } finally {
      setBusy(false);
      setPending(null);
    }
  }

  async function send(event?: FormEvent) {
    event?.preventDefault();
    const text = draft.trim();
    if (!text || busy) return;
    setDraft("");
    setPending(text);
    // On failure nothing is saved server-side, so the text goes back into the box to retry.
    await run(() => interviewApi.send(token, text), () => setDraft(text));
    input.current?.focus();
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      void send();
    }
  }

  async function onRecorded(wav: Blob) {
    const { text } = await interviewApi.transcribe(token, wav);
    // Let the employee review the transcript before sending it.
    setDraft((d) => (d ? `${d} ${text}` : text));
    input.current?.focus();
  }

  if (loadError) {
    return (
      <main className="center-page">
        <div className="card narrow">
          <Brand as="h1" />
          <p>{loadError}</p>
          <p className="muted small">If you think this is a mistake, please contact your HR team for a new link.</p>
        </div>
      </main>
    );
  }
  if (!state) return <main className="center-page muted">Loading…</main>;

  if (state.status === "completed" && state.messages.length > 0) {
    // Just finished: keep the conversation (with the closing message) on screen, read-only.
    return (
      <div className="chat-page">
        <header className="chat-header">
          <Brand />
          <span className="muted small">Interview complete</span>
          <ThemeToggle />
        </header>
        <main className="chat-log">
          {state.messages.map((m) => (
            <div key={m.id} className={`bubble bubble-${m.role}`}>
              {m.content}
            </div>
          ))}
          <div className="notice">Thank you, {state.first_name}. Your feedback has been shared confidentially with HR. You can close this page.</div>
          <div ref={bottom} />
        </main>
      </div>
    );
  }

  if (state.status === "completed") {
    return (
      <main className="center-page">
        <div className="card narrow">
          <h1 className="brand">Thank you, {state.first_name}</h1>
          <p>Your exit interview is complete. Your feedback has been shared confidentially with the HR team at {state.company}.</p>
          <p className="muted">We wish you all the best in your next chapter.</p>
        </div>
      </main>
    );
  }

  if (state.status === "pending") {
    return (
      <main className="center-page">
        <div className="card narrow">
          <h1 className="brand">Hi {state.first_name},</h1>
          <p>
            Thanks for taking a few minutes to talk with Parting Pal, {state.company}'s HR assistant, about your time here. It
            covers {state.topics.length} short topics and usually takes 10–15 minutes.
          </p>
          <p className="muted small">
            Your answers are shared only with HR. You can skip any question, and you can leave and come back later using the
            same link.
          </p>
          {error && <p className="error">{error}</p>}
          <button className="primary" disabled={busy} onClick={() => run(() => interviewApi.start(token))}>
            {busy ? "Starting…" : "Start the interview"}
          </button>
        </div>
      </main>
    );
  }

  const messages: Message[] = state.messages;
  const tooLong = draft.length > state.max_message_chars;

  return (
    <div className="chat-page">
      <header className="chat-header">
        <Brand />
        <TopicProgressBar topics={state.topics} compact />
        <ThemeToggle />
        <button
          className="ghost small"
          disabled={busy}
          onClick={() => {
            if (confirm("End the interview now? What you've shared so far will be sent to HR.")) {
              void run(() => interviewApi.complete(token));
            }
          }}
        >
          End interview
        </button>
      </header>

      <main className="chat-log" aria-live="polite">
        {messages.map((m) => (
          <div key={m.id} className={`bubble bubble-${m.role}`}>
            {m.content}
          </div>
        ))}
        {pending && <div className="bubble bubble-user">{pending}</div>}
        {pending && <div className="bubble bubble-assistant typing">Parting Pal is typing…</div>}
        <div ref={bottom} />
      </main>

      <form className="composer" onSubmit={send}>
        {error && <p className="error">{error}</p>}
        <div className="composer-row">
          <textarea
            ref={input}
            rows={2}
            placeholder="Type your answer… (Enter to send, Shift+Enter for a new line)"
            value={draft}
            disabled={busy}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={onKeyDown}
            autoFocus
          />
          {state.transcription_available && (
            <AudioRecorder disabled={busy} onRecorded={onRecorded} onError={setError} />
          )}
          <button className="primary" disabled={busy || !draft.trim() || tooLong}>
            Send
          </button>
        </div>
        {draft.length > state.max_message_chars * 0.8 && (
          <span className={`small ${tooLong ? "error" : "muted"}`}>
            {draft.length} / {state.max_message_chars}
          </span>
        )}
      </form>
    </div>
  );
}
