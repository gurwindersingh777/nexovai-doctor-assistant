import { useEffect, useRef, useState } from "react";
import {
  CalendarCheck,
  CalendarX,
  Mic,
  MicOff,
  Phone,
  PhoneOff,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Waveform } from "@/components/voice/Waveform";
import { cn } from "@/lib/utils";
import { fmtDayShort, fmtDuration, fmtTime } from "@/lib/format";
import type { CallState, TranscriptMessage } from "@/hooks/useVoiceCall";
import type { AppointmentEvent } from "@/types";

interface VoicePhoneProps {
  state: CallState;
  muted: boolean;
  speaking: boolean;
  seconds: number;
  transcript: TranscriptMessage[];
  error: string | null;
  event: AppointmentEvent | null;
  getLevel: () => number;
  onStart: () => void;
  onEnd: () => void;
  onToggleMute: () => void;
}

function Monogram({
  className,
  pulsing = false,
  dim = false,
}: {
  className?: string;
  pulsing?: boolean;
  dim?: boolean;
}) {
  return (
    <div className="relative grid place-items-center">
      {pulsing && (
        <>
          <span className="anim-ring absolute inset-0 rounded-full border border-[#d6f55c]/50" />
          <span className="anim-ring absolute inset-0 rounded-full border border-[#d6f55c]/40 [animation-delay:0.6s]" />
          <span className="anim-ring absolute inset-0 rounded-full border border-[#d6f55c]/30 [animation-delay:1.2s]" />
        </>
      )}
      <div
        className={cn(
          "relative grid place-items-center rounded-full bg-[#d6f55c] font-display text-[#10231c] transition-opacity",
          dim && "opacity-40",
          className,
        )}
      >
        N
      </div>
    </div>
  );
}

const roundButton =
  "size-14 rounded-full border border-white/15 bg-white/10 text-white hover:bg-white/20";

