# PM Body Winding – Clean Spec for New Chat

This markdown file is a **clean specification** for rebuilding the Plane‑Maker
body ring logic from scratch in a new chat.

The new chat should *only* focus on:

1. Building the **correct j‑ring (0..17)** for each station of each mesh
   in `bodies.obj`, matching the reference data we already derived.
2. Doing this in a **generic way** that works for all meshes in
   `bodies.obj` (fuselage, cowlings, tail fairing), not just hard‑coded
   cases.
3. Returning the **lateral offset** (`part_x`) as part of the function,
   based on recentering in X.

Only after that winding function is tested and correct will we integrate it
into the full ACF body writer.

---

## 1. Context and coordinate system

Target: **X‑Plane Plane‑Maker body geometry** (`P _body/n/_geo_xyz/i,j,k`)
for the Chieftain, based on `bodies.obj`.

Each **body mesh** (fuselage, cowlings, tail fairing, etc.) is:

- Symmetrical about the **center plane** (`x = 0` after recentering).
- Built so that **tip and tail** have **one vertex** each.
- Middle cross‑sections (stations) have a loop of vertices with:
  - Full loop: typically 8 or 16 verts.
  - After splitting by half (x ≥ 0), we get **n** vertices on the
    +X/center side with **5 ≤ n ≤ 9**.

We assume the mesh we give the function is in **Plane‑Maker coordinates**:

- `x` – lateral (left/right)
- `y` – vertical (up/down)
- `z` – longitudinal (tip‑to‑tail, with **tip at negative z**, tail at positive z)
- Units: **meters** in the OBJ → we will convert to **feet** for the ACF.

If the original mesh comes from Blender, axis flips / conversions
(Blender → PM) must already be handled before calling this function.

---

## 2. Overall pipeline for one mesh

For a single OBJ mesh/group (e.g. fuselage, LF cowling, RT cowling, fairing):

1. **Compute lateral center and recenter in X**

   - Compute:

     ```text
     center_x_m = (min_x + max_x) / 2   (in meters)
     ```

   - Recenter all vertices:

     ```text
     x_local = x - center_x_m
     ```

   - This guarantees the **true mid‑span** is at `x_local ≈ 0`.

   - Store the lateral offset (in feet) for use as PM’s `part_x`:

     ```text
     part_x_ft = center_x_m * 3.28084
     ```

2. **Group vertices into stations (cross‑sections) by z**

   - After recentering, vertices are grouped into stations by **longitudinal
     position** (z).
   - Each station should be a list of verts whose z values are all almost
     equal (within a tolerance).
   - Stations must then be **sorted by increasing z** (tip → tail):

     - `i = 0` → most negative z = tip
     - `i = N` → most positive z = tail

3. **For each station, build the j‑ring (0..17)**

   - We build **one ring of 18 points** per station.
   - `j` goes **around the circumference**:

     - `j = 0..8`  → left / +X / center side
     - `j = 9..17` → right / −X side (mirror of 0..8)

   - All coordinates are converted to **feet**.

4. **Return from the function**

   The target function in the new chat should, for one mesh, return at least:

   - `part_x_ft` – lateral offset to be used as `_part_x` in PM.
   - `rings` – list of stations, each station is a list of 18 (x_ft, y_ft, z_ft)
     in the correct `j` order.
   - `half_n_max` – maximum number of distinct half‑ring vertices across stations
     (for computing `_r_dim = 2 * half_n_max`).

Later, this will be used to emit:

- `P _body/k/_geo_xyz/i,j,0` = x_ft
- `P _body/k/_geo_xyz/i,j,1` = y_ft
- `P _body/k/_geo_xyz/i,j,2` = z_ft
- `P _body/k/_part_x` = part_x_ft
- `P _body/k/_r_dim` and `_s_dim`, etc.

---

## 3. Station ordering (i index rule)

Within a single body:

- Stations (`i`) must be ordered strictly by **increasing z**:

  ```text
  i = 0   → tip (most negative z)
  ...
  i = N-1 → tail (most positive z)
  ```

- Tip and tail stations have **exactly one vertex**.

