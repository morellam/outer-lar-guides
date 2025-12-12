import yaml
import pyg4ometry as pg4
import pygeomtools
from materials import define_materials
from math import pi, cos, sin, tan
# from typing import Optional, Union # Importa Union per i type hints più robusti

class LightGuide:
    """
    Class to construct and manage the Light Guide geometry based on external configuration file.
    """

    def __init__(self, config_path: str, registry: pg4.geant4.Registry):
        self.reg = registry
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)

        # Load configuration parameters
        self.lg_cfg   = self.config["light_guide"]
        self.geometry = self.lg_cfg["geometry"]
        self.n_sides  = self.lg_cfg["n_sides"]
        self.lg_x, self.lg_y, self.lg_z = self.lg_cfg["dimensions_in_mm"]
        
        self.wls_ext_cfg = self.config["external_wls"]
        
        self.sipm_cfg       = self.config["sipm"]
        self.sipm_placement = self.sipm_cfg["placement"]
        self.sipm_number    = self.sipm_cfg["number"]
        self.sipm_gap       = self.sipm_cfg["gap_in_mm"]

        self.reflector_cfg = self.config["reflector"]
        self.reflector     = self.reflector_cfg["placement"]
        self.reflector_gap = self.reflector_cfg["gap_in_mm"]
        
        # compute apothem and side length for polygonal geometry
        if self.geometry == "polygonal":
            self.apothem = self.lg_x / 2 / tan(pi / self.n_sides)
            self.side_length = self.lg_x
        # else: # Rectangular
        #     self.apothem = self.lg_x / 2 
            # self.side_length = self.lg_y 


    def construct_container_solid(self): 
        """Constructs the container solid for the Light Guide."""
        sipm_z, sipm_gap = 1.0, self.sipm_gap
        wls_ext_thick = self.wls_ext_cfg.get("thickness_in_mm", 0)
        wls_ext_gap = self.wls_ext_cfg.get("gap_in_mm", 0)
        z_ext = self.lg_z / 2 + wls_ext_thick * 2 + wls_ext_gap

        if self.geometry == "polygonal":
            r_ext = self.apothem + sipm_z * 2 + sipm_gap
            zPlanes = [-z_ext, z_ext]              
            rInner = [0.0, 0.0]
            rOuter = [r_ext, r_ext] 
            container_s = pg4.geant4.solid.Polyhedra("lightguide_container_s", 0, 2 * pi, self.n_sides, len(zPlanes), zPlanes, rInner, rOuter, registry=self.reg, lunit="mm")
        elif self.geometry == "rectangular":
            container_s = pg4.geant4.solid.Box("lightguide_container_s", self.lg_x + 2 * (sipm_z * 2 + sipm_gap), self.lg_y + 2 * (sipm_z * 2 + sipm_gap), 2 * z_ext, registry=self.reg, lunit="mm")
        else:
            raise ValueError(f"Geometria Light Guide sconosciuta: {self.geometry}")
            
        return container_s    


    def construct_light_guide_solid(self): 
        """Constructs the solid for the Light Guide."""
        if self.geometry == "polygonal":
            zPlanes = [-self.lg_z / 2, self.lg_z / 2]
            rInner = [0.0, 0.0]
            rOuter = [self.apothem, self.apothem]

            lightguide_s = pg4.geant4.solid.Polyhedra("lightguide_s", 0, 2 * pi, self.n_sides, len(zPlanes), zPlanes, rInner, rOuter, registry=self.reg, lunit="mm")
        elif self.geometry == "rectangular":
            lightguide_s = pg4.geant4.solid.Box("lightguide_s", self.lg_x, self.lg_y, self.lg_z, registry=self.reg, lunit="mm")
        else:
            raise ValueError(f"Unknown Light Guide geometry: {self.geometry}")
        
        return lightguide_s


    def construct_external_wls_solid(self): 
        """Construct external WLS, if any."""
        if not self.wls_ext_cfg["material"]:
            return None
        
        thickness = self.wls_ext_cfg["thickness_in_mm"]
        
        if self.geometry == "polygonal":
            zPlanes = [-thickness / 2, thickness / 2]
            rInner = [0.0, 0.0]
            rOuter = [self.apothem, self.apothem]
            wls_external_s = pg4.geant4.solid.Polyhedra("wls_external_s", 0, 2 * pi, self.n_sides, len(zPlanes), zPlanes, rInner, rOuter, registry=self.reg, lunit="mm")
        elif self.geometry == "rectangular":
             wls_external_s = pg4.geant4.solid.Box("wls_external_s", self.lg_x, self.lg_y, thickness, registry=self.reg, lunit="mm")
        else:
            return None

        return wls_external_s


    def construct_reflector(self):
        if self.geometry == "polygon":
            self.reflector_s = pg4.geant4.solid.Box("reflector_s", self.side_length, self.lg_z, self.reflector_thickness, lunit="mm", registry=self.reg)
            self.reflector_l = pg4.geant4.LogicalVolume(self.reflector_s, self.reg.materialDict["pmma"], "reflector_l", registry=self.reg)
            self.reflector_l.pygeom_color_rgba = (0.92, 0.92, 0.92, 1) # light grey
        elif self.geometry == "rectangular":
            # Short side reflector
            self.reflector_short_s = pg4.geant4.solid.Box("reflector_short_s", self.reflector_thickness, self.lg_y, self.lg_z, lunit="mm", registry=self.reg)
            self.reflector_short_l = pg4.geant4.LogicalVolume(self.reflector_short_s, self.reg.materialDict["pmma"], "reflector_short_l", registry=self.reg)
            self.reflector_short_l.pygeom_color_rgba = (0.92, 0.92, 0.92, 1) # light grey
            # Long side reflector
            self.reflector_long_s  = pg4.geant4.solid.Box("reflector_long_s", self.lg_x, self.lg_y, self.reflector_thickness, lunit="mm", registry=self.reg)
            self.reflector_long_l = pg4.geant4.LogicalVolume(self.reflector_long_s, self.reg.materialDict["pmma"], "reflector_long_l", registry=self.reg)
            self.reflector_long_l.pygeom_color_rgba = (0.92, 0.92, 0.92, 1) # light grey


    def build_geometry(self, parent_lv: pg4.geant4.LogicalVolume):
        """Costruisce l'intera geometria e la posiziona."""
        
        # Detector container and SiPM solids 
        sipm_x, sipm_y, sipm_z = 6.0, 6.0, 1.0  # in mm
        det_x, det_y, det_z = sipm_x, sipm_y, sipm_z + self.sipm_gap  # in mm
        self.det_s = pg4.geant4.solid.Box("det_s", det_x, det_y, det_z, registry=self.reg, lunit="mm")
        self.sipm_s = pg4.geant4.solid.Box("sipm_s", sipm_x, sipm_y, sipm_z, registry=self.reg, lunit="mm")
        self.reflector_thickness = .150 # in mm
        # self.reflector_s = pg4.geant4.solid.Box("reflector_s_base", self.side_length, self.lg_z, self.reflector_thickness, lunit="mm", registry=self.reg)

        # Logical Volumes for Detector, SiPM and Reflector
        self.det_l = pg4.geant4.LogicalVolume(self.det_s, "G4_lAr", "det_l", registry=self.reg)
        self.det_l.pygeom_color_rgba = False 
        self.sipm_l = pg4.geant4.LogicalVolume(self.sipm_s, "G4_Si", "sipm_l", registry=self.reg)
        self.sipm_l.pygeom_color_rgba = (0.0, 1.0, 0.0, 1.0) # green
        # self.reflector_l = pg4.geant4.LogicalVolume(self.reflector_s, self.reg.materialDict["pmma"], "reflector_l", registry=self.reg)
        # self.reflector_l.pygeom_color_rgba = (0.92, 0.92, 0.92, 1) # light grey

        # Light Guide Container 
        container_s = self.construct_container_solid()
        container_l = pg4.geant4.LogicalVolume(container_s, self.reg.materialDict["pmma"], "lightguide_container_l", registry=self.reg)
        container_l.pygeom_color_rgba = (0.92, 0.92, 0.92, 0.6) # light grey 
        
        # Rotation and Translation of the Light Guide
        rotation = [pi/2, 0, pi/self.n_sides] # Polygonal rotation
        panel_y = self.reg.solidDict["panel_s"].pY
        lg_z = self.lg_z
        gap_from_panel = 50 # mm
        translation = [0, panel_y/2 + lg_z/2 + gap_from_panel, 0]
        if self.geometry == "rectangular":
             lg_y = self.lg_y
             rotation = [0, 0, 0] # No Rotation for Rectangular geometry
             translation = [0, panel_y/2 + lg_y/2 + gap_from_panel, 0] 
        
        
        self.container_pv = pg4.geant4.PhysicalVolume(rotation, translation, container_l, "lightguide_container", parent_lv, registry=self.reg)

        # Light Guide
        lightguide_s = self.construct_light_guide_solid()
        lightguide_l = pg4.geant4.LogicalVolume(lightguide_s, self.reg.materialDict["pmma"], "lightguide_l", registry=self.reg)
        lightguide_l.pygeom_color_rgba = (0.0, 0.0, 1.0, 1) # blu
        pg4.geant4.PhysicalVolume([0, 0, 0], [0, 0, 0], lightguide_l, "lightguide", container_l, registry=self.reg)

        # External WLS 
        wls_external_s = self.construct_external_wls_solid()
        if wls_external_s:
            wls_external_l = pg4.geant4.LogicalVolume(wls_external_s, self.reg.materialDict["pmma"], "wls_external_l", registry=self.reg)
            wls_external_l.pygeom_color_rgba = (0.180, 0.600, 0.369, 1.0)
            wls_thickness = self.wls_ext_cfg["thickness_in_mm"]
            wls_gap = self.wls_ext_cfg["gap_in_mm"]
            z = wls_gap + wls_thickness / 2 + self.lg_z / 2
            pg4.geant4.PhysicalVolume([0, 0, 0], [0, 0, z], wls_external_l, "wls_external_top", container_l, registry=self.reg)

        # SiPM e Reflector
        self.place_detectors_and_reflectors(container_l)


    def place_detectors_and_reflectors(self, lightguide_container_l: pg4.geant4.LogicalVolume):
        """Chooses and places SiPMs and Reflectors based on configuration."""
        
        sipm_per_side = self.sipm_number // self.n_sides
        if self.sipm_placement != "all": 
            sipm_per_side = (self.sipm_number * 2) // self.n_sides
            
        sipm_index = 0
        reflector_thickness = self.reflector_thickness
        # reflector_l = self.reflector_l
        det_s = self.det_s
        # det_x = self.reg.solidDict["det_s"].pX
        # det_y = self.reg.solidDict["det_s"].pY
        det_z = self.reg.solidDict["det_s"].pZ

        for side in range(self.n_sides):

            # Skip sides based on SiPM placement configuration
            place_sipm_on_side = True
            if self.sipm_placement == "left_right" and side % 2 != 0:
                place_sipm_on_side = False
            elif self.sipm_placement == "top_bottom" and side % 2 == 0:
                place_sipm_on_side = False 
            
            if self.geometry == "polygonal":
                # Different reflector implementation between geometries
                reflector_l = self.reflector_l

                # Angle corresponding to the center of each side of the polygon
                side_angle = 2 * pi * side / self.n_sides + pi / self.n_sides
                
                # Position along each side for translation
                det_side_cx = (self.apothem + det_z/2) * cos(side_angle)
                det_side_cy = (self.apothem + det_z/2) * sin(side_angle)
                reflector_side_cx = (self.apothem + reflector_thickness/2 + self.reflector_gap) * cos(side_angle)
                reflector_side_cy = (self.apothem + reflector_thickness/2 + self.reflector_gap) * sin(side_angle)
                
                # Angles definition for correct rotation toward the Light Guide
                tangent_angle = side_angle + pi/2
                tx = cos(tangent_angle)
                ty = sin(tangent_angle)
                rot_angle = side_angle + pi/2
                rotation = [pi/2, rot_angle, 0]
                
            elif self.geometry == "rectangular":
                if self.n_sides != 4:
                    raise ValueError("Placemenr for rectangular geometry requires n_sides = 4.")
                    
                # Angle corresponding to the center of each side of the polygon
                side_angle = 2 * pi * side / self.n_sides 

                # Other variables for SiPM placement
                r = self.lg_x * sin(side_angle) + self.lg_z * cos(side_angle)
                distance_per_sipm = (abs(r) / sipm_per_side)
                center_index_offset = (sipm_per_side - 1) / 2   
                
                # Position along each side for translation
                det_side_cx = self.lg_x / 2 * cos(side_angle) 
                det_side_cz = self.lg_z / 2 * sin(side_angle)
                reflector_side_cx = (self.lg_x + reflector_thickness/2 + self.reflector_gap) * cos(side_angle)
                reflector_side_cz = (self.lg_z + reflector_thickness/2 + self.reflector_gap) * sin(side_angle)
                
                # Rotation
                rot_angle = side_angle + pi/2
                rotation = [0, rot_angle, 0]
                       
            current_reflector_s = self.reflector_s
            current_reflector_l = reflector_l

            if not place_sipm_on_side and self.reflector:
                pg4.geant4.PhysicalVolume(rotation, [reflector_side_cx, reflector_side_cy, 0], reflector_l, f"reflector_{side}", lightguide_container_l, registry=self.reg)
                continue

            # SiPM Placement Loop
            if place_sipm_on_side:
                for j in range(sipm_per_side): 
                    
                    if self.geometry == "polygonal":
                        if sipm_per_side > 1:
                            offset = (j - (sipm_per_side - 1)/2) * (self.side_length / sipm_per_side)
                        else:
                            offset = 0

                        x_pos = det_side_cx + offset * tx
                        y_pos = det_side_cy + offset * ty
                        translation = [x_pos, y_pos, 0]

                        # Detector Placement 
                        pg4.geant4.PhysicalVolume(rotation, translation, self.det_l, f"det_{sipm_index}", lightguide_container_l, registry=self.reg)
                        pg4.geant4.PhysicalVolume([0,0,0], [0, 0, -self.sipm_gap/2], self.sipm_l, f"sipm_{sipm_index}", self.det_l, registry=self.reg)
                        
                        if self.reflector:
                            # Subtraction volume: reflector - detector
                            current_reflector_s = pg4.geant4.solid.Subtraction(f"reflector_s_{side}_{j}", current_reflector_s, det_s, [[0, 0, 0], [offset, 0, 0]], registry=self.reg)                
                            current_reflector_l = pg4.geant4.LogicalVolume(current_reflector_s, self.reg.materialDict["pmma"], f"subtr_reflector_l_{side}_{j}", registry=self.reg)
                            current_reflector_l.pygeom_color_rgba = (0.92, 0.92, 0.92, 1)

                    elif self.geometry == "rectangular":
                        
                        if sipm_per_side > 1:
                            current_offset = (j - center_index_offset) * distance_per_sipm
                        else:
                            current_offset = 0

                        x_pos = det_side_cx + current_offset * sin(side_angle) 
                        z_pos = det_side_cz + current_offset * cos(side_angle)
                        translation = [x_pos, 0, z_pos]

                        # Detector Placement 
                        pg4.geant4.PhysicalVolume(rotation, translation, self.det_l, f"det_{sipm_index}", lightguide_container_l, registry=self.reg)
                        pg4.geant4.PhysicalVolume([0,0,0], [0, 0, -self.sipm_gap/2], self.sipm_l, f"sipm_{sipm_index}", self.det_l, registry=self.reg)
                        
                        if self.reflector:
                            # Subtraction volume: reflector - detector
                            current_reflector_s = pg4.geant4.solid.Subtraction(f"reflector_s_{side}_{j}", current_reflector_s, det_s, [[0, 0, 0], [current_offset, 0, 0]], registry=self.reg)                
                            current_reflector_l = pg4.geant4.LogicalVolume(current_reflector_s, self.reg.materialDict["pmma"], f"subtr_reflector_l_{side}_{j}", registry=self.reg)
                            current_reflector_l.pygeom_color_rgba = (0.92, 0.92, 0.92, 1)

                    sipm_index += 1
            
            # Reflector placement after all SiPMs on the side
            if self.reflector:
                pg4.geant4.PhysicalVolume(rotation, [reflector_side_cx, 0, reflector_side_cz], current_reflector_l, f"subtr_reflector_{side}", lightguide_container_l, registry=self.reg)


