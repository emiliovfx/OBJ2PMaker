import re
from collections import defaultdict
from typing import Dict, List, Tuple


def make_ref_body_split(
    acf_path: str,
    body_index: int,
    out_path: str | None = None,
    points_per_ring: int = 18,
) -> str:
    """
    Extract body/<body_index> _geo_xyz data from a ref .acf (or a body-only file)
    and write it in our "split" QC format:

        body/3 ('REF_body_3'), station i=0, z=...
          j= 0:  x=...  y=...  z=...
          ...

    Args:
        acf_path:   Path to the reference .acf file
        body_index: Which _body/n to extract
        out_path:   Output file path (default: REF_body_{body_index}_split.txt)
        points_per_ring: how many j slots to expect/print (default 18)

    Returns:
        out_path (string)
    """

    # body_data[i][j][k] = value  (i = station, j = ring index, k = 0/1/2 axis)
    body_data: Dict[int, Dict[int, Dict[int, float]]] = defaultdict(
        lambda: defaultdict(dict)
    )

    # Match lines like:
    #   P _body/3/_geo_xyz/6,10,2 12.345678
    pattern = re.compile(
        r"^P _body/(\d+)/_geo_xyz/(\d+),(\d+),(\d+)\s+(-?\d+\.\d+)$"
    )

    with open(acf_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            m = pattern.match(line.strip())
            if not m:
                continue

            b_str, i_str, j_str, k_str, val_str = m.groups()
            b = int(b_str)
            if b != body_index:
                continue

            i = int(i_str)
            j = int(j_str)
            k = int(k_str)
            val = float(val_str)

            body_data[i][j][k] = val

    if not body_data:
        raise ValueError(
            f"No _geo_xyz data found for body/{body_index} in {acf_path}"
        )

    if out_path is None:
        out_path = f"REF_body_{body_index}_split.txt"

    lines: List[str] = []

    # Stations in ascending i order
    for i in sorted(body_data.keys()):
        # Get a representative z for this station (any j with k=2)
        z_val = None
        for j_dict in body_data[i].values():
            if 2 in j_dict:
                z_val = j_dict[2]
                break
        if z_val is None:
            z_val = 0.0

        lines.append(
            f"body/{body_index} ('REF_body_{body_index}'), "
            f"station i={i}, z={z_val:.9f}"
        )

        # Print j=0..points_per_ring-1 in our usual format
        for j in range(points_per_ring):
            comp = body_data[i].get(j, {})
            x = comp.get(0, 0.0)
            y = comp.get(1, 0.0)
            z = comp.get(2, 0.0)
            lines.append(
                f"  j={j:2d}:  x={x:.9f}  y={y:.9f}  z={z:.9f}"
            )

        lines.append("")  # blank line between stations

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Saved REF body split for body/{body_index} to {out_path}")
    return out_path


if __name__ == "__main__":
    # Example usage:
    #   - If you have the full ref ACF: "PM_bodies reference.acf"
    #   - Or a pre-extracted file like "PM_refbodies_3.txt"
    ACF_PATH = "PM_bodies reference.acf"   # adjust as needed
    BODY_INDEX = 3

    make_ref_body_split(ACF_PATH, BODY_INDEX)
