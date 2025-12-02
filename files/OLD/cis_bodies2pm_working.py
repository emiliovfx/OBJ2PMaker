from typing import List, Tuple, Dict, Any
import math
from collections import defaultdict
import os, sys
import subprocess


def resource_path(relative_path: str) -> str:
    """
    Resolve resource paths for both normal execution and PyInstaller .exe.
    """
    try:
        base_path = sys._MEIPASS     # PyInstaller temp folder
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


FT_PER_M = 3.28084

def compute_part_rad_from_rings(
    rings: List[List[Tuple[float, float, float]]],
    buffer_ft: float = 1.0,
) -> float:
    """
    Compute _part_rad for a body from its rings.

    Plane-Maker crops geometry if _part_rad is smaller than the max extent
    in x or y, so we take the max(|x|, |y|) over all vertices and add a buffer.

    Args:
        rings:     rings[i][j] = (x_ft, y_ft, z_ft)
        buffer_ft: safety margin in feet (default 1.0)

    Returns:
        part_rad_ft (float)
    """
    max_x = 0.0
    max_y = 0.0

    for ring in rings:
        for x_ft, y_ft, _ in ring:
            ax = abs(x_ft)
            ay = abs(y_ft)
            if ax > max_x:
                max_x = ax
            if ay > max_y:
                max_y = ay

    base_rad = max(max_x, max_y)
    return base_rad + buffer_ft

def print_body_header_PMstyle(bodies: List[Dict[str, Any]], body_index: int) -> None:
    """
    Print the body header lines that depend on our geometry:
      - _part_x
      - _part_y, _part_z (0 for now)
      - _part_rad
      - _r_dim
      - _s_dim
    """
    body = bodies[body_index]
    part_x_ft = body["part_x_ft"]
    part_rad_ft = body["part_rad_ft"]
    half_n_max = body["half_n_max"]
    rings = body["rings"]

    r_dim = 2 * half_n_max          # number of points per full ring
    s_dim = len(rings)  # PM uses station count - 1

    b = body_index

    print(f"P _body/{b}/_part_x {part_x_ft:.9f}")
    print(f"P _body/{b}/_part_y 0.000000000")
    print(f"P _body/{b}/_part_z 0.000000000")
    print(f"P _body/{b}/_part_rad {part_rad_ft:.9f}")
    print(f"P _body/{b}/_r_dim {r_dim:d}")
    print(f"P _body/{b}/_s_dim {s_dim:d}")

# -------------------------------------------------
# OBJ loading (all groups with faces)
# -------------------------------------------------