For mid stations, we want them ordered consistently along the fuselage:
nose to tail.

---

## 4. Per‑station winding rules (j index)

### 4.1 Tip and tail stations (single vertex)

If station `i` has exactly **one vertex** in meters:

- Convert to feet:

  ```text
  x_ft = x_m * 3.28084
  y_ft = y_m * 3.28084
  z_ft = z_m * 3.28084
  ```

- For PM body poles we treat them as **true poles** at x = 0 and replicate
  around the ring (because there is no meaningful circumference):

  ```text
  For j = 0..17:
      x(j) = 0.0
      y(j) = y_ft
      z(j) = z_ft
  ```

So all 18 j slots at tip or tail share the same (0, y, z).

---

### 4.2 Mid stations (5 ≤ half‑ring n ≤ 9)

For a mid station `i`, we start with a list of vertices in meters:

- `station_vertices_m = [ (x_m, y_m, z_m), ... ]`

This is the **full loop** for this cross‑section, in **OBJ loop order**.

#### Step 1 – Build half‑ring on x ≥ 0

- After recentering the mesh, create:

  ```text
  half = [v for v in station_vertices_m if v.x >= 0]
  ```

- This preserves the **original loop order** (no sorting by y or z).
- By design, `len(half)` (call it `n`) must satisfy `5 ≤ n ≤ 9`.

#### Step 2 – Fill j0..8 (left/+X/center side) with padding

- We have 9 slots: `j = 0..8`.

- If `n = 9` (e.g., full loop has 16 verts, typical fuselage/cowling case):

  ```text
  For j = 0..8:
      use half[j]
  ```

  No padding, direct mapping.

- If `5 ≤ n < 9` (e.g., full loop has 8 verts, tail fairing case):

  ```text
  For j = 0..(n-1):
      use half[j]

  For j = n..8:
      use half[n-1]  (repeat the last half‑ring vertex)
  ```

- In these geometries, `half[n-1]` is the **bottom center** vertex
  (Min Y, X ≈ 0), so padding with it makes sense physically.

- For each selected vertex `(x_m, y_m, z_m)` we convert to feet:

  ```text
  x_ft = x_m * 3.28084
  y_ft = y_m * 3.28084
  z_ft = z_m * 3.28084
  ```

#### Step 3 – Fill j9..17 by mirroring in X

- For each `j_left = 0..8`:

  ```text
  j_right = 9 + j_left
  x_right_ft = -x_left_ft
  y_right_ft =  y_left_ft
  z_right_ft =  z_left_ft
  ```

- So:

  - j0..8 form the left/+X/center side.
  - j9..17 form the right/−X side.

#### Step 4 – Zero normalization of X

To avoid `-0.000000000` in the ACF:

- After all conversions, any x with `|x| < eps` (e.g., 1e‑6) is set to exactly 0.

This ensures the centerline entries consistently print as `0.000000000`.

---

## 5. Reference data to match (from bodies.obj)

The new chat must ensure that, when applying this logic correctly to
`bodies.obj`, **the function reproduces these rings** exactly (within
floating‑point rounding).

### 5.1 Fuselage – group `Fuselage_Chieftain_fuse_only_Mesh.0001`, station 5

After recentering, for station 5 we get:

- `half_n = 9`  → no padding; full half‑ring of 9 verts.
- All z values around −6.7363 ft.

#### j0..j8 (left / +X / center):

| j | x_ft         | y_ft         | z_ft          |
|---|-------------:|-------------:|--------------:|
| 0 | 0.000000000  | 1.906902948  | -6.736309271  |
| 1 | 0.988868142  | 1.744160161  | -6.736309271  |
| 2 | 1.807795333  | 1.426000702  | -6.736309271  |
| 3 | 2.121420672  | 0.769885195  | -6.736309271  |
| 4 | 2.179186421  | 0.003517060  | -6.736309271  |
| 5 | 2.029360301  | -0.693772988 | -6.736056646  |
| 6 | 1.510095193  | -1.249845841 | -6.736309271  |
| 7 | 0.866660133  | -1.557998738 | -6.741145229  |
| 8 | 0.000000000  | -1.697601760 | -6.736309271  |

