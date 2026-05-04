# Privacy and security tools for anonymous browsing and network analysis.
# NOTE: i2pd managed by services.i2pd

{
  constants,
  pkgs,
  pkgsStable,
  ...
}:

let
  eglWrap = import ../_helpers/_egl-wrap.nix { inherit pkgs constants; };
  inherit (eglWrap) wrapWithMesaEgl;
in
{
  home.packages =
    (with pkgsStable; [
      # Network anonymity (i2pd managed by services.i2pd)
      tribler

      # Privacy browsers — wrapped to force Mesa EGL (see wrapWithMesaEgl above)
      (wrapWithMesaEgl "mullvad-browser" mullvad-browser)
      (wrapWithMesaEgl "tor-browser" tor-browser)

      # Secure Boot preparation (sbctl installed system-wide by nixos-modules/secure-boot.nix)
      tpm2-tools

      # Security tools
      metadata-cleaner
      socat # Network relay
      srm # Secure file removal
      veracrypt # Disk encryption
    ])
    ++ (with pkgs; [
      # Supply-chain and vulnerability scanning
      gitleaks # Pre-commit/pre-push secret scanning
      grype # Vulnerability scanner for SBOMs, containers, and filesystems
      osv-scanner # OSV-backed dependency vulnerability scanner
      syft # Generate SBOMs from source trees, containers, and filesystems
      trivy # Vulnerability, misconfiguration, and secret scanning
      vulnix # Nix closure CVE checker
    ]);
}
