# Userspace security hardening: AppArmor, sudo audit, /proc hidepid, coredump suppression.

_:

{
  # graphene-hardened removed — crashes glycin/bwrap image loaders (Loupe, Nautilus
  # thumbnails) because the allocator is preloaded system-wide via ld-nix.so.preload
  # and glycin-image-rs sandbox children die with coredump signals.
  # Revisit if glycin upstream adds hardened-malloc compatibility.

  security = {
    apparmor.enable = true;
    protectKernelImage = true;
    lockKernelModules = true; # Prevent loading kernel modules after boot (reduces attack surface)

    sudo = {
      enable = true;
      wheelNeedsPassword = true;
      execWheelOnly = true;
      extraConfig = ''
        # SECURITY: Log all sudo commands for audit trail
        Defaults use_pty
        Defaults log_input
        Defaults log_output
        Defaults logfile="/var/log/sudo.log"
      '';
    };

    # Audit disabled — AppArmor + auditd kernel interaction causes
    # audit_log_subj_ctx errors spamming dmesg/journal on kernel 6.x.
    # Re-enabling breaks the graphical session. Track upstream bug.
    auditd.enable = false;
    audit.enable = false;
  };

  systemd.coredump.enable = false;
}
