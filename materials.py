import pygeomoptics
import pyg4ometry as pg4
import numpy as np
import pint

def photon_energy_from_nm(wavelength_nm):
    h_eVs = 4.1357e-15        # eV*s
    c_ms  = 2.99792458e8     # m/s
    return (h_eVs * c_ms * 1e9) / wavelength_nm  # eV

def load_array_from_txt(filename):
    return np.loadtxt(filename, delimiter=",")

def load_wls_abs(concentration):
    C_int = int(round(concentration * 10))
    filename = f"data/BBT_abs_length_C{C_int:02d}.txt"
    return load_array_from_txt(filename)

def build_optical_properties(WLSConc):

    wl = np.arange(600, 279, -1)  # wavelength
    n = wl.size

    photon_energy = photon_energy_from_nm(wl)  

    WLS_scint_spectrum = load_array_from_txt("data/BBT_emiss_spectrum.txt")
    PMMA_abs_length = load_array_from_txt("data/PMMA_abs_length.txt")

    # --- WLS ---
    if WLSConc >= 0:
        WLS_abs = load_wls_abs(WLSConc)
        idx_wls = np.clip(600 - wl, 0, len(WLS_abs) - 1)
        wls_vals = WLS_abs[idx_wls]
        WLSABS = np.where(wl < 430, wls_vals, 1000.0)
    else:
        WLSABS = np.zeros(n)

    # --- SCINT ---
    idx_scint = np.clip(wl - 380, 0, len(WLS_scint_spectrum) - 1)
    SCINT = np.where(wl >= 380, WLS_scint_spectrum[idx_scint], 0.0)

    # --- ABS ---
    if WLSConc >= 0:
        idx_wls = np.clip(600 - wl, 0, len(WLS_abs) - 1)
        wls_vals = WLS_abs[idx_wls]

        idx_pm = np.clip(550 - wl, 0, len(PMMA_abs_length) - 1)
        pm_vals = 1.5 * PMMA_abs_length[idx_pm]

        ABS = np.where(wl >= 430, wls_vals, pm_vals)
    else:
        idx_pm = np.clip(550 - wl, 0, len(PMMA_abs_length) - 1)
        pm_vals = 1.5 * PMMA_abs_length[idx_pm]
        ABS = np.where(wl >= 551, 30.0, pm_vals)

    # --- RAYLEIGH ---
    RAYLEIGH = np.where(wl >= 380, 2.0, 10.0)

    return {
        "PhotonEnergy": photon_energy,
        "ABS": ABS,
        "WLSABS": WLSABS,
        "SCINT": SCINT,
        "RAYLEIGH": RAYLEIGH,
    }

def define_PMMA(reg: pg4.geant4.Registry):
    """Define PMMA material and its optical properties."""

    H = reg.materialDict["hydrogen"]
    C = reg.materialDict["carbon"]
    O = reg.materialDict["oxygen"]

    # PMMA (Polymethyl methacrylate) C_5 H_8 O_2
    pmma = pg4.geant4.MaterialCompound("PMMA", 1.19, 3, reg)   
    pmma.add_element_natoms(H,8)
    pmma.add_element_natoms(C,5)
    pmma.add_element_natoms(O,2)

    # Taken from Sultanova, N.G., Kasarova, S.N. & Nikolov, I.D. Characterization of optical properties 
    # of optical polymers. Opt Quant Electron 45, 221–232 (2013). https://doi.org/10.1007/s11082-012-9616-6
    pmma_wl_nm = np.array([1052.0, 879.0, 833.0, 703.0, 656.3, 632.8, 587.6, 486.1, 435.8])
    pmma_rindex_energy = photon_energy_from_nm(pmma_wl_nm)
    pmma_rindex_vals = np.array([1.4813, 1.4834, 1.4839, 1.4863, 1.4890, 1.4892, 1.4914, 1.4973, 1.5025])

    BBT_optical_properties = build_optical_properties(1)
    photon_energy = BBT_optical_properties["PhotonEnergy"]
    ABS      = BBT_optical_properties["ABS"]
    WLSABS   = BBT_optical_properties["WLSABS"]
    SCINT    = BBT_optical_properties["SCINT"]
    RAYLEIGH = BBT_optical_properties["RAYLEIGH"]

    pmma.addVecProperty("RINDEX", pmma_rindex_energy, pmma_rindex_vals)
    pmma.addVecProperty("ABSLENGTH", photon_energy, ABS, vunit="m")
    # add check on concentration level (>0 or not)
    pmma.addVecProperty("WLSABSLENGTH", photon_energy, WLSABS, vunit="m")
    pmma.addVecProperty("WLSCOMPONENT", photon_energy, SCINT, vunit="m")
    pmma.addVecProperty("RAYLEIGH", photon_energy, RAYLEIGH, vunit="m")
    pmma.addConstProperty("WLSTIMECONSTANT", 0.5, "ns")

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

    for i in range(487, 335, -1):
        pTP_energy.append(photon_energy_from_nm(i))
        pTP_RI.append(1.65)
        pTP_abs_length.append(1e3)     # m   (WLSABSLENGTH)
        pTP_kill_after.append(1e-3)    # m   (ABSLENGTH)
    for i in range(335, 109, -1):
        pTP_energy.append(photon_energy_from_nm(i))
        pTP_RI.append(1.65)
        pTP_abs_length.append(1e-7)    # m   (WLSABSLENGTH)
        pTP_kill_after.append(1e-3)    # m   (ABSLENGTH)

    pTP.addVecProperty("RINDEX", pTP_energy, pTP_RI)
    pTP.addVecProperty("ABSLENGTH", pTP_energy, pTP_kill_after, vunit="m")
    pTP.addVecProperty("WLSABSLENGTH", pTP_energy, pTP_abs_length, vunit="m")
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

def define_materials(reg: pg4.geant4.Registry):
    """Define materials used in the simulation and add them to the registry."""

    pg4.geant4.ElementSimple("hydrogen", "H",   1, 1.008,   reg)
    pg4.geant4.ElementSimple("carbon",   "C",   6, 12.0096, reg)
    pg4.geant4.ElementSimple("oxygen",   "O",   8, 16.0,    reg)

    define_lar(reg)
    define_PMMA(reg)
    define_pTP(reg)
    define_PEN(reg)
    define_TPB(reg)
    