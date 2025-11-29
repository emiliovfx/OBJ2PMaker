# PM Bodies Winding Reference

This document locks the **geometry logic** for converting OBJ mesh loops into
Plane Maker body stations (`P _body/n/_geo_xyz/i,j,k`) so we don’t reinvent
the wheel again.

It is based **entirely on values extracted from `bodies.obj`**, not from the
ACF, and follows a strict 1:1 rule:

> We never change vertex values (other than recentering in X and converting
> from meters to feet). We only decide **which vertex goes to which j index**
> and when we need to **pad**.

---

## 1. Pre‑processing logic (per OBJ mesh / group)

For each OBJ group (fuselage, cowlings, fairing, etc.):

1. **Center the mesh laterally (X):**

   - Compute:
     - `center_x = (min_x + max_x) / 2`  (in meters)
   - Recenter all vertices:
     - `x_local = x - center_x`
   - This guarantees the true mid‑span is at `x_local ≈ 0`.

2. **Store lateral offset as `part_x`:**

   - Convert `center_x` to feet:
     - `part_x = center_x * 3.28084`
   - In the ACF:
     - `P _body/N/_part_x part_x`
   - This is the **lateral arm** of the body.

3. **Station loops from OBJ order (no sorting):**

   - Let `verts_local` be the centered vertices in OBJ order.
   - We **do not sort by Y or Z**.
   - We assume a PM‑style topology:

     ```text
     [ tip ] [ loop0 verts_per_loop ] [ loop1 verts_per_loop ] ... [ tail ]
     ```

   - Then:
     - Tip station: first vertex (`[0]`) → station 0
     - Middle stations: chunks of `verts_per_loop` in order
     - Tail station: last vertex (`[-1]`) → last station

4. **Split station loop into half‑ring:**

   For each station (a loop of `verts_per_loop` vertices in **original OBJ
   order**):

   - Work with the **centered** coordinates `(x_local, y, z)`.
   - Build a half‑ring list using **loop order**, not sorted:

     ```text
     half_ring = [ v for v in loop_vertices if v.x_local >= 0 ]
     ```

   - If the mesh is symmetric and centered, this gives you the "center + +X" side.

5. **Number of half‑ring vertices after split (`n`):**

   - After splitting, `n = len(half_ring)` will be between **5 and 9**:

     - 16‑vertex full loop → 9 vertices after split (fuselage, cowlings)  
     - 8‑vertex full loop  → 5 vertices after split (fairing)  

   - This range **[5, 9]** is the design space for mid stations.

---

## 2. j‑index assignment logic

For each station, we produce a ring with `J = 18` slots (`j = 0..17`):

- `j0..8`  = left/+X/center half, in loop order, with padding if needed  
- `j9..17` = right/−X half, exact mirror of `j0..8` in X only

### 2.1 Tip and tail stations

If a station has only **one vertex** (tip or tail):

- Compute its feet coordinates `(x_ft, y_ft, z_ft)` after centering.
- The station becomes a **pole**, replicated around the ring with `x = 0`:

  ```text
  For j = 0..17:
      x(j) = 0
      y(j) = y_ft
      z(j) = z_ft
  ```

### 2.2 Mid stations, general rule (`5 ≤ n ≤ 9`)

Let `half_ring` be the centered vertices on `x_local ≥ 0`, in **original loop order**.
Let `n = len(half_ring)` after the split.

1. **Pick the order for j0..(n‑1):**

   - We take `half_ring[0]..half_ring[n‑1]` in that exact order.
   - The last vertex `half_ring[n‑1]` is the **centerline bottom** if the loop
     is constructed that way (x = 0). If the last vertex has x ≠ 0 and a
     later vertex has x = 0, vertex ordering in the mesh must be adjusted
     in Blender so the **last half‑ring vertex is on the centerline**.

2. **Fill j0..8 on the +X side (with padding):**

   - `J_half = 9` slots (0..8).
   - If `n = 9`: use all of them, no padding:

     ```text
     j = 0..8 → half_ring[j]
     ```

   - If `n < 9` (i.e., 5, 6, 7, or 8):

     ```text
     For j = 0..n-1:
         j → half_ring[j]

     For j = n..8:
         j → half_ring[n-1]  (repeat the last vertex)
     ```

   - In practice, `half_ring[n‑1]` is the **bottom center** (x = 0, min y)
     for fairings and similar shapes.

3. **Fill j9..17 by mirroring j0..8 in X:**

   For each `j_left = 0..8`:

   - `j_right = 9 + j_left`
   - Copy Y and Z, negate X:

     ```text
     x_right = -x_left
     y_right =  y_left
     z_right =  z_left
     ```

