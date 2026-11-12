"""MCP server: lets an AI assistant (Claude Desktop / Claude Code / any MCP client) drive Ableton Live
through the T2A_Bridge Remote Script, and analyse audio for mixing and mastering.

Run:  track2ableton-mcp            (stdio transport)
"""
from __future__ import annotations

import functools
import json
import os
import subprocess
from typing import Any

try:  # mcp >= 2
    from mcp.server.mcpserver import Image, MCPServer as _Server
    from mcp.server.mcpserver.exceptions import ToolError
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _Server, Image  # type: ignore
    from mcp.server.fastmcp.exceptions import ToolError  # type: ignore

from .. import mixmaster
from ..audio import load
from . import guard, journal as _journal
from .client import LiveClient, LiveError

INSTRUCTIONS = """Controls Ableton Live (via the T2A_Bridge control surface) and analyses audio.
Workflow: call live_session first to see tracks/devices/scenes. Tracks can be referenced by index,
exact or partial name, 'master', or 'A'/'B'.. for returns. Times/lengths are in beats.
For device parameters, call get_device to see exact parameter names and display values, then set
with display_value (e.g. -6 for '-6.0 dB', 1200 for '1.20 kHz'); the bridge solves the raw value
using Live's own display. For mixing/mastering, analyse audio files (get_audio_files lists the
files behind clips; bounce/export the master for master_report) before changing devices.
Always tell the user what you changed (journal lists it). Use undo if a change was wrong. You cannot hear: before
judging a sound, measure it (analyze_audio, clash_report, mix_report, master_report) and say that it is a measurement."""

server = _Server("ableton-live", instructions=INSTRUCTIONS)
_client: LiveClient | None = None


def live() -> LiveClient:
    global _client
    if _client is None:
        _client = LiveClient()
    return _client


def _call(cmd: str, **args) -> Any:
    """Every tool reaches Live through here. The client refuses a change in read-only mode and journals every change."""
    try:
        return live().call(cmd, **{k: v for k, v in args.items() if v is not None})
    except LiveError as exc:  # shown to the model/user verbatim (other exceptions are masked by the SDK)
        raise ToolError(str(exc)) from exc


