import { useCallback, useEffect, useState } from 'react'
import { api, SongPlan, Track } from './api'
import { ARRANGEMENTS, COMPOSE_PLANS, GENRE_PRESETS, PRESET_FAMILIES } from './presets'

const LANGS = ['english', 'hebrew', 'spanish', 'french', 'japanese', 'arabic', 'german', 'portuguese']

export default function App() {
  const [tracks, setTracks] = useState<Track[]>([])
  const [selected, setSelected] = useState<Track | null>(null)
  const [error, setError] = useState('')

  const refresh = useCallback(async () => {
    try {
      const list = await api.listSongs()
      setTracks(list)
      setSelected(s => (s ? list.find(t => t.id === s.id) ?? null : null))
    } catch (e) {
      setError(String(e))
    }
  }, [])

  useEffect(() => {
    refresh()
    const iv = setInterval(refresh, 4000)
    return () => clearInterval(iv)
  }, [refresh])

  return (
    <div className="shell">
      <header>
        <h1>🎵 Crescendo</h1>
        <span className="tag">AI Music Studio · powered by ACE-Step 1.5</span>
      </header>
      {error && <div className="error" onClick={() => setError('')}>{error}</div>}
      <main>
        <CreatePanel onCreated={refresh} onError={setError} />
        <Library tracks={tracks} selected={selected} onSelect={setSelected} onChanged={refresh} onError={setError} />
      </main>
    </div>
  )
}

