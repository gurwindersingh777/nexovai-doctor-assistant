let context: AudioContext | null = null;

function getContext() {
  if (!context || context.state === "closed") context = new AudioContext();
  if (context.state === "suspended") void context.resume();
  return context;
}

function beep(c: AudioContext, frequency: number, start: number, duration: number, volume = 0.05) {
  const oscillator = c.createOscillator();
  const gain = c.createGain();

  oscillator.type = "sine";
  oscillator.frequency.value = frequency;

  gain.gain.setValueAtTime(0, start);
  gain.gain.linearRampToValueAtTime(volume, start + 0.02);
  gain.gain.linearRampToValueAtTime(0, start + duration);

  oscillator.connect(gain).connect(c.destination);
  oscillator.start(start);
  oscillator.stop(start + duration + 0.02);
}

/** Starts a looping ring tone. Returns a function that stops it. */
export function startRing() {
  const c = getContext();

  const burst = () => {
    const now = c.currentTime;
    for (const offset of [0, 0.5]) {
      beep(c, 440, now + offset, 0.4);
      beep(c, 480, now + offset, 0.4);
    }
  };

  burst();
  const id = window.setInterval(burst, 2400);
  return () => window.clearInterval(id);
}

export function playEndTone() {
  const c = getContext();
  const now = c.currentTime;
  beep(c, 480, now, 0.16, 0.06);
  beep(c, 380, now + 0.18, 0.16, 0.06);
  beep(c, 300, now + 0.36, 0.28, 0.06);
}