def _clear_errors(fn):
    """A tool that fails says why. Without this the SDK replaces anything that is not a ToolError with a bare
    'Error executing tool', and an unreadable file or a folder that cannot be created looks like a broken server."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except ToolError:
            raise
        except subprocess.CalledProcessError as exc:
            raise ToolError(f"{fn.__name__}: a helper program failed ({exc.cmd[0] if exc.cmd else '?'}, exit {exc.returncode})") from exc
        except Exception as exc:
            raise ToolError(f"{fn.__name__}: {type(exc).__name__}: {exc}") from exc
    return wrapper


def _file(path: str) -> str:
    if not os.path.isfile(path):
        raise ToolError(f"audio file not found: {path}")
    return path


def _j(x) -> str:
    return json.dumps(x, ensure_ascii=False, indent=1, default=str)


# ============================================================================== session / transport
@server.tool()
@_clear_errors
def live_session() -> str:
    """Overview of the Live Set: tempo, signature, transport, loop, scale, tracks (mixer, devices), returns, master, scenes,
    locators. `read_only` true means the user has switched changes off: look and measure, and say so instead of trying."""
    out = _call("get_session")
    if isinstance(out, dict):
        out["read_only"] = guard.read_only()
    return _j(out)


@server.tool()
@_clear_errors
def transport(action: str) -> str:
    """Transport: action = play | stop | continue | stop_all_clips."""
    return _j(_call("transport", action=action))


@server.tool()
@_clear_errors
def set_song(tempo: float | None = None, time: float | None = None, loop: bool | None = None, loop_start: float | None = None,
             loop_length: float | None = None, metronome: bool | None = None, record_mode: bool | None = None,
             session_record: bool | None = None, numerator: int | None = None, denominator: int | None = None,
             root_note: int | None = None, scale_name: str | None = None, overdub: bool | None = None) -> str:
    """Song settings: tempo (BPM), playhead time (beats), arrangement loop, metronome, arrangement/session record,
    time signature, scale (root_note 0=C..11=B, scale_name e.g. 'Minor'), arrangement overdub."""
    return _j(_call("set_song", tempo=tempo, time=time, loop=loop, loop_start=loop_start, loop_length=loop_length,
                    metronome=metronome, record_mode=record_mode, session_record=session_record, numerator=numerator,
                    denominator=denominator, root_note=root_note, scale_name=scale_name, overdub=overdub))


@server.tool()
@_clear_errors
def undo(redo: bool = False) -> str:
    """Undo the last change in Live (or redo)."""
    return _j(_call("redo" if redo else "undo"))


@server.tool()
@_clear_errors
def locators(action: str = "list", name: str | None = None) -> str:
    """Arrangement locators: action = list | add (at playhead; toggles) | next | prev | jump (by name)."""
    return _j(_call("cue", action=action, name=name))


# ============================================================================== tracks / mixer / routing
@server.tool()
@_clear_errors
def get_track(track: str) -> str:
    """Full detail of one track: mixer, devices (with rack chains), session clips, arrangement clips, routing."""
    return _j(_call("get_track", track=_ref(track)))


@server.tool()
@_clear_errors
def create_track(kind: str = "midi", name: str | None = None, index: int = -1) -> str:
    """Create a track: kind = midi | audio | return. index -1 = end."""
    return _j(_call("create_track", kind=kind, name=name, index=index))


@server.tool()
@_clear_errors
def delete_track(track: str) -> str:
    """Delete a track or return track."""
    return _j(_call("delete_track", track=_ref(track)))


@server.tool()
@_clear_errors
def duplicate_track(track: str) -> str:
    """Duplicate a regular track (with clips and devices)."""
    return _j(_call("duplicate_track", track=_ref(track)))


@server.tool()
@_clear_errors
def set_track(track: str, name: str | None = None, mute: bool | None = None, solo: bool | None = None, arm: bool | None = None,
              volume_db: float | None = None, pan: float | None = None, color_index: int | None = None,
              select: bool | None = None, fold: bool | None = None) -> str:
    """Track/mixer: rename, mute, solo, arm, volume in dB, pan (-1..1), colour (0-69), select, fold group."""
    return _j(_call("set_track", track=_ref(track), name=name, mute=mute, solo=solo, arm=arm, volume_db=volume_db, pan=pan,
                    color_index=color_index, select=select, fold=fold))


@server.tool()
@_clear_errors
def set_send(track: str, send: str, level_db: float) -> str:
    """Send level in dB from a track to a return (send = 'A', 'B', ... or index)."""
    return _j(_call("set_send", track=_ref(track), send=send, level_db=level_db))


@server.tool()
@_clear_errors
def routing(track: str, input_type: str | None = None, input_channel: str | None = None, output_type: str | None = None,
            output_channel: str | None = None, monitoring: str | None = None) -> str:
    """Show (no args) or set track routing. Values are display names as listed (e.g. input_type='Resampling',
    output_type='Sends Only'); monitoring = in | auto | off."""
    if all(v is None for v in (input_type, input_channel, output_type, output_channel, monitoring)):
        return _j(_call("get_routing", track=_ref(track)))
    return _j(_call("set_routing", track=_ref(track), input_type=input_type, input_channel=input_channel,
                    output_type=output_type, output_channel=output_channel, monitoring=monitoring))


# ============================================================================== clips / notes / arrangement
@server.tool()
@_clear_errors
def create_clip(track: str, slot: int, length: float = 4.0, name: str | None = None) -> str:
    """Create an empty MIDI clip in a Session slot (length in beats)."""
    return _j(_call("create_clip", track=_ref(track), slot=slot, length=length, name=name))


@server.tool()
@_clear_errors
def create_audio_clip(track: str, file_path: str, slot: int | None = None, position: float | None = None) -> str:
    """Put an audio file on an audio track: in a Session slot, or in the Arrangement at `position` beats
    (needs a Live version whose API has create_audio_clip)."""
    return _j(_call("create_audio_clip", track=_ref(track), file_path=file_path, slot=slot, position=position))


@server.tool()
@_clear_errors
def create_arrangement_clip(track: str, start: float, length: float) -> str:
    """Create an empty MIDI clip in the Arrangement (if the Live API supports Track.create_midi_clip)."""
    return _j(_call("create_arrangement_midi_clip", track=_ref(track), start=start, length=length))


@server.tool()
@_clear_errors
def clip_action(track: str, slot: int, action: str, target_track: str | None = None, target_slot: int | None = None,
                time: float | None = None) -> str:
    """Session clip actions: fire | stop | duplicate_to (target_track/target_slot) | to_arrangement (time beats) | duplicate_loop."""
    return _j(_call("clip_action", track=_ref(track), slot=slot, action=action,
                    target_track=_ref(target_track) if target_track is not None else None, target_slot=target_slot, time=time))


@server.tool()
@_clear_errors
def delete_clip(track: str, slot: int) -> str:
    """Delete a Session clip."""
    return _j(_call("delete_clip", track=_ref(track), slot=slot))


@server.tool()
@_clear_errors
def set_clip(track: str, slot: int | None = None, arrangement_index: int | None = None, name: str | None = None,
             looping: bool | None = None, loop_start: float | None = None, loop_end: float | None = None,
             start_marker: float | None = None, end_marker: float | None = None, color_index: int | None = None,
             gain: float | None = None, pitch_coarse: int | None = None, pitch_fine: float | None = None,
             warping: bool | None = None, warp_mode: int | None = None, muted: bool | None = None) -> str:
    """Clip properties (Session slot or Arrangement clip index): name, loop, markers, colour, audio gain/pitch/warp, mute."""
    return _j(_call("set_clip", track=_ref(track), slot=slot, arrangement_index=arrangement_index, name=name, looping=looping,
                    loop_start=loop_start, loop_end=loop_end, start_marker=start_marker, end_marker=end_marker,
                    color_index=color_index, gain=gain, pitch_coarse=pitch_coarse, pitch_fine=pitch_fine, warping=warping,
                    warp_mode=warp_mode, muted=muted))


@server.tool()
@_clear_errors
def get_notes(track: str, slot: int | None = None, arrangement_index: int | None = None) -> str:
    """MIDI notes of a clip: [{pitch, start, duration, velocity, mute}], times in beats."""
    return _j(_call("get_notes", track=_ref(track), slot=slot, arrangement_index=arrangement_index))


@server.tool()
@_clear_errors
def write_notes(track: str, notes: list[dict], slot: int | None = None, arrangement_index: int | None = None,
                replace: bool = False) -> str:
    """Add MIDI notes [{pitch (0-127, 60=C3), start (beats), duration (beats), velocity (1-127)}] to a clip.
    replace=True clears the clip first."""
    return _j(_call("add_notes", track=_ref(track), notes=notes, slot=slot, arrangement_index=arrangement_index, replace=replace))


@server.tool()
@_clear_errors
def quantize(track: str, slot: int | None = None, arrangement_index: int | None = None, grid: str = "1/16", amount: float = 1.0) -> str:
    """Quantize a clip: grid 1/4 1/8 1/8T 1/16 1/16T 1/32, amount 0..1."""
    return _j(_call("quantize_clip", track=_ref(track), slot=slot, arrangement_index=arrangement_index, grid=grid, amount=amount))


# ============================================================================== scenes
@server.tool()
@_clear_errors
def scenes(action: str = "list", index: int | None = None, name: str | None = None, tempo: float | None = None,
           color_index: int | None = None) -> str:
    """Scenes: list | create (index) | delete | duplicate | fire | capture (capture & insert playing clips) | set (name/tempo/colour)."""
    return _j(_call("scene", action=action, index=index, name=name, tempo=tempo, color_index=color_index))


# ============================================================================== devices / browser
@server.tool()
@_clear_errors
def get_device(track: str, device: str, chain_path: list[list[int]] | None = None) -> str:
    """All parameters of a device (name, raw value, min/max, display text, value_items). device = index or name.
    chain_path=[[rack_device_index, chain_index], ...] reaches devices inside racks."""
    return _j(_call("get_device", track=_ref(track), device=_ref(device), chain_path=chain_path))


@server.tool()
@_clear_errors
def set_parameter(track: str, device: str, parameter: str, value: float | str | None = None,
                  display_value: float | None = None, normalized: float | None = None,
                  chain_path: list[list[int]] | None = None) -> str:
    """Set one device parameter: raw `value` (or an item name for list parameters), `display_value` in the unit Live
    shows (dB, Hz, ms, %), or `normalized` 0..1."""
    return _j(_call("set_parameter", track=_ref(track), device=_ref(device), parameter=parameter, value=value,
                    display_value=display_value, normalized=normalized, chain_path=chain_path))


@server.tool()
@_clear_errors
def set_parameters(track: str, device: str, values: list[dict], chain_path: list[list[int]] | None = None) -> str:
    """Set several parameters at once: values=[{parameter, value | display_value | normalized}]."""
    return _j(_call("set_parameters", track=_ref(track), device=_ref(device), values=values, chain_path=chain_path))


@server.tool()
@_clear_errors
def sidechain(track: str, device: str = "Compressor", source: str | None = None, channel: str | None = None) -> str:
    """Route a Compressor's sidechain input (Live 12.4+ API), e.g. source='Kick'. No source = list options."""
    return _j(_call("set_sidechain", track=_ref(track), device=_ref(device), source=source, channel=channel))


