# Networking tools for analysis, monitoring, and security testing.
# NOTE: openssh managed by services.openssh, bandwhich by programs.bandwhich

{ pkgs, ... }:

{
  home.packages = with pkgs; [
    # Core networking (networkmanagerapplet managed by services.network-manager-applet)
    openssl
    openssl.dev

    # Diagnostics
    iperf3
    mtr
    trippy

    # DNS utilities
    dnsutils
    dog
    whois

    # HTTP clients
    curl
    wget

    # Network debugging
    netcat

    # Network monitoring (bandwhich managed by programs.bandwhich)
    iftop
    nethogs
    nload
    termshark # TUI Wireshark (pcap analysis in terminal)
    wireshark-cli # Wireshark CLI capture and analysis

    # Network scanning
    masscan
    nmap
    tcpdump
    zmap

    # Security testing
    thc-hydra
    mitmproxy # HTTP/HTTPS proxy for traffic analysis

    # Code coverage and binary hardening analysis
    gcovr # Code coverage report generator (gcov front-end)
    checksec # Binary security property checker (NX, PIE, RELRO, canaries, Fortify)

    # VPN tools
    openvpn
    proton-vpn-cli
    wireguard-tools
    wgnord
  ];
}
