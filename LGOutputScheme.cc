#include "LGOutputScheme.hh"

#include "G4AnalysisManager.hh"
#include "G4Event.hh"
#include "G4Step.hh"
#include "G4Track.hh"
#include "G4Box.hh"
#include "G4Polyhedra.hh"
#include "G4LogicalVolume.hh"
#include "G4Material.hh"
#include "G4VPhysicalVolume.hh"
#include "G4PhysicalVolumeStore.hh"
#include "G4NavigationHistory.hh"
#include "G4OpticalPhoton.hh"
#include "G4ProcessManager.hh"

#include "RMGLog.hh"
#include "RMGOutputManager.hh"

#include <algorithm>
#include <cmath>
#include <map>
#include <numeric>
#include <regex>

using namespace CLHEP;

namespace {
  inline double fromEvToNm(double energy_eV) {
    return 1239.84187 / energy_eV;
  }

  // "OpWLS" is wrapped by remage into "RMGOpWLS" when /RMG/Processes/OpticalPhysicsMaxOneWLSPhoton is true
  // ("OpWLS2" is the second WLS process of Geant4, for materials with WLSABSLENGTH2/WLSCOMPONENT2)
  inline bool isWLSProcess(const G4String& name) {
    return name == "RMGOpWLS" || name == "OpWLS" || name == "RMGOpWLS2" || name == "OpWLS2";
  }

  inline bool isReflection(G4OpBoundaryProcessStatus status) {
    switch (status) {
      case FresnelReflection:
      case TotalInternalReflection:
      case LambertianReflection:
      case LobeReflection:
      case SpikeReflection:
      case BackScattering:
      case CoatedDielectricReflection:
        return true;
      default:
        // reflections of the LUT models
        return status >= PolishedLumirrorAirReflection && status <= GroundVM2000GlueReflection;
    }
  }
}

LGOutputScheme::LGOutputScheme() { DefineCommands(); }

void LGOutputScheme::DefineCommands() {
  fMessenger = std::make_unique<G4GenericMessenger>(this, "/RMG/Output/LGOutputScheme/", "Commands for controlling the light guide output.");

  fMessenger->DeclareProperty("StoreAllGuidePhotons", fStoreAllGuidePhotons)
      .SetGuidance("Store in LGOutput all the photons emitted by WLS in the light guide, not only the detected ones (fate = 0).")
      .SetParameterName("flag", true)
      .SetDefaultValue("true")
      .SetStates(G4State_PreInit, G4State_Idle);
}

