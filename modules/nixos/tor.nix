# Local Tor SOCKS client and torsocks.

{
  services.tor = {
    enable = true;
    client.enable = true;
    torsocks.enable = true;
  };
}