def load_all_groups_with_faces(obj_path: str) -> Dict[str, Dict[str, Any]]:
    """
    Load all groups from an OBJ file.

    For each group we build a *local* vertex array (only vertices referenced
    by that group's faces) and remap face indices to that local array.

    Returns:
        groups[group_name] = {
            "verts_m": [(x,y,z), ...],       # local verts
            "faces":   [[v_idx0,...], ...],  # faces using 0-based local indices
        }
    """
    # First pass: collect all global vertices (index = position in this list)
    all_verts: List[Tuple[float, float, float]] = []
    with open(obj_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("v "):
                _, xs, ys, zs = line.split()[:4]
                all_verts.append((float(xs), float(ys), float(zs)))

    # Second pass: for each group, collect faces as lists of *global* indices
    groups_faces_global: Dict[str, List[List[int]]] = {}
    current_group = None

    with open(obj_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            if line.startswith("g "):
                current_group = line.split(" ", 1)[1]
                groups_faces_global.setdefault(current_group, [])

            elif line.startswith("f ") and current_group is not None:
                parts = line.split()[1:]
                face: List[int] = []
                for token in parts:
                    v_str = token.split("/")[0]
                    vi = int(v_str) - 1  # OBJ 1-based -> 0-based
                    face.append(vi)
                groups_faces_global[current_group].append(face)

    # Build per-group local verts and remapped faces
    groups: Dict[str, Dict[str, Any]] = {}
    for gname, faces_global in groups_faces_global.items():
        used_global: set[int] = set()
        for face in faces_global:
            used_global.update(face)

        used_sorted = sorted(used_global)
        global_to_local = {gv: li for li, gv in enumerate(used_sorted)}

        local_verts = [all_verts[gv] for gv in used_sorted]
        local_faces = [[global_to_local[gv] for gv in face] for face in faces_global]

        groups[gname] = {
            "verts_m": local_verts,
            "faces": local_faces,
        }

    return groups



# -------------------------------------------------
# Topology helpers
# -------------------------------------------------

def build_vertex_adjacency(
    num_verts: int,
    faces: List[List[int]]
) -> List[List[int]]:
    """
    Build undirected vertex adjacency list from faces.
    """
    neighbors: List[set] = [set() for _ in range(num_verts)]

    for face in faces:
        n = len(face)
        if n < 2:
            continue
        for i in range(n):
            v0 = face[i]
            v1 = face[(i + 1) % n]
            if v0 == v1:
                continue
            neighbors[v0].add(v1)
            neighbors[v1].add(v0)

    return [list(nb) for nb in neighbors]


def compute_topological_layers(
    verts_m: List[Tuple[float, float, float]],
    neighbors: List[List[int]]
):
    """
    BFS from nose (min z) to get topological distance per vertex.
    Nose = min z, tail = max z.
    """
    z_values = [v[2] for v in verts_m]
    nose = min(range(len(verts_m)), key=lambda i: z_values[i])
    tail = max(range(len(verts_m)), key=lambda i: z_values[i])

    from collections import deque

    dist: Dict[int, int] = {nose: 0}
    q = deque([nose])

    while q:
        v = q.popleft()
        for nb in neighbors[v]:
            if nb not in dist:
                dist[nb] = dist[v] + 1
                q.append(nb)

    return dist, nose, tail


def build_station_vertex_groups(
    verts_m: List[Tuple[float, float, float]],
    neighbors: List[List[int]],
    max_stations: int = 20,
) -> List[List[int]]:
    """
    Use BFS distance from nose to define station vertex groups (rings).

    Assumptions:
      - 1 vertex at nose, 1 at tail.
      - Mid rings have 8..16 verts.
      - Total stations <= max_stations.
    """
    dist, nose, tail = compute_topological_layers(verts_m, neighbors)

    buckets: Dict[int, List[int]] = defaultdict(list)
    for v_idx, d in dist.items():
        buckets[d].append(v_idx)

    d_values = sorted(buckets.keys())
    d_min = min(d_values)
    assert d_min == 0

    # tail = max z
    z_values = [v[2] for v in verts_m]
    tail_candidate = max(range(len(verts_m)), key=lambda i: z_values[i])
    tail_d = dist[tail_candidate]
    tail_bucket = buckets[tail_d]

    stations: List[List[int]] = []

    # station 0: nose
    stations.append([nose])

    # mid stations
    for d in d_values:
        if d == 0 or d == tail_d:
            continue
        ring = buckets[d]
        n_ring = len(ring)
        if n_ring == 0:
            continue
        if not (8 <= n_ring <= 16):
            raise ValueError(
                f"Distance layer {d} has {n_ring} verts, expected 8..16."
            )
        stations.append(ring)

    # tail
    if len(tail_bucket) != 1:
        raise ValueError(
            f"Tail distance layer {tail_d} has {len(tail_bucket)} verts, expected 1."
        )
    stations.append(tail_bucket)

    if len(stations) > max_stations:
        raise ValueError(
            f"Too many stations ({len(stations)}) – exceeds max {max_stations}"
        )

    return stations


# -------------------------------------------------
# Winding / rings (topology-based)
# -------------------------------------------------

def build_pm_rings_for_mesh(
    verts_m: List[Tuple[float, float, float]],
    faces: List[List[int]],
):
    """
    Topology-based detection of stations + building PM rings (j=0..17).
    """
    num_verts = len(verts_m)
    if num_verts == 0:
        return 0.0, [], 0

    # recenter x
    xs = [v[0] for v in verts_m]
    min_x, max_x = min(xs), max(xs)
    center_x_m = (min_x + max_x) / 2.0
    part_x_ft = center_x_m * FT_PER_M
    verts_local = [(x - center_x_m, y, z) for (x, y, z) in verts_m]

    neighbors = build_vertex_adjacency(num_verts, faces)
    station_vertex_groups = build_station_vertex_groups(verts_local, neighbors)

    rings: List[List[Tuple[float, float, float]]] = []
    half_n_max = 0
    eps = 1e-5

    for station in station_vertex_groups:
        # tip / tail
        if len(station) == 1:
            idx = station[0]
            x_m, y_m, z_m = verts_local[idx]
            y_ft = y_m * FT_PER_M
            z_ft = z_m * FT_PER_M
            if abs(y_ft) < eps:
                y_ft = 0.0
            if abs(z_ft) < eps:
                z_ft = 0.0
            rings.append([(0.0, y_ft, z_ft)] * 18)
            continue

        # mid ring
        station_verts_m = [verts_local[idx] for idx in station]

        eps_split = 1e-5
        half_raw = [v for v in station_verts_m if v[0] >= -eps_split]
        n_half = len(half_raw)
        if not (5 <= n_half <= 9):
            raise ValueError(
                f"Station with {len(station_verts_m)} verts produced "
                f"half-ring count {n_half}, expected 5..9."
            )
        if n_half > half_n_max:
            half_n_max = n_half

        half_ft = []
        for (x_m, y_m, z_m) in half_raw:
            half_ft.append([x_m * FT_PER_M, y_m * FT_PER_M, z_m * FT_PER_M])

        eps_center = 1e-4
        center_indices = [
            i for i, (x_ft, y_ft, z_ft) in enumerate(half_ft)
            if abs(x_ft) < eps_center
        ]

        if len(center_indices) >= 2:
            cl = [(i, half_ft[i][1]) for i in center_indices]
            top_i = max(cl, key=lambda t: t[1])[0]
            bot_i = min(cl, key=lambda t: t[1])[0]
            top = half_ft[top_i]
            bottom = half_ft[bot_i]
            side = [half_ft[i] for i in range(len(half_ft)) if i not in {top_i, bot_i}]

            side_with_angle = []
            for x_ft, y_ft, z_ft in side:
                ang = math.atan2(y_ft, x_ft if abs(x_ft) > 1e-12 else 0.0)
                side_with_angle.append((x_ft, y_ft, z_ft, ang))
            side_with_angle.sort(key=lambda t: t[3], reverse=True)

            ordered = [top] + [
                [x_ft, y_ft, z_ft] for (x_ft, y_ft, z_ft, _) in side_with_angle
            ] + [bottom]
        else:
            side_with_angle = []
            for x_ft, y_ft, z_ft in half_ft:
                ang = math.atan2(y_ft, x_ft if abs(x_ft) > 1e-12 else 0.0)
                side_with_angle.append((x_ft, y_ft, z_ft, ang))
            side_with_angle.sort(key=lambda t: t[3], reverse=True)
            ordered = [[x_ft, y_ft, z_ft] for (x_ft, y_ft, z_ft, _) in side_with_angle]

        left_ring: List[Tuple[float, float, float]] = []
        for j in range(9):
            if j < len(ordered):
                x_ft, y_ft, z_ft = ordered[j]
            else:
                x_ft, y_ft, z_ft = ordered[-1]

            #x_ft = -x_ft

            #print(f'X axis value {x_ft}')

            if abs(x_ft) < eps:
                x_ft = 0.0
            if abs(y_ft) < eps:
                y_ft = 0.0
            if abs(z_ft) < eps:
                z_ft = 0.0
            left_ring.append((x_ft, y_ft, z_ft))

        ring: List[Tuple[float, float, float]] = [None] * 18
        for j_left in range(9):
            x_left, y_left, z_left = left_ring[j_left]
            ring[j_left] = (x_left, y_left, z_left)
            x_right = -x_left
            if abs(x_right) < eps:
                x_right = 0.0
            ring[9 + j_left] = (x_right, y_left, z_left)

        rings.append(ring)

    return part_x_ft, rings, half_n_max


# -------------------------------------------------
# Build bodies from OBJ using new method
# -------------------------------------------------

def build_bodies_from_obj(obj_path: str) -> List[Dict[str, Any]]:
    """
    Build all bodies from an OBJ file using topology-based rings.
    Each body: { body_index, group_name, part_x_ft, rings, half_n_max }
    """
    groups = load_all_groups_with_faces(obj_path)

    # Optional: lock specific mapping order if desired
    order = []

    # Try to enforce fuselage -> 0, LF cowling -> 1, RT cowling -> 2, others after
    priority_names = [
        "Fuselage_Chieftain_fuse_only_Mesh.0001",
        "LF_Cowling_Cylinder.001",
        "RT_Cowling_Cylinder.002",
    ]
    for name in priority_names:
        if name in groups and name not in order:
            order.append(name)

    # Add any remaining groups in file order
    for name in groups.keys():
        if name not in order:
            order.append(name)

    bodies: List[Dict[str, Any]] = []

    for body_index, name in enumerate(order):
        verts_m = groups[name]["verts_m"]
        faces   = groups[name]["faces"]

        # Skip groups that clearly are NOT valid bodies
        # Design rule: a true body must have at least 10 verts.
        if not faces:
            # No faces, nothing to process
            continue

        if len(verts_m) < 10:
            # This will skip wings/flat planes and tiny helper meshes
            print(f"[INFO] Skipping group '{name}' for bodies "
                  f"(only {len(verts_m)} verts).")
            continue

        # Normal body processing
        part_x_ft, rings, half_n_max = build_pm_rings_for_mesh(verts_m, faces)
        if not rings:
            continue

        part_rad_ft = compute_part_rad_from_rings(rings, buffer_ft=1.0)

        bodies.append(
            {
                "body_index" : body_index,
                "group_name" : name,
                "part_x_ft"  : part_x_ft,
                "part_rad_ft": part_rad_ft,
                "rings"      : rings,
                "half_n_max" : half_n_max,
            }
        )

    return bodies



from typing import List, Dict, Any, Tuple

def build_body_block_lines(
    bodies: List[Dict[str, Any]],
    body_index: int,
    total_stations: int = 20,
    points_per_ring: int = 18,
) -> List[str]:
    """
    Build the COMPLETE Plane-Maker body block for one body:

        - _part_x, _part_y, _part_z
        - _part_rad
        - _r_dim, _s_dim
        - all _geo_xyz lines in PM's print order, padded with zeros.

    Returns:
        lines: list of strings ready to write into an .acf
    """
    body = bodies[body_index]
    part_x_ft = body["part_x_ft"]
    part_rad_ft = body["part_rad_ft"]
    half_n_max = body["half_n_max"]
    rings = body["rings"]

    b = body_index

    # Header params
    r_dim = 2 * half_n_max  # number of points per full ring
    s_dim = len(rings)  # number of stations

    lines: List[str] = []

    # --- Header block ---
    lines.append(f"P _body/{b}/_part_x {part_x_ft:.9f}")
    lines.append(f"P _body/{b}/_part_y 0.000000000")
    lines.append(f"P _body/{b}/_part_z 0.000000000")
    lines.append(f"P _body/{b}/_part_rad {part_rad_ft:.9f}")
    lines.append(f"P _body/{b}/_r_dim {r_dim:d}")
    lines.append(f"P _body/{b}/_s_dim {s_dim:d}")
    lines.append("")  # blank line for readability

    # --- Prepare padded rings grid for geo ---
    padded: List[List[Tuple[float, float, float]]] = []

    # Real rings first
    for i in range(min(len(rings), total_stations)):
        ring = list(rings[i])
        if len(ring) < points_per_ring:
            ring += [(0.0, 0.0, 0.0)] * (points_per_ring - len(ring))
        padded.append(ring)

    # Extra stations (up to total_stations) as all zeros
    for i in range(len(padded), total_stations):
        padded.append([(0.0, 0.0, 0.0)] * points_per_ring)

    # PM's station and j print order
    i_order = _pm_i_print_order(total_stations)
    j_order = _pm_j_print_order(points_per_ring)

    # --- _geo_xyz block in PM order ---
    for i in i_order:
        ring = padded[i]
        for j in j_order:
            x_ft, y_ft, z_ft = ring[j]
            lines.append(f"P _body/{b}/_geo_xyz/{i},{j},0 {x_ft:.9f}")
            lines.append(f"P _body/{b}/_geo_xyz/{i},{j},1 {y_ft:.9f}")
            lines.append(f"P _body/{b}/_geo_xyz/{i},{j},2 {z_ft:.9f}")

    return lines

def scan_obj_mesh_names(obj_path: str) -> List[str]:
    """
    Scan the OBJ file and return a list of group/object names
    (meshes) in the order they appear.
    """
    names: List[str] = []
    with open(obj_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if line.startswith("g ") or line.startswith("o "):
                name = line.split(maxsplit=1)[1].strip()
                if name and name not in names:
                    names.append(name)
    return names


def generate_bodies_and_rewrite_acf(
    obj_path: str,
    acf_in_path: str,
    acf_out_path: str,
    template_path: str,
    mesh_rows: List[Dict[str, Any]],
    log_fn,
) -> None:
    """
    obj_path: path to OBJ
    acf_in_path: original .acf to read
    acf_out_path: new .acf to write
    template_path: zeroed body template with _body/b/...
    mesh_rows: list of dicts with:
        {
          "mesh_name": str,
          "body_index": int,
          "pm_name": str,
        }
    log_fn: function(str) -> None for GUI logging
    """
    log = log_fn

    # Build geometry for all meshes found in OBJ
    try:
        bodies = build_bodies_from_obj(obj_path)
    except Exception as e:
        log(f"[ERROR] Failed to build bodies from OBJ: {e}")
        return

    # Map by group_name
    by_name = {b["group_name"]: b for b in bodies}

    # Build mapping from body index to body data
    bodies_by_index: Dict[int, Dict[str, Any]] = {}

    for row in mesh_rows:
        mesh_name = row["mesh_name"]
        body_idx = row["body_index"]
        pm_name = row["pm_name"].strip() or mesh_name

        if mesh_name not in by_name:
            log(f"[WARN] Mesh '{mesh_name}' not found in processed bodies, skipping.")
            continue

        if body_idx in bodies_by_index:
            log(f"[WARN] Duplicate body index {body_idx} (mesh '{mesh_name}'), skipping this one.")
            continue

        src_body = by_name[mesh_name]
        # Shallow copy so we don't mutate the shared dict
        body_copy = dict(src_body)
        body_copy["body_index"] = body_idx
        body_copy["pm_name"] = pm_name
        bodies_by_index[body_idx] = body_copy

    if not bodies_by_index:
        log("[ERROR] No valid bodies assigned; nothing to write.")
        return

    # Ensure indices are 0..N without gaps
    indices = sorted(bodies_by_index.keys())
    expected = list(range(len(indices)))
    if indices != expected:
        log(f"[ERROR] Body indices must be contiguous 0..N without gaps. Got {indices}.")
        return

    # Create ordered list where list index == body_index
    ordered_bodies = [bodies_by_index[i] for i in indices]

    # Generate all body blocks
    all_lines: List[str] = []
    for i in range(len(ordered_bodies)):
        ordered_bodies[i]["body_index"] = i   # make sure it's consistent
        body_lines = build_body_block_from_template(
            ordered_bodies, i, template_path
        )
        # No extra blank lines between bodies to preserve structure
        all_lines.extend(body_lines)

    # Rewrite ACF
    try:
        rewrite_acf_bodies(acf_in_path, acf_out_path, all_lines)
    except Exception as e:
        log(f"[ERROR] Failed to rewrite ACF: {e}")
        return

    log(f"[OK] Wrote new bodies into '{acf_out_path}'.")

# -------------------------------------------------
# QC helpers (from previous answer)
# -------------------------------------------------

def query_body_station_ring(
    bodies: List[Dict[str, Any]],
    body_index: int,
    station_i: int,
    ring_j: int
) -> Tuple[float, float, float]:
    body = bodies[body_index]
    rings = body["rings"]
    ring = rings[station_i]
    return ring[ring_j]


def print_bodies_summary(bodies: List[Dict[str, Any]]) -> None:
    for b in bodies:
        print(
            f"body/{b['body_index']}: group='{b['group_name']}', "
            f"stations={len(b['rings'])}, half_n_max={b['half_n_max']}, "
            f"part_x_ft={b['part_x_ft']:.6f}"
        )


def print_station_z_list(bodies: List[Dict[str, Any]], body_index: int) -> None:
    body = bodies[body_index]
    rings = body["rings"]
    print(f"body/{body_index} ('{body['group_name']}') station z positions:")
    for i, ring in enumerate(rings):
        z_ft = ring[0][2]
        print(f"  i={i:2d}: z={z_ft:.9f}")


def print_ring(bodies: List[Dict[str, Any]], body_index: int, station_i: int) -> None:
    body = bodies[body_index]
    ring = body["rings"][station_i]
    print(
        f"body/{body_index} ('{body['group_name']}'), "
        f"station i={station_i}, z={ring[0][2]:.9f}"
    )
    for j, (x_ft, y_ft, z_ft) in enumerate(ring):
        print(f"  j={j:2d}:  x={x_ft:.9f}  y={y_ft:.9f}  z={z_ft:.9f}")


def print_station_PMstyle(bodies: List[Dict[str, Any]], body_index: int, station_i: int) -> None:
    body = bodies[body_index]
    ring = body["rings"][station_i]
    print(
        f"body/{body_index} ('{body['group_name']}'), "
        f"station i={station_i}, z={ring[0][2]:.9f}"
    )
    for j, (x_ft, y_ft, z_ft) in enumerate(ring):
        print(f"P _body/{body_index}/_geo_xyz/{station_i},{j},0 {x_ft:.9f}")
        print(f"P _body/{body_index}/_geo_xyz/{station_i},{j},1 {y_ft:.9f}")
        print(f"P _body/{body_index}/_geo_xyz/{station_i},{j},2 {z_ft:.9f}")


def _pm_i_print_order(total_stations: int = 20) -> List[int]:
    order = []
    if total_stations > 0:
        order.append(0)
    if total_stations > 1:
        order.append(1)
    for i in range(10, total_stations):
        order.append(i)
    for i in range(2, 10):
        if i < total_stations and i not in order:
            order.append(i)
    return order


def _pm_j_print_order(points_per_ring: int = 18) -> List[int]:
    order = []
    if points_per_ring > 0:
        order.append(0)
    if points_per_ring > 1:
        order.append(1)
    for j in range(10, points_per_ring):
        order.append(j)
    for j in range(2, 10):
        if j < points_per_ring and j not in order:
            order.append(j)
    return order


def print_body_geo_PMstyle_ordered(
    bodies: List[Dict[str, Any]],
    body_index: int,
    total_stations: int = 20,
    points_per_ring: int = 18,
    write_to_file: bool = True,
) -> None:
    body = bodies[body_index]
    rings = body["rings"]

    # --- header with _part_x, _part_rad, etc. ---
    # (only printed to console; file below will still be geo-only unless you want it there too)
    print_body_header_PMstyle(bodies, body_index)
    print()

    # ... existing code that pads rings and builds `lines` for _geo_xyz ...
    padded: List[List[Tuple[float, float, float]]] = []
    for i in range(min(len(rings), total_stations)):
        ring = list(rings[i])
        if len(ring) < points_per_ring:
            ring += [(0.0, 0.0, 0.0)] * (points_per_ring - len(ring))
        padded.append(ring)
    for i in range(len(padded), total_stations):
        padded.append([(0.0, 0.0, 0.0)] * points_per_ring)

    i_order = _pm_i_print_order(total_stations)
    j_order = _pm_j_print_order(points_per_ring)

    lines = []
    for i in i_order:
        ring = padded[i]
        for j in j_order:
            x_ft, y_ft, z_ft = ring[j]
            lines.append(f"P _body/{body_index}/_geo_xyz/{i},{j},0 {x_ft:.9f}")
            lines.append(f"P _body/{body_index}/_geo_xyz/{i},{j},1 {y_ft:.9f}")
            lines.append(f"P _body/{body_index}/_geo_xyz/{i},{j},2 {z_ft:.9f}")

    if write_to_file:
        filename = f"body_{body_index}_output_block.txt"
        with open(filename, "w") as f:
            # If you want header + geo in the file, uncomment the header writes too:
            # header_lines = []
            # header_lines.append(f"P _body/{body_index}/_part_x {body['part_x_ft']:.9f}")
            # header_lines.append(f"P _body/{body_index}/_part_y 0.000000000")
            # header_lines.append(f"P _body/{body_index}/_part_z 0.000000000")
            # header_lines.append(f"P _body/{body_index}/_part_rad {body['part_rad_ft']:.9f}")
            # header_lines.append(f"P _body/{body_index}/_r_dim {2 * body['half_n_max']}")
            # header_lines.append(f"P _body/{body_index}/_s_dim {max(len(rings) - 1, 0)}")
            #
            # f.write("\n".join(header_lines) + "\n")

            f.write("\n".join(lines))
        print(f"Saved output block to {filename}")



def debug_station_z_spread(
    bodies: List[Dict[str, Any]], body_index: int, z_tol: float = 0.01
) -> None:
    body = bodies[body_index]
    rings = body["rings"]
    print(f"Body {body_index} ('{body['group_name']}') – station z spread:")
    for i, ring in enumerate(rings):
        zs = [z for (_, _, z) in ring]
        z_min = min(zs)
        z_max = max(zs)
        z_mean = sum(zs) / len(zs)
        z_range = z_max - z_min
        flag = "  <-- POSSIBLE MIXED RING" if z_range > z_tol else ""
        print(
            f"i={i:2d}: z_mean={z_mean:9.6f}, "
            f"z_min={z_min:9.6f}, z_max={z_max:9.6f}, "
            f"Δz={z_range:9.6f}{flag}"
        )

def write_body_block_to_file(
    bodies: List[Dict[str, Any]],
    body_index: int,
    total_stations: int = 20,
    points_per_ring: int = 18,
    filename: str | None = None,
) -> None:
    """
    Build the full body block for body_index and write it to a .txt file.

    If filename is None, uses body_{body_index}_block.txt
    """
    if filename is None:
        filename = f"body_{body_index}_block.txt"

    lines = build_body_block_lines(
        bodies,
        body_index,
        total_stations=total_stations,
        points_per_ring=points_per_ring,
    )

    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Saved full body block for body/{body_index} to {filename}")


def print_body_block_PMstyle(
    bodies: List[Dict[str, Any]],
    body_index: int,
    total_stations: int = 20,
    points_per_ring: int = 18,
) -> None:
    """
    Print the full body block (header + _geo_xyz) to the console.
    """
    lines = build_body_block_lines(
        bodies,
        body_index,
        total_stations=total_stations,
        points_per_ring=points_per_ring,
    )
    for line in lines:
        print(line)

# -------------------------------------------------
# Full Body Block Builder
# -------------------------------------------------
import re
from typing import List, Dict, Any, Tuple

GEO_RE = re.compile(
    r"^P _body/[^/]+/_geo_xyz/(\d+),(\d+),(\d+)\s+(-?\d+\.\d+)$"
)

def build_body_block_from_template(
    bodies: List[Dict[str, Any]],
    body_index: int,
    template_path: str,
) -> List[str]:
    """
    Build a COMPLETE _body/<body_index> block by taking a zeroed template
    (with '_body/b/...') and filling it with our parameters + geo_xyz values.

    The output is a 1:1 clone of the template's line structure and order.
    """
    body = bodies[body_index]
    part_x_ft = body["part_x_ft"]
    part_rad_ft = body["part_rad_ft"]
    half_n_max = body["half_n_max"]
    rings = body["rings"]
    pm_name = body.get("pm_name", body.get("group_name", f"Body {body_index}"))

    b = body_index

    # --- Load template lines ---
    with open(template_path, "r", encoding="utf-8") as f:
        template_lines = [ln.rstrip("\n") for ln in f]

    # --- Infer stations / j dimension from template geo lines ---
    max_i = 0
    max_j = 0
    for line in template_lines:
        m = GEO_RE.match(line)
        if not m:
            continue
        i = int(m.group(1))
        j = int(m.group(2))
        if i > max_i:
            max_i = i
        if j > max_j:
            max_j = j

    total_stations = max_i + 1
    points_per_ring = max_j + 1

    # --- Pad our rings to that grid ---
    padded: List[List[Tuple[float, float, float]]] = []

    for i in range(min(len(rings), total_stations)):
        ring = list(rings[i])
        if len(ring) < points_per_ring:
            ring += [(0.0, 0.0, 0.0)] * (points_per_ring - len(ring))
        padded.append(ring)

    for i in range(len(padded), total_stations):
        padded.append([(0.0, 0.0, 0.0)] * points_per_ring)

    # --- Dimension parameters from our geometry ---
    r_dim = 2 * half_n_max        # number of points per full ring
    s_dim = len(rings)            # number of stations

    out_lines: List[str] = []

    for line in template_lines:
        stripped = line.strip()

        # 1) geo_xyz lines: replace with our coordinates
        m = GEO_RE.match(stripped)
        if m:
            i = int(m.group(1))
            j = int(m.group(2))
            k = int(m.group(3))

            x_ft, y_ft, z_ft = padded[i][j]
            if k == 0:
                val = x_ft
            elif k == 1:
                val = y_ft
            else:
                val = z_ft

            out_lines.append(
                f"P _body/{b}/_geo_xyz/{i},{j},{k} {val:.9f}"
            )
            continue

        # 2) header params we control
        if stripped.startswith("P _body/b/_part_x"):
            out_lines.append(f"P _body/{b}/_part_x {part_x_ft:.9f}")
            continue
        if stripped.startswith("P _body/b/_part_y"):
            out_lines.append(f"P _body/{b}/_part_y 0.000000000")
            continue
        if stripped.startswith("P _body/b/_part_z"):
            out_lines.append(f"P _body/{b}/_part_z 0.000000000")
            continue
        if stripped.startswith("P _body/b/_part_rad"):
            out_lines.append(f"P _body/{b}/_part_rad {part_rad_ft:.9f}")
            continue
        if stripped.startswith("P _body/b/_r_dim"):
            out_lines.append(f"P _body/{b}/_r_dim {r_dim:d}")
            continue
        if stripped.startswith("P _body/b/_s_dim"):
            out_lines.append(f"P _body/{b}/_s_dim {s_dim:d}")
            continue
        if stripped.startswith("P _body/b/_descrip"):
            out_lines.append(f"P _body/{b}/_descrip {pm_name}")
            continue

        # 3) Any other _body/b line: just swap /b/ -> /<index>/, keep value
        if "_body/b/" in stripped:
            out_lines.append(
                stripped.replace("_body/b/", f"_body/{b}/")
            )
            continue

        # 4) Non-body lines or blanks: preserve as-is
        out_lines.append(line)

    return out_lines

def rewrite_acf_bodies(
    acf_in_path: str,
    acf_out_path: str,
    new_body_lines: List[str],
) -> None:
    """
    Read an existing .acf, strip all P _body lines between PROPERTIES_BEGIN
    and PROPERTIES_END, and reinsert our new full body block at the same
    position where the old block started.
    """
    with open(acf_in_path, "r", encoding="utf-8") as f:
        lines = [ln.rstrip("\n") for ln in f]

    prop_begin = None
    prop_end = None

    for idx, line in enumerate(lines):
        if line.strip() == "PROPERTIES_BEGIN":
            prop_begin = idx
        elif line.strip() == "PROPERTIES_END":
            prop_end = idx
            break

    if prop_begin is None or prop_end is None or prop_end <= prop_begin:
        raise RuntimeError("Could not find valid PROPERTIES_BEGIN/END block in ACF.")

    # Find first and last P _body lines inside PROPERTIES block
    body_start = None
    body_end = None
    for idx in range(prop_begin + 1, prop_end):
        if lines[idx].lstrip().startswith("P _body/"):
            if body_start is None:
                body_start = idx
            body_end = idx

    # If no existing bodies, insert just after PROPERTIES_BEGIN
    if body_start is None:
        body_start = prop_begin + 1
        body_end = body_start - 1  # so slice is empty

    # Build new lines: everything before body_start, then our bodies, then the rest
    new_lines: List[str] = []
    new_lines.extend(lines[:body_start])
    new_lines.extend(new_body_lines)
    new_lines.extend(lines[body_end + 1:])

    with open(acf_out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(new_lines))


def write_body_block_from_template_to_file(
    bodies: List[Dict[str, Any]],
    body_index: int,
    template_path: str = "body_block_template_zeroed.txt",
    filename: str | None = None,
) -> None:
    """
    Build and write a full body block to disk using the given template.
    """
    if filename is None:
        filename = f"body_{body_index}_full_block.txt"

    lines = build_body_block_from_template(bodies, body_index, template_path)

    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Saved full body block for body/{body_index} to {filename}")

#-------------------------------------------------
# GUI BLOCK
# ---------------------------------------------------

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

class OBJ2PMBodiesGUI(tk.Tk):
    def __init__(self, template_path: str):
        super().__init__()
        self.title("JSFS CIS OBJ2PM Bodies Generator")
        self.geometry("900x600")

        self.template_path = template_path

        self.acf_path_var = tk.StringVar()
        self.obj_path_var = tk.StringVar()
        self.out_name_var = tk.StringVar()

        self.mesh_rows_widgets = []   # list of dicts: {"mesh_name", "idx_entry", "name_entry"}

        self._build_ui()

    # ---------- UI layout ----------
    def _build_ui(self):
        # --- TOP AREA: ACF + OBJ file selection ---
        top_frame = tk.Frame(self)
        top_frame.pack(fill="x", pady=5, padx=5)

        # ACF
        tk.Label(top_frame, text=".acf file:").grid(row=0, column=0, sticky="w", pady=2)
        tk.Button(top_frame, text="Browse...", command=self.browse_acf).grid(row=0, column=1, padx=5)
        tk.Label(top_frame, textvariable=self.acf_path_var, anchor="w").grid(row=0, column=2, sticky="w")

        # OBJ
        tk.Label(top_frame, text=".obj file:").grid(row=1, column=0, sticky="w", pady=2)
        tk.Button(top_frame, text="Browse...", command=self.browse_obj).grid(row=1, column=1, padx=5)
        tk.Label(top_frame, textvariable=self.obj_path_var, anchor="w").grid(row=1, column=2, sticky="w")

        # Output ACF name
        tk.Label(top_frame, text="New .acf name:").grid(row=2, column=0, sticky="w", pady=2)
        tk.Entry(top_frame, textvariable=self.out_name_var, width=40).grid(row=2, column=2, sticky="w")

        # --- MAIN SECTION WITH LEFT SIDEBAR + MESH TABLE ---
        main_frame = tk.Frame(self)
        main_frame.pack(fill="both", expand=True)

        # LEFT TOOLBAR
        left_tools_frame = tk.Frame(main_frame)
        left_tools_frame.pack(side="left", fill="y", padx=8, pady=5)

        tk.Button(left_tools_frame, text="Scan OBJ Meshes",
                  height=2, width=18,
                  command=self.scan_obj_meshes).pack(pady=5)

        tk.Button(left_tools_frame, text="Run",
                  height=2, width=18,
                  command=self.run_process).pack(pady=5)

        # MESH TABLE AREA (scrollable)
        mid_frame = tk.LabelFrame(main_frame, text="Meshes → Body index + PM body name")
        mid_frame.pack(side="left", fill="both", expand=True, padx=5, pady=5)

        canvas = tk.Canvas(mid_frame)
        canvas.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(mid_frame, orient="vertical", command=canvas.yview)
        scrollbar.pack(side="right", fill="y")

        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        self.mesh_frame = tk.Frame(canvas)
        canvas.create_window((0, 0), window=self.mesh_frame, anchor="nw")

        # HEADER ROW
        hdr = tk.Frame(self.mesh_frame)
        hdr.pack(fill="x")
        tk.Label(hdr, text="Mesh name", width=40, anchor="w").grid(row=0, column=0, padx=2)
        tk.Label(hdr, text="Body index", width=10, anchor="w").grid(row=0, column=1, padx=2)
        tk.Label(hdr, text='PM body name', width=30, anchor="w").grid(row=0, column=2, padx=2)

        # LOG WINDOW AT BOTTOM
        log_frame = tk.LabelFrame(self, text="Log")
        log_frame.pack(fill="both", expand=False, padx=5, pady=5)

        self.log_text = tk.Text(log_frame, height=8, wrap="word")
        self.log_text.pack(fill="both", expand=True)

        # COPYRIGHT + VERSION FOOTER
        footer_frame = tk.Frame(self)
        footer_frame.pack(fill="x", pady=(2, 6))

        tk.Label(
            footer_frame,
            text="© 2025 Emilio Hernandez / Capt. Iceman — All Rights Reserved — v0.1 Alpha",
            anchor="center",
            font=("Arial", 9),
            fg="#555555"
        ).pack(fill="x")

    # ---------- File browsing ----------
    def browse_acf(self):
        path = filedialog.askopenfilename(
            filetypes=[("X-Plane ACF", "*.acf"), ("All files", "*.*")]
        )
        if not path:
            return
        self.acf_path_var.set(os.path.basename(path))
        self._acf_full_path = path

        # derive new acf name if not set
        base = os.path.basename(path)
        root, ext = os.path.splitext(base)
        self.out_name_var.set(root + "_bodies" + ext)

    def browse_obj(self):
        path = filedialog.askopenfilename(
            filetypes=[("Wavefront OBJ", "*.obj"), ("All files", "*.*")]
        )
        if not path:
            return
        self.obj_path_var.set(os.path.basename(path))
        self._obj_full_path = path

    # ---------- Logging ----------
    def log(self, msg: str):
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.update_idletasks()

    # ---------- Scan meshes ----------
    def scan_obj_meshes(self):
        self.mesh_rows_widgets.clear()
        for child in self.mesh_frame.winfo_children():
            if isinstance(child, tk.Frame) and child is not self.mesh_frame.winfo_children()[0]:
                child.destroy()

        obj_path = getattr(self, "_obj_full_path", None)
        if not obj_path:
            messagebox.showerror("Error", "Please select a .obj file first.")
            return

        try:
            mesh_names = scan_obj_mesh_names(obj_path)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to scan OBJ: {e}")
            return

        self.log(f"[INFO] Found {len(mesh_names)} mesh groups in OBJ.")

        # Default index assignment logic
        next_idx = 0
        used_indices = set()

        def default_index_for_name(name: str) -> int:
            nonlocal next_idx
            lname = name.lower()
            if "fuselage" in lname:
                return 0
            if lname.startswith("lf_cowling") or lname.startswith("lf-") or "lf_cowling" in lname:
                return 1
            if lname.startswith("rt_cowling") or lname.startswith("rt-") or "rt_cowling" in lname:
                return 2
            # else: sequential
            while next_idx in used_indices:
                next_idx += 1
            return next_idx

        for name in mesh_names:
            row = tk.Frame(self.mesh_frame)
            row.pack(fill="x", pady=1)

            # Mesh label
            tk.Label(row, text=name, width=40, anchor="w").grid(row=0, column=0, padx=2)

            # Body index entry
            idx_entry = tk.Entry(row, width=6)
            # Default index
            idx = default_index_for_name(name)
            used_indices.add(idx)
            idx_entry.insert(0, str(idx))
            idx_entry.grid(row=0, column=1, padx=2)

            # PM body name entry
            name_entry = tk.Entry(row, width=30)
            # Default PM name: use something nicer for fuselage/cowlings
            lname = name.lower()
            if "fuselage" in lname:
                pm_default = "Fuselage"
            elif "lf_cowling" in lname:
                pm_default = "Left Cowling"
            elif "rt_cowling" in lname:
                pm_default = "Right Cowling"
            else:
                pm_default = name
            name_entry.insert(0, pm_default)
            name_entry.grid(row=0, column=2, padx=2)

            self.mesh_rows_widgets.append(
                {
                    "mesh_name": name,
                    "idx_entry": idx_entry,
                    "name_entry": name_entry,
                }
            )

    # ---------- Run process ----------
    def run_process(self):
        acf_path = getattr(self, "_acf_full_path", None)
        obj_path = getattr(self, "_obj_full_path", None)
        out_name = self.out_name_var.get().strip()

        if not acf_path or not obj_path:
            messagebox.showerror("Error", "Please select both .acf and .obj files.")
            return

        if not out_name:
            messagebox.showerror("Error", "Please specify an output .acf name.")
            return

        acf_dir = os.path.dirname(acf_path)
        acf_out_path = os.path.join(acf_dir, out_name)

        # Build mesh_rows from GUI
        mesh_rows = []
        for row in self.mesh_rows_widgets:
            mesh_name = row["mesh_name"]
            try:
                body_idx = int(row["idx_entry"].get().strip())
            except ValueError:
                self.log(f"[WARN] Invalid body index for mesh '{mesh_name}', skipping.")
                continue
            pm_name = row["name_entry"].get()
            mesh_rows.append(
                {
                    "mesh_name": mesh_name,
                    "body_index": body_idx,
                    "pm_name": pm_name,
                }
            )

        if not mesh_rows:
            messagebox.showerror("Error", "No valid mesh mappings. Check body indices.")
            return

        self.log("[INFO] Starting bodies generation and ACF rewrite...")
        generate_bodies_and_rewrite_acf(
            obj_path=obj_path,
            acf_in_path=acf_path,
            acf_out_path=acf_out_path,
            template_path=self.template_path,
            mesh_rows=mesh_rows,
            log_fn=self.log,
        )
        self.log("[INFO] Done.")

# -------------------------------------------------
# Main QC runner (patched to use new method)
# -------------------------------------------------

if __name__ == "__main__":
    # Adjust this path to where your zeroed template lives
    TEMPLATE_PATH = "Templates/body_block_template_zeroed.txt"

    app = OBJ2PMBodiesGUI(template_path=TEMPLATE_PATH)
    app.mainloop()


