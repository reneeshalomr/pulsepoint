"use client";
import { useEffect, useRef, useState } from "react";

interface Recognition {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult:
    | ((event: {
        results: {
          [index: number]: { [index: number]: { transcript: string } };
          length: number;
        };
      }) => void)
    | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}
type VoiceWindow = Window & {
  SpeechRecognition?: new () => Recognition;
  webkitSpeechRecognition?: new () => Recognition;
};

export function useVoice(onText: (text: string) => void) {
  const [listening, setListening] = useState(false);
  const [notice, setNotice] = useState("");
  const recognition = useRef<Recognition | null>(null);
  const callback = useRef(onText);
  useEffect(() => {
    callback.current = onText;
  }, [onText]);
  useEffect(
    () => () => {
      recognition.current?.abort();
    },
    [],
  );
  function toggle() {
    if (listening) {
      recognition.current?.stop();
      return;
    }
    const browser = window as VoiceWindow;
    const Constructor =
      browser.SpeechRecognition || browser.webkitSpeechRecognition;
    if (!Constructor) {
      setNotice(
        "Voice input is unavailable in this browser. You can type your question below.",
      );
      return;
    }
    try {
      const instance = new Constructor();
      instance.lang = "en-US";
      instance.continuous = false;
      instance.interimResults = false;
      instance.onresult = (event) => {
        callback.current(
          Array.from(
            { length: event.results.length },
            (_, i) => event.results[i][0].transcript,
          ).join(" "),
        );
      };
      instance.onerror = () => {
        setNotice(
          "We couldn’t capture your voice. Check microphone access or use typed input.",
        );
        setListening(false);
      };
      instance.onend = () => setListening(false);
      recognition.current = instance;
      instance.start();
      setNotice("");
      setListening(true);
    } catch {
      setNotice(
        "Voice input could not start. Typed input is always available.",
      );
      setListening(false);
    }
  }
  return { listening, notice, toggle };
}