void LGOutputScheme::InitGeometry() {
  if (fGeometryInitialized) return;
  fGeometryInitialized = true;

  auto store = G4PhysicalVolumeStore::GetInstance();

  fLightGuidePV = store->GetVolume("lightguide", false);
  fWLSExternalPV = store->GetVolume("wls_external", false);
  fSubstratePV = store->GetVolume("wls_substrate", false);

  if (fLightGuidePV) {
    fLightGuideLV = fLightGuidePV->GetLogicalVolume();

    // the liquid around the light guide (e.g. LAr, or Xe-doped LAr), whatever the name of its material
    if (auto mother = fLightGuidePV->GetMotherLogical()) fMediumMaterial = mother->GetMaterial();
    auto solid = fLightGuideLV->GetSolid();

    // broad faces are the ones normal to the shortest dimension of the light guide
    G4ThreeVector pmin, pmax;
    solid->BoundingLimits(pmin, pmax);
    const auto size = pmax - pmin;
    fThicknessAxis = 0;
    for (G4int i = 1; i < 3; ++i) {
      if (size[i] < size[fThicknessAxis]) fThicknessAxis = i;
    }

    // lateral faces, numbered as the sides in light_guide.py
    if (auto polyhedra = dynamic_cast<const G4Polyhedra*>(solid)) {
      fNumSides = polyhedra->GetNumSide();
      fSideOffset = polyhedra->GetStartPhi() + pi / fNumSides;
    } else if (dynamic_cast<const G4Box*>(solid)) {
      fNumSides = 4;
      fSideOffset = 0.;
    } else {
      RMGLog::Out(RMGLog::warning, "LGOutputScheme: unknown light guide solid, all lateral faces counted as side 0");
      fNumSides = 1;
      fSideOffset = 0.;
    }
  } else {
    RMGLog::Out(RMGLog::warning, "LGOutputScheme: physical volume 'lightguide' not found");
  }
  if (fWLSExternalPV) fWLSExternalLV = fWLSExternalPV->GetLogicalVolume();
  if (!fMediumMaterial) fMediumMaterial = G4Material::GetMaterial("lAr", false);
  if (!fMediumMaterial) RMGLog::Out(RMGLog::warning, "LGOutputScheme: material of the liquid around the light guide not found");

  const std::regex re_reflector("^(subtr_)?reflector_(\\d+)$");
  const std::regex re_sipm("^sipm_(\\d+)$");
  const std::regex re_window("^window_(\\d+)$");
  const std::regex re_cover("^sipm_cover_.+$");

  std::map<G4int, const G4VPhysicalVolume*> reflectors;  // side -> PV, sorted by side
  for (const auto pv : *store) {
    const std::string name = pv->GetName();
    std::smatch match;
    if (std::regex_match(name, match, re_reflector)) {
      reflectors[std::stoi(match[2])] = pv;
    } else if (std::regex_match(name, match, re_sipm)) {
      fSiPMIndex[pv] = std::stoi(match[1]);
      fReadoutPVs.insert(pv);
    } else if (std::regex_match(name, re_window)) {
      fReadoutPVs.insert(pv);
    } else if (std::regex_match(name, re_cover)) {
      fCoverPVs.insert(pv);
    }
  }

  for (const auto& [side, pv] : reflectors) {
    fReflectorColumn[pv] = fReflectorSides.size();
    fReflectorSides.push_back(side);
  }
  fCurBounceReflector.assign(fReflectorSides.size(), 0);

  n_phot_escaped_guide.assign(fNumSides + 2, 0);
  fCurEscapedFace.assign(fNumSides + 2, false);

  fStatsColumns = {
    {"n_phot_produced_scint", &n_phot_produced_scint},
    {"n_phot_bulkabs_lar", &n_phot_bulkabs_lar},
    {"n_phot_hit_wls_external", &n_phot_hit_wls_external},
    {"n_phot_refl_wls_external", &n_phot_refl_wls_external},
    {"n_phot_hit_lightguide", &n_phot_hit_lightguide},
    {"n_phot_refl_lightguide", &n_phot_refl_lightguide},
    {"n_phot_hit_outer", &n_phot_hit_outer},
    {"n_phot_det", &n_phot_det},
    {"n_phot_det_all", &n_phot_det_all},
    {"n_phot_produced_wls_external", &n_phot_produced_wls_external},
    {"n_phot_produced_wls_external_reemitted", &n_phot_produced_wls_external_reemitted},
    {"n_phot_wlsabs_wls_external", &n_phot_wlsabs_wls_external},
    {"n_phot_bulkabs_wls_external", &n_phot_bulkabs_wls_external},
    {"n_phot_wls_external_hit_lightguide", &n_phot_wls_external_hit_lightguide},
    {"n_phot_wls_external_refl_lightguide", &n_phot_wls_external_refl_lightguide},
    {"n_phot_wlsabs_substrate", &n_phot_wlsabs_substrate},
    {"n_phot_bulkabs_substrate", &n_phot_bulkabs_substrate},
    {"n_phot_produced_wls_guide", &n_phot_produced_wls_guide},
    {"n_phot_produced_wls_guide_reemitted", &n_phot_produced_wls_guide_reemitted},
    {"n_phot_wlsabs_guide", &n_phot_wlsabs_guide},
    {"n_phot_bulkabs_guide", &n_phot_bulkabs_guide},
    {"n_phot_bulkabs_lar_wls", &n_phot_bulkabs_lar_wls},
  };
  for (G4int side = 0; side < fNumSides; ++side) {
    fStatsColumns.emplace_back("n_phot_escaped_guide_side_" + std::to_string(side), &n_phot_escaped_guide[side]);
  }
  fStatsColumns.emplace_back("n_phot_escaped_guide_front", &n_phot_escaped_guide[FaceFront()]);
  fStatsColumns.emplace_back("n_phot_escaped_guide_back", &n_phot_escaped_guide[FaceBack()]);
  fStatsColumns.emplace_back("n_phot_absorbed_reflector", &n_phot_absorbed_reflector);
  fStatsColumns.emplace_back("n_phot_absorbed_sipm_cover", &n_phot_absorbed_sipm_cover);
}

