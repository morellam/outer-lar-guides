# light-guides-sim

Geant4 simulation of wavelength-shifting light guides immersed in liquid argon (LAr) and read out by SiPMs 
on their edges (based on [remage](https://github.com/legend-exp/remage)). It is used to study how much of the 
LAr scintillation light is detected (PDE) as a function of the design: shape and size of the guide, thickness,
SiPM placement, reflector and shifter materials.

## How it works

1. **Geometry** (Python, pyg4ometry): `geometry.py` reads `config.yaml` and writes a GDML file.
   The guide is built by `light_guide.py`, the materials and their optical properties by `materials.py`
   (data in `data/`), the optical surfaces (SiPMs, reflector) by `surfaces.py`.
2. **Simulation** (C++): `main.cc` builds the `light-guide` executable, i.e. remage with a custom output
   scheme (`LGOutputScheme.cc/.hh`) that follows every optical photon and writes the trees described below.
3. **Macros** (`macros/`) choose the source and the output options.

The guide lies in the x–z plane, with the external shifter on its +y face.

## Usage

Generate the geometry (from the repository root, the material data are read from `data/`):

```bash
python geometry.py [config.yaml] [geom.gdml]
```

Both arguments are optional (defaults: `config.yaml`, `geom.gdml`).

Build and run the simulation:

```bash
mkdir -p build && cd build && cmake .. && make -j4 && cd ..
./build/light-guide -t 4 -g geom.gdml -o output.root -w -s x=0 -s y=162.05 -s z=0 -s nev=100 -- macros/alpha.mac
```

`-t` threads, `-o` output file (`.root` or `.lh5`), `-w` overwrite, `--rand-seed N` fixed seed,
`-s key=value` substitutes `{key}` in the macro. A `/RMG/Output/FileName` in the macro overrides `-o`.

## Configuration (`config.yaml`)

Everything is optional except `light_guide.dimensions_in_mm`: missing keys (or sections) take the default
written in brackets. See `config.yaml` for an example.

**`light_guide`**
- `dimensions_in_mm` (**required**): `[x, thickness, z]` for a `rectangle`, `[side length, -, thickness]` for
  a `polygon` (the second value is not used)
- `geometry` (`rectangle`): `rectangle` or `polygon` (regular polygon)
- `n_sides` (`4`): number of sides of the polygon (keep `4` for a `rectangle`)
- `wls` (`PMMA`): material of the guide, one of those defined in `materials.py` (`PMMA`, `PMMA_BBT`, `PEN`, ...)
- `BBT_concentration` (`0.2`): BBT concentration of `PMMA_BBT`, from `0.1` to `1.0` in steps of `0.1`
  (it selects `data/BBT_abs_length_CXX.txt`)

**`sipm`**
- `dimensions_in_mm` (`[6, 6, 1]`): width along the edge, height along the guide thickness, depth
- `placement` (`left_right`): sides with SiPMs
  - `left_right`: short sides (if rectangular, otherwise even sides)
  - `top_bottom`: long sides (if rectangular, otherwise odd sides)
  - `all`: all the sides
- `number` (`12`): total number of SiPMs on the light guide, equally spaced along the instrumented sides
- `gap_in_mm` (`0`): LAr gap between the edge of the guide and the SiPM (or window, if any)
- `efficiency` (`1`): detection efficiency of the SiPMs, the same at all wavelengths
- `window_material` (`Epoxy`): optical window between the guide and each SiPM, `null` for no window
- `window_dimensions_in_mm` (`[6, 6, 0.3]`): same convention as `dimensions_in_mm`
- `cover` (`true`): opaque cover on the back and lateral faces of the SiPMs, so that only the face towards
  the guide is active
- `cover_window` (`true`): the cover closes also the lateral faces of the epoxy windows

**`external_wls`**
- `material` (`null`, no external shifter): `pTP`, `TPB`, `PEN`, or another material of `materials.py`
- `wls_thickness_in_mm` (required with a `material`): thickness of the shifter layer
- `gap_in_mm` (`0`): LAr gap between the guide and the substrate (or the shifter, without substrate)
- `substrate` (`false`): PMMA plate carrying the shifter, between the shifter and the guide
- `substrate_thickness_in_mm` (`1`)

**`reflector`**
- `placement` (`false`): reflector on the lateral faces of the guide (98% reflectivity in the visible), with
  holes for the SiPMs
- `gap_in_mm` (`0`): LAr gap between the guide and the reflector, `null` for the same gap as the SiPMs

## Macros

`macros/alpha.mac` simulates `nev` alphas of 5 MeV at the position (`x`, `y`, `z`), in mm and in global
coordinates. The four values are given on the command line and are all required (remage stops if one is
missing):

```bash
./build/light-guide -t 4 -g geom.gdml -o alpha.root -w -s x=0 -s y=162.05 -s z=0 -s nev=100 -- macros/alpha.mac
```

- The guide is centred at x = z = 0 and lies in the x–z plane. The top of the external shifter is at
  y = 100 mm + guide thickness + `external_wls.gap_in_mm` + `substrate_thickness_in_mm` + `wls_thickness_in_mm`
  (112.05 mm for `config.yaml`): a source h mm above the shifter is at that y + h (162.05 mm = 5 cm above, in
  the example).
- The output file is the one given with `-o`.
- For a scan of the source position, run the macro once per position.


`/RMG/Output/LGOutputScheme/StoreAllGuidePhotons true|false` in the macro chooses what goes into `LGOutput`
(all the photons emitted in the guide, or only the detected ones).

## Output

Two trees in `stp/`:

**`LGEventStats`**, one row per event with photon counters. Each photon is counted at most once in each
counter. "LAr photons" are the photons created in the liquid: scintillation photons, or the primary photons
of the macro. The `wlsabs` counters are absorptions by the WLS process (the photon is converted, or lost if
the quantum efficiency is below 1), the `bulkabs` ones are absorptions without re-emission (`ABSLENGTH`).
- **LAr**
  - `n_phot_produced_scint`: scintillation photons produced in LAr
  - `n_phot_bulkabs_lar`: LAr photons absorbed in LAr
- **Arrival on the detector** (a photon "hits" a surface when it reaches it, whether it then enters or is
  reflected)
  - `n_phot_hit_wls_external`: LAr photons reaching the external shifter
  - `n_phot_refl_wls_external`: LAr photons reflected back by the external shifter
  - `n_phot_hit_lightguide`: LAr photons reaching the guide directly (e.g. on the faces without shifter)
  - `n_phot_refl_lightguide`: LAr photons reflected back by the guide
  - `n_phot_hit_outer`: LAr photons reaching the outermost surface of the detector (external shifter or
    guide, whichever comes first)
- **Detection**
  - `n_phot_det`: detected photons emitted by the WLS of the guide
  - `n_phot_det_all`: all the detected photons, whatever their origin (e.g. also photons of the external
    shifter reaching a SiPM directly)
  - `efficiency`: `n_phot_det / n_phot_hit_outer` of the event; for the PDE of a run use the ratio of the
    sums over the events
- **External shifter**
  - `n_phot_produced_wls_external`: photons emitted by the external shifter; `n_phot_produced_wls_external_reemitted`
    are those coming from the re-absorption of another photon of the shifter
  - `n_phot_wlsabs_wls_external`, `n_phot_bulkabs_wls_external`: photons absorbed in the external shifter
    (any origin)
  - `n_phot_wls_external_hit_lightguide`: photons of the external shifter reaching the guide
  - `n_phot_wls_external_refl_lightguide`: photons of the external shifter reflected back by the guide
- **Substrate**
  - `n_phot_wlsabs_substrate`, `n_phot_bulkabs_substrate`: photons absorbed in the substrate (any origin)
- **Light guide**
  - `n_phot_produced_wls_guide`: photons emitted by the WLS of the guide; `n_phot_produced_wls_guide_reemitted`
    are those coming from the re-absorption of another photon of the guide
  - `n_phot_wlsabs_guide`, `n_phot_bulkabs_guide`: photons absorbed in the guide (any origin)
- **Losses**
  - `n_phot_bulkabs_lar_wls`: photons of the external shifter or of the guide absorbed in LAr
  - `n_phot_escaped_guide_side_<k>`, `n_phot_escaped_guide_front`, `n_phot_escaped_guide_back`: photons
    leaving the guide through each face (any origin, also if they come back later; for the photons of the
    guide that are really lost use `fate` in `LGOutput`)
  - `n_phot_absorbed_reflector`: photons absorbed on the reflectors (any origin)
  - `n_phot_absorbed_sipm_cover`: photons killed on the SiPM covers (any origin)

**`LGOutput`**, one row per photon emitted by the WLS of the guide (only the detected ones, unless
`StoreAllGuidePhotons` is `true`):
- `evtID`, `trackID`: event and Geant4 track of the photon
- `lambda_nm`: wavelength of the photon
- `time_ns`: time at the end of the photon track, from the start of the event (for a detected photon, the
  detection time)
- `track_vertex_x/y/z_mm`: emission point of the photon in the guide (global coordinates)
- `track_length_mm`: total length of the photon track, from the emission point to its end, including the
  parts outside the guide (SiPM window, LAr gap, after leaving the guide, ...)
- `guide_path_mm`: length travelled inside the guide only (summed over all the passages, if the photon
  leaves the guide and comes back); this is the length to compare with the absorption length of the guide.
  For a detected photon that never left the guide, it is `track_length_mm` minus the path in the window
- `sipm_id`: SiPM reached by the photon (`NN` of `sipm_NN`), `-1` if it did not reach any SiPM
- `n_refl_guide`: reflections on the faces of the guide, seen from inside; `n_refl_guide_tir` are the total
  internal reflections and `n_refl_guide_fresnel` the Fresnel (partial) reflections, the rest are the
  reflections on a reflector in contact with the guide
- `n_bounce_reflector`: reflections on the reflectors, in total and on the reflector of each side
  (`n_bounce_reflector_<k>`), also from the LAr gap if the reflector is not in contact
- `n_exit_guide`: number of times the photon left the guide through one of its faces (the passage into a
  SiPM window is not counted)
- `exit_face`: face through which the photon left the guide for the last time without coming back
  (`0`...`N-1` lateral sides, `N` front, `N+1` back), `-1` if it ended inside the guide or on a SiPM
- `reemitted`: `1` if the photon comes from the re-absorption of another photon of the guide, `0` if it comes
  from a photon coming from outside (e.g. from the external shifter)
- `fate`: how the photon ends:
   - `0`: detected by a SiPM
   - `1`: absorbed in the guide (bulk absorption)
   - `2`: re-absorbed by the WLS of the guide (it may be re-emitted as a new photon, with `reemitted = 1`)
   - `3`: absorbed on the reflector
   - `4`: reached a SiPM but not detected (SiPM efficiency)
   - `5`: left the guide through a lateral face and lost outside
   - `6`: left the guide through the front face (towards the external shifter) and lost outside
   - `7`: left the guide through the back face and lost outside
   - `8`: none of the other cases
   - `9`: killed on a SiPM cover

Lateral sides are numbered as in `light_guide.py` (side 0 towards +x, side 1 towards +z, ...).

Optional remage trees: 
- `vtx` (`/RMG/Output/ActivateOutputScheme Vertex`) 
- `optical` (`/RMG/Geometry/RegisterDetector Optical sipm_.* 00`)
- `tracks` and `processes` (`/RMG/Output/ActivateOutputScheme Track`). Optical photons are included only
   with `/RMG/Output/Track/StoreOpticalPhotons true`, which makes the files very large.

Example (PDE of a run):

```python
import uproot
st = uproot.open("output.root")["stp/LGEventStats"].arrays(library="pd")
pde = st.n_phot_det.sum() / st.n_phot_hit_outer.sum()
```