function CreatePanel({ onCreated, onError }: { onCreated: () => void; onError: (m: string) => void }) {
  const [idea, setIdea] = useState('')
  const [title, setTitle] = useState('')
  const [prompt, setPrompt] = useState('')
  const [lyrics, setLyrics] = useState('')
  const [language, setLanguage] = useState('english')
  const [duration, setDuration] = useState(120)
  const [takes, setTakes] = useState(1)
  const [busy, setBusy] = useState('')
  const [presetId, setPresetId] = useState('')
  const [bpm, setBpm] = useState<number | null>(null)
  const [instrumental, setInstrumental] = useState(false)
  const [quality, setQuality] = useState<'draft' | 'pro'>('pro')

  const insertArrangement = () => {
    const preset = GENRE_PRESETS.find(p => p.id === presetId)
    const blueprint = ARRANGEMENTS[preset?.family ?? 'House']
    setInstrumental(false)
    setLyrics(current => (current.trim() ? `${blueprint}\n\n${current}` : blueprint))
  }

  const applyPreset = (id: string) => {
    setPresetId(id)
    const preset = GENRE_PRESETS.find(p => p.id === id)
    if (preset) {
      setPrompt(preset.prompt)
      setBpm(preset.bpm)
    }
  }

  const applyPlan = (p: SongPlan) => {
    setTitle(p.title ?? '')
    setPrompt(p.prompt ?? '')
    setLyrics(p.lyrics ?? '')
    if (p.duration) setDuration(p.duration)
    if (p.vocal_language) setLanguage(p.vocal_language)
  }

  const run = async (label: string, fn: () => Promise<void>) => {
    setBusy(label)
    try {
      await fn()
    } catch (e) {
      onError(String(e))
    } finally {
      setBusy('')
    }
  }

  return (
    <section className="panel">
      <h2>Create</h2>
      <label>Your idea (any language)</label>
      <textarea value={idea} onChange={e => setIdea(e.target.value)} rows={2}
        placeholder="e.g. שיר רוק על תל אביב בלילה / an upbeat synthwave song about the ocean" />
      <div className="row">
        <button disabled={!idea || !!busy} onClick={() => run('plan', async () => applyPlan(await api.plan(idea, language)))}>
          {busy === 'plan' ? 'Planning…' : '🪄 AI Producer: plan full song'}
        </button>
        <button disabled={!idea || !!busy} onClick={() => run('enhance', async () => setPrompt((await api.enhance(idea)).prompt))}>
          {busy === 'enhance' ? '…' : '✨ Enhance prompt'}
        </button>
        <button disabled={!idea || !!busy} onClick={() => run('lyrics', async () => setLyrics((await api.lyrics(idea, language, prompt)).lyrics))}>
          {busy === 'lyrics' ? '…' : '📝 Write lyrics'}
        </button>
      </div>

      <label>Electronic genre preset (fills prompt + BPM)</label>
      <select value={presetId} onChange={e => applyPreset(e.target.value)}>
        <option value="">— pick a genre —</option>
        {PRESET_FAMILIES.map(family => (
          <optgroup key={family} label={family}>
            {GENRE_PRESETS.filter(p => p.family === family).map(p => (
              <option key={p.id} value={p.id}>{p.label} · {p.bpm} bpm</option>
            ))}
          </optgroup>
        ))}
      </select>

      <label>Title</label>
      <input value={title} onChange={e => setTitle(e.target.value)} placeholder="Song title" />
      <label>Style prompt</label>
      <textarea value={prompt} onChange={e => setPrompt(e.target.value)} rows={2}
        placeholder="genre, mood, instruments, production…" />
      <label>
        <input type="checkbox" checked={instrumental} style={{ width: 'auto', marginRight: 6 }}
          onChange={e => { setInstrumental(e.target.checked); if (e.target.checked) setLyrics('') }} />
        Instrumental (no vocals)
      </label>
      {!instrumental && (
        <>
          <label>Lyrics / arrangement script ([section: production directions] + words; works instrumental too)</label>
          <textarea value={lyrics} onChange={e => setLyrics(e.target.value)} rows={6} dir="auto" />
        </>
      )}
      <div className="row">
        <button disabled={!!busy} onClick={insertArrangement}>
          🏗 Insert club structure {presetId ? `(${GENRE_PRESETS.find(p => p.id === presetId)?.family})` : ''}
        </button>
      </div>

      <div className="row">
        <label>Language
          <select value={language} onChange={e => setLanguage(e.target.value)}>
            {LANGS.map(l => <option key={l} value={l}>{l}</option>)}
          </select>
        </label>
        <label>Duration {duration}s
          <input type="range" min={30} max={300} step={10} value={duration}
            onChange={e => setDuration(Number(e.target.value))} />
        </label>
        <label>Takes
          <select value={takes} onChange={e => setTakes(Number(e.target.value))}>
            {[1, 2, 4, 8].map(n => <option key={n} value={n}>{n}</option>)}
          </select>
        </label>
        <label>Quality
          <select value={quality} onChange={e => setQuality(e.target.value as 'draft' | 'pro')}>
            <option value="draft">Draft · turbo, ~fast</option>
            <option value="pro">Pro · sft 50 steps, best</option>
          </select>
        </label>
      </div>

      <button className="primary" disabled={!prompt || !!busy}
        onClick={() => run('gen', async () => {
          await api.createSong({
            title: title || undefined, prompt, lyrics: instrumental ? '' : lyrics, duration,
            vocal_language: language, batch_size: takes, bpm: bpm ?? undefined,
            ...(quality === 'pro'
              ? { model: 'acestep-v15-sft', inference_steps: 50 }
              : { model: 'acestep-v15-turbo' }),
          })
          onCreated()
        })}>
        {busy === 'gen' ? 'Submitting…' : '🎧 Generate (one shot)'}
      </button>

      <button className="primary compose" disabled={!prompt || !!busy}
        title="Builds the track section-by-section (intro→build→drop→break→drop) so it has a real energy arc, then masters it"
        onClick={() => run('compose', async () => {
          const family = GENRE_PRESETS.find(p => p.id === presetId)?.family ?? 'House'
          const plan = COMPOSE_PLANS[family]
          const hook = instrumental ? '' : lyrics
          await api.composeSong({
            title: title || undefined,
            base_prompt: bpm ? `${prompt}, ${bpm} bpm, professional club mix` : `${prompt}, professional club mix`,
            vocal_language: language,
            sections: plan.map(s => ({
              name: s.name,
              prompt: s.prompt,
              duration: Math.min(120, Math.max(5, Math.round(duration * s.weight))),
              lyrics: s.vocal ? hook : '',
            })),
            ...(quality === 'pro'
              ? { model: 'acestep-v15-sft', inference_steps: 50 }
              : { model: 'acestep-v15-turbo' }),
          })
          onCreated()
        })}>
        {busy === 'compose' ? 'Composing…' : `🎼 Compose full arrangement (${GENRE_PRESETS.find(p => p.id === presetId)?.family ?? 'House'} arc)`}
      </button>
    </section>
  )
}

