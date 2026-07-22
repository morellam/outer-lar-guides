import yaml
import pyg4ometry as pg4
import numpy as np

from math import pi, cos, sin, tan
from dataclasses import dataclass
from typing import Tuple, Optional

@dataclass
class LightGuideConfig:
    """Dataclass storing geometrical and materials properties of the light guide."""
    dimensions_in_mm: Tuple[float, float, float]
    geometry: str = "rectangle"
    n_sides: int = 4
    wls: str = "PMMA"
    BBT_concentration: Optional[float] = 0.0

@dataclass
class WLSConfig:
    """Dataclass storing material properties of external WaveLength Shifting (WLS) layer."""
    material: Optional[str] = None
    thickness_in_mm: float = 0.0
    gap_in_mm: float = 0.0
    substrate: Optional[str] = None

@dataclass
class SiPMConfig:
    """Dataclass storing properties of the SiPMs."""
    dimensions_in_mm: Tuple[float, float, float] = (6.0, 6.0, 1.0)
    placement: str = "left_right"
    number: int = 12
    gap_in_mm: float = 0.

@dataclass
class ReflectorConfig:
    """Dataclass sotring geometrical properties of the reflector."""
    placement: bool = False
    gap_in_mm: float = 0.1


class BaseLightGuide:
    """Class holding common infrastructure and building steps for all Light Guides."""

    def __init__(self, config_path: str, registry: pg4.geant4.Registry):
        self.registry = registry

        with open(config_path, "r", encoding="utf-8") as f:
            config_dict = yaml.safe_load(f)

        self.lg = LightGuideConfig(**config_dict.get("light_guide", {}))
        self.sipm = SiPMConfig(**config_dict.get("sipm", {}))
        self.wls = WLSConfig(**config_dict.get("external_wls", {}))
        self.reflector = ReflectorConfig(**config_dict.get("reflector", {}))

        self.gap_from_panel_in_mm = 50.0
        self.reflector_thickness_in_mm = 0.150

        self.container_l = None
        self.container_pv = None
        self.sipm_s = None
        self.sipm_l = None
        self.reflector_s = None
        self.reflector_l = None
        self.reflector_short_s = None
        self.reflector_short_l = None
        self.reflector_long_s = None
        self.reflector_long_l = None

    def construct_light_guide_container(self):raise NotImplementedError
    def construct_light_guide_solid(self): raise NotImplementedError
    def construct_external_wls(self): raise NotImplementedError
    def construct_reflector(self): raise NotImplementedError
    def place_detectors(self): raise NotImplementedError
    def place_reflector(self): raise NotImplementedError
    def place_container_in_parent(self, parent_lv): raise NotImplementedError

    def build_light_guide(self, parent_lv: pg4.geant4.LogicalVolume):
        """Common build sequence for Light Guides."""
        self.construct_light_guide_container()
        
        # Setup SiPM Shared Solid/Logical properties
        sipm_x, sipm_y, sipm_z = self.sipm.dimensions_in_mm
        self.sipm_s = pg4.geant4.solid.Box("sipm_s", sipm_x, sipm_y, sipm_z, registry=self.registry, lunit="mm")
        self.sipm_l = pg4.geant4.LogicalVolume(self.sipm_s, "G4_Si", "sipm_l", registry=self.registry)
        self.sipm_l.pygeom_color_rgba = (0.0, 1.0, 0.0, 1.0)

        # Optical Surface setup
        energy, eff, refl = np.array([1, 20.0]), np.array([1.0, 1.0]), np.array([0., 0.])
        sipm_optical_surface = pg4.geant4.solid.OpticalSurface(
            name="sipm_optical_surface", finish="polished", model="unified",
            surf_type="dielectric_metal", value=1, registry=self.registry
        )
        sipm_optical_surface.addVecProperty("EFFICIENCY", energy, eff, eunit="eV")
        sipm_optical_surface.addVecProperty("REFLECTIVITY", energy, refl, eunit="eV")
        pg4.geant4.SkinSurface("sipm_surface", self.sipm_l, sipm_optical_surface, self.registry)

        # Build Main Body
        lightguide_s = self.construct_light_guide_solid()
        lightguide_l = pg4.geant4.LogicalVolume(lightguide_s, self.lg.wls, "lightguide_l", registry=self.registry)
        lightguide_l.pygeom_color_rgba = (0.0, 0.0, 1.0, 0.5)
        pg4.geant4.PhysicalVolume([0, 0, 0], [0, 0, 0], lightguide_l, "lightguide", self.container_l, registry=self.registry)

        self.place_detectors()

        if self.reflector.placement:
            self.place_reflector()

        if self.wls.material is not None:
            self.construct_external_wls()

        self.place_container_in_parent(parent_lv)