#### j9..j17 (right / −X side):

| j  | x_ft          | y_ft         | z_ft          |
|----|--------------:|-------------:|--------------:|
| 9  | 0.000000000   | 1.906902948  | -6.736309271  |
| 10 | -0.988868142  | 1.744160161  | -6.736309271  |
| 11 | -1.807795333  | 1.426000702  | -6.736309271  |
| 12 | -2.121420672  | 0.769885195  | -6.736309271  |
| 13 | -2.179186421  | 0.003517060  | -6.736309271  |
| 14 | -2.029360301  | -0.693772988 | -6.736056646  |
| 15 | -1.510095193  | -1.249845841 | -6.736309271  |
| 16 | -0.866660133  | -1.557998738 | -6.741145229  |
| 17 | 0.000000000   | -1.697601760 | -6.736309271  |

Any correct implementation must be able to reconstruct this ring
starting from the raw station vertices from `bodies.obj`.

---

### 5.2 Tail Fairing – group `Fairing_Tail_PM_bodies_test_Mesh.394`, station 2

After recentering, full loop has 8 vertices. After splitting by x ≥ 0 we
get **n = 5**. This is the fairing‑style, low‑vert case that requires
padding.

#### j0..j8 (left / +X / center):

| j | x_ft         | y_ft         | z_ft         |
|---|-------------:|-------------:|-------------:|
| 0 | 0.000000000  | 3.527887252  | 12.712093583 |
| 1 | 0.137568902  | 3.404363626  | 12.712093583 |
| 2 | 0.275137804  | 3.260252729  | 12.712093583 |
| 3 | 0.255282160  | 2.765039459  | 12.712093583 |
| 4 | 0.000000000  | 2.769376729  | 12.712093583 |
| 5 | 0.000000000  | 2.769376729  | 12.712093583 |
| 6 | 0.000000000  | 2.769376729  | 12.712093583 |
| 7 | 0.000000000  | 2.769376729  | 12.712093583 |
| 8 | 0.000000000  | 2.769376729  | 12.712093583 |

Notes:

- `n = 5`, so:
  - `j = 0..4` = the 5 half‑ring verts
  - `j = 5..8` = padded with the last half‑ring vertex (bottom center, x = 0)

#### j9..j17 (right / −X side):

| j  | x_ft          | y_ft         | z_ft         |
|----|--------------:|-------------:|-------------:|
| 9  | 0.000000000   | 3.527887252  | 12.712093583 |
| 10 | -0.137568902  | 3.404363626  | 12.712093583 |
| 11 | -0.275137804  | 3.260252729  | 12.712093583 |
| 12 | -0.255282160  | 2.765039459  | 12.712093583 |
| 13 | 0.000000000   | 2.769376729  | 12.712093583 |
| 14 | 0.000000000   | 2.769376729  | 12.712093583 |
| 15 | 0.000000000   | 2.769376729  | 12.712093583 |
| 16 | 0.000000000   | 2.769376729  | 12.712093583 |
| 17 | 0.000000000   | 2.769376729  | 12.712093583 |

Any correct implementation of the **padding logic** must reproduce this.

---

### 5.3 LF Cowling – group `LF_Cowling_Cylinder.001`, station 8

After recentering, full loop has 16 verts → **n = 9** after split.

`part_x_ft` for LF cowling (from center_x) is approximately:

- `part_x_ft ≈ -6.320407026` ft.

We focus on the ring itself; the winding logic does not care about the sign
of `part_x_ft`, only about the local centered geometry.

#### j0..j8 (left / +X / center):

| j | x_ft         | y_ft         | z_ft          |
|---|-------------:|-------------:|--------------:|
| 0 | 0.000000000  | 0.658018394  | -8.005623616  |
| 1 | 0.142604991  | 0.629652251  | -8.005623616  |
| 2 | 0.263500665  | 0.548874689  | -8.005623616  |
| 3 | 0.344278226  | 0.427979016  | -8.005623616  |
| 4 | 0.372644369  | 0.285374025  | -8.005623616  |
| 5 | 0.344278226  | 0.142769033  | -8.005623616  |
| 6 | 0.263500665  | 0.021873360  | -8.005623616  |
| 7 | 0.142604991  | -0.058904201 | -8.005623616  |
| 8 | 0.000000000  | -0.087270344 | -8.005623616  |

