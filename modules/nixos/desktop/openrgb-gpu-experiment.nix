# Isolated exact-ID MSI GPU build, experimentally validated on the configured card.
{ pkgs }:

pkgs.openrgb.overrideAttrs (old: {
  pname = "openrgb-exact-gpu-validation";
  postPatch = old.postPatch + ''
    printf '%s\n' 'REGISTER_I2C_PCI_DETECTOR("MSI RTX 2070 Gaming exact-ID validation", DetectMSIGPUControllers, NVIDIA_VEN, NVIDIA_RTX2070_OC_DEV, MSI_SUB_VEN, MSI_RTX2070_GAMING_SUB_DEV, 0x68);' >> Controllers/MSIGPUController/MSIGPUController/MSIGPUControllerDetect.cpp
    # This standalone experiment does not need 1,900 unrelated device drivers.
    # Remove sources only inside the disposable Nix build sandbox.
    # The GUI has a link-time dependency on Nanoleaf's pairing helpers even
    # when unused. Keep those helpers, but omit their discovery registration.
    find Controllers -mindepth 1 -maxdepth 1 -type d ! -name MSIGPUController ! -name NanoleafController -exec rm -rf {} +
    rm -rf Controllers/MSIGPUController/MSIGPUv2Controller
    rm -f Controllers/NanoleafController/*Detect.cpp
  '';
})
