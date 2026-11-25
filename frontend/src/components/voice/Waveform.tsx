import { useEffect, useRef } from "react";
import { cn } from "@/lib/utils";

interface WaveformProps {
  getLevel: () => number;
  active: boolean;
  bars?: number;
  className?: string;
}

export function Waveform({
  getLevel,
  active,
  bars = 34,
  className,
}: WaveformProps) {
  const barRefs = useRef<(HTMLSpanElement | null)[]>([]);

  useEffect(() => {
    const history = new Array<number>(bars).fill(0);
    let frame = 0;
    let raf = 0;

    const tick = () => {
      frame += 1;

      // Push a new sample every 3rd frame so the wave scrolls smoothly.
      if (frame % 3 === 0) {
        history.push(active ? getLevel() : 0);
        history.shift();
      }

      for (let i = 0; i < bars; i += 1) {
        const element = barRefs.current[i];
        if (element) {
          element.style.transform = `scaleY(${0.1 + Math.min(1, history[i]) * 0.9})`;
        }
      }

      raf = requestAnimationFrame(tick);
    };

    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [getLevel, active, bars]);

  return (
    <div
      className={cn("flex h-14 items-center justify-center gap-0.75", className)}
      aria-hidden
    >
      {Array.from({ length: bars }, (_, index) => (
        <span
          key={index}
          ref={(element) => {
            barRefs.current[index] = element;
          }}
          className="h-full w-0.75 origin-center rounded-full bg-[#d6f55c] will-change-transform"
          style={{ transform: "scaleY(0.1)" }}
        />
      ))}
    </div>
  );
}