void LGOutputScheme::ClearBeforeEvent() {
  InitGeometry();
  for (auto& [name, counter] : fStatsColumns) *counter = 0;

  trackID_wls_external.clear();
  trackID_wls_guide.clear();

  fGuidePhotons.clear();
}

void LGOutputScheme::AssignOutputNames(G4AnalysisManager* ana) {
  auto rmg = RMGOutputManager::Instance();

  // the number of reflector and face columns depends on the geometry
  InitGeometry();

  // 1. NTuple of the photons emitted by WLS in the light guide (by default only the detected ones)
  auto id_phot = rmg->RegisterNtuple(OutputRegisterID_photons,ana->CreateNtuple("LGOutput", "Photons emitted in the light guide"),"LGOutput");
  ana->CreateNtupleIColumn(id_phot, "evtID");
  ana->CreateNtupleDColumn(id_phot, "lambda_nm");
  ana->CreateNtupleDColumn(id_phot, "time_ns");
  ana->CreateNtupleIColumn(id_phot, "trackID");
  ana->CreateNtupleDColumn(id_phot, "track_vertex_x_mm");
  ana->CreateNtupleDColumn(id_phot, "track_vertex_y_mm");
  ana->CreateNtupleDColumn(id_phot, "track_vertex_z_mm");
  ana->CreateNtupleDColumn(id_phot, "track_length_mm");
  ana->CreateNtupleIColumn(id_phot, "sipm_id");
  ana->CreateNtupleIColumn(id_phot, "n_refl_guide");
  ana->CreateNtupleIColumn(id_phot, "n_refl_guide_tir");
  ana->CreateNtupleIColumn(id_phot, "n_refl_guide_fresnel");
  ana->CreateNtupleIColumn(id_phot, "n_bounce_reflector");
  for (auto side : fReflectorSides) {
    ana->CreateNtupleIColumn(id_phot, "n_bounce_reflector_" + std::to_string(side));
  }
  ana->CreateNtupleDColumn(id_phot, "guide_path_mm");
  ana->CreateNtupleIColumn(id_phot, "n_exit_guide");
  ana->CreateNtupleIColumn(id_phot, "exit_face");
  ana->CreateNtupleIColumn(id_phot, "reemitted");
  ana->CreateNtupleIColumn(id_phot, "fate");
  ana->FinishNtuple(id_phot);

  // 2. NTuple with event statistics
  auto id_stats = rmg->RegisterNtuple(OutputRegisterID_stats,ana->CreateNtuple("LGEventStats", "Per-event photon counts"),"LGEventStats");
  ana->CreateNtupleIColumn(id_stats, "evtID");
  for (auto& [name, counter] : fStatsColumns) ana->CreateNtupleIColumn(id_stats, name);
  ana->CreateNtupleDColumn(id_stats, "efficiency");
  ana->FinishNtuple(id_stats);
}

