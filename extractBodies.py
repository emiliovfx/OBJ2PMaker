# file: PM_Importer_alpha_centered_bodyindex.py
#!/usr/bin/env python3
from __future__ import annotations
from typing import List, Tuple, Dict, Set
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

FT_PER_M = 3.28084

# --------------------------- IO & parsing ---------------------------

def load_obj_groups(path: str) -> Dict[str, List[Tuple[float, float, float]]]:
    verts: List[Tuple[float, float, float]] = []
    from collections import defaultdict
    group_to_indices: Dict[str, Set[int]] = defaultdict(set)
    current_group = "default"
    group_to_indices[current_group]
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            if s.startswith("v "):
                parts = s.split()
                if len(parts) >= 4:
                    try:
                        x = float(parts[1]); y = float(parts[2]); z = float(parts[3])
                        verts.append((x, y, z))
                    except ValueError:
                        pass
            elif s.startswith(("g ", "o ")):
                parts = s.split(maxsplit=1)
                current_group = (parts[1].strip() if len(parts) == 2 and parts[1].strip() else "unnamed")
                group_to_indices[current_group]
            elif s.startswith("f "):
                if not verts:
                    continue
                parts = s.split()[1:]
                for token in parts:
                    v_str = token.split("/")[0]
                    if not v_str:
                        continue
                    try:
                        vidx = int(v_str) - 1
                    except ValueError:
                        continue
                    if 0 <= vidx < len(verts):
                        group_to_indices[current_group].add(vidx)
    groups: Dict[str, List[Tuple[float, float, float]]] = {}
    for gname, idxs in group_to_indices.items():
        if not idxs:
            continue
        groups[gname] = [verts[i] for i in sorted(idxs)]
    return groups

def read_target_dims_from_acf(acf_lines: List[str], body_index: int) -> Tuple[int, int]:
    i_count = j_count = None
    pi = f"P _body/{body_index}/_locked/i_count"
    pj = f"P _body/{body_index}/_locked/j_count"
    for s in acf_lines:
        t = s.strip()
        if t.startswith(pi):
            try: i_count = int(t.split()[-1])
            except: pass
        elif t.startswith(pj):
            try: j_count = int(t.split()[-1])
            except: pass
        if i_count is not None and j_count is not None:
            break
    if i_count is None: i_count = 20
    if j_count is None: j_count = 18
    return i_count, j_count

# ----------------------- Centering utilities -----------------------

def compute_center_x(verts: List[Tuple[float, float, float]]) -> float:
    if not verts:
        return 0.0
    xs = [x for (x, _y, _z) in verts]
    return (min(xs) + max(xs)) / 2.0

def recenter_vertices_x(verts: List[Tuple[float, float, float]], center_x: float) -> List[Tuple[float, float, float]]:
    if abs(center_x) < 1e-12:
        return verts[:]
    return [(x - center_x, y, z) for (x, y, z) in verts]

# --------------------- Stationing (Z-cluster) ----------------------

def build_stations_from_geometry(
    verts: List[Tuple[float, float, float]],
    verts_per_loop: int,
    with_tip_tail: bool = True,
) -> List[List[Tuple[float, float, float]]]:
    if not verts:
        return []
    v_sorted = sorted(verts, key=lambda v: v[2])  # by Z asc
    if len(v_sorted) < (1 + verts_per_loop + 1):
        return [v_sorted[:]]
    tip  = [v_sorted[0]]
    tail = [v_sorted[-1]]
    middle = v_sorted[1:-1]
    stations: List[List[Tuple[float, float, float]]] = []
    if with_tip_tail:
        stations.append(tip)
    off = 0; n_mid = len(middle)
    while off < n_mid:
        stations.append(middle[off: off + verts_per_loop])
        off += verts_per_loop
    if with_tip_tail:
        stations.append(tail)
    return stations

def pad_or_truncate_stations(stations: List[List[Tuple[float, float, float]]], target_i: int) -> List[List[Tuple[float, float, float]]]:
    if len(stations) == target_i:
        return stations
    if len(stations) > target_i:
        return stations[:target_i]
    out = stations[:]
    while len(out) < target_i:
        out.append([])  # empty → xyz=0
    return out

