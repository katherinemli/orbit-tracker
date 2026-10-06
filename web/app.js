const { createApp } = Vue;

const POLL_MS = 1000;
const TRAIL_LENGTH = 60;

createApp({
  data() {
    return {
      status: null,
      history: [],
      trail: [],
      connected: false,
      clock: '',
      pipeline: ['IDLE', 'ACQUIRING', 'POINTING', 'TRACKING'],
      compass: [
        { t: 'N', x: 0, y: -106 }, { t: 'E', x: 108, y: 3 },
        { t: 'S', x: 0, y: 112 }, { t: 'W', x: -108, y: 3 },
      ],
    };
  },

  computed: {
    stepIndex() { return this.pipeline.indexOf(this.status?.state); },
    active() { return ['ACQUIRING', 'POINTING', 'TRACKING'].includes(this.status?.state); },
    stateClass() { return (this.status?.state ?? 'none').toLowerCase(); },
    errorClass() {
      const e = this.status?.error_deg;
      if (e == null || !this.active) return '';
      return e < 0.4 ? 'good' : e < 2 ? 'fair' : 'bad';
    },
    trailPoints() { return this.trail.map(p => this.xy(p).join(',')).join(' '); },
    threshY() { return 110 - (0.4 / 5) * 110; },
  },

  methods: {
    // Polar projection: zenith at the center, horizon on the outer ring.
    xy({ az, el }) {
      const r = (90 - el) / 90 * 100;
      const a = az * Math.PI / 180;
      return [+(r * Math.sin(a)).toFixed(2), +(-r * Math.cos(a)).toFixed(2)];
    },

    // Map a history field into SVG polyline points, clamped to [min, max].
    series(key, min, max) {
      const pts = this.history.filter(h => h[key] != null);
      if (pts.length < 2) return '';
      const t0 = pts[0].t, span = Math.max(1, pts[pts.length - 1].t - t0);
      return pts.map(h => {
        const v = Math.min(max, Math.max(min, h[key]));
        const x = (h.t - t0) / span * 400;
        const y = 110 - (v - min) / (max - min) * 110;
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      }).join(' ');
    },

    fmt(v, digits = 2) { return v == null ? '—' : Number(v).toFixed(digits); },

    async poll() {
      try {
        const [s, h] = await Promise.all([
          fetch('/api/status').then(r => r.ok ? r.json() : Promise.reject(r)),
          fetch('/api/history').then(r => r.json()),
        ]);
        this.status = s;
        this.history = h;
        this.connected = true;
        if (this.active) {
          this.trail.push(s.mount);
          if (this.trail.length > TRAIL_LENGTH) this.trail.shift();
        }
      } catch {
        this.connected = false;
      }
    },

    async send(action) {
      await fetch('/api/command', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action }),
      });
      if (action === 'stop' || action === 'start') this.trail = [];
      setTimeout(this.poll, 200);
    },

    tick() { this.clock = new Date().toISOString().slice(11, 19) + ' UTC'; },
  },

  mounted() {
    this.poll();
    this.tick();
    setInterval(this.poll, POLL_MS);
    setInterval(this.tick, 1000);
  },
}).mount('#app');
