import re
from collections import OrderedDict

def extract_body_blocks_from_acf(
    acf_path: str = "PM_bodies reference.acf",
    output_prefix: str = "PM_refbodies_"
):
    """
    Extract all P _body/n/... lines from a reference .acf file and
    write each body's block to its own text file:

        PM_refbodies_<body_index>.txt

    Only lines starting with 'P _body/<n>/' are considered.
    """

    body_blocks = OrderedDict()  # body_index -> [lines]

    body_line_re = re.compile(r'^P _body/(\d+)/_geo_xyz/')

    with open(acf_path, "r", encoding="utf-8") as f:
        for line in f:
            m = body_line_re.match(line)
            if not m:
                continue

            body_index = int(m.group(1))

            if body_index not in body_blocks:
                body_blocks[body_index] = []

            # Store the line as-is (no stripping), so formatting is preserved
            body_blocks[body_index].append(line.rstrip("\n"))

    # Write each body block to its own file
    for body_index, lines in body_blocks.items():
        out_path = f"{output_prefix}{body_index}.txt"
        with open(out_path, "w", encoding="utf-8") as out_f:
            out_f.write("\n".join(lines))
        print(f"Saved body/{body_index} block to {out_path}")


if __name__ == "__main__":
    extract_body_blocks_from_acf()
