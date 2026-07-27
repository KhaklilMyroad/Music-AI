import { useCallback, useEffect, useRef, useState } from 'react'
import { api, Track } from './api'

/* Crescendo Studio: DAW-style editor. Load any ready track (or upload your
   own audio), see the real waveform, drag-select a region Ableton-style, and
   run engine operations on it: repaint the selection, extend, cover, stems.
   Every operation lands in the version history on the right. */

const BUCKETS = 1200

function fmt(s: number): string {
  if (!Number.isFinite(s)) return '0:00'
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
  return `${m}:${sec.toString().padStart(2, '0')}`
}

interface Peaks {
  min: Float32Array
  max: Float32Array
  duration: number
}

async function loadPeaks(url: string): Promise<Peaks> {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`audio fetch failed: ${res.status}`)
  const buf = await res.arrayBuffer()
  const ctx = new AudioContext()
  try {
    const audio = await ctx.decodeAudioData(buf)
    const data = audio.getChannelData(0)
    const min = new Float32Array(BUCKETS)
    const max = new Float32Array(BUCKETS)
    const per = Math.max(1, Math.floor(data.length / BUCKETS))
    for (let i = 0; i < BUCKETS; i++) {
      let lo = 1, hi = -1
      const base = i * per
      for (let j = 0; j < per && base + j < data.length; j += 16) {
        const v = data[base + j]
        if (v < lo) lo = v
        if (v > hi) hi = v
      }
      min[i] = lo
      max[i] = hi
    }
    return { min, max, duration: audio.duration }
  } finally {
    ctx.close()
  }
}

function Waveform({ peaks, selection, playhead, onSelect }: {
  peaks: Peaks | null
  selection: [number, number] | null
  playhead: number
  onSelect: (range: [number, number] | null) => void
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const dragRef = useRef<number | null>(null)

  const draw = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')!
    const { width: w, height: h } = canvas
    ctx.clearRect(0, 0, w, h)
    ctx.fillStyle = '#0c0f15'
    ctx.fillRect(0, 0, w, h)

    if (peaks) {
      const mid = h / 2
      for (let i = 0; i < BUCKETS; i++) {
        const x = (i / BUCKETS) * w
        const inSel = selection && peaks.duration > 0 &&
          (i / BUCKETS) * peaks.duration >= selection[0] &&
          (i / BUCKETS) * peaks.duration <= selection[1]
        ctx.fillStyle = inSel ? '#35d0ba' : '#7c5cff'
        const y1 = mid + peaks.min[i] * mid * 0.92
        const y2 = mid + peaks.max[i] * mid * 0.92
        ctx.fillRect(x, Math.min(y1, y2), Math.max(1, w / BUCKETS - 0.5), Math.max(1, Math.abs(y2 - y1)))
      }
      if (selection) {
        const x1 = (selection[0] / peaks.duration) * w
        const x2 = (selection[1] / peaks.duration) * w
        ctx.fillStyle = '#35d0ba22'
        ctx.fillRect(x1, 0, x2 - x1, h)
        ctx.fillStyle = '#35d0ba'
        ctx.fillRect(x1, 0, 1.5, h)
        ctx.fillRect(x2, 0, 1.5, h)
      }
      if (playhead > 0) {
        const x = (playhead / peaks.duration) * w
        ctx.fillStyle = '#ffffffcc'
        ctx.fillRect(x, 0, 1.5, h)
      }
    } else {
      ctx.fillStyle = '#8b93a5'
      ctx.font = '13px Inter, sans-serif'
      ctx.textAlign = 'center'
      ctx.fillText('Load a track or upload audio to see its waveform', w / 2, h / 2)
    }
  }, [peaks, selection, playhead])

  useEffect(() => { draw() }, [draw])

  const toTime = (e: React.MouseEvent) => {
    const rect = canvasRef.current!.getBoundingClientRect()
    const frac = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width))
    return frac * (peaks?.duration ?? 0)
  }

  return (
    <canvas
      ref={canvasRef} width={1200} height={150} className="waveform"
      onMouseDown={e => { if (!peaks) return; dragRef.current = toTime(e); onSelect(null) }}
      onMouseMove={e => {
        if (dragRef.current == null || !peaks) return
        const t = toTime(e)
        onSelect([Math.min(dragRef.current, t), Math.max(dragRef.current, t)])
      }}
      onMouseUp={e => {
        if (dragRef.current == null || !peaks) return
        const t = toTime(e)
        if (Math.abs(t - dragRef.current) < 0.3) onSelect(null)
        dragRef.current = null
      }}
      onMouseLeave={() => { dragRef.current = null }}
    />
  )
}