4. **Zero normalization:**

   - Any `x` value with `|x| < epsilon` (e.g., `1e-6`) is treated as **exactly** 0:

     ```text
     if abs(x_ft) < 1e-6: x_ft = 0.0
     ```

   - So centerline entries always end up as `0.000000000`, never `-0.000000000`.

---

## 3. Concrete examples from `bodies.obj`

### 3.1 Fuselage – `Fuselage_Chieftain_fuse_only_Mesh.0001`, station 5

- Mesh already centered in X → `part_x = 0.000000000` ft.
- After splitting, `n = 9` vertices on the +X/center half. No padding.

**j0..j8 (left / +X side):**

| j | x (ft)       | y (ft)        | z (ft)         |
|---|-------------:|--------------:|---------------:|
| 0 | 0.000000000  | 1.906902948   | -6.736309271   |
| 1 | 0.988868142  | 1.744160161   | -6.736309271   |
| 2 | 1.807795333  | 1.426000702   | -6.736309271   |
| 3 | 2.121420672  | 0.769885195   | -6.736309271   |
| 4 | 2.179186421  | 0.003517060   | -6.736309271   |
| 5 | 2.029360301  | -0.693772988  | -6.736056646   |
| 6 | 1.510095193  | -1.249845841  | -6.736309271   |
| 7 | 0.866660133  | -1.557998738  | -6.741145229   |
| 8 | 0.000000000  | -1.697601760  | -6.736309271   |

**j9..j17 (right / −X side, mirrored):**

| j  | x (ft)        | y (ft)        | z (ft)         |
|----|--------------:|--------------:|---------------:|
| 9  | 0.000000000   | 1.906902948   | -6.736309271   |
| 10 | -0.988868142  | 1.744160161   | -6.736309271   |
| 11 | -1.807795333  | 1.426000702   | -6.736309271   |
| 12 | -2.121420672  | 0.769885195   | -6.736309271   |
| 13 | -2.179186421  | 0.003517060   | -6.736309271   |
| 14 | -2.029360301  | -0.693772988  | -6.736056646   |
| 15 | -1.510095193  | -1.249845841  | -6.736309271   |
| 16 | -0.866660133  | -1.557998738  | -6.741145229   |
| 17 | 0.000000000   | -1.697601760  | -6.736309271   |

---

### 3.2 Fairing Tail – `Fairing_Tail_PM_bodies_test_Mesh.394`, station 2

- Recentered mesh → `part_x = 0.000000000` ft.
- Full loop has 8 verts → half‑ring has **n = 5** verts on +X/center side.
- Therefore:
  - `j0..4` = half_ring[0..4]  
  - `j5..8` = padded with half_ring[4] (bottom center, x = 0)

**j0..j8 (left / +X side):**

| j | x (ft)       | y (ft)         | z (ft)        |
|---|-------------:|---------------:|--------------:|
| 0 | 0.000000000  | 3.527887252    | 12.712093583  |
| 1 | 0.137568902  | 3.404363626    | 12.712093583  |
| 2 | 0.275137804  | 3.260252729    | 12.712093583  |
| 3 | 0.255282160  | 2.765039459    | 12.712093583  | ← off‑center dent  
| 4 | 0.000000000  | 2.769376729    | 12.712093583  | ← bottom center (x = 0)  
| 5 | 0.000000000  | 2.769376729    | 12.712093583  |
| 6 | 0.000000000  | 2.769376729    | 12.712093583  |
| 7 | 0.000000000  | 2.769376729    | 12.712093583  |
| 8 | 0.000000000  | 2.769376729    | 12.712093583  |

**j9..j17 (right / −X side, mirrored and padded):**

| j  | x (ft)         | y (ft)         | z (ft)        |
|----|---------------:|---------------:|--------------:|
| 9  | 0.000000000    | 3.527887252    | 12.712093583  |
| 10 | -0.137568902   | 3.404363626    | 12.712093583  |
| 11 | -0.275137804   | 3.260252729    | 12.712093583  |
| 12 | -0.255282160   | 2.765039459    | 12.712093583  |
| 13 | 0.000000000    | 2.769376729    | 12.712093583  |
| 14 | 0.000000000    | 2.769376729    | 12.712093583  |
| 15 | 0.000000000    | 2.769376729    | 12.712093583  |
| 16 | 0.000000000    | 2.769376729    | 12.712093583  |
| 17 | 0.000000000    | 2.769376729    | 12.712093583  |

**Padding rule (for any mesh with 5–8 half‑ring verts):**

- If `5 ≤ n < 9`, then:

  ```text
  j = 0..n-1 → half_ring[j]
  j = n..8   → half_ring[n-1]  (repeat last vertex, which must be on the centerline)
  ```

- Coded once, this handles all fairing‑style bodies and bodies that half rings have between 5 and 8 vertices.

---

### 3.3 LF Cowling – `LF_Cowling_Cylinder.001`, station 8

