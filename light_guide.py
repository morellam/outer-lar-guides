import yaml
import pyg4ometry as pg4

import numpy as np

from math import pi, cos, sin, tan


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
        
        self.wls_material    = self.lg_cfg.get("wls", False)
        self.thickness_in_mm = self.config["external_wls"].get("thickness_in_mm", 0)
        self.wls_ext_gap     = self.config["external_wls"].get("gap_in_mm", 0)
        
        self.sipm_cfg        = self.config["sipm"]
        self.sipm_placement  = self.sipm_cfg["placement"]
        self.sipm_number     = self.sipm_cfg["number"]
        self.sipm_gap        = self.sipm_cfg["gap_in_mm"]
        self.sipm_x, self.sipm_y, self.sipm_z = self.sipm_cfg.get("dimensions_in_mm", [6.0, 6.0, 1.0])

        self.reflector_cfg = self.config["reflector"]
        self.reflector     = self.reflector_cfg["placement"]
        self.reflector_gap = self.reflector_cfg.get("gap_in_mm", self.sipm_gap)

        self.gap_from_panel = 50 # mm
        self.reflector_thickness = .150 # in mm
        
        # compute apothem and side length for polygonal geometry
        if self.geometry == "polygon":
            self.apothem = self.lg_x / 2 / tan(pi / self.n_sides)
            self.side_length = self.lg_x


    def construct_light_guide_container(self): 
        """Constructs the container solid for the Light Guide."""
        sipm_z, sipm_gap = self.sipm_z, self.sipm_gap
        wls_ext_thick = self.thickness_in_mm
        wls_ext_gap   = self.wls_ext_gap
        # if there is also the reflector, just add its thickness and gap for a more conservative container
        d = sipm_z * 2 + sipm_gap if not self.reflector else sipm_z * 2 + sipm_gap + self.reflector_thickness * 2 + self.reflector_gap
        d = d + (wls_ext_thick + wls_ext_gap)* 2  if self.wls_material else d

        if self.geometry == "polygon":
            r_ext = self.apothem + d
            # check if there is external WLS to add its thickness and gap
            z_ext = self.lg_z / 2 + wls_ext_thick * 2 + wls_ext_gap if self.wls_material else self.lg_z / 2
            zPlanes = [-z_ext, z_ext]              
            rInner = [0.0, 0.0]
            rOuter = [r_ext, r_ext] 
            container_s = pg4.geant4.solid.Polyhedra("lightguide_container_s", 0, 2 * pi, self.n_sides, len(zPlanes), zPlanes, rInner, rOuter, registry=self.reg, lunit="mm")
        elif self.geometry == "rectangle":
            z_ext = self.lg_z / 2 + wls_ext_thick * 2 + wls_ext_gap if self.wls_material else self.lg_z / 2
            container_s = pg4.geant4.solid.Box("lightguide_container_s", self.lg_x + d, self.lg_y + d, 2 * z_ext, registry=self.reg, lunit="mm")
        else:
            raise ValueError(f"Unknown Light Guide geometry: {self.geometry}")
        
        self.container_l = pg4.geant4.LogicalVolume(container_s, self.reg.materialDict["lAr"], "lightguide_container_l", registry=self.reg)
        self.container_l.pygeom_color_rgba = False #


    def construct_light_guide_solid(self): 
        """Constructs the solid for the Light Guide."""
        if self.geometry == "polygon":
            zPlanes = [-self.lg_z / 2, self.lg_z / 2]
            rInner = [0.0, 0.0]
            rOuter = [self.apothem, self.apothem]

            lightguide_s = pg4.geant4.solid.Polyhedra("lightguide_s", 0, 2 * pi, self.n_sides, len(zPlanes), zPlanes, rInner, rOuter, registry=self.reg, lunit="mm")
        elif self.geometry == "rectangle":
            lightguide_s = pg4.geant4.solid.Box("lightguide_s", self.lg_x, self.lg_y, self.lg_z, registry=self.reg, lunit="mm")
        else:
            raise ValueError(f"Unknown Light Guide geometry: {self.geometry}")
        
        return lightguide_s


    def construct_external_wls(self): 
        """Construct external WLS, if any."""
        wls_material = self.wls_ext_cfg["material"]
        if not wls_material:
            return None
        
        wls_thickness = self.wls_ext_cfg["thickness_in_mm"]
        wls_gap = self.wls_ext_cfg["gap_in_mm"]
        
        if self.geometry == "polygon":
            zPlanes = [-wls_thickness / 2, wls_thickness / 2]
            rInner = [0.0, 0.0]
            rOuter = [self.apothem, self.apothem]
            wls_external_s = pg4.geant4.solid.Polyhedra("wls_external_s", 0, 2 * pi, self.n_sides, len(zPlanes), zPlanes, rInner, rOuter, registry=self.reg, lunit="mm")
            z = wls_gap + wls_thickness / 2 + self.lg_z / 2
            translation = [0, 0, z]
        elif self.geometry == "rectangle":
            wls_external_s = pg4.geant4.solid.Box("wls_external_s", self.lg_x, wls_thickness, self.lg_z, registry=self.reg, lunit="mm")
            y = wls_gap + wls_thickness / 2 + self.lg_y / 2
            translation = [0, y, 0]
        else:
            return None
        
        wls_external_l = pg4.geant4.LogicalVolume(wls_external_s, self.reg.materialDict[wls_material], "wls_external_l", registry=self.reg)
        wls_external_l.pygeom_color_rgba = (0.180, 0.600, 0.369, 1.0)
        
        pg4.geant4.PhysicalVolume([0, 0, 0], translation, wls_external_l, "wls_external_top", self.container_l, registry=self.reg)

        # return wls_external_s


    def construct_reflector(self):
        if self.geometry == "polygon":
            self.reflector_s = pg4.geant4.solid.Box("reflector_s", self.side_length, self.lg_z, self.reflector_thickness, lunit="mm", registry=self.reg)
            self.reflector_l = pg4.geant4.LogicalVolume(self.reflector_s, self.reg.materialDict["pmma"], "reflector_l", registry=self.reg)
            self.reflector_l.pygeom_color_rgba = (0.92, 0.92, 0.92, 1) # light grey
        elif self.geometry == "rectangle":
            # Short side reflector
            self.reflector_short_s = pg4.geant4.solid.Box("reflector_short_s", self.lg_z, self.lg_y, self.reflector_thickness, lunit="mm", registry=self.reg)
            self.reflector_short_l = pg4.geant4.LogicalVolume(self.reflector_short_s, self.reg.materialDict["pmma"], "reflector_short_l", registry=self.reg)
            self.reflector_short_l.pygeom_color_rgba = (0.92, 0.92, 0.92, 1) # light grey
            # Long side reflector
            self.reflector_long_s  = pg4.geant4.solid.Box("reflector_long_s", self.lg_x, self.lg_y, self.reflector_thickness, lunit="mm", registry=self.reg)
            self.reflector_long_l = pg4.geant4.LogicalVolume(self.reflector_long_s, self.reg.materialDict["pmma"], "reflector_long_l", registry=self.reg)
            self.reflector_long_l.pygeom_color_rgba = (0.92, 0.92, 0.92, 1) # light grey


    def place_detectors(self):
        """Chooses and places SiPMs based on configuration."""
        
        lightguide_container_l = self.container_l
       
        if self.geometry == "polygon":

            sipm_per_side = self.sipm_number // self.n_sides
            if self.sipm_placement != "all": 
                sipm_per_side = (self.sipm_number * 2) // self.n_sides
                
            sipm_index = 0
            sipm_z = self.reg.solidDict["sipm_s"].pZ

            # pg4.geant4.PhysicalVolume([0,0,0], [0, 0, -self.sipm_gap/2], self.sipm_l, "sipm", self.det_l, registry=self.reg)

            for side in range(self.n_sides):

                # Skip sides based on SiPM placement configuration
                place_sipm_on_side = True
                if self.sipm_placement == "left_right" and side % 2 != 0:
                    place_sipm_on_side = False
                elif self.sipm_placement == "top_bottom" and side % 2 == 0:
                    place_sipm_on_side = False 

                # Angle corresponding to the center of each side of the polygon
                side_angle = 2 * pi * side / self.n_sides + pi / self.n_sides
                
                # Position along each side for translation
                det_side_cx = (self.apothem + sipm_z/2) * cos(side_angle)
                det_side_cy = (self.apothem + sipm_z/2) * sin(side_angle)
                
                # Angles definition for correct rotation toward the Light Guide
                tangent_angle = side_angle + pi/2
                tx = cos(tangent_angle)
                ty = sin(tangent_angle)
                rot_angle = side_angle + pi/2
                rotation = [pi/2, rot_angle, 0]
                    
                # SiPM Placement Loop
                if place_sipm_on_side:
                    for j in range(sipm_per_side): 
                        
                        if sipm_per_side > 1:
                            offset = (j - (sipm_per_side - 1)/2) * (self.side_length / sipm_per_side)
                        else:
                            offset = 0

                        x_pos = det_side_cx + offset * tx
                        y_pos = det_side_cy + offset * ty
                        translation = [x_pos, y_pos, 0]

                        # Detector Placement 
                        # pg4.geant4.PhysicalVolume(rotation, translation, self.det_l, f"det_{sipm_index}", lightguide_container_l, registry=self.reg)
                        # pg4.geant4.PhysicalVolume([0,0,0], [0, 0, -self.sipm_gap/2], self.sipm_l, f"sipm_{sipm_index}", self.det_l, registry=self.reg)
                        
                        # SiPM without detector container, hopefully removes overlapping
                        pg4.geant4.PhysicalVolume(rotation, translation, self.sipm_l, f"sipm_{sipm_index}", self.container_l, registry=self.reg)

                        sipm_index += 1

        elif self.geometry == "rectangle":

            sipm_per_side = self.sipm_number // self.n_sides
            if self.sipm_placement != "all": 
                sipm_per_side = (self.sipm_number * 2) // self.n_sides
                
            sipm_index = 0
            sipm_z = self.reg.solidDict["sipm_s"].pZ

            for side in range(self.n_sides):
                # Skip sides based on SiPM placement configuration
                place_sipm_on_side = True
                if self.sipm_placement == "left_right" and side % 2 != 0:       place_sipm_on_side = False
                elif self.sipm_placement == "top_bottom" and side % 2 == 0:     place_sipm_on_side = False 
                    
                if self.n_sides != 4:
                    raise ValueError("Placement for rectangular geometry requires n_sides = 4.")
                    
                # Angle corresponding to the center of each side of the polygon
                side_angle = 2 * pi * side / self.n_sides 

                # Other variables for SiPM placement
                r = self.lg_x * sin(side_angle) + self.lg_z * cos(side_angle)
                distance_per_sipm = (abs(r) / sipm_per_side)
                center_index_offset = (sipm_per_side - 1) / 2   
                
                # Position along each side for translation
                det_side_cx = (self.lg_x/2 + sipm_z/2) * cos(side_angle) 
                det_side_cz = (self.lg_z/2 + sipm_z/2) * sin(side_angle)
                
                # Rotation
                rot_angle = side_angle + pi/2
                rotation = [0, rot_angle, 0]
                
                # SiPM Placement Loop
                if place_sipm_on_side:
                    for j in range(sipm_per_side): 
                        if sipm_per_side > 1:
                            current_offset = (j - center_index_offset) * distance_per_sipm
                        else:
                            current_offset = 0

                        x_pos = det_side_cx + current_offset * sin(side_angle) 
                        z_pos = det_side_cz + current_offset * cos(side_angle)
                        translation = [x_pos, 0, z_pos]
                        
                        pg4.geant4.PhysicalVolume(rotation, translation, self.sipm_l, f"sipm_{sipm_index}", self.container_l, registry=self.reg)
                        
                        sipm_index += 1
            

    def build_light_guide(self, parent_lv: pg4.geant4.LogicalVolume):
        """Build entire Light Guide objects with SiPMs, external shifter and reflector"""

        self.construct_light_guide_container()
        
        # Detector container and SiPM  
        sipm_x, sipm_y, sipm_z = self.sipm_x, self.sipm_y, self.sipm_z # in mm
        det_x, det_y, det_z = sipm_x + 0.1, sipm_y + 0.1, sipm_z + self.sipm_gap + 0.1 # in mm
        self.det_s = pg4.geant4.solid.Box("det_s", det_x, det_y, det_z, registry=self.reg, lunit="mm")
        self.det_l = pg4.geant4.LogicalVolume(self.det_s, self.reg.materialDict["lAr"], "det_l", registry=self.reg)
        self.det_l.pygeom_color_rgba = (1.0, 0.0, 0.0, 0.5) # green
        self.sipm_s = pg4.geant4.solid.Box("sipm_s", sipm_x, sipm_y, sipm_z, registry=self.reg, lunit="mm")
        self.sipm_l = pg4.geant4.LogicalVolume(self.sipm_s, "G4_Si", "sipm_l", registry=self.reg)
        self.sipm_l.pygeom_color_rgba = (0.0, 1.0, 0.0, 1.0) # green

        # set efficiency to 1 and reflectivity to 0 for all wavelength (for testing purposes) 
        energy = np.array([1.0, 15.0])
        eff    = np.array([1.0, 1.0])
        refl   = np.array([0., 0.])

        sipm_optical_surface = pg4.geant4.solid.OpticalSurface(
            name="sipm_optical_surface",
            finish="polished",
            model="unified",
            surf_type="dielectric_metal",
            value=1,
            registry=self.reg
        )

        sipm_optical_surface.addVecProperty("EFFICIENCY", energy, eff, eunit = "eV")
        sipm_optical_surface.addVecProperty("REFLECTIVITY", energy, refl, eunit = "eV")
        pg4.geant4.SkinSurface("sipm_surface", self.sipm_l, sipm_optical_surface, self.reg)

        # Light Guide
        lightguide_s = self.construct_light_guide_solid()
        # lightguide_l = pg4.geant4.LogicalVolume(lightguide_s, self.reg.materialDict["pmma"], "lightguide_l", registry=self.reg)
        lightguide_l = pg4.geant4.LogicalVolume(lightguide_s, self.reg.materialDict["pTP"], "lightguide_l", registry=self.reg)
        lightguide_l.pygeom_color_rgba = (0.0, 0.0, 1.0, 0.5) # blu
        pg4.geant4.PhysicalVolume([0, 0, 0], [0, 0, 0], lightguide_l, "lightguide", self.container_l, registry=self.reg)

        self.place_detectors()

        if self.reflector:
            self.place_reflector()

        if self.wls_material:
            self.construct_external_wls()

        # Rotation and Translation of the Light Guide Container
        if self.geometry == "polygon":
            rotation = [pi/2, 0, pi/self.n_sides] # Polygonal rotation
            panel_y = self.reg.solidDict["panel_s"].pY
            lg_z = self.lg_z
            translation = [0, panel_y/2 + lg_z/2 + self.gap_from_panel, 0]
            self.container_pv = pg4.geant4.PhysicalVolume(rotation, translation, self.container_l, "lightguide_container", parent_lv, registry=self.reg)        
        elif self.geometry == "rectangle":
             lg_y = self.lg_y
             panel_y = self.reg.solidDict["panel_s"].pY
             rotation = [0, 0, 0] # No Rotation for Rectangular geometry
             translation = [0, panel_y/2 + lg_y/2 + self.gap_from_panel, 0]
             self.container_pv = pg4.geant4.PhysicalVolume(rotation, translation, self.container_l, "lightguide_container", parent_lv, registry=self.reg) 

                    
    def place_reflector(self):
        """Chooses and places SiPMs and Reflectors based on configuration."""

        self.construct_reflector()

        lightguide_container_l = self.container_l

        sipm_per_side = self.sipm_number // self.n_sides
        if self.sipm_placement != "all": 
            sipm_per_side = (self.sipm_number * 2) // self.n_sides
            
        sipm_index = 0
        det_s = self.det_s
        
        if self.geometry == "polygon":

            for side in range(self.n_sides):

                # Skip sides based on SiPM placement configuration
                place_sipm_on_side = True
                if self.sipm_placement == "left_right" and side % 2 != 0:
                    place_sipm_on_side = False
                elif self.sipm_placement == "top_bottom" and side % 2 == 0:
                    place_sipm_on_side = False 

                # Angle corresponding to the center of each side of the polygon
                side_angle = 2 * pi * side / self.n_sides + pi / self.n_sides
                
                reflector_side_cx = (self.apothem + self.reflector_thickness/2 + self.reflector_gap) * cos(side_angle)
                reflector_side_cy = (self.apothem + self.reflector_thickness/2 + self.reflector_gap) * sin(side_angle)
                
                rot_angle = side_angle + pi/2
                rotation = [pi/2, rot_angle, 0]

                current_reflector_s = self.reflector_s
                if not place_sipm_on_side:
                    pg4.geant4.PhysicalVolume(rotation, [reflector_side_cx, reflector_side_cy, 0], self.reflector_l, f"reflector_{side}", lightguide_container_l, registry=self.reg)
                    continue
                    
                # SiPM Placement Loop
                if place_sipm_on_side:
                    for j in range(sipm_per_side): 
                        if sipm_per_side > 1:
                            offset = (j - (sipm_per_side - 1)/2) * (self.side_length / sipm_per_side)
                        else:
                            offset = 0
                        # Subtraction volume: reflector - detector
                        current_reflector_s = pg4.geant4.solid.Subtraction(f"reflector_s_{side}_{j}", current_reflector_s, det_s, [[0, 0, 0], [offset, 0, 0]], registry=self.reg)                
                        current_reflector_l = pg4.geant4.LogicalVolume(current_reflector_s, self.reg.materialDict["pmma"], f"subtr_reflector_l_{side}_{j}", registry=self.reg)
                        current_reflector_l.pygeom_color_rgba = (0.92, 0.92, 0.92, 1)

                        sipm_index += 1
            
                # Reflector placement after all SiPMs on the side
                pg4.geant4.PhysicalVolume(rotation, [reflector_side_cx, reflector_side_cy, 0], current_reflector_l, f"subtr_reflector_{side}", lightguide_container_l, registry=self.reg)        

        elif self.geometry == "rectangle":

            if self.n_sides != 4:
                raise ValueError("Placement for rectangular geometry requires n_sides = 4.")

            for side in range(self.n_sides):

                # Decide orientation
                is_vertical = side % 2 == 0
                place_sipm_on_reflector_side = False

                if self.sipm_placement == "left_right" and is_vertical:
                    place_sipm_on_reflector_side = True
                elif self.sipm_placement == "top_bottom" and not is_vertical:
                    place_sipm_on_reflector_side = True
                elif self.sipm_placement == "all":
                    place_sipm_on_reflector_side = True

                side_angle = 2 * pi * side / self.n_sides
                rotation = [0, side_angle + pi/2, 0]

                reflector_side_cx = (self.lg_x / 2 + self.reflector_thickness / 2 + self.reflector_gap) * cos(side_angle)
                reflector_side_cz = (self.lg_z / 2 + self.reflector_thickness / 2 + self.reflector_gap) * sin(side_angle)

                # Select correct reflector solid
                current_reflector_s = self.reflector_short_s if is_vertical else self.reflector_long_s

                # No SiPMs → simple placement
                if not place_sipm_on_reflector_side:
                    current_reflector_l = self.reflector_short_l  if is_vertical else self.reflector_long_l
                    pg4.geant4.PhysicalVolume(rotation, [reflector_side_cx, 0, reflector_side_cz], current_reflector_l, f"reflector_{side}", lightguide_container_l, registry=self.reg)
                    continue

                # Geometry for offsets
                length = self.lg_z if is_vertical else self.lg_x
                distance_per_sipm = length / sipm_per_side
                center_index_offset = (sipm_per_side - 1) / 2

                # Subtractions
                for j in range(sipm_per_side):

                    offset = (j - center_index_offset) * distance_per_sipm
                    subtraction_offset = [offset, 0, 0]

                    current_reflector_s = pg4.geant4.solid.Subtraction(f"reflector_s_{side}_{j}", current_reflector_s, det_s, [[0, 0, 0], subtraction_offset], registry=self.reg)

                    sipm_index += 1

                # Final logical + placement
                current_reflector_l = pg4.geant4.LogicalVolume(current_reflector_s, self.reg.materialDict["pmma"], f"subtr_reflector_{side}", registry=self.reg)
                current_reflector_l.pygeom_color_rgba = (0.92, 0.92, 0.92, 1)

                pg4.geant4.PhysicalVolume(rotation, [reflector_side_cx, 0, reflector_side_cz], current_reflector_l, f"subtr_reflector_{side}", lightguide_container_l, registry=self.reg) 
