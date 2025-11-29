# PlaneMaker Importer – Current Status Summary

This summary reflects the current state of the project and the corrected logic.

## 1. Multi‑Body OBJ → ACF Logic

- Every OBJ group (g/o) is treated as an independent Plane Maker body.
- The first group becomes **body0**, the second **body1**, and so on.
- The fuselage is detected automatically (largest Z-span) or given manually.

## 2. Station Construction (Z Loops)

- Vertices grouped by Z using rounding tolerance.
- Stations sorted from nose to tail.
- Each body’s station index **i starts at 0** and increases independently.
- Tip and tail stations contain **1 vertex**.
- All other stations contain `verts_per_loop` vertices (e.g., 16).

## 3. j‑Index Rules (Critical Fix)

- j‑indices are **fixed and always 0..17** for every station of every body.
- Never scanned or inferred from the ACF.
- Prevents corruption and mismatched geometry in Plane Maker.

## 4. Geometry Reconstruction

- For each station:
  - Positive‑X half of the mesh is mirrored to create left‑side vertices.
  - j indices mapped deterministically around the loop.
  - Tip and tail stations collapse to a single averaged point replicated over all j.

## 5. Lateral Offset (part_x)

- Only **non‑fuselage** bodies are recentered in X for loop symmetry.
- The removed offset becomes `_part_x` (lateral arm in feet).
- `_part_y` and `_part_z` remain unchanged.

## 6. Body Metadata Updated Per Body

Each body receives:

- `_s_dim` = station count  
- `_r_dim` = 18 (because j = 0..17)  
- `_locked/i_count` = station count  
- `_locked/j_count` = 18  
- `_part_rad` = grid radius (max(|x|, |y|) + 3 feet)  
- `_part_x` = computed lateral offset (non‑fuselage only)

## 7. Body Block Requirements

Each generated body must contain the complete set of lines found in the
provided `bodyN_block.txt` template, including:

- `_bot_*` and `_top_*`
- `_engn_for_body`, `_gear_for_body`
- `_geo_xyz/i,j,k` grid
- `_locked/i,j` grid
- `_locked/i_count`, `_locked/j_count`
- `_part_*`
- `_s_dim`, `_r_dim`

Each new body block must be inserted **immediately after** the previous body block.

## 8. Current State

- Fuselage logic: correct  
- Cowling logic: correct  
- j‑index bug: fixed  
- Geometry distortion: resolved  
- Multi‑body indexing: resolved  
- Lateral offset placement: correct  
- All bodies produce stations and vertices within PM limits (0..17)

This summary is ready to be used to start a clean new chat.

