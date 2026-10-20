#ifndef _LG_OUTPUT_SCHEME_HH_
#define _LG_OUTPUT_SCHEME_HH_

#include "RMGVOutputScheme.hh"

#include "G4GenericMessenger.hh"
#include "G4OpBoundaryProcess.hh"
#include "G4ThreeVector.hh"

#include <memory>
#include <string>
#include <utility>
#include <vector>
#include <unordered_map>
#include <unordered_set>

class G4Step;
class G4Event;
class G4Track;
class G4LogicalVolume;
class G4VPhysicalVolume;
class G4Material;

class LGOutputScheme : public RMGVOutputScheme {

public:
  LGOutputScheme();

  void ClearBeforeEvent() override;
  void AssignOutputNames(G4AnalysisManager*) override;
  void StoreEvent(const G4Event*) override;

  void SteppingAction(const G4Step*) override;
  void TrackingActionPost(const G4Track*) override;

private:

  // Where an optical photon has been created
  enum PhotonOrigin : G4int {
    kOriginLAr = 0,         // created in the liquid around the light guide (scintillation or primary optical photon)
    kOriginWLSExternal = 1, // WLS emission in the external WLS
    kOriginWLSGuide = 2,    // WLS emission in the light guide
    kOriginOther = 3
  };

  // How a photon emitted in the light guide ends (stored in the "fate" column of LGOutput)
  enum PhotonFate : G4int {
    kFateDetected = 0,
    kFateBulkAbsGuide = 1,     // absorbed in the guide (ABSLENGTH)
    kFateWLSAbsGuide = 2,      // absorbed by the WLS of the guide (WLSABSLENGTH), may be re-emitted
    kFateAbsReflector = 3,     // absorbed on a reflector
    kFateNotDetectedSiPM = 4,  // reached a SiPM but not detected (efficiency)
    kFateEscapedLateral = 5,   // left the guide through a lateral face and lost outside
    kFateEscapedFront = 6,     // left the guide through the front face and lost outside
    kFateEscapedBack = 7,      // left the guide through the back face and lost outside
    kFateOther = 8,            // e.g. absorbed in a SiPM window
    kFateAbsSiPMCover = 9      // killed on the cover (package) of a SiPM
  };

  void DefineCommands();
  void InitGeometry();
  void StartNewPhoton(const G4Track*);
  G4OpBoundaryProcessStatus GetBoundaryStatus(const G4Track*);
  // face of the light guide crossed in this step: 0..fNumSides-1 lateral sides, then front, back
  G4int GetGuideFace(const G4Step*) const;
  G4int FaceFront() const { return fNumSides; }
  G4int FaceBack() const { return fNumSides + 1; }

  std::unique_ptr<G4GenericMessenger> fMessenger;
  bool fStoreAllGuidePhotons = false;  // false: only detected photons in LGOutput

  G4int OutputRegisterID_stats = 3001;
  G4int OutputRegisterID_photons = 3002;

  // Geometry cache (volumes are looked up by name once per thread)
  bool fGeometryInitialized = false;
  const G4VPhysicalVolume* fLightGuidePV = nullptr;
  const G4VPhysicalVolume* fWLSExternalPV = nullptr;
  const G4VPhysicalVolume* fSubstratePV = nullptr;
  const G4LogicalVolume* fLightGuideLV = nullptr;
  const G4LogicalVolume* fWLSExternalLV = nullptr;
  const G4Material* fMediumMaterial = nullptr;  // liquid around the light guide (material of its mother volume)
  G4int fThicknessAxis = 1;    // local axis of the light guide normal to the broad faces
  G4int fNumSides = 4;         // number of lateral faces
  G4double fSideOffset = 0.;   // azimuth of the normal of lateral side 0
  std::unordered_map<const G4VPhysicalVolume*, size_t> fReflectorColumn;  // reflector PV -> index in n_bounce_reflector_*
  std::vector<G4int> fReflectorSides;                                     // side number of each reflector column
  std::unordered_map<const G4VPhysicalVolume*, G4int> fSiPMIndex;          // sipm_NN -> NN
  std::unordered_set<const G4VPhysicalVolume*> fReadoutPVs;               // SiPM windows and SiPMs
  std::unordered_set<const G4VPhysicalVolume*> fCoverPVs;                 // SiPM covers (sipm_cover_*)

