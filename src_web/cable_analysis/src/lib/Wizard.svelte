<script lang="ts">
  import { createEventDispatcher } from 'svelte';

  const dispatch = createEventDispatcher<{
    add: LineSpec;
    close: void;
  }>();

  // The locked plot type from parent (null = free, 'vna' | 'pulse' = locked)
  let { lockedType }: { lockedType: 'vna' | 'pulse' | null } = $props();

  type LineSpec =
    | { type: 'vna'; folder: string; file: string; sparam: string }
    | { type: 'pulse'; subfolder: string; file: string; channel: string };

  const CHANNEL_OPTIONS = [
    { value: 'C1', label: 'C1 — Raw Original' },
    { value: 'C2', label: 'C2 — Raw Transmission' },
    { value: 'C3', label: 'C3 — Raw Adjacent Transmission' },
    { value: 'C4', label: 'C4 — Raw Adjacent Reflection' },
    { value: 'C5', label: 'C5 — Avg Original' },
    { value: 'C6', label: 'C6 — Avg Transmission' },
    { value: 'C7', label: 'C7 — Avg Adjacent Transmission' },
    { value: 'C8', label: 'C8 — Avg Adjacent Reflection' },
  ];

  // Step machine
  // step 0: choose type (unless locked)
  // VNA: step 1 = folder, step 2 = file, step 3 = sparam
  // Pulse: step 1 = subfolder, step 2 = file, step 3 = channel
  let plotType = $state<'vna' | 'pulse' | null>(lockedType);
  let step = $state(lockedType ? 1 : 0);

  // Selections
  let folder = $state('');
  let file = $state('');
  let subfolder = $state('');

  // Multi-selections (step 3)
  let selectedSparams = $state(new Set<string>());
  let selectedChannels = $state(new Set<string>());

  // Fetched lists
  let folders = $state<string[]>([]);
  let subfolders = $state<string[]>([]);
  let files = $state<string[]>([]);
  let sparams = $state<string[]>([]);

  let loading = $state(false);

  // If type is already locked, pre-fetch the folder/subfolder list immediately
  if (lockedType === 'vna') {
    loading = true;
    fetch('/api/vna/folders').then(r => r.json()).then(data => {
      folders = data;
      loading = false;
    });
  } else if (lockedType === 'pulse') {
    loading = true;
    fetch('/api/pulse/subfolders').then(r => r.json()).then(data => {
      subfolders = data;
      loading = false;
    });
  }

  function toggleSparam(s: string) {
    const next = new Set(selectedSparams);
    next.has(s) ? next.delete(s) : next.add(s);
    selectedSparams = next;
  }

  function toggleChannel(c: string) {
    const next = new Set(selectedChannels);
    next.has(c) ? next.delete(c) : next.add(c);
    selectedChannels = next;
  }

  async function chooseType(t: 'vna' | 'pulse') {
    plotType = t;
    loading = true;
    if (t === 'vna') {
      folders = await fetch('/api/vna/folders').then(r => r.json());
    } else {
      subfolders = await fetch('/api/pulse/subfolders').then(r => r.json());
    }
    loading = false;
    step = 1;
  }

  async function chooseFolder(f: string) {
    folder = f;
    loading = true;
    files = await fetch(`/api/vna/files?folder=${encodeURIComponent(f)}`).then(r => r.json());
    loading = false;
    step = 2;
  }

  async function chooseSubfolder(sf: string) {
    subfolder = sf;
    loading = true;
    files = await fetch(`/api/pulse/files?subfolder=${encodeURIComponent(sf)}`).then(r => r.json());
    loading = false;
    step = 2;
  }

  async function chooseFile(f: string) {
    file = f;
    selectedSparams = new Set();
    selectedChannels = new Set();
    if (plotType === 'vna') {
      loading = true;
      sparams = await fetch(
        `/api/vna/sparams?folder=${encodeURIComponent(folder)}&file=${encodeURIComponent(f)}`
      ).then(r => r.json());
      loading = false;
    }
    step = 3;
  }

  function confirm() {
    if (plotType === 'vna') {
      for (const s of selectedSparams) {
        dispatch('add', { type: 'vna', folder, file, sparam: s });
      }
    } else {
      for (const c of selectedChannels) {
        dispatch('add', { type: 'pulse', subfolder, file, channel: c });
      }
    }
  }

  function back() {
    if (step > (lockedType ? 1 : 0)) step--;
  }
</script>