@server.tool()
@_clear_errors
def device_action(track: str, device: str, action: str) -> str:
    """Device: on | off | delete | select."""
    return _j(_call("device_action", track=_ref(track), device=_ref(device), action=action))


@server.tool()
@_clear_errors
def add_device(track: str, name: str, index: int | None = None) -> str:
    """Add a Live device by name (e.g. 'EQ Eight', 'Compressor', 'Reverb', 'Drift', 'Utility'); uses the native insert API
    when available, else finds it in the browser and loads it onto the track."""
    return _j(_call("insert_device", track=_ref(track), name=name, index=index))


@server.tool()
@_clear_errors
def browse(path: str | None = None) -> str:
    """Browse Live's browser. No path = categories (sounds, drums, instruments, audio_effects, midi_effects, plugins,
    clips, samples, packs, user_library, current_project); then e.g. 'instruments/Drift'."""
    return _j(_call("browse", path=path))


@server.tool()
@_clear_errors
def search_browser(query: str, category: str | None = None, limit: int = 30) -> str:
    """Search loadable browser items (devices, presets, samples, plug-ins) by name."""
    return _j(_call("search_browser", query=query, category=category, limit=limit))


@server.tool()
@_clear_errors
def load_item(track: str, path: str | None = None, query: str | None = None, category: str | None = None) -> str:
    """Load a browser item (by path from browse, or first search hit for query) onto a track."""
    return _j(_call("load_from_browser", track=_ref(track), path=path, query=query, category=category))


