# **CIS_PM_Generator**

CIS_PM_Generator is a specialized tool designed for **X-Plane aircraft developers** to convert **3D fuselage and wing meshes** from Blender (.obj) into **valid Plane-Maker body definitions**.  
It automates the extraction, cleaning, station generation, vertex mapping, and output of Plane-Maker compatible geometry—removing hours of manual work per aircraft.

This tool is part of the **CIS (Captain Iceman Series) Flight Model Pipeline**, used internally to build high‑accuracy aircraft such as the CIS Seneca II, CIS Seminole, and CIS Navajo Chieftain.

![cover](images/cover.png)

---

## ✨ Features

### ✔ OBJ → Plane‑Maker Body Generator
- Reads fuselage or nacelle meshes directly from a Blender-exported OBJ.
- Handles:
  - Symmetrical meshes centered on the **X‑axis**
  - Off‑center meshes with lateral offsets
  - Tail fairings with **non‑uniform vertex loops**
  - Mesh groups with arbitrary naming
- Automatically detects:
  - Number of stations
  - Vertices per loop
  - Tip and tail single-vertex stations
  - Correct winding order for Plane‑Maker

### ✔ Wing Generator Module
- Converts wing geometry into Plane-Maker wing definitions.
- Properly assigns:
  - `part_x`
  - `part_y`
  - `part_z`
- Supports:
  - Paired wing generation (wing1/wing2)
  - Dihedral angle inputs
  - Wing log tables shown in GUI

### ✔ Interactive GUI
- Select OBJ and ACF files  
- Choose mesh groups directly from the OBJ  
- Real‑time logs and geometry validation  
- Show station/vertex assignments  
- Multi‑body aircraft support (fuselage, cowlings, fairings, nacelles, etc.)

### ✔ Automatic ACF Reinjection
- Rebuilds the entire **BODIES** section in the .acf  
- Deletes old body blocks and reinserts clean, newly generated ones  
- Guarantees synchronization between geometry and X-Plane’s flight model  

---

## 🧠 How It Works

1. **Mesh recentering**  
   Detects off‑axis meshes and recenters them in PM coordinates.

2. **Symmetry plane slicing**  
   Keeps positive X‑axis and centerline vertices.

3. **Station builder**  
   - Detects loops  
   - Handles 1‑vertex tip/tail stations  
   - Normalizes irregular loops  
   - Computes correct PM winding order  

4. **Body line generator**  
   Produces:  
   - `P _body/N/_station/M`  
   - `P _body/N/_vert/M`  
   - Complete body header blocks  

5. **ACF writer**  
   - Outputs a new bodies section  
   - Reinserts into target .acf cleanly
  
6. **User's Guide**  
   - Inside the UserGuide folder
   - Guide for Blender, Tool and Plane Maker usage  
   

---

## 🔧 Installation

Extract the zip and place it in the folder of your preference.
Run the .exe

---

## 🖥 GUI Overview
- **OBJ Path** – Select fuselage/wings OBJ  
- **ACF Path** – Select aircraft ACF  
- **Body Index** – Choose which body to generate  
- **Mesh Group Selector** – Choose fuselage or wing meshes  
- **Logs** – Shows station detection, winding, offsets  
- **Generate** – Builds & injects body blocks  

---

## 📁 Project Structure
```
CIS_PM_Generator/
│
├── cis_PMGenerator.py       # Main GUI
├── bodies_module.py         # Fuselage generator engine
├── wings_module.py          # Wing generator engine
├── templates/               # Zeroed templates
└── output/                  # Generated ACF files
```

---

## 🛠 Development Status
- ✔ Stable fuselage body generation  
- ✔ Stable wing generation  
- ✔ Multi‑mesh OBJ support Bodies and Wings
- ✔ GUI system complete
- ✔ Executable available at the releases.  
- ⏳ Preparing for Blender 4.5 add‑on port  
 

---

## 📜 License (Attribution Required)

CIS_PM_Generator is free to use, modify, and integrate into personal or commercial X‑Plane aircraft development workflows.

However, **proper attribution is required**.

If your project, aircraft, or publication used this tool, please include the following credit:

> **"3D Flight Model created with the help of the CIS_PM_Generator tool developed by Emilio Hernandez (Capt. Iceman)."**

See the `LICENSE` file for full details.

---

## ✈ Author

**Emilio Hernandez (Capt. Iceman)**  
Developer of the CIS Flight Model Series  
JetstreamFS.com

---

## 💬 Support

Open an issue on GitHub for help, debugging, or feature requests.






