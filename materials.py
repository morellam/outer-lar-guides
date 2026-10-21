import pygeomoptics
import pyg4ometry as pg4
import numpy as np
import pint

def photon_energy_from_nm(wavelength_nm):
    h_eVs = 4.1357e-15        # eV*s
    c_ms  = 2.99792458e8     # m/s
    return (h_eVs * c_ms * 1e9) / wavelength_nm  # eV

def _load_array_from_txt(filename):
    return np.loadtxt(filename, delimiter=",")

def _load_wls_abs(concentration):
    C_int = int(round(concentration * 10))
    filename = f"data/BBT_abs_length_C{C_int:02d}.txt"
    return _load_array_from_txt(filename)

def _pmma_intrinsic_abs_length(wl):
    """Intrinsic PMMA absorption length [m]."""
    PMMA_abs_length = _load_array_from_txt("data/PMMA_abs_length.txt")
    idx_pm = np.clip(550 - wl, 0, len(PMMA_abs_length) - 1)
    return 1.5 * PMMA_abs_length[idx_pm]

def _pmma_rayleigh_length(wl):
    """Rayleigh scattering length [m]: 2 m above 380 nm, 10 m below."""
    return np.where(wl >= 380, 2.0, 10.0)

def build_PMMA_optical_properties():
    """Optical properties of pure PMMA: ABSLENGTH and RAYLEIGH (RINDEX is added separately)."""
    wl = np.arange(600, 279, -1)  # wavelength [nm]: 600 -> 280, 1 nm steps

    pm_vals = _pmma_intrinsic_abs_length(wl)
    ABS = np.where(wl >= 551, 30.0, pm_vals)
    RAYLEIGH = _pmma_rayleigh_length(wl)

    return {
        "PhotonEnergy": photon_energy_from_nm(wl),
        "ABS": ABS,
        "RAYLEIGH": RAYLEIGH,
    }

def build_PMMA_BBT_optical_properties(BBT_concentration):
    """Optical properties of PMMA doped with BBT (relative concentration > 0)."""
    wl = np.arange(600, 279, -1) 

    WLS_scint_spectrum = _load_array_from_txt("data/BBT_emiss_spectrum.txt")
    WLS_abs = _load_wls_abs(BBT_concentration)

    idx_wls = np.clip(600 - wl, 0, len(WLS_abs) - 1)
    wls_vals = WLS_abs[idx_wls]

    # BBT below 430 nm, transparent above
    WLSABS = np.where(wl < 430, wls_vals, 1000.0)

    idx_scint = np.clip(wl - 380, 0, len(WLS_scint_spectrum) - 1)
    SCINT = np.where(wl >= 380, WLS_scint_spectrum[idx_scint], 0.0)

    # BBT attenuation above 430 nm, intrinsic PMMA below
    ABS = np.where(wl >= 430, wls_vals, _pmma_intrinsic_abs_length(wl))

    RAYLEIGH = _pmma_rayleigh_length(wl)

    return {
        "PhotonEnergy": photon_energy_from_nm(wl),
        "ABS": ABS,
        "WLSABS": WLSABS,
        "SCINT": SCINT,
        "RAYLEIGH": RAYLEIGH,
    }

def _create_PMMA_compound(name: str, reg: pg4.geant4.Registry):
    """Create a PMMA compound called `name` and attach its RINDEX (common to PMMA and PMMA_BBT)."""

    H = reg.materialDict["hydrogen"]
    C = reg.materialDict["carbon"]
    O = reg.materialDict["oxygen"]

    # PMMA (Polymethyl methacrylate) C_5 H_8 O_2
    pmma = pg4.geant4.MaterialCompound(name, 1.19, 3, reg)
    pmma.add_element_natoms(H,8)
    pmma.add_element_natoms(C,5)
    pmma.add_element_natoms(O,2)

    # Taken from Sultanova, N.G., Kasarova, S.N. & Nikolov, I.D. Characterization of optical properties
    # of optical polymers. Opt Quant Electron 45, 221–232 (2013). https://doi.org/10.1007/s11082-012-9616-6
    pmma_wl_nm = np.array([1052.0, 879.0, 833.0, 703.0, 656.3, 632.8, 587.6, 486.1, 435.8])
    pmma_rindex_energy = photon_energy_from_nm(pmma_wl_nm)
    pmma_rindex_vals = np.array([1.4813, 1.4834, 1.4839, 1.4863, 1.4890, 1.4892, 1.4914, 1.4973, 1.5025])
    pmma.addVecProperty("RINDEX", pmma_rindex_energy, pmma_rindex_vals)

    return pmma

