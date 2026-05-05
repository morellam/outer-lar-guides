#include "RMGHardware.hh"
#include "RMGLog.hh"
#include "RMGManager.hh"

#include "LGOutputScheme.hh"

int main(int argc, char** argv) {

    RMGManager manager("light-guide", argc, argv);
    manager.GetDetectorConstruction()->IncludeGDMLFile("geom.gdml");
    // manager.SetNumberOfThreads(1);

    auto user_init = manager.GetUserInit();
    user_init->AddOptionalOutputScheme<LGOutputScheme>("LGOutputScheme");

    //  Need at least 1 active detector, otherwise persistency not enabled (even if manually setting it)
    // manager.GetDetectorConstruction()->RegisterDetector(kOptical, "sipm_00", 0);

    std::string macro = argc > 1 ? argv[1] : "";
    if (!macro.empty()) manager.IncludeMacroFile(macro);

    manager.Initialize();
    manager.Run();

    return 0;
}