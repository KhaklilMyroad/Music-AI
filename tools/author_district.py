#!/usr/bin/env python3
"""Author a playable district from a reviewable ASCII layout.

Usage: python3 -I tools/author_district.py <district_id> > shared-data/districts/<district_id>.json

Why ASCII: a level designer, a historian and the project owner can all read and
argue about the layout in a text diff. The emitted JSON is what both the Godot
project and the web prototype build geometry, navigation, audio zones and
patrol routes from, so the layout and the shipped district cannot drift apart.
"""
import json, sys, math

CELL = 8.0  # metres per layout cell

# ---------------------------------------------------------------- templates --
BUILDING_TEMPLATES = {
    "farmhouse": {
        "label_key": "bld.farmhouse", "footprint": [12.0, 9.0], "wall_h": 5.6,
        "wall_thickness": 0.45, "roof": {"type": "gable", "pitch": 42, "overhang": 0.5, "material": "mat_slate"},
        "material": "mat_limestone_render", "floors": 2,
        "openings": [
            {"kind": "door",   "face": "south", "u": 0.5,  "w": 1.05, "h": 2.05, "sill": 0.0, "hinge": "left",  "swing": "inward", "state": "closed"},
            {"kind": "window", "face": "south", "u": 0.17, "w": 0.95, "h": 1.35, "sill": 1.0, "recess": 0.28, "shutters": True},
            {"kind": "window", "face": "south", "u": 0.83, "w": 0.95, "h": 1.35, "sill": 1.0, "recess": 0.28, "shutters": True},
            {"kind": "window", "face": "north", "u": 0.3,  "w": 0.85, "h": 1.2,  "sill": 1.05, "recess": 0.28},
            {"kind": "window", "face": "east",  "u": 0.5,  "w": 0.8,  "h": 1.1,  "sill": 1.1, "recess": 0.26},
            {"kind": "window", "face": "south", "u": 0.5,  "w": 0.8,  "h": 1.0,  "sill": 3.6, "recess": 0.24, "floor": 1},
        ],
        "interior": {
            "rooms": [
                {"id": "kitchen",  "label_key": "room.kitchen",  "floor": 0, "rect": [0.0, 0.0, 7.0, 9.0], "surface": "surf_stone_floor", "ambience": "amb_interior_kitchen",
                 "props": [{"t": "prop_hearth", "p": [0.9, 4.5], "rot": 90, "light": {"kind": "fire", "warm": 1900, "intensity": 2.4, "radius": 5.0}},
                           {"t": "prop_table_long", "p": [3.6, 4.2], "rot": 0},
                           {"t": "prop_bench", "p": [3.6, 2.9], "rot": 0}, {"t": "prop_bench", "p": [3.6, 5.5], "rot": 0},
                           {"t": "prop_dresser", "p": [6.3, 7.4], "rot": 270},
                           {"t": "prop_pail", "p": [1.4, 7.9], "rot": 15}, {"t": "prop_sack_flour", "p": [6.1, 1.3], "rot": 40}]},
                {"id": "backroom","label_key": "room.backroom", "floor": 0, "rect": [7.0, 0.0, 12.0, 9.0], "surface": "surf_board_floor", "ambience": "amb_interior_quiet",
                 "props": [{"t": "prop_bed_iron", "p": [9.4, 2.0], "rot": 0}, {"t": "prop_chair", "p": [11.1, 5.6], "rot": 250},
                           {"t": "prop_crate", "p": [10.8, 8.0], "rot": 10}]},
                {"id": "upper",   "label_key": "room.upper_room", "floor": 1, "rect": [0.0, 0.0, 12.0, 9.0], "surface": "surf_board_floor", "ambience": "amb_interior_attic",
                 "props": [{"t": "prop_bed_iron", "p": [2.1, 1.8], "rot": 0}, {"t": "prop_trunk", "p": [8.9, 7.6], "rot": 70},
                           {"t": "prop_washstand", "p": [10.9, 2.2], "rot": 270}]},
            ],
            "stairs": [{"from_floor": 0, "to_floor": 1, "rect": [6.2, 7.2, 7.6, 9.0], "steps": 15, "rise": 0.19, "run": 0.24, "surface": "surf_board_floor"}],
            "internal_doors": [{"between": ["kitchen", "backroom"], "p": [7.0, 3.1], "w": 0.95, "h": 2.0, "state": "open"}],
        },
    },
    "barn": {
        "label_key": "bld.barn", "footprint": [16.0, 11.0], "wall_h": 6.4,
        "wall_thickness": 0.5, "roof": {"type": "gable", "pitch": 34, "overhang": 0.7, "material": "mat_clay_tile"},
        "material": "mat_rubble_stone", "floors": 1,
        "openings": [
            {"kind": "door", "face": "south", "u": 0.45, "w": 3.2, "h": 3.6, "sill": 0.0, "hinge": "double", "swing": "outward", "state": "ajar", "ajar_deg": 22},
            {"kind": "door", "face": "north", "u": 0.8,  "w": 1.0, "h": 2.0, "sill": 0.0, "hinge": "right", "swing": "inward", "state": "closed"},
            {"kind": "opening", "face": "east", "u": 0.5, "w": 1.4, "h": 1.4, "sill": 4.3},
        ],
        "interior": {
            "rooms": [
                {"id": "floor", "label_key": "room.threshing_floor", "floor": 0, "rect": [0.0, 0.0, 16.0, 11.0], "surface": "surf_packed_earth", "ambience": "amb_interior_barn",
                 "props": [{"t": "prop_hay_pile", "p": [13.2, 2.4], "rot": 0}, {"t": "prop_hay_pile", "p": [14.1, 8.2], "rot": 30},
                           {"t": "prop_cart", "p": [4.4, 7.9], "rot": 12}, {"t": "prop_plough", "p": [2.2, 2.3], "rot": 200},
                           {"t": "prop_barrel", "p": [9.1, 1.2], "rot": 0}, {"t": "prop_barrel", "p": [10.0, 1.3], "rot": 0},
                           {"t": "prop_toolrack", "p": [0.6, 5.5], "rot": 90},
                           {"t": "prop_lantern", "p": [8.0, 5.5], "rot": 0, "light": {"kind": "lamp", "warm": 2300, "intensity": 1.1, "radius": 6.5}}]},
            ],
            "stairs": [],
            "internal_doors": [],
            "mezzanine": {"rect": [10.5, 0.0, 16.0, 11.0], "height": 3.4, "access": "prop_ladder", "ladder_p": [10.6, 5.5], "surface": "surf_board_floor"},
        },
    },
    "shed": {
        "label_key": "bld.shed", "footprint": [5.0, 4.0], "wall_h": 2.9,
        "wall_thickness": 0.3, "roof": {"type": "shed", "pitch": 18, "overhang": 0.35, "material": "mat_corrugated"},
        "material": "mat_plank_timber", "floors": 1,
        "openings": [{"kind": "door", "face": "south", "u": 0.5, "w": 0.9, "h": 1.95, "sill": 0.0, "hinge": "left", "swing": "outward", "state": "closed"}],
        "interior": {"rooms": [{"id": "store", "label_key": "room.store", "floor": 0, "rect": [0.0, 0.0, 5.0, 4.0], "surface": "surf_packed_earth", "ambience": "amb_interior_quiet",
                                "props": [{"t": "prop_shelf", "p": [0.5, 2.0], "rot": 90}, {"t": "prop_crate", "p": [3.9, 1.0], "rot": 20}, {"t": "prop_jerrycan", "p": [4.1, 3.2], "rot": 0}]}],
                     "stairs": [], "internal_doors": []},
    },
    "chapel": {
        "label_key": "bld.chapel", "footprint": [9.0, 14.0], "wall_h": 7.2,
        "wall_thickness": 0.6, "roof": {"type": "gable", "pitch": 46, "overhang": 0.4, "material": "mat_slate"},
        "material": "mat_limestone_block", "floors": 1,
        "openings": [
            {"kind": "door", "face": "south", "u": 0.5, "w": 1.3, "h": 2.6, "sill": 0.0, "hinge": "double", "swing": "inward", "state": "closed", "arch": True},
            {"kind": "window", "face": "east", "u": 0.3, "w": 0.7, "h": 2.2, "sill": 2.2, "recess": 0.45, "arch": True, "glass": "mat_leaded_glass"},
            {"kind": "window", "face": "east", "u": 0.7, "w": 0.7, "h": 2.2, "sill": 2.2, "recess": 0.45, "arch": True, "glass": "mat_leaded_glass"},
            {"kind": "window", "face": "west", "u": 0.5, "w": 0.7, "h": 2.2, "sill": 2.2, "recess": 0.45, "arch": True, "glass": "mat_leaded_glass"},
        ],
        "interior": {"rooms": [{"id": "nave", "label_key": "room.nave", "floor": 0, "rect": [0.0, 0.0, 9.0, 14.0], "surface": "surf_stone_floor", "ambience": "amb_interior_chapel",
                                "props": [{"t": "prop_pew", "p": [4.5, 4.0], "rot": 0}, {"t": "prop_pew", "p": [4.5, 5.6], "rot": 0}, {"t": "prop_pew", "p": [4.5, 7.2], "rot": 0},
                                          {"t": "prop_candle_stand", "p": [4.5, 11.8], "rot": 0, "light": {"kind": "candle", "warm": 1850, "intensity": 0.6, "radius": 3.2}}]}],
                     "stairs": [], "internal_doors": []},
    },
}