export function VoicePhone({
  state,
  muted,
  speaking,
  seconds,
  transcript,
  error,
  event,
  getLevel,
  onStart,
  onEnd,
  onToggleMute,
}: VoicePhoneProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [seenAt, setSeenAt] = useState(0);
  const [card, setCard] = useState<AppointmentEvent | null>(null);

  const connected = state === "connected";
  const calling = state === "connecting";

  // Show a confirmation card when the agent books or cancels mid-call.
  if (event && event.at > seenAt) {
    setSeenAt(event.at);
    setCard(state === "connected" ? event : null);
  }

  useEffect(() => {
    if (!card) return;
    const id = window.setTimeout(() => setCard(null), 9000);
    return () => window.clearTimeout(id);
  }, [card]);

  useEffect(() => {
    const element = scrollRef.current;
    if (element) element.scrollTo({ top: element.scrollHeight, behavior: "smooth" });
  }, [transcript]);

  const status = speaking
    ? "NexovAI is speaking"
    : muted
      ? "Muted"
      : "Listening";

  const visibleCard = connected ? card : null;

  return (
    <div className="mx-auto w-full max-w-95 rounded-[2.75rem] bg-[#0a1210] p-2 shadow-[0_30px_80px_-30px_rgba(16,35,28,0.55)] ring-1 ring-black/20">
      <div className="relative flex h-150 flex-col overflow-hidden rounded-[2.25rem] bg-[radial-gradient(120%_80%_at_50%_0%,#1f3d33_0%,#0b1511_62%)] text-[#eef2e6]">
        <div
          className="mx-auto mt-2.5 h-5 w-24 shrink-0 rounded-full bg-black"
          aria-hidden
        />

        {connected ? (
          <>
            <div className="flex items-center gap-3 px-6 pt-5">
              <Monogram className="size-10 text-xl" />
              <div className="min-w-0 flex-1">
                <p className="font-display text-2xl leading-none">NexovAI</p>
                <p className="mt-1 text-xs text-white/55">{status}</p>
              </div>
              <p className="text-sm tabular-nums text-white/70">
                {fmtDuration(seconds)}
              </p>
            </div>

            <Waveform getLevel={getLevel} active className="mt-3 px-6" />

            <div
              ref={scrollRef}
              role="log"
              aria-live="polite"
              className="mt-2 flex-1 space-y-2.5 overflow-y-auto px-5 pb-3 mask-[linear-gradient(to_bottom,transparent,black_20px,black_calc(100%-8px),transparent)] scrollbar-none"
            >
              {transcript.length === 0 && (
                <p className="pt-6 text-center text-xs text-white/35">
                  Say hello
                </p>
              )}

              {transcript.map((message) => (
                <div
                  key={message.id}
                  className={cn(
                    "flex",
                    message.speaker === "user" ? "justify-end" : "justify-start",
                  )}
                >
                  <p
                    className={cn(
                      "max-w-[84%] rounded-2xl px-3.5 py-2 text-[13px] leading-snug",
                      message.speaker === "user"
                        ? "rounded-br-md bg-[#d6f55c] text-[#10231c]"
                        : "rounded-bl-md bg-white/10 text-white/90",
                    )}
                  >
                    {message.text}
                  </p>
                </div>
              ))}
            </div>

            {visibleCard && (
              <div className="anim-pop mx-4 mb-3 rounded-2xl bg-[#f4f1ea] p-4 text-[#10231c] shadow-lg">
                <div className="flex items-center gap-2 text-[11px] font-medium uppercase tracking-[0.16em]">
                  <span
                    className={cn(
                      "grid size-5 place-items-center rounded-full",
                      visibleCard.kind === "booked"
                        ? "bg-[#d6f55c]"
                        : "bg-red-200",
                    )}
                  >
                    {visibleCard.kind === "booked" ? (
                      <CalendarCheck className="size-3" />
                    ) : (
                      <CalendarX className="size-3" />
                    )}
                  </span>
                  {visibleCard.kind === "booked" ? "Booked" : "Cancelled"}
                </div>
                <p className="mt-2 font-display text-2xl leading-tight">
                  {visibleCard.appointment.doctor_name}
                </p>
                <p className="text-sm tabular-nums text-[#10231c]/65">
                  {fmtDayShort(visibleCard.appointment.starts_at)} ·{" "}
                  {fmtTime(visibleCard.appointment.starts_at)}
                </p>
              </div>
            )}
          </>
        ) : (
          <div className="flex flex-1 flex-col items-center justify-center gap-6 px-8 text-center">
            <Monogram
              className="size-24 text-5xl"
              pulsing={calling}
              dim={state === "ended"}
            />
            <div>
              <h2 className="font-display text-4xl">NexovAI</h2>
              <p className="mt-1.5 text-sm text-white/55">
                {state === "ended"
                  ? `Call ended · ${fmtDuration(seconds)}`
                  : calling
                    ? "Calling…"
                    : "Doctor appointments"}
              </p>
            </div>

            {state === "idle" && !error && (
              <p className="max-w-60 text-xs text-white/40">
                Try saying “Book a cardiologist tomorrow”
              </p>
            )}

            {error && (
              <p role="alert" className="max-w-[16rem] text-xs text-red-300">
                {error}
              </p>
            )}
          </div>
        )}

        <div className="flex shrink-0 items-center justify-center gap-5 pb-8 pt-3">
          {connected && (
            <Button
              type="button"
              size="icon"
              variant="ghost"
              onClick={onToggleMute}
              aria-label={muted ? "Unmute microphone" : "Mute microphone"}
              className={cn(
                roundButton,
                muted && "bg-white text-[#10231c] hover:bg-white/90",
              )}
            >
              {muted ? <MicOff className="size-6" /> : <Mic className="size-6" />}
            </Button>
          )}

          {(connected || calling) && (
            <Button
              type="button"
              size="icon"
              onClick={onEnd}
              aria-label="End call"
              className="size-14 rounded-full bg-red-500 text-white hover:bg-red-600"
            >
              <PhoneOff className="size-6" />
            </Button>
          )}

          {!connected && !calling && (
            <Button
              type="button"
              onClick={onStart}
              className="h-14 rounded-full bg-[#d6f55c] px-9 text-base font-medium text-[#10231c] hover:bg-[#e3fb7e]"
            >
              <Phone className="mr-2 size-5" />
              {state === "ended" ? "Call again" : "Try call"}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}