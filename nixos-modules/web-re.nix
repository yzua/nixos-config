# Web reverse engineering and security assessment tools.
# Static analysis of JS, dynamic API discovery, vulnerability scanning, CVE detection.

{
  pkgs,
  lib,
  config,
  ...
}:

{
  options.mySystem.webRe = {
    enable = lib.mkEnableOption "web reverse engineering and security tools";
  };

  config = lib.mkIf config.mySystem.webRe.enable {
    environment.systemPackages = with pkgs; [
      # === Vulnerability scanning ===
      nuclei # Fast vuln scanner with community CVE templates (ProjectDiscovery)
      nikto # Web server vulnerability scanner
      sqlmap # SQL injection detection and exploitation
      subfinder # Passive subdomain discovery
      amass # In-depth DNS enumeration and network mapping

      # === Web reconnaissance ===
      httpx # Fast HTTP prober (live hosts, titles, tech stack, TLS)
      katana # Web crawler/spider with JS parsing and endpoint extraction
      hakrawler # Fast passive/active endpoint crawler
      gau # Fetch known URLs from AlienVault, Wayback, Common Crawl, and URLScan
      waybackurls # Fetch historical URLs from the Wayback Machine
      ffuf # Fast web fuzzer (directories, vhosts, parameters)
      arjun # HTTP parameter discovery
      whatweb # Website technology fingerprinter

      # === Web app testing ===
      dalfox # XSS scanner with WAF bypass payloads
      zap # OWASP ZAP web proxy and vulnerability scanner

      # === OOB interaction and callback ===
      interactsh # OOB interaction server for blind vuln detection (ProjectDiscovery)

      # === TLS and crypto analysis ===
      testssl # TLS cipher and protocol testing against web servers

      # === Directory and endpoint fuzzing ===
      kiterunner # API route/content discovery with contextual wordlists
      gobuster # Directory/file/DNS/VHost brute-forcing tool
      feroxbuster # Recursive content discovery with heuristic filter

      # === Injection testing ===
      commix # Automated command injection detection and exploitation
      jaeles # Automated web application testing/signature scanner

      # === Port scanning ===
      rustscan # Fast port scanner (nmap wrapper for rapid discovery)

      # === Crypto / cert analysis ===
      # openssl — already in home-manager/packages/networking.nix
    ];

    environment.sessionVariables = {
      # nuclei templates directory (default location after first `nuclei -update-templates`)
      NUCLEI_TEMPLATES_PATH = "$HOME/.local/share/nuclei-templates";
    };

    # TPROXY kernel modules for mitmproxy transparent proxy mode
    boot.kernelModules = [
      "xt_TPROXY"
      "nf_tproxy_ipv4"
      "nf_tproxy_ipv6"
      "nf_conntrack"
    ];
  };
}
