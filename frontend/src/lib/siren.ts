// Siren generated with the Web Audio API (no audio file to download).
// Browsers only allow sound after a user gesture: call unlockAudio() from a click/tap first.

let ctx: AudioContext | null = null;

function audioContext(): AudioContext | null {
  if (typeof window === "undefined") return null;
  const Ctor = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!Ctor) return null;
  if (!ctx) ctx = new Ctor();
  return ctx;
}

/** Call from a click/tap handler. Returns true when sound can play. */
export async function unlockAudio(): Promise<boolean> {
  const c = audioContext();
  if (!c) return false;
  if (c.state === "suspended") {
    try {
      await c.resume();
    } catch {
      return false;
    }
  }
  return c.state === "running";
}

export function audioReady(): boolean {
  return !!ctx && ctx.state === "running";
}

/** Rising-falling wail, `cycles` × 1.2 s. Returns false if audio is still locked. */
export function playSiren(cycles = 3, volume = 0.18): boolean {
  const c = audioContext();
  if (!c || c.state !== "running") return false;
  const t0 = c.currentTime;
  const dur = cycles * 1.2;
  const osc = c.createOscillator();
  const gain = c.createGain();
  osc.type = "sawtooth";
  for (let i = 0; i < cycles; i++) {
    const t = t0 + i * 1.2;
    osc.frequency.setValueAtTime(620, t);
    osc.frequency.linearRampToValueAtTime(1350, t + 0.6);
    osc.frequency.linearRampToValueAtTime(620, t + 1.2);
  }
  gain.gain.setValueAtTime(0.0001, t0);
  gain.gain.exponentialRampToValueAtTime(volume, t0 + 0.08);
  gain.gain.setValueAtTime(volume, t0 + dur - 0.15);
  gain.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
  osc.connect(gain).connect(c.destination);
  osc.start(t0);
  osc.stop(t0 + dur + 0.05);
  return true;
}

/** SOS-like vibration on phones that support it. */
export function vibrateAlert() {
  try {
    navigator.vibrate?.([500, 200, 500, 200, 1000]);
  } catch {}
}
