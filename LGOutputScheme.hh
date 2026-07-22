#ifndef _LG_OUTPUT_SCHEME_HH_
#define _LG_OUTPUT_SCHEME_HH_

#include "RMGVOutputScheme.hh"

#include <vector>
#include <map>

class G4Step;
class G4Event;

class LGOutputScheme : public RMGVOutputScheme {

public:
  LGOutputScheme() = default;

  void ClearBeforeEvent() override;
  void AssignOutputNames(G4AnalysisManager*) override;
  void StoreEvent(const G4Event*) override;

  void SteppingAction(const G4Step*) override;

private:

  G4int OutputRegisterID_stats = 3001;
  G4int OutputRegisterID_photons = 3002;
  G4int n_phot_det;
  G4int n_phot_produced_scint;
  G4int n_phot_produced_wls_guide;
  G4int n_phot_produced_wls_external;

  std::vector<G4int>      trackID_hit_wls_external;
  std::vector<G4int>      trackID_hit_lightguide;
  std::vector<G4double>   lambda_phot_det;
  std::vector<G4double>   time_phot_det;
  std::vector<G4int>      trackID_phot_det;
  std::vector<G4double>   trackLength_phot_det;
  std::vector<G4ThreeVector>  prodPosition_phot;
};

#endif
