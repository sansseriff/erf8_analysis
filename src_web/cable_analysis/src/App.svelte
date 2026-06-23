<script lang="ts">
  import Wizard from './lib/Wizard.svelte';

  type VnaLine = { type: 'vna'; folder: string; file: string; sparam: string };
  type PulseLine = { type: 'pulse'; subfolder: string; file: string; channel: string };
  type LineSpec = VnaLine | PulseLine;

  const PALETTE = [
    '#a6cee3', '#1f78b4', '#b2df8a', '#33a02c',
    '#fb9a99', '#e31a1c', '#fdbf6f', '#ff7f00',
    '#cab2d6', '#6a3d9a', '#ffff99', '#b15928',
  ];

  const CHANNEL_LABELS: Record<string, string> = {
    C1: 'Raw Original',
    C2: 'Raw Transmission',
    C3: 'Raw Adjacent Transmission',
    C4: 'Raw Adjacent Reflection',
    C5: 'Avg Original',
    C6: 'Avg Transmission',
    C7: 'Avg Adjacent Transmission',
    C8: 'Avg Adjacent Reflection',
  };

  let lines = $state<LineSpec[]>([]);
  let plotType = $state<'vna' | 'pulse' | null>(null);
  let showWizard = $state(false);
  let plotImageUrl = $state<string | null>(null);
  let isPlotting = $state(false);
  let plotError = $state<string | null>(null);

  // dB measurement
  let measureA = $state(0);
  let measureB = $state(1);
  let isMeasuring = $state(false);
  let measureResult = $state<{ db: number; max_a: number; max_b: number } | null>(null);
  let measureError = $state<string | null>(null);

  // Axis range (strings so we can tell empty-vs-zero; parsed at send time)
  let xMin = $state('');
  let xMax = $state('');
  let yMin = $state('');
  let yMax = $state('');

  function parseRange(s: string): number | null {
    const t = s.trim();
    if (t === '') return null;
    const v = parseFloat(t);
    return Number.isFinite(v) ? v : null;
  }

  function rangePayload() {
    return {
      x_min: parseRange(xMin),
      x_max: parseRange(xMax),
      y_min: parseRange(yMin),
      y_max: parseRange(yMax),
    };
  }

  function resetRange() {
    xMin = '';
    xMax = '';
    yMin = '';
    yMax = '';
  }

  function lineLabel(l: LineSpec): string {
    if (l.type === 'vna') return `${l.folder} / ${l.file} — ${l.sparam}`;
    const ch = CHANNEL_LABELS[l.channel] ?? l.channel;
    return `${l.subfolder} / ${l.file} — ${l.channel} ${ch}`;
  }

  function addLine(e: CustomEvent<LineSpec>) {
    const spec = e.detail;
    if (!plotType) plotType = spec.type;
    lines = [...lines, spec];
    showWizard = false;
    measureResult = null;
  }

  function removeLine(i: number) {
    lines = lines.filter((_, idx) => idx !== i);
    if (lines.length === 0) { plotType = null; measureResult = null; }
    // clamp measure indices
    measureA = Math.min(measureA, Math.max(0, lines.length - 1));
    measureB = Math.min(measureB, Math.max(0, lines.length - 1));
  }

  function clearAll() {
    lines = [];
    plotType = null;
    plotImageUrl = null;
    plotError = null;
    measureResult = null;
    measureError = null;
  }

  async function plot() {
    if (lines.length === 0) return;
    isPlotting = true;
    plotError = null;
    measureResult = null;
    try {
      const res = await fetch('/api/plot', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type: plotType, lines, ...rangePayload() }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
        plotError = err.detail ?? 'Plot failed';
        return;
      }
      const blob = await res.blob();
      if (plotImageUrl) URL.revokeObjectURL(plotImageUrl);
      plotImageUrl = URL.createObjectURL(blob);
    } catch (e) {
      plotError = String(e);
    } finally {
      isPlotting = false;
    }
  }

  async function measure() {
    isMeasuring = true;
    measureError = null;
    try {
      const res = await fetch('/api/measure', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type: plotType, lines, measure_a: measureA, measure_b: measureB, ...rangePayload() }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
        measureError = err.detail ?? 'Measure failed';
        return;
      }
      const data = await res.json();
      measureResult = { db: data.db, max_a: data.max_a, max_b: data.max_b };
      // Replace plot with annotated version
      const bytes = atob(data.image);
      const arr = new Uint8Array(bytes.length);
      for (let i = 0; i < bytes.length; i++) arr[i] = bytes.charCodeAt(i);
      const blob = new Blob([arr], { type: 'image/png' });
      if (plotImageUrl) URL.revokeObjectURL(plotImageUrl);
      plotImageUrl = URL.createObjectURL(blob);
    } catch (e) {
      measureError = String(e);
    } finally {
      isMeasuring = false;
    }
  }