# ============================================================================== samples / meters
@server.tool()
@_clear_errors
def get_audio_files(track: str | None = None) -> str:
    """Audio file paths behind audio clips (Session and Arrangement) and Simpler samples, for analysis tools."""
    return _j(_call("get_audio_files", track=_ref(track) if track is not None else None))


@server.tool()
@_clear_errors
def meters(track: str | None = None) -> str:
    """Current output meter levels (0..1) of tracks and master."""
    return _j(_call("get_meters", track=_ref(track) if track is not None else None))


# ============================================================================== analysis (works without Live)
@server.tool()
@_clear_errors
def analyze_audio(file_path: str) -> str:
    """Mix metrics of one audio file: integrated LUFS, peak, true peak, crest, LRA, band energies, spectrum tilt, EQ shape,
    stereo width/correlation, clipping, DC offset, and issues."""
    return _j(mixmaster.measure(_file(file_path)).__dict__)


@server.tool()
@_clear_errors
def waveform(file_path: str, width: int = 1200):
    """Waveform image (peak + RMS per channel; red marks at the top = samples at full scale)."""
    return Image(data=mixmaster.waveform_png(load(_file(file_path)), width=width), format="png")


@server.tool()
@_clear_errors
def spectrogram(file_path: str, width: int = 1200, height: int = 320) -> list:
    """Log-frequency spectrogram image (grid lines at 100 Hz, 1 kHz, 10 kHz) and its axis description."""
    data, axis = mixmaster.spectrogram_png(load(_file(file_path)), width=width, height=height)
    return [Image(data=data, format="png"), _j(axis)]


