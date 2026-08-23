#!/usr/bin/env node
/**
 * bench-frames.mjs - headless frame-time harness for browser games.
 *
 * WHAT IT MEASURES
 *   Per-frame deltas collected inside the page with requestAnimationFrame, not
 *   wall-clock around the whole run. Wall-clock timing hides where the time
 *   went; a frame-delta series shows the hitches.
 *
 * THE ONE NUMBER
 *   By default stdout carries a single value: the median across runs of p1-low
 *   FPS (1000 / the 99th-percentile frame time). Higher is better. p1-low is
 *   the metric that tracks stutter. Mean FPS hides exactly the hitches players
 *   feel: a run that holds 60 FPS and drops four 200 ms frames still averages
 *   near 60.
 *
 *   Use this as the MEASURE command of a hill-climb SPEC:
 *     METRIC   p1-low FPS (higher is better)
 *     MEASURE  node scripts/bench-frames.mjs --url http://127.0.0.1:8080/
 *     TARGET   e.g. >= 55
 *
 * HOW TO PIN THE FIXTURE
 *   A hill climb against a moving workload measures nothing. Pin all of these
 *   and change none of them between iterations:
 *     - The URL and the build it serves. Serve a built artifact from loopback;
 *       do not bench a dev server with hot reload attached.
 *     - --seed. The page reads window.__BENCH_SEED__ before any of its own
 *       script runs. Seed every RNG the game uses from it. Without that, each
 *       run is a different workload wearing the same URL.
 *     - --frames, --warmup, --runs. Changing the sample count changes the
 *       distribution, and p1-low most of all.
 *     - The machine, and whether it is otherwise idle.
 *
 * WHAT THIS HARNESS CANNOT MAKE DETERMINISTIC
 *   It fixes the viewport, the browser flags, the seed exposed to the page, and
 *   the sample counts. It cannot fix: GPU driver and compositor scheduling,
 *   JavaScript garbage-collection timing, JIT warm-up, thermal throttling,
 *   other load on the machine, or any randomness the page does not actually
 *   seed from window.__BENCH_SEED__. Frame timing is wall-clock timing, so run
 *   the baseline at least 10 times and trust the measured spread over any
 *   single run.
 *
 * KNOWN NOISE SOURCES
 *   Thermal throttling on a laptop after a few minutes of benching; background
 *   load (browsers, build watchers, other agents); GC pauses, which land
 *   directly in the low percentiles; a shared or virtualized GPU; page assets
 *   fetched over a network instead of from loopback.
 *
 * EXIT CODES
 *   0 ok. 1 bad usage or setup (no Playwright, bad args). 2 page failed: a page
 *   error, a failed navigation, or no frames drawn. 3 run-to-run spread
 *   exceeded --max-spread. Without --max-spread a wide spread only warns on
 *   stderr; it never fails the run.
 */

