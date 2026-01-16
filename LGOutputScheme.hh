#ifndef _LG_OUTPUT_SCHEME_HH_
#define _LG_OUTPUT_SCHEME_HH_

#include "RMGVOutputScheme.hh"

#include <vector>
#include <map>

class G4Step;
class G4Event;
// class G4AnalysisManager;
// class G4ThreeVector;

class LGOutputScheme : public RMGVOutputScheme {

public:
  LGOutputScheme() = default;

  void ClearBeforeEvent() override;
  void AssignOutputNames(G4AnalysisManager*) override;
  void StoreEvent(const G4Event*) override;

  void SteppingAction(const G4Step*) override;

private:
  G4int OutputRegisterID = 3000;

  // ---- counters
  int n_phot_det = 0;

  // ---- per-photon data
  std::vector<double> lambda_phot_det;
  std::vector<double> time_phot_det;
  std::vector<double> angle_phot_det;
  std::vector<int>    trackID_phot_det;

  // ---- auxiliary maps
  std::map<int, double> trackLengthMap_phot_det;
  std::map<int, G4ThreeVector> prodPositionMap_phot;
};

#endif
