import { useEffect, useRef, useState } from "react";
import { toWav } from "../lib/wav";

const MAX_SECONDS = 120;

interface Props {
  disabled?: boolean;
  onRecorded: (wav: Blob) => Promise<void>;
  onError: (message: string) => void;
}

export default function AudioRecorder({ disabled, onRecorded, onError }: Props) {
  const [state, setState] = useState<"idle" | "recording" | "processing">("idle");
  const [seconds, setSeconds] = useState(0);
  const recorder = useRef<MediaRecorder | null>(null);
  const timer = useRef<number | null>(null);

  useEffect(
    () => () => {
      if (timer.current) clearInterval(timer.current);
      recorder.current?.stream.getTracks().forEach((t) => t.stop());
    },
    [],
  );

  async function start() {
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      onError("Microphone access was blocked. You can type your answer instead.");
      return;
    }
    const chunks: Blob[] = [];
    const media = new MediaRecorder(stream);
    media.ondataavailable = (e) => e.data.size && chunks.push(e.data);
    media.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop());
      if (timer.current) clearInterval(timer.current);
      setState("processing");
      try {
        await onRecorded(await toWav(new Blob(chunks, { type: media.mimeType })));
      } catch (err) {
        onError(err instanceof Error ? err.message : "Couldn't process the recording.");
      } finally {
        setState("idle");
      }
    };
    recorder.current = media;
    media.start();
    const startedAt = Date.now();
    setSeconds(0);
    setState("recording");
    timer.current = window.setInterval(() => {
      const elapsed = Math.floor((Date.now() - startedAt) / 1000);
      setSeconds(elapsed);
      if (elapsed >= MAX_SECONDS && media.state === "recording") media.stop();
    }, 1000);
  }

  if (state === "recording") {
    return (
      <button type="button" className="mic recording" onClick={() => recorder.current?.stop()} title="Stop recording">
        ■ {seconds}s
      </button>
    );
  }
  return (
    <button
      type="button"
      className="mic"
      disabled={disabled || state === "processing"}
      onClick={start}
      title="Record your answer"
      aria-label="Record your answer"
    >
      {state === "processing" ? "…" : "🎤"}
    </button>
  );
}