import { existsSync, globSync, mkdtempSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import process from 'node:process';

const USAGE = `bench-frames.mjs - measure game frame rate headlessly.

Usage:
  node scripts/bench-frames.mjs --url <url> [options]

Required:
  --url <url>          Page to bench. Use a loopback URL (http://127.0.0.1:...).

Options:
  --frames <n>         Frames measured per run (default 600, about 10s at 60fps).
  --warmup <n>         Frames discarded at the start of each run (default 120).
  --runs <n>           Runs; the printed number is their median (default 5).
  --seed <n>           Exposed to the page as window.__BENCH_SEED__ (default 1).
  --json               Print the full distribution as JSON instead of one number.
  --max-spread <n>     Fail (exit 3) if max-min of p1-low FPS across runs
                       exceeds this. Default: warn only.
  --timeout <ms>       Per-run budget for collecting frames (default 60000).
  --width <px>         Viewport width (default 1280).
  --height <px>        Viewport height (default 720).
  --headed             Run with a visible browser window (debugging only).
  --keep-vsync         Do not pass the vsync/frame-rate-limit overrides.
  --chromium <path>    Chrome/Chromium binary to drive. Defaults to the browser
                       Playwright installed; falls back to a local Chrome build.
                       Also read from BENCH_CHROMIUM.
  -h, --help           Show this help.

Output:
  Default: one number on stdout - the median across runs of p1-low FPS.
           Higher is better.
  --json:  mean, p50, p1-low, p0.1-low and the across-run spread, so a
           hill-climb BASELINE phase can compute variance.

Make the page deterministic: seed its RNG from window.__BENCH_SEED__ and serve a
fixed build. See the header comment of this file for what the harness can and
cannot hold still.

Examples:
  node scripts/bench-frames.mjs --url http://127.0.0.1:8080/
  node scripts/bench-frames.mjs --url http://127.0.0.1:8080/ --runs 10 --json
`;

function fail(message, code = 1) {
  process.stderr.write(`bench-frames: ${message}\n`);
  process.exit(code);
}

function parseArgs(argv) {
  const opts = {
    url: null,
    frames: 600,
    warmup: 120,
    runs: 5,
    seed: 1,
    json: false,
    maxSpread: null,
    timeout: 60000,
    width: 1280,
    height: 720,
    headed: false,
    keepVsync: false,
    chromium: process.env.BENCH_CHROMIUM ?? null,
  };
  const numeric = {
    '--frames': 'frames',
    '--warmup': 'warmup',
    '--runs': 'runs',
    '--seed': 'seed',
    '--max-spread': 'maxSpread',
    '--timeout': 'timeout',
    '--width': 'width',
    '--height': 'height',
  };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '-h' || arg === '--help') {
      process.stdout.write(USAGE);
      process.exit(0);
    } else if (arg === '--json') {
      opts.json = true;
    } else if (arg === '--headed') {
      opts.headed = true;
    } else if (arg === '--keep-vsync') {
      opts.keepVsync = true;
    } else if (arg === '--url') {
      opts.url = argv[++i];
    } else if (arg === '--chromium') {
      opts.chromium = argv[++i];
    } else if (arg in numeric) {
      const raw = argv[++i];
      const value = Number(raw);
      if (!Number.isFinite(value)) fail(`${arg} needs a number, got ${raw ?? '(nothing)'}`);
      opts[numeric[arg]] = value;
    } else {
      fail(`unknown argument ${arg}. Run with --help.`);
    }
  }
  if (!opts.url) fail('--url is required. Run with --help.');
  if (opts.frames < 1) fail('--frames must be at least 1');
  if (opts.runs < 1) fail('--runs must be at least 1');
  if (opts.warmup < 0) fail('--warmup cannot be negative');
  return opts;
}

/**
 * Resolve Playwright without adding a dependency to this repo.
 *
 * This repo has no package.json, so there is no project-local Playwright. Look
 * in PLAYWRIGHT_MODULE_PATH, then the usual local spots, then the npx cache
 * where the Playwright MCP server keeps its copy.
 */
async function loadPlaywright() {
  const require_ = createRequire(import.meta.url);
  // A CommonJS Playwright build lands under .default when imported from ESM.
  const unwrap = (mod) => (mod?.chromium ? mod : mod?.default);
  const candidates = [];
  if (process.env.PLAYWRIGHT_MODULE_PATH) candidates.push(process.env.PLAYWRIGHT_MODULE_PATH);
  candidates.push('playwright', 'playwright-core');
  for (const spec of candidates) {
    try {
      const mod = unwrap(await import(require_.resolve(spec, { paths: [process.cwd(), import.meta.dirname] })));
      if (mod?.chromium) return mod;
    } catch {
      /* try the next candidate */
    }
  }
  const home = process.env.HOME ?? '';
  if (home) {
    let hits = [];
    try {
      hits = globSync(`${home}/.npm/_npx/*/node_modules/playwright{,-core}/index.js`);
    } catch {
      /* node without fs.globSync: skip the npx-cache lookup */
    }
    for (const hit of hits) {
      try {
        const mod = unwrap(await import(hit));
        if (mod?.chromium) return mod;
      } catch {
        /* try the next candidate */
      }
    }
  }
  fail(
    'Playwright not found. This repo has no package.json, so nothing pins it.\n' +
      '  Point at an existing copy:  PLAYWRIGHT_MODULE_PATH=/path/to/playwright node scripts/bench-frames.mjs ...\n' +
      '  Or install it where you run the bench:  npm i -D playwright && npx playwright install chromium\n' +
      '  Ask the owner before adding it as a repo dependency.',
  );
  return null;
}


/** Candidate Chrome binaries, newest local Playwright build first, then system Chrome. */
function chromiumCandidates(explicit) {
  if (explicit) return [explicit];
  const found = [];
  const home = process.env.HOME ?? '';
  if (home) {
    try {
      const builds = globSync(`${home}/.cache/ms-playwright/chromium-*/chrome-linux*/chrome`);
      // Directory names sort as chromium-<revision>; the highest revision is newest.
      found.push(...builds.sort().reverse());
    } catch {
      /* no local Playwright browser cache */
    }
  }
  found.push('/usr/bin/google-chrome', '/usr/bin/chromium');
  return found.filter((path) => existsSync(path));
}

