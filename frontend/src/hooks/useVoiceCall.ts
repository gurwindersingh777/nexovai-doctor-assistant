import { useCallback, useEffect, useRef, useState } from "react";
import { PipecatClient } from "@pipecat-ai/client-js";
import { SmallWebRTCTransport } from "@pipecat-ai/small-webrtc-transport";
import { createLevelMeter, type LevelMeter } from "@/lib/audio";
import { playEndTone, startRing } from "@/lib/sounds";

export type CallState = "idle" | "connecting" | "connected" | "ended";

export interface TranscriptMessage {
  id: string;
  speaker: "user" | "assistant";
  text: string;
  timestamp: number;
  final: boolean;
}

const VOICE_URL =
  import.meta.env.VITE_VOICE_URL || "http://localhost:7860";

export function useVoiceCall() {
  const clientRef = useRef<PipecatClient | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const botMeterRef = useRef<LevelMeter | null>(null);
  const userMeterRef = useRef<LevelMeter | null>(null);
  const stopRingRef = useRef<(() => void) | null>(null);
  const timerRef = useRef<number | null>(null);
  const resetRef = useRef<number | null>(null);
  const stateRef = useRef<CallState>("idle");
  const botSegmentsRef = useRef<Map<string, string>>(new Map());

  const [callState, setCallStateValue] = useState<CallState>("idle");
  const [muted, setMuted] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [transcript, setTranscript] = useState<TranscriptMessage[]>([]);
  const [error, setError] = useState<string | null>(null);

  const setCallState = useCallback((next: CallState) => {
    stateRef.current = next;
    setCallStateValue(next);
  }, []);

  // transcript 

  const addUserTranscript = useCallback((text: string) => {
    const cleanText = text.replace(/\*+/g, "").replace(/^\s*[-•]\s+/gm, "").trim();
    if (!cleanText) return;

    setTranscript((previous) => [
      ...previous,
      {
        id: `user-${Date.now()}-${Math.random()}`,
        speaker: "user",
        text: cleanText,
        timestamp: Date.now(),
        final: true,
      },
    ]);
  }, []);

  const updateBotTranscript = useCallback(
    (segmentId: number | undefined, text: string) => {
      const cleanText = text.trim();
      if (!cleanText) return;

      const key =
        segmentId !== undefined ? `segment-${segmentId}` : `text-${cleanText}`;

      const existingId = botSegmentsRef.current.get(key);

      if (existingId) {
        setTranscript((previous) =>
          previous.map((message) =>
            message.id === existingId
              ? { ...message, text: cleanText }
              : message,
          ),
        );
        return;
      }

      const id = `assistant-${Date.now()}-${Math.random()}`;
      botSegmentsRef.current.set(key, id);

      setTranscript((previous) => [
        ...previous,
        {
          id,
          speaker: "assistant",
          text: cleanText,
          timestamp: Date.now(),
          final: true,
        },
      ]);
    },
    [],
  );

  // audio 

  const attachBotAudio = useCallback((track: MediaStreamTrack) => {
    const current = audioRef.current?.srcObject as MediaStream | null | undefined;
    if (current?.getAudioTracks()[0]?.id === track.id) return;

    const stream = new MediaStream([track]);

    if (!audioRef.current) {
      const element = document.createElement("audio");
      element.autoplay = true;
      element.setAttribute("playsinline", "");
      document.body.appendChild(element);
      audioRef.current = element;
    }

    audioRef.current.srcObject = stream;
    void audioRef.current.play().catch(() => {
      setError("Your browser blocked audio. Click the page and call again.");
    });

    botMeterRef.current?.close();
    botMeterRef.current = createLevelMeter(stream);
  }, []);

  const attachMicMeter = useCallback((track: MediaStreamTrack) => {
    userMeterRef.current?.close();
    userMeterRef.current = createLevelMeter(new MediaStream([track]));
  }, []);

  const teardownMedia = useCallback(() => {
    stopRingRef.current?.();
    stopRingRef.current = null;

    if (timerRef.current !== null) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }

    botMeterRef.current?.close();
    botMeterRef.current = null;
    userMeterRef.current?.close();
    userMeterRef.current = null;

    if (audioRef.current) audioRef.current.srcObject = null;
  }, []);

  // call lifecycle 

  const finishCall = useCallback(() => {
    const current = stateRef.current;
    if (current === "idle" || current === "ended") return;

    teardownMedia();
    clientRef.current = null;
    setMuted(false);
    setSpeaking(false);

    if (current === "connected") {
      playEndTone();
      setCallState("ended");
      resetRef.current = window.setTimeout(() => {
        setCallState("idle");
        setSeconds(0);
      }, 5000);
    } else {
      setCallState("idle");
    }
  }, [setCallState, teardownMedia]);

  const startCall = useCallback(async () => {
    if (clientRef.current) return;

    if (resetRef.current !== null) {
      window.clearTimeout(resetRef.current);
      resetRef.current = null;
    }

    setError(null);
    setTranscript([]);
    setSeconds(0);
    botSegmentsRef.current.clear();
    setCallState("connecting");
    stopRingRef.current = startRing();

    try {
      const client = new PipecatClient({
        transport: new SmallWebRTCTransport(),
        enableMic: true,
        enableCam: false,
        callbacks: {
          onConnected: () => {
            stopRingRef.current?.();
            stopRingRef.current = null;

            const startedAt = Date.now();
            timerRef.current = window.setInterval(() => {
              setSeconds(Math.floor((Date.now() - startedAt) / 1000));
            }, 500);

            setCallState("connected");
          },

          onDisconnected: () => finishCall(),

          onTrackStarted: (track, participant) => {
            if (track.kind !== "audio") return;

            if (participant?.local) attachMicMeter(track);
            else attachBotAudio(track);
          },

          onUserInput: (data) => {
            if (data.final) addUserTranscript(data.text);
          },

          onBotOutput: (data) => {
            if (data.will_be_spoken === false) return;
            updateBotTranscript(data.segment_id, data.text);
          },

          onBotStartedSpeaking: () => setSpeaking(true),
          onBotStoppedSpeaking: () => setSpeaking(false),

          onError: (message) => {
            const errorMessage =
              typeof message === "string" ? message : JSON.stringify(message);
            setError(errorMessage || "Voice connection error");
          },
        },
      });

      clientRef.current = client;

      // Ask for microphone access before establishing WebRTC.
      await client.initDevices();

      await client.startBotAndConnect({
        endpoint: `${VOICE_URL}/start`,
      });
    } catch (err) {
      const failed = clientRef.current;

      setError(
        err instanceof Error ? err.message : "Unable to start voice call",
      );
      finishCall();
      void failed?.disconnect().catch(() => undefined);
    }
  }, [
    addUserTranscript,
    attachBotAudio,
    attachMicMeter,
    finishCall,
    setCallState,
    updateBotTranscript,
  ]);

  const endCall = useCallback(async () => {
    const client = clientRef.current;
    if (!client) return;

    try {
      await client.disconnect();
    } catch (err) {
      if (stateRef.current === "connected") {
        setError(err instanceof Error ? err.message : "Unable to end call");
      }
    } finally {
      finishCall();
    }
  }, [finishCall]);

  const toggleMute = useCallback(() => {
    const client = clientRef.current;
    if (!client) return;

    const nextMuted = !muted;
    client.enableMic(!nextMuted);
    setMuted(nextMuted);
  }, [muted]);

  const getLevel = useCallback(
    () =>
      Math.max(
        botMeterRef.current?.getLevel() ?? 0,
        userMeterRef.current?.getLevel() ?? 0,
      ),
    [],
  );

  useEffect(
    () => () => {
      teardownMedia();
      if (resetRef.current !== null) window.clearTimeout(resetRef.current);
      void clientRef.current?.disconnect().catch(() => undefined);
    },
    [teardownMedia],
  );

  return {
    callState,
    muted,
    speaking,
    seconds,
    transcript,
    error,
    getLevel,
    startCall,
    endCall,
    toggleMute,
  };
}