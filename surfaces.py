import pyg4ometry as pg4
import numpy as np

def define_optical_detector(reg: pg4.geant4.Registry, sipm_efficiency: float = 1.0):
    """Define optical surfaces for optical detectors."""

    energy       = np.array([1, 20.0]) # eV
    efficiency   = np.array([sipm_efficiency, sipm_efficiency])
    reflectivity = np.array([0., 0.])

    detector_optical_surface = pg4.geant4.solid.OpticalSurface(
        name="detector_optical_surface", 
        finish="polished", 
        model="unified",
        surf_type="dielectric_metal", 
        value=1, 
        registry=reg
    )
    detector_optical_surface.addVecProperty("EFFICIENCY", energy, efficiency, eunit="eV")
    detector_optical_surface.addVecProperty("REFLECTIVITY", energy, reflectivity, eunit="eV")

    return detector_optical_surface

def define_Vikuiti(reg: pg4.geant4.Registry):
    """Define optical surfaces for Vikuiti reflector."""
    
    energy = np.array([2.07, 2.75, 3.26, 3.35, 4.13, 4.96])
    reflectivity = np.array([0.98, 0.98, 0.98, 0.1, 0.1, 0.1])
    specularlobe = np.array([0.1, 0.1, 0.1, 0.1, 0.1, 0.1])
    specularspike = np.array([0.8, 0.8, 0.8, 0.8, 0.8, 0.8])
    backscatter = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    rindex = np.array([1.6, 1.6, 1.6, 1.6, 1.6, 1.6])
    efficiency = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0])

    vikuiti_optical_surface = pg4.geant4.solid.OpticalSurface(
        name="vikuiti_optical_surface", 
        finish="polished", 
        model="unified",
        surf_type="dielectric_metal", 
        value=1, 
        registry=reg
    )
    
    vikuiti_optical_surface.addVecProperty("REFLECTIVITY", energy, reflectivity, eunit="eV")
    vikuiti_optical_surface.addVecProperty("RINDEX", energy, rindex, eunit="eV")
    vikuiti_optical_surface.addVecProperty("SPECULARLOBECONSTANT", energy, specularlobe, eunit="eV")
    vikuiti_optical_surface.addVecProperty("SPECULARSPIKECONSTANT", energy, specularspike, eunit="eV")
    vikuiti_optical_surface.addVecProperty("BACKSCATTERCONSTANT", energy, backscatter, eunit="eV")
    vikuiti_optical_surface.addVecProperty("EFFICIENCY", energy, efficiency, eunit="eV")

    return vikuiti_optical_surface

def define_surfaces(reg, sipm_efficiency: float = 1.0):
    """Define optical surfaces to attach to materials used in the simulation."""

    vikuiti_optical_surface = define_Vikuiti(reg)
    detector_optical_surface = define_optical_detector(reg, sipm_efficiency)

    return {"vikuiti": vikuiti_optical_surface,
            "detector": detector_optical_surface}