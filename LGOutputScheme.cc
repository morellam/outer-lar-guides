#include "LGOutputScheme.hh"

#include "G4AnalysisManager.hh"
#include "G4Event.hh"
#include "G4Step.hh"
#include "G4Track.hh"
#include "G4OpticalPhoton.hh"
#include "G4OpBoundaryProcess.hh"
#include "G4ProcessManager.hh"

#include "RMGOutputManager.hh"

using namespace CLHEP;

namespace {
  inline double fromEvToNm(double energy_eV) {
    return 1239.84187 / energy_eV;
  }
}

void LGOutputScheme::ClearBeforeEvent() {
  trackID_hit_wls_external.clear();
  trackID_hit_lightguide.clear();

  n_phot_det = 0;
  n_phot_produced_scint = 0;
  n_phot_produced_wls_guide = 0;
  n_phot_produced_wls_external = 0;

  lambda_phot_det.clear();
  time_phot_det.clear();
  trackID_phot_det.clear();
  trackLength_phot_det.clear();
  prodPosition_phot.clear();
}

void LGOutputScheme::AssignOutputNames(G4AnalysisManager* ana) {
  auto rmg = RMGOutputManager::Instance();

  // 1. NTuple of detected photons
  auto id_phot = rmg->RegisterNtuple(OutputRegisterID_photons,ana->CreateNtuple("LGOutput", "Detected photons"),"LGOutput");
  ana->CreateNtupleIColumn(id_phot, "evtID");
  ana->CreateNtupleDColumn(id_phot, "lambda_nm");
  ana->CreateNtupleDColumn(id_phot, "time_ns");
  ana->CreateNtupleIColumn(id_phot, "trackID");
  ana->CreateNtupleDColumn(id_phot, "track_vertex_x_mm");
  ana->CreateNtupleDColumn(id_phot, "track_vertex_y_mm");
  ana->CreateNtupleDColumn(id_phot, "track_vertex_z_mm");
  ana->CreateNtupleDColumn(id_phot, "track_length_mm");
  ana->FinishNtuple(id_phot);

  // 2. NTuple with event statistics
  auto id_stats = rmg->RegisterNtuple(OutputRegisterID_stats,ana->CreateNtuple("LGEventStats", "Per-event photon counts"),"LGEventStats");
  ana->CreateNtupleIColumn(id_stats, "evtID");
  ana->CreateNtupleIColumn(id_stats, "n_phot_produced_scint");
  // ana->CreateNtupleIColumn(id_stats, "n_phot_produced_wls_guide");
  // ana->CreateNtupleIColumn(id_stats, "n_phot_produced_wls_external");
  ana->CreateNtupleIColumn(id_stats, "n_phot_hit_wls_external");  
  ana->CreateNtupleIColumn(id_stats, "n_phot_hit_lightguide");  
  ana->CreateNtupleIColumn(id_stats, "n_phot_det");
  ana->FinishNtuple(id_stats);
}