void LGOutputScheme::StartNewPhoton(const G4Track* track) {
  fCurReemitted = false;
  fCurFate = kFateOther;
  fCurSiPM = -1;
  fCurHitOuter = false;
  fCurHitWLSExternal = false;
  fCurHitLightGuide = false;
  fCurReflWLSExternal = false;
  fCurReflLightGuide = false;
  std::fill(fCurEscapedFace.begin(), fCurEscapedFace.end(), false);
  fCurLastExitFace = -1;
  fCurNumExitGuide = 0;
  fCurReflGuide = 0;
  fCurReflGuideTIR = 0;
  fCurReflGuideFresnel = 0;
  fCurPathInGuide = 0.;
  std::fill(fCurBounceReflector.begin(), fCurBounceReflector.end(), 0);

  auto vertexLV = track->GetLogicalVolumeAtVertex();
  auto creator = track->GetCreatorProcess();  // nullptr for primary photons
  const G4String creatorProcName = creator ? creator->GetProcessName() : G4String("primary");
  const bool fromWLS = isWLSProcess(creatorProcName);

  // a WLS photon is a re-emission if its parent was itself emitted by WLS in the same volume
  if (fromWLS && fWLSExternalLV && vertexLV == fWLSExternalLV) {
    fCurOrigin = kOriginWLSExternal;
    fCurReemitted = trackID_wls_external.count(track->GetParentID()) > 0;
    n_phot_produced_wls_external += 1;
    if (fCurReemitted) n_phot_produced_wls_external_reemitted += 1;
    trackID_wls_external.insert(track->GetTrackID());
  }
  else if (fromWLS && fLightGuideLV && vertexLV == fLightGuideLV) {
    fCurOrigin = kOriginWLSGuide;
    fCurReemitted = trackID_wls_guide.count(track->GetParentID()) > 0;
    n_phot_produced_wls_guide += 1;
    if (fCurReemitted) n_phot_produced_wls_guide_reemitted += 1;
    trackID_wls_guide.insert(track->GetTrackID());
  }
  else if (vertexLV && vertexLV->GetMaterial() == fMediumMaterial) {
    fCurOrigin = kOriginLAr;
    if (creatorProcName == "Scintillation") n_phot_produced_scint += 1;
  }
  else {
    fCurOrigin = kOriginOther;
  }
}

G4OpBoundaryProcessStatus LGOutputScheme::GetBoundaryStatus(const G4Track* track) {
  if (!fBoundaryProc) {
    auto pm = track->GetDefinition()->GetProcessManager();
    auto pv = pm->GetPostStepProcessVector(typeDoIt);
    for (size_t i = 0; i < pv->entries(); ++i) {
      fBoundaryProc = dynamic_cast<G4OpBoundaryProcess*>((*pv)[i]);
      if (fBoundaryProc) break;
    }
  }
  return fBoundaryProc ? fBoundaryProc->GetStatus() : Undefined;
}

G4int LGOutputScheme::GetGuideFace(const G4Step* step) const {
  // the pre-step point is inside the light guide: go to its local frame and take the normal there
  const auto& transform = step->GetPreStepPoint()->GetTouchableHandle()->GetHistory()->GetTopTransform();
  const auto localPos = transform.TransformPoint(step->GetPostStepPoint()->GetPosition());
  const auto normal = fLightGuideLV->GetSolid()->SurfaceNormal(localPos);

  // broad faces: the external WLS is placed on the positive side of the thickness axis
  const double n_thick = normal[fThicknessAxis];
  if (n_thick > 0.5) return FaceFront();
  if (n_thick < -0.5) return FaceBack();

  // lateral faces: side k has its normal at azimuth fSideOffset + k * 2pi/fNumSides in the plane
  // of the two other axes (x-z for the rectangle, x-y for the polygon, as in light_guide.py)
  const G4int a = fThicknessAxis == 0 ? 1 : 0;
  const G4int b = fThicknessAxis == 2 ? 1 : 2;
  const long side = std::lround((std::atan2(normal[b], normal[a]) - fSideOffset) / (twopi / fNumSides));
  return static_cast<G4int>(((side % fNumSides) + fNumSides) % fNumSides);
}