def define_PMMA(reg: pg4.geant4.Registry):
    """Define pure PMMA (no dopant): RINDEX, ABSLENGTH, RAYLEIGH."""

    pmma = _create_PMMA_compound("PMMA", reg)

    props = build_PMMA_optical_properties()
    pmma.addVecProperty("ABSLENGTH", props["PhotonEnergy"], props["ABS"], vunit="m")
    pmma.addVecProperty("RAYLEIGH", props["PhotonEnergy"], props["RAYLEIGH"], vunit="m")

def define_PMMA_BBT(reg: pg4.geant4.Registry, BBT_concentration: float = 0.2):
    """Define PMMA doped with BBT (material name: PMMA_BBT) and its optical properties.

    RINDEX, ABSLENGTH and RAYLEIGH as for pure PMMA (ABSLENGTH includes the BBT absorption),
    plus the WLS properties (WLSABSLENGTH, WLSCOMPONENT, WLSTIMECONSTANT).
    """
    if BBT_concentration <= 0:
        raise ValueError(
            f"PMMA_BBT needs BBT_concentration > 0 (got {BBT_concentration}); "
            "for undoped PMMA use the 'PMMA' material (define_PMMA)."
        )

    pmma_bbt = _create_PMMA_compound("PMMA_BBT", reg)

    props = build_PMMA_BBT_optical_properties(BBT_concentration)
    photon_energy = props["PhotonEnergy"]

    pmma_bbt.addVecProperty("ABSLENGTH", photon_energy, props["ABS"], vunit="m")
    pmma_bbt.addVecProperty("RAYLEIGH", photon_energy, props["RAYLEIGH"], vunit="m")
    pmma_bbt.addVecProperty("WLSABSLENGTH", photon_energy, props["WLSABS"], vunit="m")
    pmma_bbt.addVecProperty("WLSCOMPONENT", photon_energy, props["SCINT"])
    pmma_bbt.addConstProperty("WLSTIMECONSTANT", 0.5, "ns")


def define_Epoxy(reg: pg4.geant4.Registry):
    """Define the epoxy used for the SiPM windows.
    """

    H = reg.materialDict["hydrogen"]
    C = reg.materialDict["carbon"]
    O = reg.materialDict["oxygen"]

    epoxy = pg4.geant4.MaterialCompound("Epoxy", 1.19, 3, reg)
    epoxy.add_element_massfraction(C, 5.0 / 15.0)
    epoxy.add_element_massfraction(O, 2.0 / 15.0)
    epoxy.add_element_massfraction(H, 8.0 / 15.0)

    epoxy_energy = np.array([1.0, 2.034, 4.136, 10.0])  # eV
    epoxy_rindex = np.array([1.5, 1.5, 1.5, 1.5])
    epoxy.addVecProperty("RINDEX", epoxy_energy, epoxy_rindex)


