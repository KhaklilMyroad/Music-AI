"""Dev-time script: builds track2ableton/ableton/templates/live12_templates.xml.gz from
Live 12.4.x sets saved by Ableton Live (MIT-licensed donor files from github.com/aboard-io/stellate,
tools/ableton/donor/). Only structure is kept: tracks are emptied, clips/notes/sample paths cleared.

Usage: python tools/build_templates.py <dir with Ableton2.als Answers.als Answers2.als Generic.als>
"""
import copy
import gzip
import os
import sys
import xml.etree.ElementTree as ET


def load(d, name):
    with gzip.open(os.path.join(d, name)) as f:
        return ET.parse(f).getroot()


def direct_devices(track):
    return list(track.find("DeviceChain/DeviceChain/Devices"))


def clear_children(el):
    for c in list(el):
        el.remove(c)


def scrub_refs(el):
    """Remove references to the donor author's preset/sample files (empty forms observed in Live sets)."""
    for tag in ("LastPresetRef", "SourceContext"):
        for node in el.iter(tag):
            v = node.find("Value")
            if v is not None:
                clear_children(v)
    for bsc in el.iter("BranchSourceContext"):
        clear_children(bsc)


def strip_track(t):
    t = copy.deepcopy(t)
    clear_children(t.find("DeviceChain/DeviceChain/Devices"))
    for v in t.findall(".//ClipSlotList/ClipSlot/ClipSlot/Value"):
        clear_children(v)
    for ev in t.findall(".//ArrangerAutomation/Events"):
        clear_children(ev)
    ae = t.find("AutomationEnvelopes/Envelopes")
    if ae is not None:
        clear_children(ae)
    scrub_refs(t)
    return t


def main(d):
    a2, ans, ans2, gen = (load(d, n) for n in ("Ableton2.als", "Answers.als", "Answers2.als", "Generic.als"))
    out = ET.Element("Track2AbletonTemplates", Source="github.com/aboard-io/stellate tools/ableton/donor (MIT)")
    # --- skeleton
    sk = copy.deepcopy(ans)
    ls = sk.find("LiveSet")
    clear_children(ls.find("Tracks"))
    clear_children(ls.find("MainTrack/DeviceChain/DeviceChain/Devices"))
    gp = ls.find("GroovePool/Grooves")
    if gp is not None:
        clear_children(gp)
    loc = ls.find("Locators/Locators")
    if loc is not None:
        clear_children(loc)
    ET.SubElement(out, "Skeleton").append(sk)
    # --- tracks
    tr = {t.find("Name/EffectiveName").get("Value"): t for t in ans.find("LiveSet/Tracks")}
    midi = next(t for n, t in tr.items() if "Drift" in n and t.tag == "MidiTrack")
    ret = next(t for t in ans.find("LiveSet/Tracks") if t.tag == "ReturnTrack")
    aud = next(t for t in a2.find("LiveSet/Tracks") if t.tag == "AudioTrack")
    for kind, t in (("midi", midi), ("audio", aud), ("return", ret)):
        ET.SubElement(out, "Track", kind=kind).append(strip_track(t))
    # --- clips
    mclip = midi.find(".//ClipSlotList/ClipSlot/ClipSlot/Value/MidiClip")
    aclip = aud.find(".//ClipSlotList/ClipSlot/ClipSlot/Value/AudioClip")
    mclip = copy.deepcopy(mclip)
    clear_children(mclip.find("Notes/KeyTracks"))
    ET.SubElement(out, "Clip", kind="midi").append(mclip)
    ET.SubElement(out, "Clip", kind="audio").append(copy.deepcopy(aclip))
    # --- devices
    want = {}
    pools = [direct_devices(t) for t in list(a2.find("LiveSet/Tracks")) + list(ans2.find("LiveSet/Tracks")) + list(gen.find("LiveSet/Tracks")) + list(ans.find("LiveSet/Tracks"))]
    pools.append(direct_devices(ans.find("LiveSet/MainTrack")))
    for devs in pools:
        for dv in devs:
            if dv.tag in ("Eq8", "Reverb", "AutoFilter2", "StereoGain", "Compressor2", "Echo", "Saturator",
                          "GlueCompressor", "Limiter", "Drift", "Operator", "InstrumentVector", "MultiSampler") and dv.tag not in want:
                want[dv.tag] = dv
    # A Sampler that holds exactly one sample (found inside the donor's Drum Rack pads).
    for ms in a2.iter("MultiSampler"):
        parts_parent = ms.find(".//SampleParts")
        if parts_parent is not None and len(parts_parent) >= 1:
            ms = copy.deepcopy(ms)
            parts_parent = ms.find(".//SampleParts")
            for extra in list(parts_parent)[1:]:
                parts_parent.remove(extra)
            want["MultiSampler"] = ms
            break
    for tag, dv in want.items():
        dv = copy.deepcopy(dv)
        scrub_refs(dv)
        ET.SubElement(out, "Device", tag=tag).append(dv)
    missing = {"Eq8", "Reverb", "Compressor2", "Echo", "GlueCompressor", "Limiter", "Drift", "MultiSampler"} - set(want)
    if missing:
        raise SystemExit(f"missing devices: {missing}")
    dst = os.path.join(os.path.dirname(__file__), "..", "track2ableton", "ableton", "templates", "live12_templates.xml.gz")
    for fr in out.iter("FileRef"):  # writer fills these in; do not ship the donor's local paths
        for tag in ("RelativePath", "Path"):
            if fr.find(tag) is not None:
                fr.find(tag).set("Value", "")
    data = ET.tostring(out, encoding="utf-8")
    with gzip.open(dst, "wb") as f:
        f.write(data)
    print("wrote", os.path.abspath(dst), len(data) // 1024, "KB uncompressed;", sorted(want))


if __name__ == "__main__":
    main(sys.argv[1])