# ----------------- Geometry emission (winding) ---------------------

def generate_geo_xyz_literal_from_stations(
    stations_mesh: List[List[Tuple[float, float, float]]],
    body_index: int,
    target_i: int,
    target_j: int,
    with_tip_tail: bool = True,
) -> List[str]:
    stations = pad_or_truncate_stations(stations_mesh, target_i)
    lines: List[str] = []
    J = max(2, int(target_j))
    half = J // 2
    js_right = list(range(0, half))
    js_left  = list(range(J - 1, half - 1, -1))

    # last non-empty station index
    last_non_empty_idx = -1
    for _idx in range(len(stations) - 1, -1, -1):
        if stations[_idx]:
            last_non_empty_idx = _idx
            break

    for i, verts_here in enumerate(stations):
        if not verts_here:
            for j in range(J):
                lines.append(f"P _body/{body_index}/_geo_xyz/{i},{j},0 {0.000000000:.9f}")
                lines.append(f"P _body/{body_index}/_geo_xyz/{i},{j},1 {0.000000000:.9f}")
                lines.append(f"P _body/{body_index}/_geo_xyz/{i},{j},2 {0.000000000:.9f}")
            continue

        is_tip  = with_tip_tail and (i == 0)
        is_tail = with_tip_tail and (i == last_non_empty_idx)

        if is_tip or is_tail:
            ys = [y for (_x, y, _z) in verts_here]
            zs = [z for (_x, _y, z) in verts_here]
            y_ft = (sum(ys)/len(ys) if ys else 0.0) * FT_PER_M
            z_ft = (sum(zs)/len(zs) if zs else 0.0) * FT_PER_M
            for j in range(J):
                lines.append(f"P _body/{body_index}/_geo_xyz/{i},{j},0 {0.000000000:.9f}")
                lines.append(f"P _body/{body_index}/_geo_xyz/{i},{j},1 {y_ft:.9f}")
                lines.append(f"P _body/{body_index}/_geo_xyz/{i},{j},2 {z_ft:.9f}")
            continue

        pos = [v for v in verts_here if v[0] >= 0.0] or verts_here[:]
        pos_sorted = sorted(pos, key=lambda v: v[1], reverse=True)

        cell: Dict[Tuple[int, int], float] = {}
        for idx, (x_m, y_m, z_m) in enumerate(pos_sorted):
            x_ft = x_m * FT_PER_M; y_ft = y_m * FT_PER_M; z_ft = z_m * FT_PER_M
            jr = js_right[idx % max(1, len(js_right))]
            jl = js_left [idx % max(1, len(js_left ))]
            cell[(jr, 0)] =  x_ft; cell[(jr, 1)] = y_ft; cell[(jr, 2)] = z_ft
            cell[(jl, 0)] = -x_ft; cell[(jl, 1)] = y_ft; cell[(jl, 2)] = z_ft

        for j in range(J):
            x = cell.get((j, 0), 0.0)
            y = cell.get((j, 1), 0.0)
            z = cell.get((j, 2), 0.0)
            lines.append(f"P _body/{body_index}/_geo_xyz/{i},{j},0 {x:.9f}")
            lines.append(f"P _body/{body_index}/_geo_xyz/{i},{j},1 {y:.9f}")
            lines.append(f"P _body/{body_index}/_geo_xyz/{i},{j},2 {z:.9f}")

    return lines

# ----------------------- Body block builder ------------------------

def compute_grid_radius_ft(verts: List[Tuple[float, float, float]]) -> float:
    if not verts:
        return 5.0
    max_abs_x = max((abs(x) for (x, _, _) in verts), default=0.0)
    max_abs_y = max((abs(y) for (_, y, _) in verts), default=0.0)
    return max(max_abs_x, max_abs_y) * FT_PER_M + 3.0