  G4OpBoundaryProcess* fBoundaryProc = nullptr;

  // State of the optical photon currently being tracked (reset at its first step)
  G4int fCurOrigin = kOriginOther;
  bool fCurReemitted = false;
  G4int fCurFate = kFateOther;
  G4int fCurSiPM = -1;
  bool fCurHitOuter = false;
  bool fCurHitWLSExternal = false;
  bool fCurHitLightGuide = false;
  bool fCurReflWLSExternal = false;
  bool fCurReflLightGuide = false;
  std::vector<char> fCurEscapedFace;
  G4int fCurLastExitFace = -1;  // face of the last exit from the guide, -1 if inside or never left
  G4int fCurNumExitGuide = 0;
  G4int fCurReflGuide = 0;
  G4int fCurReflGuideTIR = 0;
  G4int fCurReflGuideFresnel = 0;
  G4double fCurPathInGuide = 0.;
  std::vector<G4int> fCurBounceReflector;

  // Per-event counters, (name, counter) in the order they are written
  std::vector<std::pair<std::string, G4int*>> fStatsColumns;
  G4int n_phot_produced_scint = 0;
  G4int n_phot_bulkabs_lar = 0;
  G4int n_phot_hit_wls_external = 0;
  G4int n_phot_refl_wls_external = 0;
  G4int n_phot_hit_lightguide = 0;
  G4int n_phot_refl_lightguide = 0;
  G4int n_phot_hit_outer = 0;
  G4int n_phot_det = 0;
  G4int n_phot_det_all = 0;
  G4int n_phot_produced_wls_external = 0;
  G4int n_phot_produced_wls_external_reemitted = 0;
  G4int n_phot_wlsabs_wls_external = 0;
  G4int n_phot_bulkabs_wls_external = 0;
  G4int n_phot_wls_external_hit_lightguide = 0;
  G4int n_phot_wls_external_refl_lightguide = 0;
  G4int n_phot_wlsabs_substrate = 0;
  G4int n_phot_bulkabs_substrate = 0;
  G4int n_phot_produced_wls_guide = 0;
  G4int n_phot_produced_wls_guide_reemitted = 0;
  G4int n_phot_wlsabs_guide = 0;
  G4int n_phot_bulkabs_guide = 0;
  G4int n_phot_bulkabs_lar_wls = 0;
  std::vector<G4int> n_phot_escaped_guide;  // per face, same indexing as GetGuideFace()
  G4int n_phot_absorbed_reflector = 0;
  G4int n_phot_absorbed_sipm_cover = 0;

  // trackIDs of the WLS photons emitted in this event, needed to tag re-emissions
  std::unordered_set<G4int> trackID_wls_external;
  std::unordered_set<G4int> trackID_wls_guide;

  // One row of LGOutput: a photon emitted by WLS in the light guide
  struct GuidePhoton {
    G4int trackID;
    G4double lambda;       // nm
    G4double time;         // ns, at the end of the track (detection time for detected photons)
    G4ThreeVector vertex;  // mm
    G4double trackLength;  // mm
    G4int sipm;
    G4int nRefl;
    G4int nReflTIR;
    G4int nReflFresnel;
    std::vector<G4int> nBounceReflector;
    G4double guidePath;    // mm
    G4int nExitGuide;
    G4int exitFace;
    G4int reemitted;
    G4int fate;
  };
  std::vector<GuidePhoton> fGuidePhotons;
};

#endif
