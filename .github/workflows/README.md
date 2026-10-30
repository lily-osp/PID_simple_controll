# GitHub Actions Workflow

## Compile Arduino Sketches & Auto-Release - **THE ONLY WORKFLOW**

**This single workflow handles everything!** Complete CI/CD pipeline in one place.

### What it does
1. Installs Arduino CLI and required cores
2. Compiles ESP32-C3 bench sketch → `esp32-c3/control/compiled/`
3. Compiles ESP32-C3 production sketch → `esp32-c3/embedded/compiled/`
4. Creates complete ZIP with source + compiled firmware
5. Automatically creates GitHub releases with packages
6. Displays memory usage statistics

### Example Output
- **ZIP File**: `25112025_PID_simple_controll.zip`
- **Release Tag**: `25112025`
- **Release Title**: `Release 25112025`

### Complete Package Contents
- **Source Code**: All ESP32-C3 sketches, configs, and documentation
- **Compiled Firmware**: Ready-to-flash binaries for both builds
- **Documentation**: Complete setup guides and troubleshooting
- ❌ **Excluded**: `.git` directories, workflow files

### Triggers
- **Push to main/master**: Auto-creates daily release + complete ZIP
- **Version Tags** (v*.*.*): Creates versioned releases
- **Pull Request**: Validates compilation without creating releases
- **Manual**: Actions → "Compile Arduino Sketches & Auto-Release" → Run workflow

### Output Locations
- **ZIP Artifacts**: Actions → Workflow → `complete-package` artifact
- **Automatic Releases**: Created daily on main branch pushes
- **Release Assets**: Complete packages automatically attached
- **Memory Reports**: Shows flash/RAM usage in workflow logs

### Automatic Release System
- **Daily Releases**: Every push creates a dated release (e.g., `25112025`)
- **Smart Updates**: Updates existing releases if date tag exists
- **Complete Packages**: Source code + compiled firmware included
- **No Manual Work**: Fully automated CI/CD pipeline

### File Structure in Release ZIP
```
25112025_PID_simple_controll.zip/
├── esp32-c3/
│   ├── control/
│   │   ├── control.ino        # Source code (bench)
│   │   └── compiled/          # ← Ready-to-flash firmware
│   ├── embedded/
│   │   ├── embedded.ino       # Source code (production)
│   │   └── compiled/          # ← Ready-to-flash firmware
│   ├── BUILDS.md
│   └── DIAGNOSTICS.md
├── docs/                      # Documentation
├── README.md                  # Main documentation
└── ...
```

## Why Only One Workflow?

- **Simplicity**: One workflow handles the entire pipeline
- **No Conflicts**: No cross-workflow dependencies or artifacts
- **Complete Automation**: Compilation → Packaging → Release all in one
- **Easier Maintenance**: Single workflow to manage and debug

**This workflow does everything automatically! Push to main → Get a complete release!**

---

*Previous secondary workflow was removed as redundant.*