<!-- Modal overlay -->
<div class="overlay" role="dialog" aria-modal="true">
  <div class="modal">
    <button class="close-btn" onclick={() => dispatch('close')} aria-label="Close">✕</button>

    <h2>Add Line</h2>

    {#if loading}
      <p class="hint">Loading…</p>
    {:else if step === 0}
      <!-- Choose type -->
      <p class="prompt">What type of comparison?</p>
      <div class="choice-row">
        <button class="choice-btn" onclick={() => chooseType('vna')}>VNA Comparison</button>
        <button class="choice-btn" onclick={() => chooseType('pulse')}>Pulse Comparison</button>
      </div>

    {:else if plotType === 'vna'}
      {#if step === 1}
        <p class="prompt">Select a folder:</p>
        <ul class="pick-list">
          {#each folders as f}
            <li><button class="pick-btn" onclick={() => chooseFolder(f)}>{f}</button></li>
          {/each}
        </ul>

      {:else if step === 2}
        <p class="prompt">Folder: <strong>{folder}</strong> — Select a file:</p>
        <ul class="pick-list">
          {#each files as f}
            <li><button class="pick-btn" onclick={() => chooseFile(f)}>{f}</button></li>
          {/each}
        </ul>

      {:else if step === 3}
        <p class="prompt">File: <strong>{file}</strong> — Select S-parameters (multiple allowed):</p>
        <ul class="pick-list sparam-grid">
          {#each sparams as s}
            <li>
              <button
                class="pick-btn sparam-btn"
                class:selected={selectedSparams.has(s)}
                onclick={() => toggleSparam(s)}
              >{s}</button>
            </li>
          {/each}
        </ul>
        {#if selectedSparams.size > 0}
          <button class="confirm-btn" onclick={confirm}>
            Add {selectedSparams.size} line{selectedSparams.size > 1 ? 's' : ''}
          </button>
        {/if}
      {/if}

    {:else if plotType === 'pulse'}
      {#if step === 1}
        <p class="prompt">Select a subfolder:</p>
        <ul class="pick-list">
          {#each subfolders as sf}
            <li><button class="pick-btn" onclick={() => chooseSubfolder(sf)}>{sf}</button></li>
          {/each}
        </ul>

      {:else if step === 2}
        <p class="prompt">Subfolder: <strong>{subfolder}</strong> — Select a file:</p>
        <ul class="pick-list">
          {#each files as f}
            <li><button class="pick-btn" onclick={() => chooseFile(f)}>{f}</button></li>
          {/each}
        </ul>

      {:else if step === 3}
        <p class="prompt">File: <strong>{file}</strong> — Select channels (multiple allowed):</p>
        <ul class="pick-list channel-grid">
          {#each CHANNEL_OPTIONS as opt}
            <li>
              <button
                class="pick-btn"
                class:selected={selectedChannels.has(opt.value)}
                onclick={() => toggleChannel(opt.value)}
              >{opt.label}</button>
            </li>
          {/each}
        </ul>
        {#if selectedChannels.size > 0}
          <button class="confirm-btn" onclick={confirm}>
            Add {selectedChannels.size} line{selectedChannels.size > 1 ? 's' : ''}
          </button>
        {/if}
      {/if}
    {/if}

    {#if step > (lockedType ? 1 : 0) && !loading}
      <button class="back-btn" onclick={back}>← Back</button>
    {/if}
  </div>
</div>

<style>
  .overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.45);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 100;
  }

  .modal {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 2rem;
    min-width: 420px;
    max-width: 640px;
    max-height: 80vh;
    overflow-y: auto;
    position: relative;
    box-shadow: 0 8px 32px rgba(0,0,0,0.18);
  }

  h2 { margin: 0 0 1rem; font-size: 1.2rem; color: var(--text); }

  .close-btn {
    position: absolute;
    top: 1rem;
    right: 1rem;
    background: none;
    border: none;
    color: var(--text-muted);
    font-size: 1.1rem;
    cursor: pointer;
    padding: 0.2rem 0.5rem;
  }
  .close-btn:hover { color: var(--text); }

  .prompt { margin: 0 0 0.8rem; color: var(--text-muted); font-size: 0.88rem; }
  .hint { color: var(--text-muted); font-size: 0.88rem; }

  .choice-row { display: flex; gap: 1rem; }

  .choice-btn {
    flex: 1;
    padding: 0.75rem 1rem;
    background: var(--btn-bg);
    border: 1px solid var(--btn-border);
    border-radius: 8px;
    color: var(--text);
    cursor: pointer;
    font-size: 0.92rem;
    transition: background 0.12s;
  }
  .choice-btn:hover { background: var(--accent); border-color: var(--accent); color: #fff; }

  .pick-list {
    list-style: none;
    padding: 0;
    margin: 0 0 0.5rem;
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
  }

  .sparam-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 0.4rem;
  }

  .channel-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 0.4rem;
  }

  .pick-btn {
    width: 100%;
    padding: 0.45rem 0.75rem;
    background: var(--btn-bg);
    border: 1px solid var(--btn-border);
    border-radius: 6px;
    color: var(--text);
    cursor: pointer;
    text-align: left;
    font-size: 0.83rem;
    transition: background 0.1s;
  }
  .pick-btn:hover { filter: brightness(0.93); border-color: var(--accent); }

  .sparam-btn { text-align: center; }
  .pick-btn.selected { background: var(--accent); border-color: var(--accent); color: #fff; }

  .confirm-btn {
    margin-top: 1rem;
    padding: 0.55rem 1.3rem;
    background: var(--accent);
    border: none;
    border-radius: 6px;
    color: #fff;
    cursor: pointer;
    font-size: 0.92rem;
    font-weight: 600;
  }
  .confirm-btn:hover { background: var(--accent-h); }

  .back-btn {
    margin-top: 0.8rem;
    background: none;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    font-size: 0.83rem;
    padding: 0;
  }
  .back-btn:hover { color: var(--text); }
</style>
