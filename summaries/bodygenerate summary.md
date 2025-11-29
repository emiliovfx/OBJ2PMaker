# Plane Maker MObject Import — Station Winding & Mapping (summary)

**Scope**: How the fixed MObject importer transforms an OBJ mesh into a Plane Maker body block for **`_body/0`**. This document specifies **ordering**, **station definition**, **vertex-to-cell correspondence**, and **edge cases**.

---

## Coordinate & Units
- OBJ vertex tuple **(x, y, z)** is assumed in meters (Blender default).
- Plane Maker `_geo_xyz/{i},{j},k` is written in **feet** (`k=0→x`, `k=1→y`, `k=2→z`).
- Conversion: `ft = m × 3.28084`.

---

## Stationing (Z-cluster, Importer_002-compatible)
We build stations **monotonically along body axis (Z)**:
1. **Sort all mesh vertices by Z ascending**.
2. **Tip station (i=0)** = *min-Z* vertex only.
3. **Tail station (last non-empty)** = *max-Z* vertex only.
4. **Middle stations**: remaining vertices **in Z order** chunked into contiguous rings of size `verts_per_loop`.
   - If the count isn’t an exact multiple, the last middle station is a **partial ring**.

### Why Z-cluster?
- Keeps `i` increasing from nose to tail.
- Reproduces Importer_002’s notion of “station slices along Z”.

---

## Grid Dimensions & Padding
- We **lock** the grid to the ACF:
  - `target_i = P _body/0/_locked/i_count` (typically **20**)
  - `target_j = P _body/0/_locked/j_count` (typically **18**)
- Mesh may report **S** stations (tip + middle rings + tail). We **conform to the grid**:
  - If `S < target_i`: **pad** stations `i=S..target_i-1` with **EMPTY** stations → all **xyz = 0**.
  - If `S > target_i`: **truncate** to the first `target_i` stations (Plane Maker limit).
- `_s_dim` records the **actual mesh station count `S`** (e.g., 15), not the padded `target_i`.

---

## Per-Station Emission Rules
Each cell is `P _body/0/_geo_xyz/{i},{j},k`:

### A) Empty station (padding)
- For all `j` in `[0, target_j-1]`:
  - `x = 0`, `y = 0`, `z = 0`.

### B) Tip (i=0) and Tail (i = last non-empty)
- Compute **averages** over the single-vertex set (tip/tail are size 1, so averages = the vertex):
  - `y_tip = mean(y)`, `z_tip = mean(z)`; `x_tip = 0` (by definition).
- For **every `j`**:
  - `(x, y, z) = (0, y_tip, z_tip)` for `i=tip`.
  - `(x, y, z) = (0, y_tail, z_tail)` for `i=tail`.
- **Tail detection** uses the **last non-empty station** (not the padded end).

### C) Loop stations (non-empty middle)
We split the ring across **right** and **left** halves of `j`:
- Let `J = target_j`, `half = J // 2`.
- **Right-half indices**: `j_r = 0, 1, ..., half-1`.
- **Left-half indices**: `j_l = J-1, J-2, ..., half` (descending).

**Selection and ordering of vertices:**
1. Take **+X-side vertices**: `{ v | v.x ≥ 0 }`.
   - If none exist (degenerate ring), use the entire ring.
2. **Sort by Y descending** (top → bottom): `sorted(+X, key=lambda v: v.y, reverse=True)`.
3. Iterate `idx = 0..(N-1)` over this sorted list and map vertices **round-robin**:
   - Right half: `j_r = (idx mod len(right_half))`.
   - Left half:  `j_l = (idx mod len(left_half))`.
4. For each selected vertex `(x_m, y_m, z_m)` (meters), **write**:
   - Right cell `(i, j_r)`:
     - `x = +x_m * ft_per_m`, `y = y_m * ft_per_m`, `z = z_m * ft_per_m`.
   - Left cell `(i, j_l)` (**mirror X only**):
     - `x = -x_m * ft_per_m`, `y =  y_m * ft_per_m`, `z =  z_m * ft_per_m`.
5. If the ring has **fewer** vertices than `half`, the last assigned vertex **wraps/repeats** (round-robin). Unassigned cells (rare) default to `0,0,0`.

**Rationale**: Plane Maker expects a symmetric left/right distribution. We use +X data as the source of truth and mirror X to the left side for a consistent, closed cross-section per station.

---

## Index Correspondence Summary
- **Stations (`i`)**:
  - `i=0`: tip (min Z)
  - `i=1..S-2`: middle rings in **ascending Z** (chunked by `verts_per_loop`)
  - `i=S-1`: tail (max Z)
  - `i=S..target_i-1`: **empty** (padded), xyz=0 for all `j`

- **Circumferential (`j`)** (for each `i`)**:**
  - Right half: `j=0..half-1` (top→bottom by Y because we sort Y desc)
  - Left half:  `j=J-1..half` (bottom→top due to descending index order)  
  - Mapping is **round-robin** over the sorted +X vertices.

- **Components (`k`)**:
  - `k=0`: X (ft)
  - `k=1`: Y (ft)
  - `k=2`: Z (ft)

---

## Output Block Fields
- `_locked/i_count = target_i`
- `_locked/j_count = target_j`
- `_r_dim        = target_j`
- `_s_dim        = S` (mesh stations, pre-padding)
- `_geo_xyz/{i},{j},k` written per rules above.
- Headers (`_bot_*`, `_top_*`, `_part_*`) untouched except `_part_rad` computed from mesh extent.

---

## Edge Cases & Notes
- **Partial rings**: middle’s last chunk can be < `verts_per_loop`; round-robin still applies.
- **No +X vertices**: fall back to the full ring.
- **Degenerate tip/tail**: still written for **all `j`**, ensuring fully populated end caps.
- **S > target_i**: stations are truncated (PM limit). Consider using fewer OBJ slices if needed.
- **Units**: ensure OBJ is in **meters**. If using another unit, adjust scale before import.

---

## Pseudocode (reference)
```python
verts = load_obj(fus_group)              # (x,y,z) in meters
v_sorted = sort_by_z(verts)              # asc
stations = [ [v_sorted[0]],             # tip
             chunks(v_sorted[1:-1], VPL),
             [v_sorted[-1]] ]           # tail

target_i, target_j = read_acf_dims()
stations = pad_or_truncate(stations, target_i)

J = target_j; half = J // 2
right = range(0, half)
left  = range(J-1, half-1, -1)

tail_idx = last_non_empty(stations)

for i, ring in enumerate(stations):
    if empty(ring): write_all_j(i, 0,0,0); continue
    if i==0 or i==tail_idx: write_all_j(i, x=0, y=avg(ring.y), z=avg(ring.z)); continue

    pos = [v for v in ring if v.x>=0] or ring
    pos = sort_by_y_desc(pos)
    for idx, v in enumerate(pos):
        jr = right[idx % len(right)]
        jl = left [idx % len(left )]
        write(i,jr, +v.x, v.y, v.z)
        write(i,jl, -v.x, v.y, v.z)
```

---

## Validation Checklist
- Station Z’s increase monotonically; tip/tail at ends.
- `_s_dim` equals **mesh stations**; `_locked/i_count` equals grid **target**.
- Tail station has **uniform Z** across all `j` (same averaged value).
- All padded stations write **(0,0,0)** for every `j`.
- Round-robin mapping produces a filled circumference without gaps.