def main():
    # Initialization
    config_file = "config.yaml"
    reg = pg4.geant4.Registry()
    define_materials(reg)

    # Setup World and LAr Container
    world_s = pg4.geant4.solid.Box("world_s", 5000, 5000, 5000, registry=reg, lunit="mm")
    world_l = pg4.geant4.LogicalVolume(world_s, "G4_Galactic", "world_l", registry=reg)
    reg.setWorld(world_l)

    container_s = pg4.geant4.solid.Box("container_s", 5000, 5000, 5000, registry=reg, lunit="mm")
    container_l = pg4.geant4.LogicalVolume(container_s, "G4_lAr", "container_l", registry=reg)
    container_l.pygeom_color_rgba = False
    pg4.geant4.PhysicalVolume([0, 0, 0], [0, 0, 0], container_l, "container", world_l, registry=reg)
    
    # PMMA Panel for Light Guide Placement
    panel_y = 100 
    panel_s = pg4.geant4.solid.Box("panel_s", 1000, panel_y, 3000, registry=reg, lunit="mm")
    panel_l = pg4.geant4.LogicalVolume(panel_s, reg.materialDict["pmma"], "panel_l", registry=reg)
    panel_l.pygeom_color_rgba = False
    pg4.geant4.PhysicalVolume([0, 0, 0], [0, 0, 0], panel_l, "panel", container_l, registry=reg)

    # Light Guide Construction
    light_guide_builder = LightGuide(config_file, reg)
    light_guide_builder.build_geometry(container_l)#, panel_y)

    # Export Geometry to GDML
    gdml_filename = "geometry.gdml"
    pygeomtools.write_pygeom(reg, gdml_filename)
    print(f"\nSuccessfully exported geometry to {gdml_filename}")


if __name__ == "__main__":
    
    main()