@server.tool()
@_clear_errors
def mix_report(files: dict[str, str] | None = None) -> str:
    """Analyse several stems/tracks together: loudness order, per-track issues, frequency masking between tracks,
    headroom. files = {track_name: path}; omit to use the audio files of the current Live Set."""
    if not files:
        files = {}
        for f in _call("get_audio_files"):
            if f.get("file_path") and os.path.exists(f["file_path"]):
                files.setdefault(f["track"], f["file_path"])
        if not files:
            raise ValueError("no analysable audio files found in the Set; pass files={name: path}")
    return _j(mixmaster.mix_report(files))


@server.tool()
@_clear_errors
def master_report(file_path: str, target: str = "streaming", reference_path: str | None = None) -> str:
    """Mastering check of a bounced mix: loudness vs target (streaming -14, apple -16, club -9, or a number), true peak,
    crest, stereo; with reference_path also a loudness-matched EQ comparison giving EQ Eight moves."""
    t: str | float = target
    try:
        t = float(target)
    except ValueError:
        pass
    return _j(mixmaster.master_report(_file(file_path), t, _file(reference_path) if reference_path else None))


# ============================================================================== rebuild from track2ableton analysis
@server.tool()
@_clear_errors
def rebuild_in_live(project_dir: str, slot: int = 0) -> str:
    """Take a folder made by `track2ableton <song>` and build it in the open Live Set: tempo, one MIDI track per part
    with the suggested instrument and effects, the transcribed notes in Session slot `slot`, and reference stems."""
    from .rebuild import rebuild
    return _j(rebuild(project_dir, _call, slot))


# ============================================================================== what was changed
@server.tool()
@_clear_errors
def journal(last: int = 30, this_session: bool = True) -> str:
    """The changes sent to Live, newest last: time, command, arguments (long lists shown as a count), and how each ended:
    ok true or false, or null when Live gave no answer in time and the change may still have been made. Reading,
    measuring and playback are not listed. this_session=False shows the last three days from every session. If the
    result carries a `note`, changes are NOT being recorded: say so instead of reporting that nothing changed."""
    return _j(_journal.read(last, this_session))


# ============================================================================== layers, reference, sample packs
@server.tool()
@_clear_errors
def clash_report(files: dict[str, str], bpm: float | None = None) -> str:
    """Which layers get in each other's way, measured in time AND frequency (a kick and an off-beat bass share a band and
    do not clash; an average spectrum cannot tell). files = {name: path} of stems or loops that start at the same moment.
    For every pair: how much of each sits where the other is present, the bands and (with bpm) the bars where it is
    worst, and who owns each third of an octave. Numbers about where energy is, not about taste."""
    from .. import clash
    try:
        return _j(clash.report({k: _file(v) for k, v in files.items()}, bpm))
    except ValueError as exc:
        raise ToolError(str(exc)) from exc


@server.tool()
@_clear_errors
def fit_layers(bed: dict[str, str], candidates: dict[str, str]) -> str:
    """Rank candidate loops or samples by how well each fits into what is already there: the share of the candidate's
    loudness that lands where the bed (the existing layers, {name: path}) leaves room, at matched level. All files must
    start at the same moment and be at the same tempo."""
    from .. import clash
    try:
        return _j(clash.fit({k: _file(v) for k, v in bed.items()}, {k: _file(v) for k, v in candidates.items()}))
    except ValueError as exc:
        raise ToolError(str(exc)) from exc


@server.tool()
@_clear_errors
def match_reference(mix_path: str, reference_path: str) -> str:
    """A starting master chain in Live's own devices, as numbers, that moves a bounced mix towards a reference track:
    EQ Eight bands for tone, a Glue Compressor only if the reference is clearly denser, Limiter gain and ceiling for
    loudness. Apply it on the master with get_device / set_parameters, export, then call verify_reference."""
    return _j(mixmaster.match_chain(_file(mix_path), _file(reference_path)))