- Before centering, cowling is offset left.
- After centering, we store:
  - `part_x ≈ -6.320407026` ft.
- Full loop has 16 verts → half‑ring has **n = 9** verts.
- No padding required (`n = 9` → use all 9 directly).

**j0..j8 (left / +X side after centering):**

| j | x (ft)       | y (ft)        | z (ft)         |
|---|-------------:|--------------:|---------------:|
| 0 | 0.000000000  | 0.658018394   | -8.005623616   |
| 1 | 0.142604991  | 0.629652251   | -8.005623616   |
| 2 | 0.263500665  | 0.548874689   | -8.005623616   |
| 3 | 0.344278226  | 0.427979016   | -8.005623616   |
| 4 | 0.372644369  | 0.285374025   | -8.005623616   |
| 5 | 0.344278226  | 0.142769033   | -8.005623616   |
| 6 | 0.263500665  | 0.021873360   | -8.005623616   |
| 7 | 0.142604991  | -0.058904201  | -8.005623616   |
| 8 | 0.000000000  | -0.087270344  | -8.005623616   |

**j9..j17 (right / −X side):**

| j  | x (ft)         | y (ft)        | z (ft)         |
|----|---------------:|--------------:|---------------:|
| 9  | 0.000000000    | 0.658018394   | -8.005623616   |
| 10 | -0.142604991   | 0.629652251   | -8.005623616   |
| 11 | -0.263500665   | 0.548874689   | -8.005623616   |
| 12 | -0.344278226   | 0.427979016   | -8.005623616   |
| 13 | -0.372644369   | 0.285374025   | -8.005623616   |
| 14 | -0.344278226   | 0.142769033   | -8.005623616   |
| 15 | -0.263500665   | 0.021873360   | -8.005623616   |
| 16 | -0.142604991   | -0.058904201  | -8.005623616   |
| 17 | 0.000000000    | -0.087270344  | -8.005623616   |

---

### 3.4 RT Cowling – `RT_Cowling_Cylinder.002`, station 8

- Recentered to x = 0:
  - `part_x ≈ +6.320390622` ft.
- Same `n = 9`, so no padding.

**j0..j8 (left / +X side in local coordinates):**

| j | x (ft)       | y (ft)        | z (ft)         |
|---|-------------:|--------------:|---------------:|
| 0 | 0.000000000  | 0.658018394   | -8.005623616   |
| 1 | 0.142608272  | 0.629652251   | -8.005623616   |
| 2 | 0.263500665  | 0.548874689   | -8.005623616   |
| 3 | 0.344281507  | 0.427979016   | -8.005623616   |
| 4 | 0.372647650  | 0.285374025   | -8.005623616   |
| 5 | 0.344281507  | 0.142769033   | -8.005623616   |
| 6 | 0.263500665  | 0.021873360   | -8.005623616   |
| 7 | 0.142608272  | -0.058904201  | -8.005623616   |
| 8 | 0.000000000  | -0.087270344  | -8.005623616   |

**j9..j17 (right / −X side):**

| j  | x (ft)         | y (ft)        | z (ft)         |
|----|---------------:|--------------:|---------------:|
| 9  | 0.000000000    | 0.658018394   | -8.005623616   |
| 10 | -0.142608272   | 0.629652251   | -8.005623616   |
| 11 | -0.263500665   | 0.548874689   | -8.005623616   |
| 12 | -0.344281507   | 0.427979016   | -8.005623616   |
| 13 | -0.372647650   | 0.285374025   | -8.005623616   |
| 14 | -0.344281507   | 0.142769033   | -8.005623616   |
| 15 | -0.263500665   | 0.021873360   | -8.005623616   |
| 16 | -0.142608272   | -0.058904201  | -8.005623616   |
| 17 | 0.000000000    | -0.087270344  | -8.005623616   |

---

## 4. Summary of the generic padding rule (for `5 ≤ n ≤ 9`)

After splitting a station loop by X into a half‑ring of `n` vertices:

- If `n = 9` (e.g. 16‑vertex full rings like fuselage and cowlings):
  - Use all 9 directly: `j0..8 = half_ring[0..8]`
  - No padding.

- If `5 ≤ n < 9` (e.g. 8‑vertex full rings like fairings):
  - `j0..(n-1)` come from `half_ring[0..(n-1)]`
  - `j(n)..8` are padded using `half_ring[n-1]`
    - This must be the **bottom center** vertex at x = 0.

- In all cases:
  - `j9..17` are the mirror of `j0..8` in X.
  - Centerline entries are normalized to x = `0.000000000`.

Once this is coded, the winding is locked and works for:

- Fuselage
- Cowlings
- Fairing / tail cones
- Any body that obeys the “1 tip vertex, 1 tail vertex, mid loops 5–9 verts/half” rule.