void LGOutputScheme::SteppingAction(const G4Step* step) {

  auto track = step->GetTrack();
  if (track->GetDefinition() != G4OpticalPhoton::OpticalPhotonDefinition())
    return;

  if (!fGeometryInitialized) InitGeometry();

  // optical photons are tracked one at a time: per-photon quantities are reset at the first step
  if (track->GetCurrentStepNumber() == 1) StartNewPhoton(track);

  auto prePoint = step->GetPreStepPoint();
  auto postPoint = step->GetPostStepPoint();
  auto prePV = prePoint->GetPhysicalVolume();
  auto postPV = postPoint->GetPhysicalVolume();

  // geometrical path inside the light guide, from the emission point (or the entrance)
  const bool inGuide = fLightGuidePV && prePV == fLightGuidePV;
  if (inGuide) fCurPathInGuide += step->GetStepLength();

  // Step limited by a volume process: count photons absorbed in the bulk (OpAbsorption)
  // or absorbed by the wavelength shifter (OpWLS, the re-emitted photon is a new track)
  if (postPoint->GetStepStatus() == fPostStepDoItProc) {
    auto proc = postPoint->GetProcessDefinedStep();
    if (!proc) return;
    const auto& procName = proc->GetProcessName();
    const bool wlsAbs = isWLSProcess(procName);
    const bool bulkAbs = procName == "OpAbsorption";

    if (fWLSExternalPV && prePV == fWLSExternalPV) {
      if (wlsAbs) n_phot_wlsabs_wls_external += 1;
      else if (bulkAbs) n_phot_bulkabs_wls_external += 1;
    }
    else if (inGuide) {
      if (wlsAbs) {
        n_phot_wlsabs_guide += 1;
        fCurFate = kFateWLSAbsGuide;
      }
      else if (bulkAbs) {
        n_phot_bulkabs_guide += 1;
        fCurFate = kFateBulkAbsGuide;
      }
    }
    else if (fSubstratePV && prePV == fSubstratePV) {
      if (wlsAbs) n_phot_wlsabs_substrate += 1;
      else if (bulkAbs) n_phot_bulkabs_substrate += 1;
    }
    // absorbed in the liquid: photons created there and WLS photons (from the external WLS or the guide)
    else if (bulkAbs && fMediumMaterial && prePoint->GetMaterial() == fMediumMaterial) {
      if (fCurOrigin == kOriginLAr) n_phot_bulkabs_lar += 1;
      else if (fCurOrigin == kOriginWLSExternal || fCurOrigin == kOriginWLSGuide) n_phot_bulkabs_lar_wls += 1;
    }
    return;
  }

  // Everything below happens at a geometrical boundary, where the boundary process is always
  // invoked: its status refers to this step (elsewhere it can be left over from a previous step)
  if (postPoint->GetStepStatus() != fGeomBoundary) return;

  const auto status = GetBoundaryStatus(track);
  // zero-length step that relocates the photon after a reflection, nothing physical happens
  if (status == StepTooSmall) return;

  // NB: at the boundary the post-step point is in the volume beyond the surface, also when the
  // photon gets reflected (it is the volume the photon has been reflected from)
  const bool toGuide = fLightGuidePV && postPV == fLightGuidePV;
  const bool toWLSExternal = fWLSExternalPV && postPV == fWLSExternalPV;
  const bool reflected = isReflection(status);

  // Scintillation photons reaching the external surface of the external WLS or of the light guide
  // (counted once per photon, whether they are then refracted or reflected), and those reflected
  // back by that surface (counted once per photon, at any of its arrivals)
  if (fCurOrigin == kOriginLAr) {
    if (toWLSExternal && prePV != fWLSExternalPV) {
      if (!fCurHitWLSExternal) {
        n_phot_hit_wls_external += 1;
        fCurHitWLSExternal = true;
      }
      if (reflected && !fCurReflWLSExternal) {
        n_phot_refl_wls_external += 1;
        fCurReflWLSExternal = true;
      }
    }
    else if (toGuide && !inGuide) {
      if (!fCurHitLightGuide) {
        n_phot_hit_lightguide += 1;
        fCurHitLightGuide = true;
      }
      if (reflected && !fCurReflLightGuide) {
        n_phot_refl_lightguide += 1;
        fCurReflLightGuide = true;
      }
    }
    // outermost surface: external WLS or light guide, whichever is reached first
    if ((fCurHitWLSExternal || fCurHitLightGuide) && !fCurHitOuter) {
      n_phot_hit_outer += 1;
      fCurHitOuter = true;
    }
  }
  else if (fCurOrigin == kOriginWLSExternal && toGuide && !inGuide) {
    if (!fCurHitLightGuide) {
      n_phot_wls_external_hit_lightguide += 1;
      fCurHitLightGuide = true;
    }
    if (reflected && !fCurReflLightGuide) {
      n_phot_wls_external_refl_lightguide += 1;
      fCurReflLightGuide = true;
    }
  }

  // Reflections inside the light guide (any surface: LAr, window, reflector)
  if (inGuide && reflected) {
    fCurReflGuide += 1;
    if (status == TotalInternalReflection) fCurReflGuideTIR += 1;
    else if (status == FresnelReflection) fCurReflGuideFresnel += 1;
  }

  // Bounces on the reflectors (from the light guide or from the LAr in the gap)
  auto itRefl = fReflectorColumn.find(postPV);
  if (itRefl != fReflectorColumn.end()) {
    if (reflected) fCurBounceReflector[itRefl->second] += 1;
    else if (status == Absorption) {
      n_phot_absorbed_reflector += 1;
      fCurFate = kFateAbsReflector;
    }
  }

  // Photons killed on a SiPM cover (no RINDEX: NoRINDEX; with an optical surface: Absorption)
  if (fCoverPVs.count(postPV) && (status == NoRINDEX || status == Absorption)) {
    n_phot_absorbed_sipm_cover += 1;
    fCurFate = kFateAbsSiPMCover;
  }

  // Photons leaving the light guide through one of its faces, except towards the SiPM
  // windows/SiPMs (counted once per photon and per face)
  const bool transmitted = status == FresnelRefraction || status == Transmission;
  if (inGuide && transmitted && !toGuide && !fReadoutPVs.count(postPV)) {
    const auto face = GetGuideFace(step);
    if (!fCurEscapedFace[face]) n_phot_escaped_guide[face] += 1;
    fCurEscapedFace[face] = true;
    fCurLastExitFace = face;
    fCurNumExitGuide += 1;
  }
  else if (toGuide && !inGuide && transmitted) {
    fCurLastExitFace = -1;  // back inside the guide
  }

  // Photons ending on a SiPM, detected or not
  if (status == Detection || status == Absorption) {
    auto itSiPM = fSiPMIndex.find(postPV);
    if (itSiPM != fSiPMIndex.end()) {
      fCurSiPM = itSiPM->second;
      if (status == Absorption) fCurFate = kFateNotDetectedSiPM;
    }
  }

  // Detected photons: all of them in n_phot_det_all, only those emitted in the guide in n_phot_det
  if (status == Detection) {
    fCurFate = kFateDetected;
    n_phot_det_all += 1;
    if (fCurOrigin == kOriginWLSGuide) n_phot_det += 1;
  }
}

