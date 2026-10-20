# Gate audio consumers on a real default output, not just a running PipeWire process.

{ pkgs }:

pkgs.writeShellApplication {
  name = "wait-for-audio-output";
  runtimeInputs = [ pkgs.pipewire ];
  text = ''
    exec ${pkgs.python3}/bin/python3 ${./audio-ready.py}
  '';
}