def build_body_block(
    body_index: int,
    stations_mesh: List[List[Tuple[float, float, float]]],
    local_verts_centered: List[Tuple[float, float, float]],
    target_i: int,
    target_j: int,
    lateral_offset_ft: float,
) -> List[str]:
    station_count_mesh = len(stations_mesh)
    grid_radius_ft = compute_grid_radius_ft(local_verts_centered)

    lines: List[str] = []
    lines.append(f"P _body/{body_index}/_bot_s1 0.000000000")
    lines.append(f"P _body/{body_index}/_bot_s2 1.000000000")
    lines.append(f"P _body/{body_index}/_bot_t1 0.000000000")
    lines.append(f"P _body/{body_index}/_bot_t2 1.000000000")
    lines.append(f"P _body/{body_index}/_engn_for_body -1")
    lines.append(f"P _body/{body_index}/_gear_for_body -1")

    lines.extend(
        generate_geo_xyz_literal_from_stations(
            stations_mesh, body_index=body_index, target_i=target_i, target_j=target_j, with_tip_tail=True
        )
    )

    for i in range(target_i):
        for j in range(target_j):
            lines.append(f"P _body/{body_index}/_locked/{i},{j} 0")

    lines.append(f"P _body/{body_index}/_locked/i_count {target_i}")
    lines.append(f"P _body/{body_index}/_locked/j_count {target_j}")
    lines.append(f"P _body/{body_index}/_r_dim {target_j}")
    lines.append(f"P _body/{body_index}/_s_dim {station_count_mesh}")

    lines.append(f"P _body/{body_index}/_part_area_rule 1.000000000")
    lines.append(f"P _body/{body_index}/_part_cd 0.075000003")
    lines.append(f"P _body/{body_index}/_part_phi 0.000000000")
    lines.append(f"P _body/{body_index}/_part_psi 0.000000000")
    lines.append(f"P _body/{body_index}/_part_rad {grid_radius_ft:.9f}")
    lines.append(f"P _body/{body_index}/_part_specs_eq 1")
    lines.append(f"P _body/{body_index}/_part_specs_invis 0")
    lines.append(f"P _body/{body_index}/_part_specs_rmod 1")
    lines.append(f"P _body/{body_index}/_part_tex 1")
    lines.append(f"P _body/{body_index}/_part_the 0.000000000")

    lines.append(f"P _body/{body_index}/_part_x {lateral_offset_ft:.9f}")
    lines.append(f"P _body/{body_index}/_part_y 0.000000000")
    lines.append(f"P _body/{body_index}/_part_z 0.000000000")

    lines.append(f"P _body/{body_index}/_top_s1 0.000000000")
    lines.append(f"P _body/{body_index}/_top_s2 1.000000000")
    lines.append(f"P _body/{body_index}/_top_t1 0.000000000")
    lines.append(f"P _body/{body_index}/_top_t2 1.000000000")
    return lines

def replace_body_block(acf_lines: List[str], body_index: int, new_block: List[str]) -> List[str]:
    prefix = f"P _body/{body_index}/"
    kept = [l for l in acf_lines if not l.lstrip().startswith(prefix)]
    first_pos = next((i for i, l in enumerate(acf_lines) if l.lstrip().startswith(prefix)), len(kept))
    first_pos = min(first_pos, len(kept))
    return kept[:first_pos] + new_block + kept[first_pos:]

# -------------------------------- GUI ------------------------------

