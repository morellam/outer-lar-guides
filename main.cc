#include "RMGDefaultCli.hh"
#include "RMGManager.hh"
#include "LGOutputScheme.hh"

class MyCLI : public RMGDefaultCli {
public:
    void SetupRuntime(RMGManager& manager) override {
        RMGDefaultCli::SetupRuntime(manager);
        auto user_init = manager.GetUserInit();
        user_init->AddOptionalOutputScheme<LGOutputScheme>("LGOutputScheme");
    }

    void SetupGeometry(RMGManager& manager) override {
        RMGDefaultCli::SetupGeometry(manager);
    }
};

int main(int argc, char** argv) {
    MyCLI app;
    app.ParseCliArgs(argc, argv);
    app.SetupLoggingAndIpc();
    return app.RunSimulation(argc, argv);
}