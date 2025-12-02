
# CIS Flight Model Generator Documentation
Friendly Technical Guide  
© 2025 JetstreamFS / Capt. Iceman Series

---

## 1. Overview

The CIS Flight Model Generator is a unified tool designed to convert Blender-exported OBJ geometry into high-quality, PlaneMaker-compatible flight model bodies and wings. It streamlines building full ACF files by combining topology analysis, geometric extraction, template-driven block generation, and a simple UI workflow.

**What it does:**
- Reads a combined OBJ containing bodies and wings
- Separates and classifies meshes automatically
- Generates full `_body` and `_wing` blocks using templates
- Supports creating a brand-new ACF file or modifying an existing one
- Handles wing dihedral and automatically applies cowling tilt
- Works as a portable standalone tool

**High-Level Flow:**  
[DIAGRAM: OBJ → Bodies Module + Wings Module → PMGenerator GUI → ACF Output]

---

## 2. Installation & Folder Structure

The tool is portable and requires only Python and the provided scripts.

Recommended folder layout:

```
cis_pm_generator/
│
├─ cis_PMGenerator.py
├─ cis_bodies2pm.py
├─ cis_wings2pm.py
│
├─ Templates/
│   ├─ body_block_template_zeroed.txt
│   ├─ wing_block_template_zeroed.txt
│
├─ acfnew/
│   └─ acfnew.acf
│
├─ examples/
│   ├─ PA31_350_Chieftain_FlightModel_geo.obj
│   ├─ CIS_Chieftain_Master.acf
│
└─ docs/
    └─ CIS_FlightModelGenerator_Documentation.md
```

---

## 3. Using the GUI

Launch the GUI by double-clicking `cis_PMGenerator.py` or running:

```
python cis_PMGenerator.py
```

### 3.1 Selecting an OBJ
Load the OBJ that contains **all** body and wing meshes. The tool automatically:

- Reads both `g` and `o` group declarations
- Counts vertices per group
- Classifies them into:
  - **Bodies** (≥10 verts)
  - **Wings** (≤8 verts)
  - **Ambiguous** (9 verts)

### 3.2 Understanding Detected Groups
The GUI shows three lists:
- Body candidates  
- Wing candidates  
- Ambiguous groups  

Mesh classification is automatic, but the lists give visual confirmation.

### 3.3 Choosing Processing Mode

#### **Create New Aircraft (default)**
- Uses `acfnew/acfnew.acf` as a blank template
- Generates a completely new ACF
- You choose the output location and file name

#### **Modify Existing ACF**
- Select an existing `.acf`
- The script:
  - Creates `*_bak.acf` backup
  - Strips current body & wing blocks
  - Injects newly generated blocks

### 3.4 Wing Dihedral Input
Enter the dihedral angle (e.g. `5.0`) for Wing1/Wing2.

The tool also:
- Sets **left cowling** `_part_phi = +dihedral`
- Sets **right cowling** `_part_phi = -dihedral`

### 3.5 Logs & Validation
The log displays:
- Detected groups  
- Body and wing processing  
- Output path  
- Any warnings or errors  

---

## 4. How OBJ Processing Works

### 4.1 Bodies Module – Topology Analysis
The bodies module identifies “stations” based on mesh topology using adjacency/BFS. Each station is converted into an 18-slot ring:

- j0..j8 → +X side
- j9..j17 → -X mirrored
- Centerline vertices flattened if near zero

This ensures proper symmetry and PlaneMaker compatibility.

[DIAGRAM: Body ring j-index orientation around cross-section]

### 4.2 Wings Module – Panel Extraction
Wings are planar surfaces with simple topology. The module finds:

- Wing1
- Wing2
- Horizontal Stabilizer
- Vertical Stabilizer

and computes panel coordinates required by PlaneMaker.

---

## 5. The Template System

Templates allow the generator to output highly structured ACF blocks.

### 5.1 Body Template
`body_block_template_zeroed.txt` contains all required `_body/b/...` lines with placeholder values (zeros). The script fills:

- Dimensions  
- Centers  
- Ring geometry  
- Cowling φ  
- Description fields  

### 5.2 Wing Template
`wing_block_template_zeroed.txt` contains:

- Geometry lines  
- Outer/inner panels  
- Airfoil references  

The script fills in:

- Panel coordinates  
- Dihedral  
- Airfoil assignments  
  - Wings → NACA 2412 (popular).afl  
  - Stabs → NACA 0009 (symmetrical).afl  

---

## 6. ACF Rewriting Logic

### 6.1 Block Stripping
The tool removes **all existing** `P _body/` and `P _wing/` blocks from the target ACF before inserting fresh ones.

### 6.2 Block Insertion
The new body and wing blocks (generated from templates) are appended exactly where PlaneMaker expects them.

### 6.3 Temporary Files
Writing happens in two stages:
1. Bodies into `*.tmp_bodies`
2. Wings into the final output `.acf`

This avoids file corruption and keeps backups clean.

[DIAGRAM: ACF strip/replace flow]

---

## 7. Naming Conventions & Mesh Requirements

### 7.1 OBJ Group Names
The system recognizes either:
- `g GroupName`
- `o GroupName`

Recommended naming:

- Fuselage  
- LF_Cowling  
- RT_Cowling  

Wings **must** follow planar naming:
- Wing1  
- Wing2  
- Horizontal_Stab  
- Vertical_Stab  

### 7.2 Geometry Requirements

**Bodies:**
- Must contain at least **10 vertices**
- Should be symmetrical around X=0

**Wings:**
- Should contain **8 or fewer vertices** (typical wing plane)

Ambiguous (9 vertices) will still show in GUI but not be used unless recognized as a wing.

---

## 8. Troubleshooting

### “No bodies detected”
- Body groups have too few vertices  
- OBJ exported incorrectly  
- Mesh names not recognized  

### “Wings missing”
- Wrong naming (must include Wing1, Wing2, etc.)  
- OBJ missing wing groups  

### “PlaneMaker changes values when opening”
Normal behavior! PM normalizes ring order on first save.

### “ACF not writing”
- Path issue  
- Missing template  
- Insufficient permissions  

---

## 9. Developer Notes

The system is divided into three independent modules:

### 9.1 PMGenerator (GUI)
- Handles user input  
- Calls both modules  
- Orchestrates ACF writing  
- Includes dark theme styling  

### 9.2 Bodies Module
- OBJ → stations → rings  
- Builds full `_body/b` blocks  
- Includes cowling dihedral logic  
- Accepts `g` and `o` grouping  

### 9.3 Wings Module
- OBJ → panels  
- Template filling for `_wing/w` blocks  
- Airfoil rule system  

[DIAGRAM: Module-level architecture]

---

## 10. Future Directions

Planned enhancements include:

- Blender 4.5 integration as an add-on  
- Gear mesh → gear block generator  
- Automatic visualization of rings and panels  
- Batch processing of multiple aircraft  
- Auto-detection for more mesh types (fairings, nacelles, etc.)

---

## 11. Credits & License

This system is developed for the **Capt. Iceman Series** aircraft family under JetstreamFS.

> The goal: make flight-model building smooth, predictable, and enjoyable — so you can focus on crafting beautiful aircraft.

End of documentation.

---

