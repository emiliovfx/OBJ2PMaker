# file: scripts/extract_body0_tk.py
#!/usr/bin/env python3
"""
GUI helper: choose a file, extract lines containing 'P_body0',
save as '<stem>_body0.txt' in the same directory, and show a result dialog.
"""

from __future__ import annotations
from pathlib import Path
import sys
import traceback

STA = 5
BODY = 0
# Tkinter GUI
import tkinter as tk
from tkinter import filedialog, messagebox

def derive_output_path(input_path: Path) -> Path:
    # Why: Ensure predictable naming independent of original extension.
    return input_path.with_name(f"{input_path.stem}_body{BODY}_station_{STA}.txt")

def extract_lines_to_file(input_path: Path) -> tuple[Path, int]:
    output_path = derive_output_path(input_path)
    matches: list[str] = []
    with input_path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
        for line in f:
            if line.startswith(f"P _body/0/_geo_xyz/{STA},") :
                matches.append(line)
    with output_path.open("w", encoding="utf-8", newline="") as out:
        out.writelines(matches)
    return output_path, len(matches)

def pick_file() -> Path | None:
    root = tk.Tk()
    root.withdraw()
    root.update_idletasks()
    # First entry is the default/active filter.
    filetypes = [
        ("ACF files", "*.acf"),
        ("All files", "*.*"),
    ]
    path_str = filedialog.askopenfilename(
        title="Select an .acf file to extract 'P_body0' lines",
        filetypes=filetypes,
        defaultextension=".acf",  # Why: Ensures .acf when typing a name manually.
    )
    root.destroy()
    return Path(path_str) if path_str else None

def main() -> int:
    try:
        in_path = pick_file()
        if not in_path:
            # Why: Silent exit on cancel to avoid confusing users.
            return 0

        if not in_path.exists():
            messagebox.showerror("Error", f"File not found:\n{in_path}")
            return 2

        out_path, count = extract_lines_to_file(in_path)

        if count == 0:
            messagebox.showwarning(
                "No Matches Found",
                f"No lines containing 'P_body0' were found.\n\n"
                f"Input : {in_path}\nOutput: {out_path}\n"
                f"(An empty file was still created.)"
            )
            return 1

        messagebox.showinfo(
            "Extraction Complete",
            f"Matched lines: {count}\n\n"
            f"Input : {in_path}\nOutput: {out_path}"
        )
        return 0

    except Exception as exc:
        # Show full error to help debugging.
        traceback.print_exc()
        messagebox.showerror("Unexpected Error", f"{exc}\n\n{traceback.format_exc()}")
        return 3

if __name__ == "__main__":
    sys.exit(main())