void LGOutputScheme::SteppingAction(const G4Step* step) {

  auto track = step->GetTrack();
  if (track->GetDefinition() != G4OpticalPhoton::OpticalPhotonDefinition())
    return;

  int trackID = track->GetTrackID();

  G4String vertexLVName = track->GetLogicalVolumeAtVertex()->GetName();
  G4String vertexMat    = track->GetLogicalVolumeAtVertex()->GetMaterial()->GetName();
  G4String creatorProcName = track->GetCreatorProcess()->GetProcessName();

  bool bornInsideDetector = (vertexLVName == "lightguide_l") || (vertexLVName == "wls_external_l");

  if (track->GetCurrentStepNumber() == 1) {
    if (creatorProcName == "Scintillation" && vertexMat == "lAr"){
      n_phot_produced_scint += 1;
    } 
    // You should check if the parent photon was produced outside
    // If produced inside the LG/external WLS do not count
    else if (creatorProcName == "RMGOpWLS"){
      if (vertexLVName == "lightguide_l") n_phot_produced_wls_guide += 1;
      else if (vertexLVName == "wls_external_l") n_phot_produced_wls_external += 1;
    } 
  }

  // Computing number of photons hitting the external surface, 
  // Either of the Light Guide or of the external WLS
  auto prePoint = step->GetPreStepPoint();
  auto postPoint = step->GetPostStepPoint();

  if (!bornInsideDetector && postPoint->GetStepStatus() == fGeomBoundary) {
    if (prePoint->GetPhysicalVolume() && postPoint->GetPhysicalVolume()){
      G4String preName = prePoint->GetPhysicalVolume()->GetName();
      G4String postName = postPoint->GetPhysicalVolume()->GetName();

      if (vertexMat == "lAr"){
        if (preName != "lightguide" && postName == "lightguide"){
          auto it = std::find(trackID_hit_lightguide.begin(), trackID_hit_lightguide.end(), trackID);
          if (it == trackID_hit_lightguide.end()) {
            trackID_hit_lightguide.push_back(trackID);
          }
        }
        else if (preName != "wls_external" && postName == "wls_external"){
          auto it = std::find(trackID_hit_wls_external.begin(), trackID_hit_wls_external.end(), trackID);
          if (it == trackID_hit_wls_external.end()) {
            trackID_hit_wls_external.push_back(trackID);
          }
        }
      }
    }
  }

  // Check if photons are detected and write to disk
  G4OpBoundaryProcessStatus status = Undefined;
  static G4ThreadLocal G4OpBoundaryProcess* opProc = nullptr;

  if (!opProc) {
    auto pm = track->GetDefinition()->GetProcessManager();
    auto pv = pm->GetPostStepProcessVector(typeDoIt);
    for (size_t i = 0; i < pv->entries(); ++i) {
      opProc = dynamic_cast<G4OpBoundaryProcess*>((*pv)[i]);
      if (opProc) break;
    }
  }

  if (opProc)
    status = opProc->GetStatus();

  if (status == Detection && vertexLVName == "lightguide_l") {
    lambda_phot_det.push_back(fromEvToNm(track->GetTotalEnergy() / eV));
    time_phot_det.push_back(step->GetPreStepPoint()->GetGlobalTime() / nanosecond);
    trackID_phot_det.push_back(trackID);
    trackLength_phot_det.push_back(track->GetTrackLength() / mm);
    prodPosition_phot.push_back(track->GetVertexPosition());
  }
}

void LGOutputScheme::StoreEvent(const G4Event* event) {

  auto rmg = RMGOutputManager::Instance();
  if (!rmg->IsPersistencyEnabled()) return;

  auto ana = G4AnalysisManager::Instance();
  int eventID = event->GetEventID();

  auto ntid_stats = rmg->GetNtupleID(OutputRegisterID_stats);
  int col_stats = 0;
  ana->FillNtupleIColumn(ntid_stats, col_stats++, eventID);
  ana->FillNtupleIColumn(ntid_stats, col_stats++, n_phot_produced_scint);
  // ana->FillNtupleIColumn(ntid_stats, col_stats++, n_phot_produced_wls_guide);
  // ana->FillNtupleIColumn(ntid_stats, col_stats++, n_phot_produced_wls_external);
  ana->FillNtupleIColumn(ntid_stats, col_stats++, (G4int)trackID_hit_wls_external.size());
  ana->FillNtupleIColumn(ntid_stats, col_stats++, (G4int)trackID_hit_lightguide.size());
  ana->FillNtupleIColumn(ntid_stats, col_stats++, (G4int)trackID_phot_det.size());
  ana->AddNtupleRow(ntid_stats);

  auto ntid_phot = rmg->GetNtupleID(OutputRegisterID_photons);
  for (size_t i = 0; i < lambda_phot_det.size(); ++i) {
    int col = 0;
    ana->FillNtupleIColumn(ntid_phot, col++, eventID);
    ana->FillNtupleDColumn(ntid_phot, col++, lambda_phot_det[i]);
    ana->FillNtupleDColumn(ntid_phot, col++, time_phot_det[i]);
    ana->FillNtupleIColumn(ntid_phot, col++, trackID_phot_det[i]);
    ana->FillNtupleDColumn(ntid_phot, col++, prodPosition_phot[i].x());
    ana->FillNtupleDColumn(ntid_phot, col++, prodPosition_phot[i].y());
    ana->FillNtupleDColumn(ntid_phot, col++, prodPosition_phot[i].z());
    ana->FillNtupleDColumn(ntid_phot, col++, trackLength_phot_det[i]);
    ana->AddNtupleRow(ntid_phot);
  }
} 