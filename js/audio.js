/** Lightweight engine tone. Starts on first user gesture. */

export class EngineAudio {
  constructor() {
    this.ctx = null;
    this.osc = null;
    this.gain = null;
    this.filter = null;
    this.enabled = false;
  }

  unlock() {
    if (this.ctx) return;
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return;
    this.ctx = new Ctx();
    this.osc = this.ctx.createOscillator();
    this.osc.type = "sawtooth";
    this.filter = this.ctx.createBiquadFilter();
    this.filter.type = "lowpass";
    this.filter.frequency.value = 420;
    this.gain = this.ctx.createGain();
    this.gain.gain.value = 0;
    this.osc.connect(this.filter);
    this.filter.connect(this.gain);
    this.gain.connect(this.ctx.destination);
    this.osc.start();
    this.enabled = true;
  }

  update(speed, throttle, muted) {
    if (!this.ctx || !this.enabled) return;
    if (this.ctx.state === "suspended") this.ctx.resume();
    const rpm = 70 + Math.abs(speed) * 6.2 + throttle * 18;
    this.osc.frequency.setTargetAtTime(rpm, this.ctx.currentTime, 0.05);
    this.filter.frequency.setTargetAtTime(280 + Math.abs(speed) * 14, this.ctx.currentTime, 0.08);
    const vol = muted ? 0 : Math.min(0.045, 0.008 + Math.abs(speed) * 0.0012 + throttle * 0.012);
    this.gain.gain.setTargetAtTime(vol, this.ctx.currentTime, 0.08);
  }

  stop() {
    if (!this.gain || !this.ctx) return;
    this.gain.gain.setTargetAtTime(0, this.ctx.currentTime, 0.05);
  }
}
