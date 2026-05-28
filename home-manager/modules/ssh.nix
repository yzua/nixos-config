# SSH client hardening (algorithms, forwarding, host key verification).

_:

{
  programs.ssh = {
    enable = true;
    enableDefaultConfig = false;

    settings = {
      "*" = {
        # Prefer modern key exchange and ciphers
        KexAlgorithms = "sntrup761x25519-sha512@openssh.com,curve25519-sha256,curve25519-sha256@libssh.org";
        Ciphers = "chacha20-poly1305@openssh.com,aes256-gcm@openssh.com";
        MACs = "hmac-sha2-512-etm@openssh.com,hmac-sha2-256-etm@openssh.com";
        HostKeyAlgorithms = "ssh-ed25519-cert-v01@openssh.com,ssh-ed25519";

        # Security defaults
        ForwardAgent = "no";
        ForwardX11 = "no";
        AddKeysToAgent = "confirm";
        IdentitiesOnly = "yes";
        StrictHostKeyChecking = "ask";
        VerifyHostKeyDNS = "yes";
        UpdateHostKeys = "yes";
        HashKnownHosts = "yes";

        # Connection keepalive + auto-close idle sessions
        ServerAliveInterval = "60";
        ServerAliveCountMax = "3";

        # Timeout idle connections after 10 minutes (prevents stale session hijacking)
        ConnectionAttempts = "3";
        ConnectTimeout = "30";
      };

      "github.com" = {
        HostName = "github.com";
        User = "git";
        PreferredAuthentications = "publickey";
      };

      "codeberg.org" = {
        HostName = "codeberg.org";
        User = "git";
        IdentityFile = "~/.ssh/id_ed25519";
        AddressFamily = "inet";
        PreferredAuthentications = "publickey";
      };
    };
  };
}