/**
 * Launch the browser Playwright installed. When that binary is missing - common
 * when the Playwright module and the browser cache come from different
 * installs - fall back to a local Chrome build rather than failing the bench.
 */
async function launchChromium(chromium, opts, args) {
  const base = { headless: !opts.headed, args };
  if (!opts.chromium) {
    try {
      return await chromium.launch(base);
    } catch (error) {
      if (!/Executable doesn't exist/.test(error?.message ?? '')) throw error;
    }
  }
  for (const executablePath of chromiumCandidates(opts.chromium)) {
    try {
      return await chromium.launch({ ...base, executablePath });
    } catch {
      /* try the next binary */
    }
  }
  fail(
    'no usable Chrome binary. Install one for Playwright (npx playwright install chromium) ' +
      'or pass --chromium /path/to/chrome.',
  );
  return null;
}

/**
 * Injected at document start, before any page script. Records rAF deltas into
 * window.__BENCH__ and exposes the seed the page should use for its RNG.
 */
function instrument({ seed, needed }) {
  window.__BENCH_SEED__ = seed;
  const state = { deltas: [], done: false, error: null, pageRafCalls: 0 };
  window.__BENCH__ = state;
  // Count the page's own rAF calls. The harness loop below ticks even on a dead
  // page, so frames alone cannot prove the page is animating; its own rAF calls
  // can. Hold the native function so the harness never counts itself.
  const rawRaf = window.requestAnimationFrame.bind(window);
  window.requestAnimationFrame = (cb) => {
    state.pageRafCalls += 1;
    return rawRaf(cb);
  };
  let last = null;
  const tick = (now) => {
    if (last !== null) state.deltas.push(now - last);
    last = now;
    if (state.deltas.length >= needed) {
      state.done = true;
      return;
    }
    rawRaf(tick);
  };
  rawRaf(tick);
  window.addEventListener('error', (event) => {
    state.error = String(event.message ?? event.error);
  });
}

const quantile = (sorted, q) => {
  if (sorted.length === 1) return sorted[0];
  const pos = (sorted.length - 1) * q;
  const lo = Math.floor(pos);
  const hi = Math.ceil(pos);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - lo);
};

const median = (values) => quantile([...values].sort((a, b) => a - b), 0.5);
const round = (value, digits = 2) => Number(value.toFixed(digits));

/** Frame times in ms -> the FPS figures. Low percentiles come from slow frames. */
function summarize(deltas) {
  const sorted = [...deltas].sort((a, b) => a - b);
  const mean = deltas.reduce((a, b) => a + b, 0) / deltas.length;
  return {
    frames: deltas.length,
    meanFps: round(1000 / mean),
    p50Fps: round(1000 / quantile(sorted, 0.5)),
    p1LowFps: round(1000 / quantile(sorted, 0.99)),
    p01LowFps: round(1000 / quantile(sorted, 0.999)),
    worstFrameMs: round(sorted[sorted.length - 1]),
  };
}

async function runOnce(browser, opts) {
  const context = await browser.newContext({ viewport: { width: opts.width, height: opts.height } });
  const page = await context.newPage();
  const pageErrors = [];
  page.on('pageerror', (error) => pageErrors.push(error.message));
  try {
    const needed = opts.warmup + opts.frames;
    await page.addInitScript(instrument, { seed: opts.seed, needed });
    const response = await page.goto(opts.url, { waitUntil: 'load', timeout: opts.timeout });
    if (response && !response.ok()) {
      fail(`page returned HTTP ${response.status()} for ${opts.url}`, 2);
    }
    await page
      .waitForFunction(() => window.__BENCH__?.done === true, null, {
        timeout: opts.timeout,
        polling: 100,
      })
      .catch(() => {
        /* fall through to the frame-count check, which gives a better message */
      });
    const state = await page.evaluate(() => ({
      deltas: window.__BENCH__?.deltas ?? [],
      error: window.__BENCH__?.error ?? null,
      pageRafCalls: window.__BENCH__?.pageRafCalls ?? 0,
    }));
    if (pageErrors.length) fail(`page threw: ${pageErrors[0]}`, 2);
    if (state.error) fail(`page threw: ${state.error}`, 2);
    if (state.deltas.length === 0) {
      fail(`page drew no frames in ${opts.timeout} ms. Is ${opts.url} animating?`, 2);
    }
    if (state.pageRafCalls === 0) {
      fail(
        `page never called requestAnimationFrame, so it is not animating: ${opts.url}. ` +
          'Frame timings from a static page measure the browser, not the game.',
        2,
      );
    }
    if (state.deltas.length <= opts.warmup) {
      fail(
        `page drew only ${state.deltas.length} frames in ${opts.timeout} ms, ` +
          `fewer than --warmup ${opts.warmup}. Lower --warmup/--frames or raise --timeout.`,
        2,
      );
    }
    return summarize(state.deltas.slice(opts.warmup));
  } finally {
    await context.close();
  }
}