def define_pTP(reg: pg4.geant4.Registry):
    """Define p-Terphenyl (pTP) material and its optical properties."""

    H = reg.materialDict["hydrogen"]
    C = reg.materialDict["carbon"]

    # pTP (p-Terphenyl) C_18 H_14 ??
    pTP = pg4.geant4.MaterialCompound("pTP", 1.23, 2, reg)   
    pTP.add_element_natoms(H,14)
    pTP.add_element_natoms(C,18)

    pTP_spectrum_energy = np.loadtxt('data/pTP_energy.txt', delimiter=',')
    
    # pTP emission spectrum at 100K
    pTP_scint_spectrum_cryo = np.loadtxt('data/pTP_emission_spectrum.txt', delimiter=',')
    
    pTP_energy = []
    pTP_RI = []
    pTP_abs_length = []
    pTP_kill_after = []
    pTP_rayleigh = []

    for i in range(487, 335, -1):
        pTP_energy.append(photon_energy_from_nm(i))
        pTP_RI.append(1.65)
        pTP_abs_length.append(1e4)     # m   (WLSABSLENGTH)
        pTP_kill_after.append(1e-3)    # m   (ABSLENGTH)
        pTP_rayleigh.append(1e-4)      # m   (RAYLEIGH)
    for i in range(335, 109, -1):
        pTP_energy.append(photon_energy_from_nm(i))
        pTP_RI.append(1.65)
        pTP_abs_length.append(1e-7)    # m   (WLSABSLENGTH)
        pTP_kill_after.append(1e-3)    # m   (ABSLENGTH)
        pTP_rayleigh.append(1e5)       # m   (RAYLEIGH)

    pTP.addVecProperty("RINDEX", pTP_energy, pTP_RI)
    pTP.addVecProperty("ABSLENGTH", pTP_energy, pTP_kill_after, vunit="m")
    pTP.addVecProperty("WLSABSLENGTH", pTP_energy, pTP_abs_length, vunit="m")
    pTP.addVecProperty("RAYLEIGH", pTP_energy, pTP_rayleigh, vunit="m")
    pTP.addVecProperty("WLSCOMPONENT", pTP_spectrum_energy, pTP_scint_spectrum_cryo)
    pTP.addConstProperty("WLSTIMECONSTANT", 0.5, "ns")

def define_lar(reg: pg4.geant4.Registry):
    """Define Liquid Argon (LAr) material and its optical properties."""

    u = pint.get_application_registry().get() 

    lar = pg4.geant4.MaterialSingleElement("lAr", 18, 39.948, 1.396, reg) 

    pygeomoptics.lar.pyg4_lar_attach_rindex(lar, reg)
    pygeomoptics.lar.pyg4_lar_attach_attenuation(lar, reg, lar_temperature=88.8 * u.K)
    pygeomoptics.lar.pyg4_lar_attach_scintillation(lar, reg)

def define_PEN(reg: pg4.geant4.Registry):
    """Define Polyethylene Naphthalate (PEN) material and its optical properties."""

    H = reg.materialDict["hydrogen"]
    C = reg.materialDict["carbon"]
    O = reg.materialDict["oxygen"]

    # PEN (Polyethylene Naphthalate) C_14 H_10 O_4
    pen = pg4.geant4.MaterialCompound("PEN", 1.33, 3, reg)   
    pen.add_element_natoms(H,10)
    pen.add_element_natoms(C,14)
    pen.add_element_natoms(O,4)

    pygeomoptics.pen.pyg4_pen_attach_rindex(pen, reg)
    pygeomoptics.pen.pyg4_pen_attach_attenuation(pen, reg)
    pygeomoptics.pen.pyg4_pen_attach_scintillation(pen, reg)
    pygeomoptics.pen.pyg4_pen_attach_wls(pen, reg, quantum_efficiency = True)

def define_TPB(reg: pg4.geant4.Registry):
    """Define Tetraphenyl butadiene (TPB) material and its optical properties."""

    H = reg.materialDict["hydrogen"]
    C = reg.materialDict["carbon"]

    # TPB (Tetraphenyl butadiene) C_28 H_22
    tpb = pg4.geant4.MaterialCompound("TPB", 1.079, 2, reg)   
    tpb.add_element_natoms(H,22)
    tpb.add_element_natoms(C,28)

    pygeomoptics.tpb.pyg4_tpb_attach_rindex(tpb, reg)
    pygeomoptics.tpb.pyg4_tpb_attach_wls(tpb, reg, quantum_efficiency = True, emission_spectrum = "default")

def define_materials(reg: pg4.geant4.Registry, BBT_concentration):
    """Define materials used in the simulation and add them to the registry.
    """

    pg4.geant4.ElementSimple("hydrogen", "H",   1, 1.008,   reg)
    pg4.geant4.ElementSimple("carbon",   "C",   6, 12.0096, reg)
    pg4.geant4.ElementSimple("oxygen",   "O",   8, 16.0,    reg)

    define_lar(reg)
    define_PMMA(reg)
    define_PMMA_BBT(reg, BBT_concentration)
    define_Epoxy(reg)
    define_pTP(reg)
    define_PEN(reg)
    define_TPB(reg)