@server.tool()
@_clear_errors
def verify_reference(master_path: str, reference_path: str) -> str:
    """After mastering: did the export land near the reference? Loudness within 1 LU, every third of an octave within
    2.5 dB at matched loudness, true peak at or under -1 dBTP. Returns pass/fail per check and what is still off."""
    return _j(mixmaster.verify_match(_file(master_path), _file(reference_path)))


@server.tool()
@_clear_errors
def sample_pack(source: str, out_dir: str | None = None, bars: int = 4, max_loops_per_stem: int = 6) -> str:
    """Make a sample pack from an audio file or a folder of stems: loops cut on the song's real bar lines (exactly `bars`
    bars long, also when the tempo is not round or drifts), named with tempo and key, repeats left out, plus drum
    one-shots, a manifest and a README. Only for music the user owns or has cleared; the manifest says so."""
    from .. import samplepack
    if not os.path.exists(source):
        raise ToolError(f"not found: {source}")
    try:
        m = samplepack.build(source, out_dir, None, bars, max_loops_per_stem, log=lambda *_: None)
    except (ValueError, RuntimeError) as exc:
        raise ToolError(str(exc)) from exc
    return _j(m)


# ============================================================================== vocals and stems
@server.tool()
@_clear_errors
def vocal_score(track: str, lyrics: str, out_dir: str, language: str = "en", slot: int | None = None,
                arrangement_index: int | None = None, fit: str = "strict", phrase_gap: float = 1.0) -> str:
    """Turn a MIDI clip with a vocal melody plus its lyrics into a vocal score: one syllable per note, checked (counts per
    line, range, breath, syllables too fast to sing, word stress against the bar), written to out_dir as vocal.mid (with
    lyric events), vocal.musicxml, vocal.json and VOCAL_REPORT.md (Hebrew). It prepares the score for a singing engine; it
    does not make sound. lyrics: one line per phrase; a lone "-" holds the previous syllable on that note; "sha-lom" sets
    syllables by hand. language: "en" (needs the cmudict package for sure counts), "es", or "typed" (as typed only).
    Give slot (Session) or arrangement_index. fit="end" lets the last syllable of a line carry its extra notes."""
    from ..vocal.live import score_clip
    try:
        return _j(score_clip(_call, _ref(track), lyrics, out_dir, language, slot, arrangement_index, fit, phrase_gap))
    except ValueError as exc:
        raise ToolError(str(exc)) from exc


@server.tool()
@_clear_errors
def split_stems(file_path: str, out_dir: str | None = None, to_live: bool = True, position: float = 0.0, model: str = "htdemucs_6s") -> str:
    """Split an audio file into stems (drums, bass, vocals, other, and guitar/piano with the default model) and, with
    to_live, put each on its own new audio track at `position` (arrangement beats). Uses Demucs when it is installed
    (pip install demucs); otherwise a rough built-in split, and the result says which was used."""
    from . import stems
    if to_live and guard.read_only():
        raise ToolError("Read-only mode is on, so the stems could not be put on tracks. Nothing was split. "
                        "Call again with to_live=false to get the stem files only.")
    res = stems.split(_file(file_path), out_dir, "auto", model)
    if to_live:
        res["tracks"] = stems.to_live(_call, res["stems"], position)
    return _j(res)


def _ref(x):
    if x is None:
        return None
    if isinstance(x, str) and x.strip().lstrip("-").isdigit():
        return int(x)
    return x


def main(argv=None):
    import sys
    args = sys.argv[1:] if argv is None else list(argv)
    if any(a in ("-h", "--help") for a in args):
        print("track2ableton-mcp: MCP server (stdio) that lets an AI assistant work in Ableton Live.\n"
              "It is started by the assistant, not by hand. Register it once:\n"
              "  claude mcp add ableton -- track2ableton-mcp\n"
              "Check the installation with: python -m track2ableton.doctor")
        return 0
    server.run("stdio")
    return 0


if __name__ == "__main__":
    main()
