from pygeomtools import write_pygeom
import pyg4ometry as pg4

import light_guide
from surfaces import define_surfaces
from materials import define_materials


def main():
    # Initialization
    config_file = "config.yaml"
    reg = pg4.geant4.Registry()
    define_materials(reg)
    surfaces = define_surfaces(reg)

    # Setup World
    world_s = pg4.geant4.solid.Box("world_s", 10000, 10000, 10000, registry=reg, lunit="mm")
    world_l = pg4.geant4.LogicalVolume(world_s, "G4_Galactic", "world_l", registry=reg)
    reg.setWorld(world_l)

    # Setup LAr container
    container_s = pg4.geant4.solid.Box("container_s", 10000, 10000, 10000, registry=reg, lunit="mm")
    container_l = pg4.geant4.LogicalVolume(container_s, reg.materialDict["lAr"], "container_l", registry=reg)
    container_l.pygeom_color_rgba = False
    pg4.geant4.PhysicalVolume([0, 0, 0], [0, 0, 0], container_l, "container", world_l, registry=reg)

    # PMMA Panel for Light Guide Placement
    panel_y = 100
    panel_s = pg4.geant4.solid.Box("panel_s", 1000, panel_y, 3000, registry=reg, lunit="mm")
    panel_l = pg4.geant4.LogicalVolume(panel_s, reg.materialDict["PMMA"], "panel_l", registry=reg)
    panel_l.pygeom_color_rgba = False
    # #pg4.geant4.PhysicalVolume([0, 0, 0], [0, 0, 0], panel_l, "panel", container_l, registry=reg)

    # Light Guide Construction
    light_guide_builder = light_guide.create_light_guide(config_file, reg, surfaces)
    light_guide_builder.build_light_guide(container_l)

    # Export Geometry to GDML
    gdml_filename = "geom.gdml"
    write_pygeom(reg, gdml_filename)
    print(f"\nSuccessfully exported geometry to {gdml_filename}\n")


if __name__ == "__main__":
    main()
