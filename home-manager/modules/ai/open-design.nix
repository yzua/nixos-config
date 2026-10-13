# Install the local OpenDesign workspace without managing credentials or agent skills.
{ openDesignPackage, ... }:
{
  home.packages = [ openDesignPackage ];

  xdg.desktopEntries.open-design = {
    name = "OpenDesign";
    comment = "Local AI design workspace";
    exec = "${openDesignPackage}/bin/open-design";
    # Keep the foreground daemon visible and easy to stop with Ctrl+C.
    terminal = true;
    categories = [
      "Graphics"
      "Development"
    ];
  };
}