</script>

<header>
  <h1>Cable Analysis</h1>
</header>

<main>
  <section class="controls">
    <div class="btn-row">
      <button class="btn primary" onclick={() => (showWizard = true)} disabled={showWizard}>
        + Add Line
      </button>
      <button class="btn" onclick={plot} disabled={lines.length === 0 || isPlotting}>
        {isPlotting ? 'Plotting…' : 'Plot'}
      </button>
      {#if lines.length > 0}
        <button class="btn danger" onclick={clearAll}>Clear All</button>
      {/if}
    </div>

    {#if plotType}
      <p class="type-hint">
        Mode: <strong>{plotType === 'vna' ? 'VNA Comparison' : 'Pulse Comparison'}</strong>
        {#if lines.length > 0}— add more {plotType === 'vna' ? 'VNA' : 'Pulse'} lines, or Clear All to switch{/if}
      </p>
    {/if}
  </section>

  {#if lines.length > 0}
    <section class="lines-panel">
      <h2>Lines ({lines.length})</h2>
      <ul class="lines-list">
        {#each lines as line, i}
          <li class="line-item" style="border-left-color: {PALETTE[i % PALETTE.length]}">
            <span class="badge {line.type}">{line.type.toUpperCase()}</span>
            <span class="line-label">{lineLabel(line)}</span>
            <button class="remove-btn" onclick={() => removeLine(i)} aria-label="Remove">✕</button>
          </li>
        {/each}
      </ul>
    </section>
  {:else}
    <p class="empty-hint">Click <strong>+ Add Line</strong> to get started.</p>
  {/if}

  {#if plotError}
    <p class="error">{plotError}</p>
  {/if}

  {#if plotImageUrl}
    <section class="range-section">
      <h2>Axis Range</h2>
      <div class="range-row">
        <label class="range-field">
          <span>X min</span>
          <input type="text" inputmode="decimal" bind:value={xMin} placeholder="auto" />
        </label>
        <label class="range-field">
          <span>X max</span>
          <input type="text" inputmode="decimal" bind:value={xMax} placeholder="auto" />
        </label>
        <label class="range-field">
          <span>Y min</span>
          <input type="text" inputmode="decimal" bind:value={yMin} placeholder="auto" />
        </label>
        <label class="range-field">
          <span>Y max</span>
          <input type="text" inputmode="decimal" bind:value={yMax} placeholder="auto" />
        </label>
        <button class="btn primary" onclick={plot} disabled={isPlotting}>
          {isPlotting ? 'Replotting…' : 'Replot'}
        </button>
        <button class="btn" onclick={resetRange} disabled={isPlotting}>Reset</button>
      </div>
      <p class="range-hint">
        Leave blank for auto.
        {#if plotType === 'pulse'}X in ns, Y in V.{:else}X in MHz, Y in dB.{/if}
      </p>
    </section>

    <section class="plot-section">
      <img src={plotImageUrl} alt="Matplotlib plot" class="plot-img" />
    </section>
  {/if}

  <!-- dB Measurement tool — only in pulse mode with a plot and ≥2 lines -->
  {#if plotType === 'pulse' && plotImageUrl && lines.length >= 2}
    <section class="measure-section">
      <h2>dB Measurement</h2>
      <div class="measure-row">
        <select bind:value={measureA} class="measure-select">
          {#each lines as line, i}
            <option value={i}>{i + 1}: {lineLabel(line)}</option>
          {/each}
        </select>
        <span class="vs-label">vs</span>
        <select bind:value={measureB} class="measure-select">
          {#each lines as line, i}
            <option value={i}>{i + 1}: {lineLabel(line)}</option>
          {/each}
        </select>
        <button
          class="btn"
          onclick={measure}
          disabled={isMeasuring || measureA === measureB}
        >
          {isMeasuring ? 'Measuring…' : 'Measure'}
        </button>
      </div>

      {#if measureError}
        <p class="error">{measureError}</p>
      {/if}

      {#if measureResult}
        <div class="measure-result">
          <div class="measure-row-values">
            <span class="mval">Line {measureA + 1} peak: <strong>{measureResult.max_a.toExponential(3)} V</strong></span>
            <span class="mval">Line {measureB + 1} peak: <strong>{measureResult.max_b.toExponential(3)} V</strong></span>
          </div>
          <div class="db-result">
            <span class="db-label">A / B ratio:</span>
            <span class="db-value">{measureResult.db.toFixed(2)} dB</span>
          </div>
        </div>
      {/if}
    </section>
  {/if}
</main>

{#if showWizard}
  <Wizard
    lockedType={plotType}
    on:add={addLine}
    on:close={() => (showWizard = false)}
  />
{/if}

<style>
  /* ---- Theme tokens ---- */
  :global(:root) {
    --bg:          #f8f9fa;
    --bg-header:   #ffffff;
    --bg-card:     #ffffff;
    --border:      #dee2e6;
    --text:        #212529;
    --text-muted:  #6c757d;
    --btn-bg:      #f0f0f0;
    --btn-border:  #ced4da;
    --accent:      #7c3aed;
    --accent-h:    #6d28d9;
    --danger-text: #dc3545;
    --danger-bg:   #fff5f5;
    --danger-bdr:  #f5c2c7;
    --badge-vna-bg:    #dbeafe;
    --badge-vna-fg:    #1e40af;
    --badge-pulse-bg:  #fef3c7;
    --badge-pulse-fg:  #92400e;
  }

  @media (prefers-color-scheme: dark) {
    :global(:root) {
      --bg:          #0f0f1a;
      --bg-header:   #12121f;
      --bg-card:     #161626;
      --border:      #2a2a3e;
      --text:        #e0e0e0;
      --text-muted:  #888;
      --btn-bg:      #1e1e30;
      --btn-border:  #444;
      --accent:      #aa3bff;
      --accent-h:    #8a2fd0;
      --danger-text: #ff6b6b;
      --danger-bg:   #2a1010;
      --danger-bdr:  #5a2020;
      --badge-vna-bg:    #1a3a6a;
      --badge-vna-fg:    #7ac0ff;
      --badge-pulse-bg:  #3a2200;
      --badge-pulse-fg:  #fbbf24;
    }
  }

  :global(*, *::before, *::after) { box-sizing: border-box; margin: 0; padding: 0; }

  :global(body) {
    background: var(--bg);
    color: var(--text);
    font-family: Inter, system-ui, sans-serif;
    min-height: 100vh;
  }

  /* ---- Layout ---- */
  header {
    padding: 1.1rem 2rem;
    border-bottom: 1px solid var(--border);
    background: var(--bg-header);
  }

  h1 { font-size: 1.3rem; font-weight: 700; }

  main { max-width: 980px; margin: 0 auto; padding: 2rem; }

  h2 { font-size: 0.95rem; font-weight: 600; color: var(--text-muted); margin-bottom: 0.6rem; }

  /* ---- Controls ---- */
  .controls { margin-bottom: 1.5rem; }

  .btn-row { display: flex; gap: 0.65rem; flex-wrap: wrap; }

  .btn {
    padding: 0.5rem 1.1rem;
    border: 1px solid var(--btn-border);
    border-radius: 6px;
    background: var(--btn-bg);
    color: var(--text);
    cursor: pointer;
    font-size: 0.88rem;
    transition: background 0.12s, border-color 0.12s;
  }

  .btn:hover:not(:disabled) { filter: brightness(0.93); }
  .btn:disabled { opacity: 0.42; cursor: not-allowed; }

  .btn.primary {
    background: var(--accent);
    border-color: var(--accent);
    color: #fff;
    font-weight: 600;
  }
  .btn.primary:hover:not(:disabled) { background: var(--accent-h); border-color: var(--accent-h); }

  .btn.danger { color: var(--danger-text); border-color: var(--danger-bdr); }
  .btn.danger:hover:not(:disabled) { background: var(--danger-bg); }

  .type-hint { margin-top: 0.7rem; font-size: 0.8rem; color: var(--text-muted); }

  /* ---- Lines panel ---- */
  .lines-panel { margin-bottom: 1.5rem; }

  .lines-list { list-style: none; display: flex; flex-direction: column; gap: 0.35rem; }

  .line-item {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.5rem 0.75rem;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-left: 4px solid transparent;
    border-radius: 6px;
  }

  .badge {
    font-size: 0.68rem;
    font-weight: 700;
    padding: 0.15rem 0.4rem;
    border-radius: 4px;
    flex-shrink: 0;
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }
  .badge.vna   { background: var(--badge-vna-bg);   color: var(--badge-vna-fg); }
  .badge.pulse { background: var(--badge-pulse-bg); color: var(--badge-pulse-fg); }

  .line-label {
    flex: 1; font-size: 0.83rem; overflow: hidden;
    text-overflow: ellipsis; white-space: nowrap;
  }

  .remove-btn {
    background: none; border: none; color: var(--text-muted);
    cursor: pointer; font-size: 0.8rem; padding: 0.1rem 0.3rem; flex-shrink: 0;
  }
  .remove-btn:hover { color: var(--danger-text); }

  .empty-hint { color: var(--text-muted); font-size: 0.88rem; }

  /* ---- Error ---- */
  .error {
    color: var(--danger-text);
    background: var(--danger-bg);
    border: 1px solid var(--danger-bdr);
    border-radius: 6px;
    padding: 0.55rem 0.9rem;
    font-size: 0.83rem;
    margin-bottom: 1rem;
  }

  /* ---- Range ---- */
  .range-section {
    margin-top: 1.5rem;
    padding: 1rem 1.2rem;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 8px;
  }

  .range-row {
    display: flex;
    align-items: flex-end;
    gap: 0.6rem;
    flex-wrap: wrap;
  }

  .range-field {
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
    font-size: 0.78rem;
    color: var(--text-muted);
  }
  .range-field input {
    width: 110px;
    padding: 0.4rem 0.55rem;
    border: 1px solid var(--btn-border);
    border-radius: 6px;
    background: var(--btn-bg);
    color: var(--text);
    font-size: 0.85rem;
  }

  .range-hint {
    margin-top: 0.55rem;
    font-size: 0.78rem;
    color: var(--text-muted);
  }

  /* ---- Plot ---- */
  .plot-section { margin-top: 1.5rem; }

  .plot-img {
    max-width: 100%;
    border-radius: 8px;
    border: 1px solid var(--border);
    display: block;
  }

  /* ---- dB Measure ---- */
  .measure-section {
    margin-top: 1.5rem;
    padding: 1rem 1.2rem;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 8px;
  }

  .measure-row {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    flex-wrap: wrap;
  }

  .measure-select {
    flex: 1;
    min-width: 160px;
    padding: 0.45rem 0.7rem;
    border: 1px solid var(--btn-border);
    border-radius: 6px;
    background: var(--btn-bg);
    color: var(--text);
    font-size: 0.83rem;
  }

  .vs-label { font-size: 0.8rem; color: var(--text-muted); flex-shrink: 0; }

  .measure-result {
    margin-top: 0.9rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .measure-row-values {
    display: flex;
    gap: 1.5rem;
    flex-wrap: wrap;
  }

  .mval { font-size: 0.85rem; color: var(--text-muted); }
  .mval strong { color: var(--text); }

  .db-result {
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
  }

  .db-label { font-size: 0.85rem; color: var(--text-muted); }

  .db-value {
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--accent);
  }
</style>
