import pygeomoptics.lar
import pyg4ometry as pg4
import numpy as np
import pint

def photon_energy_from_nm(wavelength_nm):
    h_eVs = 4.1357e-15        # eV*s
    c_ms  = 2.99792458e8     # m/s
    return (h_eVs * c_ms * 1e9) / wavelength_nm  # eV


def define_PMMA(reg: pg4.geant4.Registry):
    """Define PMMA material and its optical properties."""

    H = reg.materialDict["hydrogen"]
    C = reg.materialDict["carbon"]
    O = reg.materialDict["oxygen"]

    # PMMA (Polymethyl methacrylate) C_5 H_8 O_2
    pmma = pg4.geant4.MaterialCompound("pmma", 1.19, 3, reg)   
    pmma.add_element_natoms(H,8)
    pmma.add_element_natoms(C,5)
    pmma.add_element_natoms(O,2)

    photon_energy = [
    2.0664,2.0879,2.1095,2.1314,2.1533,2.1754,2.1976,2.2200,2.2425,2.2651,
    2.2879,2.3108,2.3339,2.3572,2.3806,2.4042,2.4279,2.4518,2.4759,2.5001,
    2.5245,2.5490,2.5737,2.5986,2.6236,2.6487,2.6740,2.6995,2.7251,2.7508,
    2.7767,2.8027,2.8289,2.8552,2.8817,2.9083,2.9351,2.9620,2.9890,3.0162,
    3.0436,3.0711,3.0988,3.1266,3.1545,3.1826,3.2108,3.2392,3.2677,3.2964,
    3.3252,3.3542,3.3833,3.4126,3.4420,3.4716,3.5013,3.5312,3.5612,3.5914,
    3.6217,3.6522,3.6828,3.7136,3.7445,3.7755,3.8067,3.8381,3.8696,3.9012,
    3.9329,3.9648,3.9969,4.0291,4.0614,4.0939,4.1266,4.1594,4.1923,4.2254,
    4.2587,4.2921,4.3257,4.3594,4.3933,4.4273,4.4615,4.4959,4.5304,4.5650,
    4.5998,4.6348,4.6699,4.7052,4.7406,4.7762,4.8119,4.8478,4.8839,4.9201
    ]

    abs_length = [
    10.0000,9.8620,9.7264,9.5923,9.4604,9.3306,9.2029,9.0774,8.9540,8.8327,
    8.7135,8.5964,8.4813,8.3682,8.2571,8.1480,8.0409,7.9357,7.8325,7.7312,
    7.6318,7.5343,7.4386,7.3448,7.2528,7.1626,7.0742,6.9876,6.9027,6.8195,
    6.7381,6.6583,6.5803,6.5039,6.4292,6.3561,6.2846,6.2147,6.1463,6.0795,
    6.0143,5.9505,5.8882,5.8274,5.7681,5.7102,5.6537,5.5986,5.5449,5.4926,
    5.4416,5.3920,5.3437,5.2967,5.2510,5.2065,5.1633,5.1214,5.0806,5.0411,
    5.0028,4.9656,4.9296,4.8947,4.8609,4.8282,4.7966,4.7660,4.7365,4.7080,
    4.6805,4.6540,4.6285,4.6040,4.5804,4.5577,4.5360,4.5151,4.4952,4.4761,
    4.4579,4.4406,4.4241,4.4085,4.3937,4.3797,4.3665,4.3541,4.3425,4.3317,
    4.3216,4.3123,4.3037,4.2959,4.2888,4.2825,4.2769,4.2720,4.2678,4.2644
    ]

    pmma.addVecProperty("ABSLENGTH", photon_energy, abs_length, vunit="m")

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
    pTP.addConstProperty("WLSTIMECONSTANT", 0.5, "ns")  # in ns

def define_lar(reg: pg4.geant4.Registry):
    """Define Liquid Argon (LAr) material and its optical properties."""

    u = pint.get_application_registry().get() 

    lar = pg4.geant4.MaterialSingleElement("lAr", 18, 39.948, 1.396, reg) 

    pygeomoptics.lar.pyg4_lar_attach_rindex(lar, reg)
    pygeomoptics.lar.pyg4_lar_attach_attenuation(lar, reg, lar_temperature=88.8 * u.K)
    pygeomoptics.lar.pyg4_lar_attach_scintillation(lar, reg)

def define_materials(reg: pg4.geant4.Registry):
    """Define materials used in the simulation and add them to the registry."""

    pg4.geant4.ElementSimple("hydrogen", "H",   1, 1.008,   reg)
    pg4.geant4.ElementSimple("carbon",   "C",   6, 12.0096, reg)
    pg4.geant4.ElementSimple("oxygen",   "O",   8, 16.0,    reg)

    define_lar(reg)
    define_PMMA(reg)
    define_pTP(reg)
    