function Library({ tracks, selected, onSelect, onChanged, onError }: {
  tracks: Track[]
  selected: Track | null
  onSelect: (t: Track | null) => void
  onChanged: () => void
  onError: (m: string) => void
}) {
  return (
    <section className="panel">
      <h2>Library</h2>
      {tracks.length === 0 && <p className="muted">No tracks yet — generate your first song.</p>}
      <ul className="tracks">
        {tracks.map(t => (
          <li key={t.id} className={selected?.id === t.id ? 'active' : ''} onClick={() => onSelect(t)}>
            <span className={`dot ${t.status}`} title={t.status} />
            <div>
              <strong>{t.title}</strong>
              <small>{t.task_type} · {t.stage ?? t.status}{t.bpm ? ` · ${t.bpm} bpm` : ''}{t.key_scale ? ` · ${t.key_scale}` : ''}</small>
            </div>
          </li>
        ))}
      </ul>
      {selected && <StudioPanel track={selected} onChanged={onChanged} onError={onError} />}
    </section>
  )
}

function StudioPanel({ track, onChanged, onError }: { track: Track; onChanged: () => void; onError: (m: string) => void }) {
  const [editPrompt, setEditPrompt] = useState('')
  const [start, setStart] = useState(0)
  const [end, setEnd] = useState(10)
  const [strength, setStrength] = useState(0.7)
  const [busy, setBusy] = useState(false)

  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true)
    try {
      await fn()
      onChanged()
    } catch (e) {
      onError(String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="studio">
      <h3>{track.title}</h3>
      {track.status === 'ready' && <audio controls src={api.audioUrl(track.id)} style={{ width: '100%' }} />}
      {track.status === 'failed' && <p className="error">{track.error}</p>}
      {(track.status === 'queued' || track.status === 'generating') && <p className="muted">⏳ {track.stage ?? track.status}…</p>}

      {track.status === 'ready' && (
        <>
          <label>Edit prompt (for repaint / cover / extend)</label>
          <input value={editPrompt} onChange={e => setEditPrompt(e.target.value)}
            placeholder="new style or direction…" />
          <div className="row">
            <button disabled={busy} onClick={() => act(() => api.stems(track.id))}>🎚 Split stems</button>
            <button disabled={busy || !editPrompt} onClick={() => act(() => api.cover(track.id, editPrompt, strength))}>
              🎭 Cover
            </button>
            <button disabled={busy || !editPrompt} onClick={() => act(() => api.extend(track.id, editPrompt))}>
              ➕ Extend
            </button>
          </div>
          <div className="row">
            <label>From <input type="number" min={0} value={start} onChange={e => setStart(Number(e.target.value))} style={{ width: 70 }} />s</label>
            <label>To <input type="number" min={1} value={end} onChange={e => setEnd(Number(e.target.value))} style={{ width: 70 }} />s</label>
            <button disabled={busy || !editPrompt || end <= start}
              onClick={() => act(() => api.repaint(track.id, editPrompt, start, end))}>
              🖌 Repaint section
            </button>
            <label>Cover strength {strength}
              <input type="range" min={0} max={1} step={0.05} value={strength}
                onChange={e => setStrength(Number(e.target.value))} />
            </label>
          </div>
        </>
      )}
      <div className="row">
        <button className="danger" disabled={busy} onClick={() => act(() => api.deleteSong(track.id))}>🗑 Delete</button>
      </div>
      {track.lyrics && <details><summary>Lyrics</summary><pre dir="auto">{track.lyrics}</pre></details>}
    </div>
  )
}
