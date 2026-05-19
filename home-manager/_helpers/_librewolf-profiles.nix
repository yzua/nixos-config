# Single source of truth for LibreWolf profile definitions.
# Used by librewolf/default.nix (browser config) and desktop-entries.nix (launcher entries).

{ constants }:
let
  inherit (constants.proxies.librewolf)
    personal
    work
    banking
    shopping
    illegal
    ;
  inherit (constants.proxies) i2pd;
in
[
  {
    name = "personal";
    label = "Personal";
    comment = "LibreWolf with Sweden proxy";
    id = 0;
    isDefault = true;
    path = "personal.default";
    proxyHost = personal;
    homepage = "http://${constants.localhost}:${toString constants.ports.glance}/search";
  }
  {
    name = "work";
    label = "Work";
    comment = "LibreWolf with Germany proxy";
    id = 1;
    isDefault = false;
    path = "work.default";
    proxyHost = work;
    homepage = "about:blank";
  }
  {
    name = "banking";
    label = "Banking";
    comment = "LibreWolf with Netherlands proxy";
    id = 2;
    isDefault = false;
    path = "banking.default";
    proxyHost = banking;
    homepage = "about:blank";
  }
  {
    name = "shopping";
    label = "Shopping";
    comment = "LibreWolf with Romania proxy";
    id = 3;
    isDefault = false;
    path = "shopping.default";
    proxyHost = shopping;
    homepage = "about:blank";
  }
  {
    name = "illegal";
    label = "Illegal";
    comment = "LibreWolf with Switzerland proxy";
    id = 4;
    isDefault = false;
    path = "illegal.default";
    proxyHost = illegal;
    homepage = "about:blank";
  }
  {
    name = "i2pd";
    label = "I2P";
    comment = "LibreWolf with I2P proxy";
    id = 5;
    isDefault = false;
    path = "i2pd.default";
    proxyHost = i2pd;
    homepage = "about:blank";
    extraSettings = {
      "browser.newtabpage.enabled" = false;
      "network.proxy.socks_port" = constants.ports.i2pd-socks;
    };
  }
]