void LGOutputScheme::TrackingActionPost(const G4Track* track) {
  if (fCurOrigin != kOriginWLSGuide) return;
  if (track->GetDefinition() != G4OpticalPhoton::OpticalPhotonDefinition()) return;
  if (!fStoreAllGuidePhotons && fCurFate != kFateDetected) return;

  // a photon that left the guide through one of its faces and never came back is lost outside,
  // unless it ended on a reflector or a SiPM
  G4int fate = fCurFate;
  if (fate == kFateOther && fCurLastExitFace >= 0) {
    if (fCurLastExitFace == FaceFront()) fate = kFateEscapedFront;
    else if (fCurLastExitFace == FaceBack()) fate = kFateEscapedBack;
    else fate = kFateEscapedLateral;
  }

  fGuidePhotons.push_back({
    track->GetTrackID(),
    fromEvToNm(track->GetTotalEnergy() / eV),
    track->GetGlobalTime() / nanosecond,
    track->GetVertexPosition() / mm,
    track->GetTrackLength() / mm,
    fCurSiPM,
    fCurReflGuide,
    fCurReflGuideTIR,
    fCurReflGuideFresnel,
    fCurBounceReflector,
    fCurPathInGuide / mm,
    fCurNumExitGuide,
    fCurLastExitFace,
    fCurReemitted,
    fate
  });
}