class RectangularLightGuide(BaseLightGuide):
    """Specific implementation of a standard rectangular light guide."""

    def construct_light_guide_container(self):
        lg_x, lg_y, lg_z = self.lg.dimensions_in_mm
        sipm_z = self.sipm.dimensions_in_mm[2]

        x = lg_x + self.sipm.gap_in_mm + sipm_z * 2
        if self.reflector.placement:
            x += self.reflector_thickness_in_mm + self.reflector.gap_in_mm
        
        y = lg_y + self.wls.thickness_in_mm * 2 + self.wls.gap_in_mm * 2 if self.wls.material else lg_y
        
        z = lg_z + self.sipm.gap_in_mm + sipm_z * 2
        if self.wls.material:
            z += self.wls.thickness_in_mm + self.wls.gap_in_mm
        
        container_s = pg4.geant4.solid.Box("lightguide_container_s", x, y, z, registry=self.registry, lunit="mm")
        self.container_l = pg4.geant4.LogicalVolume(container_s, self.registry.materialDict["lAr"], "lightguide_container_l", registry=self.registry)
        self.container_l.pygeom_color_rgba = False

    def construct_light_guide_solid(self):
        lg_x, lg_y, lg_z = self.lg.dimensions_in_mm
        return pg4.geant4.solid.Box("lightguide_s", lg_x, lg_y, lg_z, registry=self.registry, lunit="mm")
        
    def construct_external_wls(self):
        lg_x, lg_y, lg_z = self.lg.dimensions_in_mm
        wls_external_s = pg4.geant4.solid.Box("wls_external_s", lg_x, self.wls.thickness_in_mm, lg_z, registry=self.registry, lunit="mm")
        y = self.wls.gap_in_mm + self.wls.thickness_in_mm / 2 + lg_y / 2
        wls_external_l = pg4.geant4.LogicalVolume(wls_external_s, self.registry.materialDict[self.wls.material], "wls_external_l", registry=self.registry)
        wls_external_l.pygeom_color_rgba = (0.180, 0.600, 0.369, 1.0)
        pg4.geant4.PhysicalVolume([0, 0, 0], [0, y, 0], wls_external_l, "wls_external", self.container_l, registry=self.registry)

    def construct_reflector(self):
        lg_x, lg_y, lg_z = self.lg.dimensions_in_mm
        self.reflector_short_s = pg4.geant4.solid.Box("reflector_short_s", lg_z, lg_y, self.reflector_thickness_in_mm, lunit="mm", registry=self.registry)
        self.reflector_short_l = pg4.geant4.LogicalVolume(self.reflector_short_s, self.registry.materialDict["PMMA"], "reflector_short_l", registry=self.registry)
        self.reflector_short_l.pygeom_color_rgba = (0.92, 0.92, 0.92, 1)
        
        self.reflector_long_s  = pg4.geant4.solid.Box("reflector_long_s", lg_x, lg_y, self.reflector_thickness_in_mm, lunit="mm", registry=self.registry)
        self.reflector_long_l = pg4.geant4.LogicalVolume(self.reflector_long_s, self.registry.materialDict["PMMA"], "reflector_long_l", registry=self.registry)
        self.reflector_long_l.pygeom_color_rgba = (0.92, 0.92, 0.92, 1)
        
    def place_detectors(self):
        lg_x, _, lg_z = self.lg.dimensions_in_mm
        sipm_per_side = (self.sipm.number * 2) // self.lg.n_sides if self.sipm.placement != "all" else self.sipm.number // self.lg.n_sides
        sipm_index = 0
        sipm_z = self.registry.solidDict["sipm_s"].pZ

        for side in range(self.lg.n_sides):
            if (self.sipm.placement == "left_right" and side % 2 != 0) or (self.sipm.placement == "top_bottom" and side % 2 == 0):
                continue

            side_angle = 2 * pi * side / self.lg.n_sides 
            r = lg_x * sin(side_angle) + lg_z * cos(side_angle)
            distance_per_sipm = (abs(r) / sipm_per_side)
            
            det_side_cx = (lg_x/2 + sipm_z/2 + self.sipm.gap_in_mm) * cos(side_angle) 
            det_side_cz = (lg_z/2 + sipm_z/2 + self.sipm.gap_in_mm) * sin(side_angle)
            rotation = [0, side_angle + pi/2, 0]
            
            for j in range(sipm_per_side): 
                current_offset = (j - (sipm_per_side - 1) / 2) * distance_per_sipm if sipm_per_side > 1 else 0
                x_pos = det_side_cx + current_offset * sin(side_angle) 
                z_pos = det_side_cz + current_offset * cos(side_angle)
                pg4.geant4.PhysicalVolume(rotation, [x_pos, 0, z_pos], self.sipm_l, f"sipm_{sipm_index:02d}", self.container_l, registry=self.registry)
                sipm_index += 1

    def place_reflector(self):
        self.construct_reflector()
        lg_x, _, lg_z = self.lg.dimensions_in_mm
        sipm_per_side = (self.sipm.number * 2) // self.lg.n_sides if self.sipm.placement != "all" else self.sipm.number // self.lg.n_sides

        for side in range(self.lg.n_sides):
            is_vertical = side % 2 == 0
            place_sipm = self.sipm.placement == "all" or (self.sipm.placement == "left_right" and is_vertical) or (self.sipm.placement == "top_bottom" and not is_vertical)

            side_angle = 2 * pi * side / self.lg.n_sides
            rotation = [0, side_angle + pi/2, 0]
            cx = (lg_x / 2 + self.reflector_thickness_in_mm / 2 + self.reflector.gap_in_mm) * cos(side_angle)
            cz = (lg_z / 2 + self.reflector_thickness_in_mm / 2 + self.reflector.gap_in_mm) * sin(side_angle)

            current_reflector_s = self.reflector_short_s if is_vertical else self.reflector_long_s

            if not place_sipm:
                current_reflector_l = self.reflector_short_l if is_vertical else self.reflector_long_l
                pg4.geant4.PhysicalVolume(rotation, [cx, 0, cz], current_reflector_l, f"reflector_{side}", self.container_l, registry=self.registry)
                continue

            length = lg_z if is_vertical else lg_x
            distance_per_sipm = length / sipm_per_side
            
            for j in range(sipm_per_side):
                offset = (j - (sipm_per_side - 1) / 2) * distance_per_sipm
                current_reflector_s = pg4.geant4.solid.Subtraction(f"reflector_s_{side}_{j}", current_reflector_s, self.sipm_s, [[0, 0, 0], [offset, 0, 0]], registry=self.registry)

            current_reflector_l = pg4.geant4.LogicalVolume(current_reflector_s, self.registry.materialDict["PMMA"], f"subtr_reflector_{side}", registry=self.registry)
            current_reflector_l.pygeom_color_rgba = (0.92, 0.92, 0.92, 1)
            pg4.geant4.PhysicalVolume(rotation, [cx, 0, cz], current_reflector_l, f"subtr_reflector_{side}", self.container_l, registry=self.registry)
        
    def place_container_in_parent(self, parent_lv):
        lg_y = self.lg.dimensions_in_mm[1]
        panel_y = self.registry.solidDict["panel_s"].pY
        translation = [0, panel_y/2 + lg_y/2 + self.gap_from_panel_in_mm, 0]
        self.container_pv = pg4.geant4.PhysicalVolume([0, 0, 0], translation, self.container_l, "lightguide_container", parent_lv, registry=self.registry)
        

