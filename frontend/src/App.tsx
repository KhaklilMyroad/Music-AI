import { useCallback, useEffect, useState } from 'react'
import { api, SongPlan, Track } from './api'
import { ARRANGEMENTS, COMPOSE_PLANS, GENRE_PRESETS, PRESET_FAMILIES } from './presets'

const LANGS = ['english', 'hebrew', 'spanish', 'french', 'japanese', 'arabic', 'german', 'portuguese']

interface Health {
  engine_reachable: boolean
  mastering_ready?: boolean
  producer_reachable?: boolean
}

function coverHue(id: string): number {
  let h = 0
  for (const c of id) h = (h * 31 + c.charCodeAt(0)) % 360
  return h
}

function fmtDuration(s?: number | null): string {
  if (!s) return ''
  const m = Math.floor(s / 60)
  const sec = Math.round(s % 60)
  return `${m}:${sec.toString().padStart(2, '0')}`
}

export default function App() {
  const [tracks, setTracks] = useState<Track[]>([])
  const [selected, setSelected] = useState<Track | null>(null)
  const [error, setError] = useState('')
  const [health, setHealth] = useState<Health | null>(null)

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
    const hv = setInterval(async () => {
      try {
        const res = await fetch(`${import.meta.env.VITE_API_URL ?? 'http://localhost:8000'}/api/health`)
        setHealth(await res.json())
      } catch {
        setHealth(null)
      }
    }, 8000)
    ;(async () => {
      try {
        const res = await fetch(`${import.meta.env.VITE_API_URL ?? 'http://localhost:8000'}/api/health`)
        setHealth(await res.json())
      } catch { setHealth(null) }
    })()
    return () => { clearInterval(iv); clearInterval(hv) }
  }, [refresh])

  return (
    <div className="shell">
      <header>
        <div className="brand">
          <span className="logo">♪</span>
          <div>
            <h1>Crescendo</h1>
            <span className="tag">AI Music Studio</span>
          </div>
        </div>
        <div className="status-pills">
          <span className={`pill ${health?.engine_reachable ? 'on' : 'off'}`}>
            ● Engine {health?.engine_reachable ? 'online' : 'offline'}
          </span>
          <span className={`pill ${health?.mastering_ready ? 'on' : 'off'}`}>
            ● Mastering {health?.mastering_ready ? 'ready' : 'off'}
          </span>
          <span className={`pill ${health?.producer_reachable ? 'on' : 'off'}`}>
            ● AI Producer {health?.producer_reachable ? 'ready' : 'off'}
          </span>
        </div>
      </header>
      {error && (
        <div className="toast" onClick={() => setError('')}>
          <strong>Something went wrong</strong>
          <span>{error}</span>
          <em>click to dismiss</em>
        </div>
      )}
      <main>
        <CreatePanel onCreated={refresh} onError={setError} />
        <Library tracks={tracks} selected={selected} onSelect={setSelected} onChanged={refresh} onError={setError} />
      </main>
      <footer>Crescendo · unlimited AI music on your own GPU · you own every note</footer>
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

  const family = GENRE_PRESETS.find(p => p.id === presetId)?.family ?? 'House'

  const insertArrangement = () => {
    setInstrumental(false)
    setLyrics(current => (current.trim() ? `${ARRANGEMENTS[family]}\n\n${current}` : ARRANGEMENTS[family]))
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

  const qualityBody = quality === 'pro'
    ? { model: 'acestep-v15-sft', inference_steps: 50 }
    : { model: 'acestep-v15-turbo' }

  return (
    <section className="panel">
      <h2>Create</h2>

      <div className="field-group">
        <label>Your idea (any language)</label>
        <textarea value={idea} onChange={e => setIdea(e.target.value)} rows={2}
          placeholder="e.g. שיר אפרו-האוס עם הוק שחוזר / a melodic techno journey about the desert" />
        <div className="row">
          <button disabled={!idea || !!busy} onClick={() => run('plan', async () => applyPlan(await api.plan(idea, language)))}>
            {busy === 'plan' ? <span className="spin" /> : '🪄'} AI Producer: plan full song
          </button>
          <button disabled={!idea || !!busy} onClick={() => run('enhance', async () => setPrompt((await api.enhance(idea)).prompt))}>
            {busy === 'enhance' ? <span className="spin" /> : '✨'} Enhance prompt
          </button>
          <button disabled={!idea || !!busy} onClick={() => run('lyrics', async () => setLyrics((await api.lyrics(idea, language, prompt)).lyrics))}>
            {busy === 'lyrics' ? <span className="spin" /> : '📝'} Write lyrics
          </button>
        </div>
      </div>

      <div className="field-group">
        <label>Genre preset</label>
        <select value={presetId} onChange={e => applyPreset(e.target.value)}>
          <option value="">— pick a genre (fills prompt + BPM) —</option>
          {PRESET_FAMILIES.map(f => (
            <optgroup key={f} label={f}>
              {GENRE_PRESETS.filter(p => p.family === f).map(p => (
                <option key={p.id} value={p.id}>{p.label} · {p.bpm} bpm</option>
              ))}
            </optgroup>
          ))}
        </select>

        <label>Title</label>
        <input value={title} onChange={e => setTitle(e.target.value)} placeholder="Track title" />

        <label>Style prompt</label>
        <textarea value={prompt} onChange={e => setPrompt(e.target.value)} rows={2}
          placeholder="genre, mood, instruments, production…" />

        <label className="check">
          <input type="checkbox" checked={instrumental}
            onChange={e => { setInstrumental(e.target.checked); if (e.target.checked) setLyrics('') }} />
          Instrumental (no vocals)
        </label>
        {!instrumental && (
          <>
            <label>Lyrics / arrangement script</label>
            <textarea value={lyrics} onChange={e => setLyrics(e.target.value)} rows={6} dir="auto"
              placeholder="[verse] … [chorus] … or use the buttons above" />
          </>
        )}
        <div className="row">
          <button disabled={!!busy} onClick={insertArrangement}>🏗 Insert club structure ({family})</button>
        </div>
      </div>

      <div className="field-group">
        <div className="row controls">
          <label>Language
            <select value={language} onChange={e => setLanguage(e.target.value)}>
              {LANGS.map(l => <option key={l} value={l}>{l}</option>)}
            </select>
          </label>
          <label>Duration · {fmtDuration(duration)}
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
              <option value="draft">Draft · fast sketch</option>
              <option value="pro">Pro · full quality</option>
            </select>
          </label>
        </div>
      </div>

      <button className="primary" disabled={!prompt || !!busy}
        onClick={() => run('gen', async () => {
          await api.createSong({
            title: title || undefined, prompt, lyrics: instrumental ? '' : lyrics, duration,
            vocal_language: language, batch_size: takes, bpm: bpm ?? undefined, ...qualityBody,
          })
          onCreated()
        })}>
        {busy === 'gen' ? 'Submitting…' : '🎧 Generate · one shot'}
      </button>

      <button className="primary compose" disabled={!prompt || !!busy}
        title="Builds the track section-by-section with a real energy arc, then masters it"
        onClick={() => run('compose', async () => {
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
              gain: s.gain,
            })),
            ...qualityBody,
          })
          onCreated()
        })}>
        {busy === 'compose' ? 'Composing…' : `🎼 Compose full arrangement · ${family} arc`}
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
      <h2>Library <span className="count">{tracks.length}</span></h2>
      {tracks.length === 0 && (
        <div className="empty">
          <span>🎵</span>
          <p>No tracks yet.<br />Pick a genre, hit Compose, and your first track lands here.</p>
        </div>
      )}
      <ul className="tracks">
        {tracks.map(t => (
          <li key={t.id} className={selected?.id === t.id ? 'active' : ''} onClick={() => onSelect(t)}>
            <div className="cover" style={{
              background: `linear-gradient(135deg, hsl(${coverHue(t.id)} 70% 45%), hsl(${(coverHue(t.id) + 60) % 360} 70% 30%))`,
            }}>
              {t.status === 'generating' || t.status === 'queued' ? <span className="spin light" /> : '♪'}
            </div>
            <div className="meta">
              <strong>{t.title}</strong>
              <small>
                {t.stage ?? t.status}
                {t.bpm ? ` · ${t.bpm} bpm` : ''}
                {t.key_scale ? ` · ${t.key_scale}` : ''}
                {t.duration ? ` · ${fmtDuration(t.duration)}` : ''}
              </small>
              {(t.status === 'generating' || t.status === 'queued') && <div className="bar"><div /></div>}
            </div>
            <span className={`dot ${t.status}`} title={t.status} />
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
      <div className="studio-head">
        <h3>{track.title}</h3>
        {track.status === 'ready' && (
          <a className="download" href={`${api.audioUrl(track.id)}?download=1`}>⬇ Download</a>
        )}
      </div>
      {track.status === 'ready' && <audio controls src={api.audioUrl(track.id)} />}
      {track.status === 'failed' && <p className="fail">{track.error}</p>}
      {(track.status === 'queued' || track.status === 'generating') && (
        <p className="muted working"><span className="spin" /> {track.stage ?? track.status}…</p>
      )}

      {track.status === 'ready' && (
        <>
          <label>Edit prompt (repaint / cover / extend)</label>
          <input value={editPrompt} onChange={e => setEditPrompt(e.target.value)}
            placeholder="new style or direction…" />
          <div className="row">
            <button disabled={busy} onClick={() => act(() => api.stems(track.id))}>🎚 Split stems</button>
            <button disabled={busy || !editPrompt} onClick={() => act(() => api.cover(track.id, editPrompt, strength))}>🎭 Cover</button>
            <button disabled={busy || !editPrompt} onClick={() => act(() => api.extend(track.id, editPrompt))}>➕ Extend</button>
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
      {track.lyrics && <details><summary>Lyrics / arrangement</summary><pre dir="auto">{track.lyrics}</pre></details>}
    </div>
  )
}
