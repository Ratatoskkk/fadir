// Tiny synthesized interface sounds: no audio files, nothing to download.
//
// A key press is a ~12 ms burst of high-passed noise with a little random pitch and level,
// so fast typing sounds like a keyboard instead of a metronome. Everything runs through one
// compressor so overlapping sounds never clip. The context starts only after the user has
// interacted with the page, as browsers require.

let ctx = null;
let out = null;
let noise = null;

function audio() {
  if (typeof window === "undefined") return null;
  if (!ctx) {
    if (navigator.userActivation && !navigator.userActivation.hasBeenActive) return null;
    const Ctor = window.AudioContext ?? window.webkitAudioContext;
    if (!Ctor) return null;
    ctx = new Ctor();
    out = ctx.createGain();
    out.gain.value = 0.6;
    const limiter = ctx.createDynamicsCompressor();
    limiter.threshold.value = -12;
    limiter.ratio.value = 8;
    out.connect(limiter).connect(ctx.destination);
  }
  if (ctx.state === "suspended") ctx.resume();
  return ctx;
}

const jitter = (amount) => 1 + (Math.random() * 2 - 1) * amount;

function noiseBuffer(c) {
  if (!noise || noise.sampleRate !== c.sampleRate) {
    noise = c.createBuffer(1, Math.floor(c.sampleRate * 0.4), c.sampleRate);
    const data = noise.getChannelData(0);
    for (let i = 0; i < data.length; i += 1) data[i] = Math.random() * 2 - 1;
  }
  return noise;
}

function burst(c, { at = 0, level, length, type = "highpass", freq, q = 0.7 }) {
  const start = c.currentTime + at;
  const src = c.createBufferSource();
  src.buffer = noiseBuffer(c);
  const filter = c.createBiquadFilter();
  filter.type = type;
  filter.frequency.value = freq;
  filter.Q.value = q;
  const gain = c.createGain();
  gain.gain.setValueAtTime(level, start);
  gain.gain.exponentialRampToValueAtTime(0.0001, start + length);
  src.connect(filter).connect(gain).connect(out);
  src.start(start, Math.random() * 0.3);
  src.stop(start + length + 0.02);
}

function tone(c, freq, { at = 0, level, length, type = "sine", attack = 0.003, slideTo = 0 }) {
  const start = c.currentTime + at;
  const osc = c.createOscillator();
  osc.type = type;
  osc.frequency.setValueAtTime(freq, start);
  if (slideTo) osc.frequency.exponentialRampToValueAtTime(slideTo, start + length);
  const gain = c.createGain();
  gain.gain.setValueAtTime(0.0001, start);
  gain.gain.exponentialRampToValueAtTime(level, start + attack);
  gain.gain.exponentialRampToValueAtTime(0.0001, start + attack + length);
  osc.connect(gain).connect(out);
  osc.start(start);
  osc.stop(start + attack + length + 0.05);
}

export const sound = {
  key() {
    const c = audio();
    if (c) burst(c, { level: 0.032 * jitter(0.3), length: 0.012, freq: 4500 * jitter(0.15) });
  },
  erase() {
    const c = audio();
    if (c) burst(c, { level: 0.024 * jitter(0.2), length: 0.016, type: "bandpass", freq: 2200 * jitter(0.1), q: 1 });
  },
  wrong() {
    const c = audio();
    if (!c) return;
    [0, 0.1].forEach((at) => {
      tone(c, 230, { at, level: 0.13, length: 0.08, type: "triangle", slideTo: 190 });
      burst(c, { at, level: 0.08, length: 0.04, type: "bandpass", freq: 700, q: 1 });
    });
  },
  open() {
    const c = audio();
    if (!c) return;
    burst(c, { level: 0.05, length: 0.03, type: "bandpass", freq: 2600, q: 1.2 });
    [783.99, 1046.5, 1318.5].forEach((f, i) => tone(c, f, { at: 0.04 + i * 0.06, level: 0.06, length: 1.1, type: "triangle", attack: 0.004 }));
  },
};