class PolygonalLightGuide(BaseLightGuide):
    """Specific implementation of a general n-sided polygonal light guide."""

    def __init__(self, config_path: str, registry: pg4.geant4.Registry):
        super().__init__(config_path, registry)
        lg_x = self.lg.dimensions_in_mm[0]
        self.apothem = lg_x / 2 / tan(pi / self.lg.n_sides)
        self.side_length = lg_x
    
    def construct_light_guide_container(self):
        lg_z = self.lg.dimensions_in_mm[2]
        d = self.sipm.dimensions_in_mm[2] * 2 + self.sipm.gap_in_mm
        if self.reflector.placement:
            d += self.reflector_thickness_in_mm * 2 + self.reflector.gap_in_mm
            
        r_ext = self.apothem + d
        z_ext = lg_z / 2 + self.wls.thickness_in_mm * 2 + self.wls.gap_in_mm if self.wls.material else lg_z / 2
        
        container_s = pg4.geant4.solid.Polyhedra("lightguide_container_s", 0, 2 * pi, self.lg.n_sides, 2, [-z_ext, z_ext], [0.0, 0.0], [r_ext, r_ext], registry=self.registry, lunit="mm")
        self.container_l = pg4.geant4.LogicalVolume(container_s, self.registry.materialDict["lAr"], "lightguide_container_l", registry=self.registry)
        self.container_l.pygeom_color_rgba = False
    
    def construct_light_guide_solid(self):
        lg_z = self.lg.dimensions_in_mm[2]
        return pg4.geant4.solid.Polyhedra("lightguide_s", 0, 2 * pi, self.lg.n_sides, 2, [-lg_z / 2, lg_z / 2], [0.0, 0.0], [self.apothem, self.apothem], registry=self.registry, lunit="mm")

    def construct_external_wls(self):
        lg_z = self.lg.dimensions_in_mm[2]
        wls_external_s = pg4.geant4.solid.Polyhedra("wls_external_s", 0, 2 * pi, self.lg.n_sides, 2, [-self.wls.thickness_in_mm / 2, self.wls.thickness_in_mm / 2], [0.0, 0.0], [self.apothem, self.apothem], registry=self.registry, lunit="mm")
        z = self.wls.gap_in_mm + self.wls.thickness_in_mm / 2 + lg_z / 2
        wls_external_l = pg4.geant4.LogicalVolume(wls_external_s, self.registry.materialDict[self.wls.material], "wls_external_l", registry=self.registry)
        wls_external_l.pygeom_color_rgba = (0.180, 0.600, 0.369, 1.0)
        pg4.geant4.PhysicalVolume([0, 0, 0], [0, 0, z], wls_external_l, "wls_external", self.container_l, registry=self.registry)

    def construct_reflector(self):
        lg_z = self.lg.dimensions_in_mm[2]
        self.reflector_s = pg4.geant4.solid.Box("reflector_s", self.side_length, lg_z, self.reflector_thickness_in_mm, lunit="mm", registry=self.registry)
        self.reflector_l = pg4.geant4.LogicalVolume(self.reflector_s, self.registry.materialDict["PMMA"], "reflector_l", registry=self.registry)
        self.reflector_l.pygeom_color_rgba = (0.92, 0.92, 0.92, 1)

    def place_detectors(self):
        sipm_per_side = (self.sipm.number * 2) // self.lg.n_sides if self.sipm.placement != "all" else self.sipm.number // self.lg.n_sides
        sipm_index = 0
        sipm_z = self.registry.solidDict["sipm_s"].pZ

        for side in range(self.lg.n_sides):
            if (self.sipm.placement == "left_right" and side % 2 != 0) or (self.sipm.placement == "top_bottom" and side % 2 == 0):
                continue

            side_angle = 2 * pi * side / self.lg.n_sides + pi / self.lg.n_sides
            cx = (self.apothem + sipm_z/2 + self.sipm.gap_in_mm) * cos(side_angle)
            cy = (self.apothem + sipm_z/2 + self.sipm.gap_in_mm) * sin(side_angle)
            
            tx, ty = cos(side_angle + pi/2), sin(side_angle + pi/2)
            rotation = [pi/2, side_angle + pi/2, 0]
                
            for j in range(sipm_per_side): 
                offset = (j - (sipm_per_side - 1)/2) * (self.side_length / sipm_per_side) if sipm_per_side > 1 else 0
                pg4.geant4.PhysicalVolume(rotation, [cx + offset * tx, cy + offset * ty, 0], self.sipm_l, f"sipm_{sipm_index:02d}", self.container_l, registry=self.registry)
                sipm_index += 1

    def place_reflector(self):
        self.construct_reflector()
        sipm_per_side = (self.sipm.number * 2) // self.lg.n_sides if self.sipm.placement != "all" else self.sipm.number // self.lg.n_sides

        for side in range(self.lg.n_sides):
            place_sipm = self.sipm.placement == "all" or (self.sipm.placement == "left_right" and side % 2 == 0) or (self.sipm.placement == "top_bottom" and side % 2 != 0)
            side_angle = 2 * pi * side / self.lg.n_sides + pi / self.lg.n_sides
            
            cx = (self.apothem + self.reflector_thickness_in_mm/2 + self.reflector.gap_in_mm) * cos(side_angle)
            cy = (self.apothem + self.reflector_thickness_in_mm/2 + self.reflector.gap_in_mm) * sin(side_angle)
            rotation = [pi/2, side_angle + pi/2, 0]

            if not place_sipm:
                pg4.geant4.PhysicalVolume(rotation, [cx, cy, 0], self.reflector_l, f"reflector_{side}", self.container_l, registry=self.registry)
                continue
                
            current_reflector_s = self.reflector_s
            for j in range(sipm_per_side): 
                offset = (j - (sipm_per_side - 1)/2) * (self.side_length / sipm_per_side) if sipm_per_side > 1 else 0
                current_reflector_s = pg4.geant4.solid.Subtraction(f"reflector_s_{side}_{j}", current_reflector_s, self.sipm_s, [[0, 0, 0], [offset, 0, 0]], registry=self.registry)                
            
            current_reflector_l = pg4.geant4.LogicalVolume(current_reflector_s, self.registry.materialDict["PMMA"], f"subtr_reflector_l_{side}_{j}", registry=self.registry)
            current_reflector_l.pygeom_color_rgba = (0.92, 0.92, 0.92, 1)
            pg4.geant4.PhysicalVolume(rotation, [cx, cy, 0], current_reflector_l, f"subtr_reflector_{side}", self.container_l, registry=self.registry)

    def place_container_in_parent(self, parent_lv):
        lg_z = self.lg.dimensions_in_mm[2]
        panel_y = self.registry.solidDict["panel_s"].pY
        rotation = [pi/2, 0, pi/self.lg.n_sides]
        translation = [0, panel_y/2 + lg_z/2 + self.gap_from_panel_in_mm, 0]
        self.container_pv = pg4.geant4.PhysicalVolume(rotation, translation, self.container_l, "lightguide_container", parent_lv, registry=self.registry)



def create_light_guide(config_path: str, registry: pg4.geant4.Registry) -> BaseLightGuide:
    """Factory function that returns the right LightGuide object depending on the configuration geometry."""
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    
    geometry = data.get("light_guide", {}).get("geometry", "rectangle")
    
    if geometry == "polygon":
        return PolygonalLightGuide(config_path, registry)
    elif geometry == "rectangle":
        return RectangularLightGuide(config_path, registry)
    else:
        raise ValueError(f"Unknown geometry: {geometry}")