import pyg4ometry as pg4

def define_materials(reg: pg4.geant4.Registry) -> None:
    """Define materials used in the simulation and add them to the registry."""

    # PMMA (Polymethyl methacrylate) C_5 H_8 O_2
    pmma = pg4.geant4.MaterialCompound("pmma",1.19,3,reg)   
    H = pg4.geant4.ElementSimple("hydrogen","H",1,1.008, reg)
    C = pg4.geant4.ElementSimple("carbon","C",6,12.0096, reg)
    O = pg4.geant4.ElementSimple("oxygen","O",8,16.0, reg)
    pmma.add_element_natoms(H,8)
    pmma.add_element_natoms(C,5)
    pmma.add_element_natoms(O,2)