export function StudioView({ tracks, initialId, onError, onChanged, onOpenTrack }: {
  tracks: Track[]
  initialId?: string
  onError: (m: string) => void
  onChanged: () => void
  onOpenTrack: (id: string) => void
}) {
  const [sourceId, setSourceId] = useState(initialId ?? '')
  const [peaks, setPeaks] = useState<Peaks | null>(null)
  const [loading, setLoading] = useState(false)
  const [selection, setSelection] = useState<[number, number] | null>(null)
  const [prompt, setPrompt] = useState('')
  const [strength, setStrength] = useState(0.7)
  const [extendBy, setExtendBy] = useState(30)
  const [busy, setBusy] = useState(false)
  const [playhead, setPlayhead] = useState(0)
  const audioRef = useRef<HTMLAudioElement>(null)

  const ready = tracks.filter(t => t.status === 'ready')
  const source = tracks.find(t => t.id === sourceId) ?? null
  const children = source ? tracks.filter(t => t.parent_id === source.id) : []

  useEffect(() => {
    setPeaks(null); setSelection(null); setPlayhead(0)
    if (!sourceId) return
    setLoading(true)
    loadPeaks(api.audioUrl(sourceId))
      .then(setPeaks)
      .catch(e => onError(`waveform: ${e}`))
      .finally(() => setLoading(false))
    if (audioRef.current) {
      audioRef.current.src = api.audioUrl(sourceId)
    }
  }, [sourceId])

  const act = async (label: string, fn: () => Promise<unknown>) => {
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

  const upload = async (file: File) => {
    setBusy(true)
    try {
      const t = await api.uploadSong(file)
      onChanged()
      setSourceId(t.id)
    } catch (e) {
      onError(String(e))
    } finally {
      setBusy(false)
    }
  }

  const playSelection = () => {
    const a = audioRef.current
    if (!a) return
    a.currentTime = selection ? selection[0] : 0
    a.play().catch(() => undefined)
  }

  return (
    <div className="view">
      <h2 className="view-title">Studio</h2>

      <div className="studio-toolbar">
        <select value={sourceId} onChange={e => setSourceId(e.target.value)}>
          <option value="">— load a track from your library —</option>
          {ready.map(t => <option key={t.id} value={t.id}>{t.title}</option>)}
        </select>
        <label className="upload-btn">
          ⬆ Upload audio
          <input type="file" accept=".mp3,.wav,.flac,.ogg,.m4a,.aac,.opus" hidden
            onChange={e => { const f = e.target.files?.[0]; if (f) upload(f); e.target.value = '' }} />
        </label>
      </div>

      <div className="wave-wrap">
        {loading && <div className="wave-loading"><span className="spin" /> decoding audio…</div>}
        <Waveform peaks={peaks} selection={selection} playhead={playhead} onSelect={setSelection} />
        <div className="wave-footer">
          <audio ref={audioRef} onTimeUpdate={e => setPlayhead(e.currentTarget.currentTime)} />
          <button disabled={!peaks} onClick={playSelection}>▶ {selection ? 'Play selection' : 'Play'}</button>
          <button disabled={!peaks} onClick={() => audioRef.current?.pause()}>⏸</button>
          <span className="muted">
            {selection
              ? `Selection: ${fmt(selection[0])} – ${fmt(selection[1])} (${fmt(selection[1] - selection[0])})`
              : peaks ? `Length: ${fmt(peaks.duration)} · drag on the waveform to select a region` : ''}
          </span>
        </div>
      </div>

      {source && (
        <div className="field-group">
          <label>Direction prompt (what should the operation sound like)</label>
          <input value={prompt} onChange={e => setPrompt(e.target.value)}
            placeholder="e.g. heavier drums, darker atmosphere, add a piano breakdown…" />
          <div className="row">
            <button className="primary inline" disabled={busy || !prompt || !selection}
              title="Regenerate only the selected region"
              onClick={() => act('repaint', () => api.repaint(source.id, prompt, Math.floor(selection![0]), Math.ceil(selection![1])))}>
              🖌 Repaint selection
            </button>
            <button disabled={busy || !prompt}
              onClick={() => act('extend', () => api.extend(source.id, prompt, (peaks?.duration ?? 0) + extendBy))}>
              ➕ Extend by
            </button>
            <label style={{ maxWidth: 90 }}>seconds
              <input type="number" min={10} max={120} value={extendBy}
                onChange={e => setExtendBy(Number(e.target.value))} />
            </label>
            <button disabled={busy || !prompt}
              onClick={() => act('cover', () => api.cover(source.id, prompt, strength))}>
              🎭 Cover
            </button>
            <label style={{ maxWidth: 160 }}>strength {strength}
              <input type="range" min={0} max={1} step={0.05} value={strength}
                onChange={e => setStrength(Number(e.target.value))} />
            </label>
            <button disabled={busy} onClick={() => act('stems', () => api.stems(source.id))}>
              🎚 Split stems
            </button>
          </div>
          <p className="muted" style={{ fontSize: 12 }}>
            Every operation creates a new version in the history — the original is never touched.
          </p>
        </div>
      )}

      {source && (
        <div className="field-group">
          <h3>Version history</h3>
          {children.length === 0 && <p className="muted">No versions yet — run an operation above.</p>}
          {children.map(c => (
            <div className="rel-row" key={c.id}>
              <div style={{ flex: 1, cursor: 'pointer' }} onClick={() => onOpenTrack(c.id)}>
                <strong>{c.title}</strong>
                <small className="muted"> · {c.stage ?? c.status}</small>
              </div>
              {c.status === 'ready' && (
                <button onClick={() => setSourceId(c.id)}>Open in editor</button>
              )}
              {(c.status === 'generating' || c.status === 'queued') && <span className="spin" />}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
