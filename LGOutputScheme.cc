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

//--------------------------------------------------

void LGOutputScheme::ClearBeforeEvent() {
  n_phot_det = 0;
  lambda_phot_det.clear();
  time_phot_det.clear();
  angle_phot_det.clear();
  trackID_phot_det.clear();
  trackLengthMap_phot_det.clear();
  prodPositionMap_phot.clear();
}

//--------------------------------------------------

void LGOutputScheme::AssignOutputNames(G4AnalysisManager* ana) {

  auto rmg = RMGOutputManager::Instance();

  auto id = rmg->RegisterNtuple(
    OutputRegisterID,
    ana->CreateNtuple("LGOutput", "Detected photons"),
    "LGOutput"
  );

  ana->CreateNtupleIColumn(id, "evtID");
  ana->CreateNtupleDColumn(id, "lambda_nm");
  ana->CreateNtupleDColumn(id, "time_ps");
  ana->CreateNtupleDColumn(id, "angle");
  ana->CreateNtupleIColumn(id, "trackID");
  ana->CreateNtupleDColumn(id, "track_vertex_x_mm");
  ana->CreateNtupleDColumn(id, "track_vertex_y_mm");
  ana->CreateNtupleDColumn(id, "track_vertex_z_mm");
  ana->CreateNtupleDColumn(id, "track_length_mm");

  ana->FinishNtuple(id);
}

//--------------------------------------------------

void LGOutputScheme::SteppingAction(const G4Step* step) {

  auto track = step->GetTrack();
  if (track->GetDefinition() != G4OpticalPhoton::OpticalPhotonDefinition())
    return;

  // retrieve boundary status
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

  const auto& vertexDir = track->GetVertexMomentumDirection();
  const int trackID = track->GetTrackID();

  // track length + production position
  trackLengthMap_phot_det[trackID] += step->GetStepLength();
  prodPositionMap_phot[trackID] = track->GetVertexPosition();

  // detection
  if (status == Detection) {
    n_phot_det++;

    lambda_phot_det.push_back(
      fromEvToNm(track->GetTotalEnergy() / eV)
    );
    time_phot_det.push_back(
      step->GetPreStepPoint()->GetGlobalTime() / picosecond
    );
    angle_phot_det.push_back(
      cos(G4ThreeVector(1.,0.,0.).angle(vertexDir))
    );
    trackID_phot_det.push_back(trackID);
  }
}

//--------------------------------------------------

void LGOutputScheme::StoreEvent(const G4Event* event) {

  auto rmg = RMGOutputManager::Instance();
  if (!rmg->IsPersistencyEnabled()) return;

  auto ana = G4AnalysisManager::Instance();
  auto ntid = rmg->GetNtupleID(OutputRegisterID);

  for (size_t i = 0; i < lambda_phot_det.size(); ++i) {
    int col = 0;
    ana->FillNtupleIColumn(ntid, col++, event->GetEventID());
    ana->FillNtupleDColumn(ntid, col++, lambda_phot_det[i]);
    ana->FillNtupleDColumn(ntid, col++, time_phot_det[i]);
    ana->FillNtupleDColumn(ntid, col++, angle_phot_det[i]);
    ana->FillNtupleIColumn(ntid, col++, trackID_phot_det[i]);
    ana->FillNtupleDColumn(ntid, col++, prodPositionMap_phot[trackID_phot_det[i]].x());
    ana->FillNtupleDColumn(ntid, col++, prodPositionMap_phot[trackID_phot_det[i]].y());
    ana->FillNtupleDColumn(ntid, col++, prodPositionMap_phot[trackID_phot_det[i]].z());
    ana->FillNtupleDColumn(ntid, col++, trackLengthMap_phot_det[trackID_phot_det[i]]);
    ana->AddNtupleRow(ntid);
  }
}