async function main() {
  const opts = parseArgs(process.argv.slice(2));
  const { chromium } = await loadPlaywright();
  const args = [
    '--no-sandbox',
    '--hide-scrollbars',
    `--window-size=${opts.width},${opts.height}`,
    // Deterministic-ish JS timing: same JIT and GC behaviour run to run.
    '--js-flags=--expose-gc',
  ];
  if (!opts.keepVsync) {
    // Let the page draw as fast as it can instead of quantizing every frame to
    // the display refresh. Without this, frame deltas cluster on 16.7 ms
    // multiples and small regressions round away to nothing.
    args.push('--disable-gpu-vsync', '--disable-frame-rate-limit', '--disable-background-timer-throttling');
  }
  const browser = await launchChromium(chromium, opts, args);
  let runs;
  try {
    runs = [];
    for (let i = 0; i < opts.runs; i += 1) {
      runs.push(await runOnce(browser, opts));
    }
  } finally {
    await browser.close();
  }

  const p1Lows = runs.map((r) => r.p1LowFps);
  const spread = round(Math.max(...p1Lows) - Math.min(...p1Lows));
  const result = {
    metric: 'p1LowFps',
    value: round(median(p1Lows)),
    higherIsBetter: true,
    url: opts.url,
    seed: opts.seed,
    frames: opts.frames,
    warmup: opts.warmup,
    runs: opts.runs,
    across: {
      meanFps: round(median(runs.map((r) => r.meanFps))),
      p50Fps: round(median(runs.map((r) => r.p50Fps))),
      p1LowFps: round(median(p1Lows)),
      p01LowFps: round(median(runs.map((r) => r.p01LowFps))),
      spreadP1Low: spread,
      spreadPct: round((spread / median(p1Lows)) * 100),
    },
    perRun: runs,
  };

  if (opts.json) {
    process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
  } else {
    process.stdout.write(`${result.value}\n`);
  }

  if (opts.maxSpread !== null && spread > opts.maxSpread) {
    fail(
      `run-to-run spread of p1-low FPS is ${spread}, above --max-spread ${opts.maxSpread}. ` +
        'Any hill-climb delta smaller than that is noise. Close background load, ' +
        'let the machine cool, or raise --runs.',
      3,
    );
  }
  if (opts.maxSpread === null && result.across.spreadPct > 10) {
    process.stderr.write(
      `bench-frames: warning: spread ${spread} FPS (${result.across.spreadPct}% of the median) ` +
        'across runs. Treat smaller deltas as noise.\n',
    );
  }
}

const SELFTEST_PAGE = `<!doctype html><meta charset="utf-8"><title>bench-frames self-test</title>
<style>html,body{margin:0;background:#111}canvas{display:block}</style>
<canvas id="c" width="1280" height="720"></canvas>
<script>
// Seeded RNG so the workload is identical run to run.
let s = (window.__BENCH_SEED__ || 1) >>> 0;
const rnd = () => (s = (s * 1664525 + 1013904223) >>> 0) / 4294967296;
const ctx = document.getElementById('c').getContext('2d');
const dots = Array.from({length: 400}, () => ({x: rnd()*1280, y: rnd()*720, vx: rnd()*4-2, vy: rnd()*4-2}));
let n = 0;
(function draw(){
  ctx.fillStyle = '#111'; ctx.fillRect(0,0,1280,720);
  ctx.fillStyle = '#6cf';
  for (const d of dots) {
    d.x = (d.x + d.vx + 1280) % 1280; d.y = (d.y + d.vy + 720) % 720;
    ctx.fillRect(d.x, d.y, 3, 3);
  }
  // Deterministic hitch every 90 frames, so p1-low has something real to catch.
  if (++n % 90 === 0) { const t = performance.now(); while (performance.now() - t < 25); }
  requestAnimationFrame(draw);
})();
</script>`;

// Keep the self-test page generator next to the harness it exercises.
if (process.argv.includes('--write-selftest-page')) {
  const dir = mkdtempSync(join(tmpdir(), 'bench-frames-'));
  const file = join(dir, 'index.html');
  writeFileSync(file, SELFTEST_PAGE);
  process.stdout.write(`${file}\n`);
  process.exit(0);
}

main().catch((error) => fail(error?.message ?? String(error), 2));