# ------------------------------------------------------------------ layouts --
DISTRICTS = {
  "district_normandy_bocage": {
    "label_key": "district.normandy_bocage",
    "location": "loc_normandy",
    "theater": "theater_western_europe",
    "history_refs": ["hist_1944_normandy_landings"],
    "season": "early_summer",
    "latitude": 49.2,
    "default_date": "1944-06-07",
    "states": ["occupied_1944", "contested_1944", "liberated_1944"],
    "default_state": "occupied_1944",
    "ambience_default": "amb_bocage_day",
    "weather_profiles": ["clear_morning", "overcast", "light_rain", "night_clear"],
    "default_weather": "clear_morning",
    # 16 x 14 cells of 8 m = 128 x 112 m
    "layout": [
        "HHHHHHHHHHHHHHHH",
        "H..o o..H,,,,..H",
        "H.oFo...H,SS,..H",
        "H..o,,,,,,,,,..H",
        "HHHH,HHHHH,HHH.H",
        "H...,...j.,....H",
        "H.BB,....,..oo.H",
        "H.BB,RRRRc RR,.H",
        "H...,....,...,.H",
        "HHH.,HHH.,HHH,.H",
        "H..x,..C.,....#H",
        "H...,...., ...##H"[:16],
        "H,,,,,,,,,,,,,,H",
        "HHHHHHHHHHHHHHHH",
    ],
    "pois": [
        {"id": "poi_field_telephone_junction", "label_key": "poi.field_telephone_junction", "glyph": "j",
         "kind": "interactable", "interaction": "wire_cut", "stages": 3, "stage_seconds": 1.4, "tool": "tool_wire_cutters",
         "noise_radius_m": 6.0, "persists": True, "objective": "obj_cut_field_line"},
        {"id": "poi_gun_position", "label_key": "poi.gun_position", "glyph": "#",
         "kind": "observation_target", "interaction": "observe", "required_seconds": 3.0, "required_distance_m": 45.0,
         "requires_line_of_sight": True, "persists": True, "objective": "obj_mark_battery"},
        {"id": "poi_safe_barn", "label_key": "poi.safe_barn", "glyph": "B",
         "kind": "zone", "interaction": "reach", "radius_m": 6.0, "persists": True, "objective": "obj_reach_barn",
         "is_extraction": True},
        {"id": "poi_arms_cache", "label_key": "poi.arms_cache", "glyph": "x",
         "kind": "container", "interaction": "open", "contents": [{"item": "amm_9x19", "count": 64}, {"item": "tool_medical_kit", "count": 1}],
         "hidden_until_intel": 1, "persists": True, "objective": "obj_recover_cache"},
        {"id": "poi_crossroad", "label_key": "poi.crossroad", "glyph": "c",
         "kind": "zone", "interaction": "hold", "radius_m": 10.0, "persists": False, "objective": "obj_hold_crossroad"},
        {"id": "poi_chapel", "label_key": "poi.chapel", "glyph": "C",
         "kind": "landmark", "interaction": "enter", "persists": True, "objective": None},
    ],
    "glyph_buildings": {"F": "farmhouse", "B": "barn", "S": "shed", "C": "chapel"},
    "patrols": [
        {"id": "pat_road_pair", "faction": "axis_army", "count": 2, "weapon": "wpn_bolt_rifle_de", "alertness": 0.35,
         "route": [[5, 7], [9, 7], [9, 10], [5, 10]], "pause_s": [4.0, 9.0], "gait": "walk",
         "states": {"patrol": {}, "investigate": {"sprint_to_last_known": True, "search_seconds": 22.0, "search_radius_m": 14.0},
                    "combat": {"use_cover": True, "reposition_s": [3.5, 7.0], "suppress": True},
                    "lost_contact": {"hold_seconds": 18.0, "then": "sweep"}, "recover": {"return_to_route": True, "decay_seconds": 45.0}}},
        {"id": "pat_battery_static", "faction": "axis_army", "count": 2, "weapon": "wpn_bolt_rifle_de", "alertness": 0.5,
         "route": [[14, 10], [14, 11]], "pause_s": [10.0, 20.0], "gait": "walk",
         "states": {"patrol": {}, "investigate": {"sprint_to_last_known": False, "search_seconds": 15.0, "search_radius_m": 9.0},
                    "combat": {"use_cover": True, "reposition_s": [5.0, 9.0], "suppress": True},
                    "lost_contact": {"hold_seconds": 25.0, "then": "return"}, "recover": {"return_to_route": True, "decay_seconds": 60.0}}},
        {"id": "pat_farm_sentry", "faction": "axis_army", "count": 1, "weapon": "wpn_pistol_civ", "alertness": 0.2,
         "route": [[3, 3], [8, 3], [8, 5], [3, 5]], "pause_s": [6.0, 14.0], "gait": "walk",
         "states": {"patrol": {}, "investigate": {"sprint_to_last_known": True, "search_seconds": 20.0, "search_radius_m": 12.0},
                    "combat": {"use_cover": True, "reposition_s": [3.0, 6.0], "suppress": False},
                    "lost_contact": {"hold_seconds": 14.0, "then": "sweep"}, "recover": {"return_to_route": True, "decay_seconds": 40.0}}},
    ],
    "civilians": [
        {"id": "civ_farm_woman", "label_key": "npc.farm_woman", "is_fictional": True, "home": [3, 2], "schedule": [
            {"from_h": 5.5, "to_h": 8.0, "at": [3, 3], "activity": "yard_work"},
            {"from_h": 8.0, "to_h": 12.0, "at": [2, 6], "activity": "barn_work"},
            {"from_h": 12.0, "to_h": 14.0, "at": [3, 2], "activity": "indoors"},
            {"from_h": 14.0, "to_h": 20.5, "at": [4, 3], "activity": "field_work"},
            {"from_h": 20.5, "to_h": 5.5, "at": [3, 2], "activity": "indoors"}],
         "dialogue_mode": "subtitled", "language": "fr", "priority": "self_preservation",
         "narrative_flags": ["knows_cache_location"], "persists_when_unloaded": True},
        {"id": "civ_boy_runner", "label_key": "npc.boy_runner", "is_fictional": True, "home": [2, 2], "schedule": [
            {"from_h": 6.0, "to_h": 11.0, "at": [5, 5], "activity": "errand"},
            {"from_h": 11.0, "to_h": 18.0, "at": [10, 8], "activity": "errand"},
            {"from_h": 18.0, "to_h": 6.0, "at": [2, 2], "activity": "indoors"}],
         "dialogue_mode": "subtitled", "language": "fr", "priority": "flee_from_danger",
         "narrative_flags": [], "persists_when_unloaded": True},
        {"id": "civ_priest", "label_key": "npc.priest", "is_fictional": True, "home": [7, 10], "schedule": [
            {"from_h": 6.0, "to_h": 19.0, "at": [7, 10], "activity": "chapel_duty"},
            {"from_h": 19.0, "to_h": 6.0, "at": [7, 10], "activity": "indoors"}],
         "dialogue_mode": "subtitled", "language": "fr", "priority": "shelter_others",
         "narrative_flags": ["can_shelter_player"], "persists_when_unloaded": True},
    ],
    "ambience_zones": [
        {"id": "az_open_field", "match_surface": ["surf_grass", "surf_crop"], "soundscape": "amb_bocage_field", "reverb": "rv_open"},
        {"id": "az_lane",       "match_surface": ["surf_dirt_track", "surf_cobble"], "soundscape": "amb_bocage_lane", "reverb": "rv_open_hedged"},
        {"id": "az_hedge",      "match_surface": ["surf_hedge_base"], "soundscape": "amb_bocage_hedge", "reverb": "rv_dense_foliage"},
    ],
    "persistence_rules": {
        "permanent": ["poi_states", "door_open_states_on_objective_doors", "container_looted", "objective_flags", "inventory", "civilian_narrative_flags", "patrol_casualties"],
        "resets_on_reentry": ["small_props_displaced", "broken_glass", "spent_casings", "ambient_animal_positions", "patrol_positions_when_no_casualty"],
        "note": "A revisited objective never pays its reward twice: completion is recorded in DistrictCheckpoint.mission_flags and checked before any grant.",
    },
  },
}