#### j9..j17 (right / −X side):

| j  | x_ft          | y_ft         | z_ft          |
|----|--------------:|-------------:|--------------:|
| 9  | 0.000000000   | 0.658018394  | -8.005623616  |
| 10 | -0.142604991  | 0.629652251  | -8.005623616  |
| 11 | -0.263500665  | 0.548874689  | -8.005623616  |
| 12 | -0.344278226  | 0.427979016  | -8.005623616  |
| 13 | -0.372644369  | 0.285374025  | -8.005623616  |
| 14 | -0.344278226  | 0.142769033  | -8.005623616  |
| 15 | -0.263500665  | 0.021873360  | -8.005623616  |
| 16 | -0.142604991  | -0.058904201 | -8.005623616  |
| 17 | 0.000000000   | -0.087270344 | -8.005623616  |

---

### 5.4 RT Cowling – group `RT_Cowling_Cylinder.002`, station 8

Same geometry as LF, mirrored laterally, with:

- `part_x_ft ≈ +6.320390622` ft.

The local centered ring should be essentially identical to LF’s:

#### j0..j8 (left / +X / center):

| j | x_ft         | y_ft         | z_ft          |
|---|-------------:|-------------:|--------------:|
| 0 | 0.000000000  | 0.658018394  | -8.005623616  |
| 1 | 0.142608272  | 0.629652251  | -8.005623616  |
| 2 | 0.263500665  | 0.548874689  | -8.005623616  |
| 3 | 0.344281507  | 0.427979016  | -8.005623616  |
| 4 | 0.372647650  | 0.285374025  | -8.005623616  |
| 5 | 0.344281507  | 0.142769033  | -8.005623616  |
| 6 | 0.263500665  | 0.021873360  | -8.005623616  |
| 7 | 0.142608272  | -0.058904201 | -8.005623616  |
| 8 | 0.000000000  | -0.087270344 | -8.005623616  |

#### j9..j17 (right / −X side):

| j  | x_ft          | y_ft         | z_ft          |
|----|--------------:|-------------:|--------------:|
| 9  | 0.000000000   | 0.658018394  | -8.005623616  |
| 10 | -0.142608272  | 0.629652251  | -8.005623616  |
| 11 | -0.263500665  | 0.548874689  | -8.005623616  |
| 12 | -0.344281507  | 0.427979016  | -8.005623616  |
| 13 | -0.372647650  | 0.285374025  | -8.005623616  |
| 14 | -0.344281507  | 0.142769033  | -8.005623616  |
| 15 | -0.263500665  | 0.021873360  | -8.005623616  |
| 16 | -0.142608272  | -0.058904201 | -8.005623616  |
| 17 | 0.000000000   | -0.087270344 | -8.005623616  |

---

## 6. Target function for the new chat

In the new chat, we want to design and test something along the lines of:

```python
def build_pm_rings_for_mesh(
    verts_m: List[Tuple[float, float, float]]
) -> Tuple[
    float,                       # part_x_ft
    List[List[Tuple[float, float, float]]],  # rings[i][j] = (x_ft, y_ft, z_ft)
    int                          # half_n_max (for r_dim = 2 * half_n_max)
]:
    ...
```

Where:

- `verts_m` are the mesh vertices (already converted into PM coordinate
  system and meters).
- The function:
  - Computes `center_x_m`, recenters vertices in X, and returns `part_x_ft`.
  - Groups verts into stations by z, sorts stations by z (tip → tail).
  - For each station, builds the j‑ring (0..17) using the logic above.
  - Tracks `half_n_max` across stations.

Then we will **unit‑test** this function in the new chat by:

- Running it on `bodies.obj` (per group).
- Inspecting the appropriate station for each group.
- Confirming those j‑rings exactly match the reference tables above.

Once that is done and stable, we can then plug this function into the full
PM body writer to generate the `P _body/...` blocks automatically.
