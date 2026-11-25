export interface LevelMeter {
  getLevel: () => number;
  close: () => void;
}

export function createLevelMeter(stream: MediaStream): LevelMeter | null {
  try {
    const context = new AudioContext();
    void context.resume();

    const source = context.createMediaStreamSource(stream);
    const analyser = context.createAnalyser();
    analyser.fftSize = 512;
    source.connect(analyser);

    const samples = new Uint8Array(analyser.fftSize);
    let smoothed = 0;

    return {
      getLevel() {
        analyser.getByteTimeDomainData(samples);

        let sum = 0;
        for (const sample of samples) {
          const value = (sample - 128) / 128;
          sum += value * value;
        }

        const rms = Math.sqrt(sum / samples.length);
        // Fast attack, slow release.
        smoothed = Math.max(rms * 4, smoothed * 0.8);
        return Math.min(1, smoothed);
      },
      close() {
        source.disconnect();
        void context.close();
      },
    };
  } catch {
    return null;
  }
}