class ImporterGUI(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Plane Maker Importer (alpha, centered; selectable body index)")
        self.geometry("860x600")

        self.obj_path = tk.StringVar()
        self.acf_path = tk.StringVar()
        self.body_index = tk.StringVar(value="0")
        self.verts_per_loop = tk.StringVar(value="16")

        frm = ttk.Frame(self); frm.pack(fill="x", padx=10, pady=10)
        row = 0
        ttk.Label(frm, text="OBJ file:").grid(row=row, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.obj_path, width=64).grid(row=row, column=1, sticky="we", padx=6)
        ttk.Button(frm, text="Browse...", command=self.browse_obj).grid(row=row, column=2, padx=4); row += 1

        ttk.Label(frm, text="ACF file:").grid(row=row, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.acf_path, width=64).grid(row=row, column=1, sticky="we", padx=6)
        ttk.Button(frm, text="Browse...", command=self.browse_acf).grid(row=row, column=2, padx=4); row += 1

        ttk.Label(frm, text="Body index:").grid(row=row, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.body_index, width=8).grid(row=row, column=1, sticky="w"); row += 1

        ttk.Label(frm, text="Verts per loop:").grid(row=row, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.verts_per_loop, width=10).grid(row=row, column=1, sticky="w"); row += 1

        ttk.Button(frm, text="Rebuild body", command=self.run_once).grid(row=row, column=0, pady=10)

        self.txt = tk.Text(self, wrap="word", height=26)
        self.txt.pack(fill="both", expand=True, padx=10, pady=8)

    def log(self, s: str) -> None:
        self.txt.insert("end", s + "\n"); self.txt.see("end"); self.update_idletasks()

    def browse_obj(self) -> None:
        p = filedialog.askopenfilename(title="Select OBJ", filetypes=[("OBJ files", "*.obj"), ("All files", "*.*")])
        if p: self.obj_path.set(p)

    def browse_acf(self) -> None:
        p = filedialog.askopenfilename(title="Select ACF", filetypes=[("ACF files", "*.acf"), ("All files", "*.*")])
        if p: self.acf_path.set(p)

    def run_once(self) -> None:
        self.txt.delete("1.0", "end")
        obj = self.obj_path.get().strip()
        acf = self.acf_path.get().strip()
        try:
            bidx = int(self.body_index.get())
        except Exception:
            messagebox.showerror("Error", "Body index must be an integer"); return
        if not obj or not os.path.isfile(obj):
            messagebox.showerror("Error", "Select a valid OBJ file"); return
        if not acf or not os.path.isfile(acf):
            messagebox.showerror("Error", "Select a valid ACF file"); return
        try:
            vpl = int(self.verts_per_loop.get()); assert vpl > 0
        except Exception:
            messagebox.showerror("Error", "verts_per_loop must be a positive integer"); return

        try:
            with open(acf, "r", encoding="utf-8", errors="ignore") as f:
                acf_lines = [ln.rstrip("\n") for ln in f]
            target_i, target_j = read_target_dims_from_acf(acf_lines, body_index=bidx)
            self.log(f"Target dims (body {bidx}): i={target_i}, j={target_j}")

            groups = load_obj_groups(obj)
            if not groups:
                self.log("No groups with faces found."); return
            zspan = {g: ((max(v[2] for v in vs) - min(v[2] for v in vs)) if vs else 0.0) for g, vs in groups.items()}
            gsel = "fuselage" if "fuselage" in groups else max(zspan, key=lambda g: zspan[g])
            verts_orig = groups[gsel]
            self.log(f"Using group '{gsel}' with {len(verts_orig)} verts.")

            center_x_m = compute_center_x(verts_orig)
            offset_ft = center_x_m * FT_PER_M
            verts = recenter_vertices_x(verts_orig, center_x_m)
            self.log(f"Lateral center: x0 = {center_x_m:.6f} m → part_x = {offset_ft:.6f} ft")

            stations_mesh = build_stations_from_geometry(verts, verts_per_loop=vpl, with_tip_tail=True)
            self.log(f"Mesh stations (Z-cluster): {len(stations_mesh)} → emit grid i={target_i} (pad zeros as needed)")
            body_block = build_body_block(
                body_index=bidx,
                stations_mesh=stations_mesh,
                local_verts_centered=verts,
                target_i=target_i,
                target_j=target_j,
                lateral_offset_ft=offset_ft,
            )
            new_acf = replace_body_block(acf_lines, body_index=bidx, new_block=body_block)

            base, ext = os.path.splitext(acf)
            out_path = f"{base}_mobject_centered_body{bidx}{ext}"
            with open(out_path, "w", encoding="utf-8") as f:
                for ln in new_acf:
                    f.write(ln + "\n")
            self.log(f"✅ Wrote: {out_path}")
            messagebox.showinfo("Done", f"Rebuilt body {bidx} written:\n{out_path}")
        except Exception as e:
            self.log(f"ERROR: {e}")
            messagebox.showerror("Error", str(e))

if __name__ == "__main__":
    app = ImporterGUI()
    app.mainloop()