void LGOutputScheme::StoreEvent(const G4Event* event) {

  auto rmg = RMGOutputManager::Instance();
  if (!rmg->IsPersistencyEnabled()) return;

  auto ana = G4AnalysisManager::Instance();
  int eventID = event->GetEventID();

  // efficiency: detected photons emitted in the guide over scintillation photons reaching the
  // outermost surface (external WLS or light guide)
  const G4double efficiency = n_phot_hit_outer > 0 ? static_cast<G4double>(n_phot_det) / n_phot_hit_outer : 0.;

  auto ntid_stats = rmg->GetNtupleID(OutputRegisterID_stats);
  int col_stats = 0;
  ana->FillNtupleIColumn(ntid_stats, col_stats++, eventID);
  for (auto& [name, counter] : fStatsColumns) ana->FillNtupleIColumn(ntid_stats, col_stats++, *counter);
  ana->FillNtupleDColumn(ntid_stats, col_stats++, efficiency);
  ana->AddNtupleRow(ntid_stats);

  auto ntid_phot = rmg->GetNtupleID(OutputRegisterID_photons);
  for (const auto& phot : fGuidePhotons) {
    int col = 0;
    ana->FillNtupleIColumn(ntid_phot, col++, eventID);
    ana->FillNtupleDColumn(ntid_phot, col++, phot.lambda);
    ana->FillNtupleDColumn(ntid_phot, col++, phot.time);
    ana->FillNtupleIColumn(ntid_phot, col++, phot.trackID);
    ana->FillNtupleDColumn(ntid_phot, col++, phot.vertex.x());
    ana->FillNtupleDColumn(ntid_phot, col++, phot.vertex.y());
    ana->FillNtupleDColumn(ntid_phot, col++, phot.vertex.z());
    ana->FillNtupleDColumn(ntid_phot, col++, phot.trackLength);
    ana->FillNtupleIColumn(ntid_phot, col++, phot.sipm);
    ana->FillNtupleIColumn(ntid_phot, col++, phot.nRefl);
    ana->FillNtupleIColumn(ntid_phot, col++, phot.nReflTIR);
    ana->FillNtupleIColumn(ntid_phot, col++, phot.nReflFresnel);
    const auto& bounces = phot.nBounceReflector;
    ana->FillNtupleIColumn(ntid_phot, col++, std::accumulate(bounces.begin(), bounces.end(), 0));
    for (auto n : bounces) ana->FillNtupleIColumn(ntid_phot, col++, n);
    ana->FillNtupleDColumn(ntid_phot, col++, phot.guidePath);
    ana->FillNtupleIColumn(ntid_phot, col++, phot.nExitGuide);
    ana->FillNtupleIColumn(ntid_phot, col++, phot.exitFace);
    ana->FillNtupleIColumn(ntid_phot, col++, phot.reemitted);
    ana->FillNtupleIColumn(ntid_phot, col++, phot.fate);
    ana->AddNtupleRow(ntid_phot);
  }
}
