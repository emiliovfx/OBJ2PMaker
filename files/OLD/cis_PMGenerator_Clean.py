import os
import sys
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext


# ---------------------------------------------------------------------------
# Resource helper (PyInstaller-friendly)
# ---------------------------------------------------------------------------

def resource_path(relative_path: str) -> str:
    """
    Get absolute path to resource, works for dev and for PyInstaller bundle.
    """
    try:
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

from collections import defaultdict

def scan_obj_groups_by_vertex_count(obj_path):
    """
    Parse a Wavefront-style OBJ and classify groups/objects
    into 'bodies', 'wings', and 'ambiguous' based on vertex count.

    Rules:
      - wings:    vertex_count <= 8
      - bodies:   vertex_count >= 10
      - 9 verts:  ambiguous

    Returns:
      bodies:    list of (name, vertex_count)
      wings:     list of (name, vertex_count)
      ambig:     list of (name, vertex_count)
    """
    if not os.path.isfile(obj_path):
        raise FileNotFoundError(f"OBJ not found: {obj_path}")

    # Count vertices per current group/object
    vert_counts = defaultdict(int)
    current_name = None

    with open(obj_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            # New group or object: "g Name" or "o Name"
            if line.startswith("g ") or line.startswith("o "):
                parts = line.split(maxsplit=1)
                if len(parts) == 2:
                    current_name = parts[1].strip()
                else:
                    current_name = None
                # Ensure we have a key even if no vertices yet
                if current_name:
                    _ = vert_counts[current_name]
                continue

            # Vertex line
            if line.startswith("v "):
                if current_name:
                    vert_counts[current_name] += 1
                continue

    bodies = []
    wings = []
    ambig = []

    for name, count in sorted(vert_counts.items(), key=lambda x: x[0].lower()):
        if count <= 8:
            wings.append((name, count))
        elif count >= 10:
            bodies.append((name, count))
        else:  # count == 9 or any weird case
            ambig.append((name, count))

    return bodies, wings, ambig

# ---------------------------------------------------------------------------
# Try to import bodies & wings modules under the expected names
# ---------------------------------------------------------------------------

# Bodies
try:
    import cis_bodies2pm as bodies_mod
except ImportError:
    try:
        import cis_bodies as bodies_mod
    except ImportError:
        bodies_mod = None

# Wings
try:
    import cis_wing2pm as wings_mod
except ImportError:
    try:
        import cis_wings2pm as wings_mod
    except ImportError:
        wings_mod = None


# Paths to templates + new-ACF template
BODY_TEMPLATE_PATH = "Templates/body_block_template_zeroed.txt"
WING_TEMPLATE_PATH = "Templates/wing_block_template_zeroed.txt"

# Default new-aircraft template: acfnew/acfnew.acf
ACFNEW_REL_PATH = os.path.join("acfnew", "acfnew.acf")


# ---------------------------------------------------------------------------
# Main GUI
# ---------------------------------------------------------------------------

class PMGeneratorGUI:
    def __init__(self, master: tk.Tk):
        self.master = master
        master.title("CIS PM Generator – Bodies + Wings")

        # -------------------------------------------------------------------
        # Top: OBJ selection
        # -------------------------------------------------------------------
        obj_frame = tk.LabelFrame(master, text="OBJ Source (Bodies + Wings)")
        obj_frame.pack(fill="x", padx=8, pady=6)

        self.obj_path_var = tk.StringVar()
        tk.Label(obj_frame, text="Integrated OBJ:").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        tk.Entry(obj_frame, textvariable=self.obj_path_var, width=60).grid(row=0, column=1, padx=4, pady=4, sticky="we")
        tk.Button(obj_frame, text="Browse...", command=self.browse_obj).grid(row=0, column=2, padx=4, pady=4)

        obj_frame.grid_columnconfigure(1, weight=1)

        # -------------------------------------------------------------------
        # Detected groups (bodies vs wings)
        # -------------------------------------------------------------------
        grp_frame = tk.LabelFrame(master, text="Detected Groups in OBJ")
        grp_frame.pack(fill="x", padx=8, pady=4)

        # Bodies
        tk.Label(grp_frame, text="Body candidates (>= 10 verts):").grid(
            row=0, column=0, sticky="w", padx=4, pady=(4, 2)
        )
        self.lst_bodies = tk.Listbox(grp_frame, height=6, width=40)
        self.lst_bodies.grid(row=1, column=0, padx=4, pady=(0, 4), sticky="nwe")

        # Wings
        tk.Label(grp_frame, text="Wing candidates (<= 8 verts):").grid(
            row=0, column=1, sticky="w", padx=4, pady=(4, 2)
        )
        self.lst_wings = tk.Listbox(grp_frame, height=6, width=40)
        self.lst_wings.grid(row=1, column=1, padx=4, pady=(0, 4), sticky="nwe")

        # Ambiguous
        tk.Label(grp_frame, text="Ambiguous (9 verts):").grid(
            row=0, column=2, sticky="w", padx=4, pady=(4, 2)
        )
        self.lst_ambig = tk.Listbox(grp_frame, height=6, width=25)
        self.lst_ambig.grid(row=1, column=2, padx=4, pady=(0, 4), sticky="nwe")

        grp_frame.grid_columnconfigure(0, weight=1)
        grp_frame.grid_columnconfigure(1, weight=1)
        grp_frame.grid_columnconfigure(2, weight=1)


        # Wing dihedral (for Wing1/Wing2)
        dihed_frame = tk.Frame(master)
        dihed_frame.pack(fill="x", padx=8, pady=(0, 4))

        tk.Label(dihed_frame, text="Wing1/Wing2 dihedral (deg):").grid(
            row=0, column=0, sticky="w", padx=4, pady=2
        )
        self.wing_dihed_var = tk.StringVar(value="0.0")
        tk.Entry(dihed_frame, textvariable=self.wing_dihed_var, width=10).grid(
            row=0, column=1, sticky="w", padx=4, pady=2
        )

        dihed_frame.grid_columnconfigure(2, weight=1)



        # -------------------------------------------------------------------
        # Mode selection: New vs Modify
        # -------------------------------------------------------------------
        mode_frame = tk.LabelFrame(master, text="ACF Mode")
        mode_frame.pack(fill="x", padx=8, pady=6)

        self.mode_var = tk.StringVar(value="new")  # "new" (default) or "modify"

        rb_new = tk.Radiobutton(
            mode_frame,
            text="Create NEW aircraft from template (acfnew/acfnew.acf)",
            variable=self.mode_var,
            value="new",
            command=self.update_mode_state,
        )
        rb_new.grid(row=0, column=0, columnspan=3, sticky="w", padx=4, pady=2)

        rb_mod = tk.Radiobutton(
            mode_frame,
            text="Modify EXISTING .acf (backup original to *_bak.acf)",
            variable=self.mode_var,
            value="modify",
            command=self.update_mode_state,
        )
        rb_mod.grid(row=1, column=0, columnspan=3, sticky="w", padx=4, pady=2)

        # -------------------------------------------------------------------
        # NEW-aircraft options
        # -------------------------------------------------------------------
        new_frame = tk.LabelFrame(master, text="New Aircraft Options")
        new_frame.pack(fill="x", padx=8, pady=4)

        self.new_output_dir_var = tk.StringVar(value=os.getcwd())
        self.new_filename_var = tk.StringVar(value="CIS_NewAircraft.acf")

        tk.Label(new_frame, text="Output folder:").grid(row=0, column=0, sticky="w", padx=4, pady=3)
        tk.Entry(new_frame, textvariable=self.new_output_dir_var, width=50).grid(
            row=0, column=1, padx=4, pady=3, sticky="we"
        )
        tk.Button(new_frame, text="Browse...", command=self.browse_output_dir).grid(
            row=0, column=2, padx=4, pady=3
        )

        tk.Label(new_frame, text="New ACF filename:").grid(row=1, column=0, sticky="w", padx=4, pady=3)
        tk.Entry(new_frame, textvariable=self.new_filename_var, width=40).grid(
            row=1, column=1, padx=4, pady=3, sticky="w"
        )

        new_frame.grid_columnconfigure(1, weight=1)
        self.new_frame = new_frame

        # -------------------------------------------------------------------
        # MODIFY-existing options
        # -------------------------------------------------------------------
        mod_frame = tk.LabelFrame(master, text="Modify Existing ACF")
        mod_frame.pack(fill="x", padx=8, pady=4)

        self.modify_acf_path_var = tk.StringVar()

        tk.Label(mod_frame, text="ACF to modify:").grid(row=0, column=0, sticky="w", padx=4, pady=3)
        tk.Entry(mod_frame, textvariable=self.modify_acf_path_var, width=60).grid(
            row=0, column=1, padx=4, pady=3, sticky="we"
        )
        tk.Button(mod_frame, text="Browse...", command=self.browse_modify_acf).grid(
            row=0, column=2, padx=4, pady=3
        )

        mod_frame.grid_columnconfigure(1, weight=1)
        self.mod_frame = mod_frame

        # -------------------------------------------------------------------
        # Run button + log
        # -------------------------------------------------------------------
        btn_frame = tk.Frame(master)
        btn_frame.pack(fill="x", padx=8, pady=4)

        tk.Button(btn_frame, text="Generate Bodies + Wings", command=self.run_process).pack(
            side="right", padx=4, pady=4
        )

        log_frame = tk.LabelFrame(master, text="Log")
        log_frame.pack(fill="both", expand=True, padx=8, pady=6)

        self.txt_log = scrolledtext.ScrolledText(log_frame, height=18)
        self.txt_log.pack(fill="both", expand=True, padx=4, pady=4)

        # -------------------------------------------------------------------
        # Footer / Copyright
        # -------------------------------------------------------------------
        footer = tk.Label(
            master,
            text="© 2025 JetstreamFS / Capt. Iceman Series – All Rights Reserved",
            font=("Segoe UI", 8),
            fg="#888888"
        )
        footer.pack(side="bottom", pady=(0, 4))

        # Initialize widget state according to default mode
        self.update_mode_state()

    # -------------------------------------------------------------------
    # GUI helpers
    # -------------------------------------------------------------------

    def update_group_lists_from_obj(self):
        """
        Scan the selected OBJ and populate the three lists:
        bodies, wings, ambiguous.
        """
        obj_path = self.obj_path_var.get().strip()
        if not obj_path or not os.path.isfile(obj_path):
            return

        try:
            bodies, wings, ambig = scan_obj_groups_by_vertex_count(obj_path)
        except Exception as e:
            self.log(f"ERROR scanning OBJ groups: {e}")
            return

        # Clear listboxes
        self.lst_bodies.delete(0, tk.END)
        self.lst_wings.delete(0, tk.END)
        self.lst_ambig.delete(0, tk.END)

        # Populate
        for name, cnt in bodies:
            self.lst_bodies.insert(tk.END, f"{name}  ({cnt} verts)")

        for name, cnt in wings:
            self.lst_wings.insert(tk.END, f"{name}  ({cnt} verts)")

        for name, cnt in ambig:
            self.lst_ambig.insert(tk.END, f"{name}  ({cnt} verts)")

        # Log summary
        self.log("OBJ group scan:")
        self.log(f"  Bodies:    {len(bodies)}")
        self.log(f"  Wings:     {len(wings)}")
        self.log(f"  Ambiguous: {len(ambig)}")


    def log(self, msg: str) -> None:
        self.txt_log.insert("end", msg + "\n")
        self.txt_log.see("end")
        self.master.update_idletasks()

    def browse_obj(self) -> None:
        path = filedialog.askopenfilename(
            title="Select integrated OBJ (bodies + wings)",
            filetypes=[("OBJ files", "*.obj"), ("All files", "*.*")],
        )
        if path:
            self.obj_path_var.set(path)
            # Immediately scan and update group lists
            self.update_group_lists_from_obj()


    def browse_output_dir(self) -> None:
        path = filedialog.askdirectory(
            title="Select output folder for new ACF",
        )
        if path:
            self.new_output_dir_var.set(path)

    def browse_modify_acf(self) -> None:
        path = filedialog.askopenfilename(
            title="Select existing ACF to modify",
            filetypes=[("ACF files", "*.acf"), ("All files", "*.*")],
        )
        if path:
            self.modify_acf_path_var.set(path)

    def update_mode_state(self) -> None:
        """
        Enable/disable fields depending on mode (new vs modify).
        """
        mode = self.mode_var.get()

        # NEW mode: enable new_frame, disable mod_frame
        state_new = "normal" if mode == "new" else "disabled"
        state_mod = "normal" if mode == "modify" else "disabled"

        for child in self.new_frame.winfo_children():
            try:
                child.configure(state=state_new)
            except tk.TclError:
                pass

        for child in self.mod_frame.winfo_children():
            try:
                child.configure(state=state_mod)
            except tk.TclError:
                pass

    # -------------------------------------------------------------------
    # Core processing
    # -------------------------------------------------------------------

    def run_process(self) -> None:
        self.txt_log.delete("1.0", "end")

        # Basic sanity: modules present?
        if bodies_mod is None:
            messagebox.showerror("Error", "Bodies module (cis_bodies2pm / cis_bodies) not found.")
            return
        if wings_mod is None:
            messagebox.showerror("Error", "Wings module (cis_wing2pm / cis_wings2pm) not found.")
            return

        obj_path = self.obj_path_var.get().strip()
        if not obj_path or not os.path.isfile(obj_path):
            messagebox.showerror("Error", "Please select a valid integrated OBJ file.")
            return

        mode = self.mode_var.get()

        try:
            if mode == "new":
                self._run_new_aircraft(obj_path)
            else:
                self._run_modify_existing(obj_path)
        except Exception as e:
            self.log(f"ERROR: {e}")
            messagebox.showerror("Error", f"An error occurred:\n{e}")

    # -------------------------------------------------------------------
    # Mode 1: Create NEW aircraft from acfnew/acfnew.acf
    # -------------------------------------------------------------------

    def _resolve_acfnew_template(self) -> str:
        """
        Try acfnew/acfnew.acf first, then fallback to ./acfnew.acf
        """
        candidate1 = resource_path(ACFNEW_REL_PATH)
        candidate2 = resource_path("acfnew.acf")

        if os.path.isfile(candidate1):
            return candidate1
        if os.path.isfile(candidate2):
            return candidate2

        raise FileNotFoundError(
            f"Could not find new-aircraft template ACF.\n"
            f"Tried:\n  {candidate1}\n  {candidate2}"
        )

    def _run_new_aircraft(self, obj_path: str) -> None:
        self.log("Mode: Create NEW aircraft from template.")

        acf_template = self._resolve_acfnew_template()
        self.log(f"Using ACF template: {acf_template}")

        out_dir = self.new_output_dir_var.get().strip()
        filename = self.new_filename_var.get().strip()

        if not out_dir:
            raise ValueError("Output folder for new aircraft is empty.")
        if not os.path.isdir(out_dir):
            raise FileNotFoundError(f"Output folder does not exist: {out_dir}")

        if not filename:
            raise ValueError("New ACF filename is empty.")

        # Ensure .acf extension
        root, ext = os.path.splitext(filename)
        if ext.lower() != ".acf":
            filename = root + ".acf"

        final_out = os.path.join(out_dir, filename)
        tmp_out = final_out + ".tmp_bodies"

        self.log(f"Final ACF will be written to: {final_out}")

        # Generate body + wing blocks from OBJ
        body_lines, wing_lines = self._build_body_and_wing_blocks(obj_path)

        # First: rewrite bodies into template -> tmp_out
        self.log("Rewriting bodies into template...")
        bodies_mod.rewrite_acf_bodies(
            acf_in_path=acf_template,
            acf_out_path=tmp_out,
            new_body_lines=body_lines,
        )

        # Then: rewrite wings into tmp_out -> final_out
        self.log("Rewriting wings into intermediate ACF...")
        wings_mod.rewrite_acf_wings(
            acf_in_path=tmp_out,
            acf_out_path=final_out,
            new_wing_lines=wing_lines,
        )

        # Cleanup tmp
        try:
            os.remove(tmp_out)
        except OSError:
            pass

        self.log("DONE: New aircraft ACF generated.")
        messagebox.showinfo("Success", f"New ACF created:\n{final_out}")

    # -------------------------------------------------------------------
    # Mode 2: Modify EXISTING ACF (with backup)
    # -------------------------------------------------------------------

    def _run_modify_existing(self, obj_path: str) -> None:
        self.log("Mode: Modify EXISTING ACF (with backup).")

        acf_path = self.modify_acf_path_var.get().strip()
        if not acf_path or not os.path.isfile(acf_path):
            raise FileNotFoundError("Please select a valid ACF to modify.")

        self.log(f"ACF to modify: {acf_path}")

        # Make backup: name_bak.acf
        base, ext = os.path.splitext(acf_path)
        backup_path = f"{base}_bak{ext}"

        self.log(f"Creating backup: {backup_path}")
        shutil.copy2(acf_path, backup_path)

        tmp_out = acf_path + ".tmp_bodies"

        # Generate body + wing blocks
        body_lines, wing_lines = self._build_body_and_wing_blocks(obj_path)

        # First rewrite bodies: original -> tmp_out
        self.log("Rewriting bodies into existing ACF...")
        bodies_mod.rewrite_acf_bodies(
            acf_in_path=acf_path,
            acf_out_path=tmp_out,
            new_body_lines=body_lines,
        )

        # Then rewrite wings: tmp_out -> original path
        self.log("Rewriting wings into intermediate ACF...")
        wings_mod.rewrite_acf_wings(
            acf_in_path=tmp_out,
            acf_out_path=acf_path,  # ✅ use acf_path here, NOT final_out
            new_wing_lines=wing_lines,
        )

        # Cleanup tmp
        try:
            os.remove(tmp_out)
        except OSError:
            pass

        self.log("DONE: Existing ACF updated (backup saved).")
        messagebox.showinfo(
            "Success",
            f"ACF updated:\n{acf_path}\n\nBackup saved as:\n{backup_path}",
        )

    # -------------------------------------------------------------------
    # Shared geometry → block generation
    # -------------------------------------------------------------------

    def _build_body_and_wing_blocks(self, obj_path: str):
        """
        Common helper that:
        - builds bodies from OBJ and expands them into template lines
        - builds wings from OBJ and expands them into template lines
        Returns (body_lines, wing_lines).
        """

        # ------------------ Shared wing dihedral ------------------
        dihed_str = (self.wing_dihed_var.get() if hasattr(self, "wing_dihed_var") else "0.0") or "0.0"
        try:
            wing_dihed = float(dihed_str)
        except ValueError:
            wing_dihed = 0.0
            self.log(f"[WARN] Invalid dihedral '{dihed_str}', using 0.0 deg.")


        self.log("Parsing OBJ and computing body volumes...")
        bodies = bodies_mod.build_bodies_from_obj(obj_path)
        self.log(f"Found {len(bodies)} body meshes.")

        body_template = resource_path(BODY_TEMPLATE_PATH)
        if not os.path.isfile(body_template):
            raise FileNotFoundError(f"Body template not found: {body_template}")

        body_lines = []
        for b_idx in range(len(bodies)):
            self.log(f"  Building body block for body index {b_idx}...")
            block = bodies_mod.build_body_block_from_template(
                bodies=bodies,
                body_index=b_idx,
                template_path=body_template,
                wing_dihed_deg=wing_dihed,   # keeps your cowling phi logic
            )
            body_lines.extend(block)  # ✅ this was missing



        # ------------------ Wings side ------------------
        self.log("Parsing OBJ and computing wing panels...")

        # Get dihedral input (default 0.0 if empty / invalid)
        dihed_str = (self.wing_dihed_var.get() if hasattr(self, "wing_dihed_var") else "0.0") or "0.0"
        try:
            wing_dihed = float(dihed_str)
        except ValueError:
            wing_dihed = 0.0
            self.log(f"[WARN] Invalid dihedral '{dihed_str}', using 0.0 deg.")

        # Use the locked cis_wings2pm API
        panel_data = wings_mod.compute_all_panels(
            obj_path,
            wing_dihed,
            log_func=self.log,
        )

        wing_template = resource_path(WING_TEMPLATE_PATH)
        if not os.path.isfile(wing_template):
            raise FileNotFoundError(f"Wing template not found: {wing_template}")

        wing_lines = wings_mod.build_wing_blocks_from_template(
            panel_data,
            template_path=wing_template,
            log_func=self.log,
        )

        self.log(f"Total body lines: {len(body_lines)}")
        self.log(f"Total wing lines: {len(wing_lines)}")

        return body_lines, wing_lines



# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    root = tk.Tk()
    app = PMGeneratorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