SURFACE_BY_GLYPH = {
    ".": "surf_grass", ",": "surf_dirt_track", "R": "surf_cobble", "H": "surf_hedge_base",
    "o": "surf_grass", "#": "surf_packed_earth", "c": "surf_cobble", "j": "surf_dirt_track",
    "x": "surf_grass", " ": "surf_grass",
}

def build(did):
    d = DISTRICTS[did]
    rows = d["layout"]
    h = len(rows); w = max(len(r) for r in rows)
    rows = [r.ljust(w, ".") for r in rows]

    tiles, structures, vegetation, hedges, poi_out = [], [], [], [], []
    poi_by_glyph = {}
    for p in d["pois"]:
        poi_by_glyph.setdefault(p["glyph"], []).append(p)
    glyph_bld = d["glyph_buildings"]
    placed_bld = {}
    claimed_poi = set()

    for r in range(h):
        for c in range(w):
            g = rows[r][c]
            x, z = c * CELL, r * CELL
            surf = SURFACE_BY_GLYPH.get(g, "surf_grass")
            if g in glyph_bld:
                surf = "surf_packed_earth"
            tiles.append({"c": c, "r": r, "glyph": g, "surface": surf,
                          "passable": g != "H",
                          "cover": 0.95 if g == "H" else (0.12 if g == "o" else 0.0)})
            if g == "H":
                hedges.append({"c": c, "r": r, "height_m": round(2.6 + 0.9 * ((c * 7 + r * 13) % 5) / 4.0, 2),
                               "width_m": round(1.6 + 0.6 * ((c * 3 + r * 5) % 4) / 3.0, 2),
                               "bank_m": 1.1, "species": "mixed_hedge", "mantle_points": []})
            if g == "o":
                vegetation.append({"t": "veg_apple_tree", "p": [round(x + 4.0, 2), round(z + 4.0, 2)],
                                   "scale": round(0.85 + 0.3 * ((c * 11 + r * 17) % 4) / 3.0, 2),
                                   "rot": (c * 47 + r * 29) % 360, "sway": 0.35})
            if g in glyph_bld and g not in placed_bld:
                tpl = glyph_bld[g]
                placed_bld.setdefault(g, 0)
            if g in poi_by_glyph:
                for p in poi_by_glyph[g]:
                    if p["id"] in claimed_poi:
                        continue
                    claimed_poi.add(p["id"])
                    q = dict(p); q.pop("glyph")
                    q["p"] = [round(x + CELL / 2, 2), round(z + CELL / 2, 2)]
                    q["cell"] = [c, r]
                    poi_out.append(q)
                    break

    # place buildings: one instance per contiguous glyph run, anchored at its top-left cell
    seen = set()
    inst = 0
    for r in range(h):
        for c in range(w):
            g = rows[r][c]
            if g not in glyph_bld or (c, r) in seen:
                continue
            # flood the contiguous same-glyph block
            block = []
            stack = [(c, r)]
            while stack:
                cc, rr = stack.pop()
                if (cc, rr) in seen or not (0 <= cc < w and 0 <= rr < h) or rows[rr][cc] != g:
                    continue
                seen.add((cc, rr)); block.append((cc, rr))
                stack += [(cc + 1, rr), (cc - 1, rr), (cc, rr + 1), (cc, rr - 1)]
            tpl_name = glyph_bld[g]
            tpl = BUILDING_TEMPLATES[tpl_name]
            minc = min(b[0] for b in block); minr = min(b[1] for b in block)
            maxc = max(b[0] for b in block); maxr = max(b[1] for b in block)
            span_x = (maxc - minc + 1) * CELL; span_z = (maxr - minr + 1) * CELL
            fx, fz = tpl["footprint"]
            ox = minc * CELL + max(0.0, (span_x - fx) / 2.0)
            oz = minr * CELL + max(0.0, (span_z - fz) / 2.0)
            inst += 1
            structures.append({
                "id": f"{did}_{tpl_name}_{inst}", "template": tpl_name, "label_key": tpl["label_key"],
                "origin": [round(ox, 2), round(oz, 2)], "rot_deg": 0,
                "footprint": tpl["footprint"], "wall_h": tpl["wall_h"], "wall_thickness": tpl["wall_thickness"],
                "roof": tpl["roof"], "material": tpl["material"], "floors": tpl["floors"],
                "openings": tpl["openings"], "interior": tpl["interior"],
                "cells": [[b[0], b[1]] for b in sorted(block)],
            })

    # streaming cells: 4x4 layout cells = 32 x 32 m
    sc = []
    for sr in range(0, h, 4):
        for scol in range(0, w, 4):
            sc.append({"id": f"chunk_{scol // 4}_{sr // 4}",
                       "rect_m": [scol * CELL, sr * CELL, min(w, scol + 4) * CELL, min(h, sr + 4) * CELL],
                       "preload_radius_m": 48.0,
                       "structures": [s["id"] for s in structures
                                      if scol <= s["cells"][0][0] < scol + 4 and sr <= s["cells"][0][1] < sr + 4]})

    def world(cell):
        return [round(cell[0] * CELL + CELL / 2, 2), round(cell[1] * CELL + CELL / 2, 2)]

    patrols = []
    for p in d["patrols"]:
        q = dict(p); q["route_m"] = [world(x) for x in p["route"]]; patrols.append(q)
    civs = []
    for cv in d["civilians"]:
        q = dict(cv); q["home_m"] = world(cv["home"])
        q["schedule"] = [{**s, "at_m": world(s["at"])} for s in cv["schedule"]]
        civs.append(q)

    return {
        "schema": "wbtm.district", "schema_version": 3, "content_version": "0.9.0-blockout",
        "id": did, "label_key": d["label_key"], "location": d["location"], "theater": d["theater"],
        "history_refs": d["history_refs"], "season": d["season"], "latitude": d["latitude"],
        "default_date": d["default_date"], "states": d["states"], "default_state": d["default_state"],
        "weather_profiles": d["weather_profiles"], "default_weather": d["default_weather"],
        "ambience_default": d["ambience_default"],
        "grid": {"cell_m": CELL, "cols": w, "rows": h, "size_m": [w * CELL, h * CELL]},
        "tiles": tiles, "hedgerows": hedges, "vegetation": vegetation,
        "structures": structures, "pois": poi_out,
        "patrols": patrols, "civilians": civs,
        "ambience_zones": d["ambience_zones"], "streaming_cells": sc,
        "persistence_rules": d["persistence_rules"],
        "art_status": {
            "level": "blockout",
            "statement": "Geometry, openings, interiors, navigation, patrol routes and audio zones are authored. Production meshes, materials, characters and recorded audio are NOT present. This district does not meet the commercial art bar in the brief and must not be presented as if it does.",
        },
    }

if __name__ == "__main__":
    did = sys.argv[1] if len(sys.argv) > 1 else "district_normandy_bocage"
    json.dump(build(did), sys.stdout, indent=1, ensure_ascii=False)
    print()
