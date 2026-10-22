# Local Room Cam viewers and CPU person/hand data with pinned firmware and models.

{ pkgs }:

let
  python = pkgs.python3.withPackages (ps: [ ps.opencv4 ]);
  pin = "48b10fa505aeb51fbd127fc60a5c660040e823b7";
  raw = "https://raw.githubusercontent.com/opencv/opencv_zoo/${pin}/models";
  media = "https://media.githubusercontent.com/media/opencv/opencv_zoo/${pin}/models";
  firmware = pkgs.fetchurl {
    url = "https://raw.githubusercontent.com/zweiler2/PS5_Camera_Loader/6df56c6c2a0e6b5e4e782c56458e5f9d8525b837/resources/firmware_discord_and_gamma_fix.bin";
    hash = "sha256-Qs5fcDOhEVmIyto+u44KFD6LJBZh8gOhInU1TdK6C/Y=";
  };
  model = pkgs.fetchurl {
    url = "${media}/object_detection_yolox/object_detection_yolox_2022nov.onnx";
    hash = "sha256-xcLRPlmuiD5q87RdrqZK9IM6SVHJLRFuwnDZ3b6ZgGM=";
  };
  palmModel = pkgs.fetchurl {
    url = "${media}/palm_detection_mediapipe/palm_detection_mediapipe_2023feb.onnx";
    hash = "sha256-eP9Rw4SWt/yLjr22zIwauwL6bDhCfGhIJUzaulf8znw=";
  };
  handModel = pkgs.fetchurl {
    url = "${media}/handpose_estimation_mediapipe/handpose_estimation_mediapipe_2023feb.onnx";
    hash = "sha256-2wiYrnF7drB12b9WOvMVspVi4R+N9QJ6HvB7Ar722Bw=";
  };
  handCode = pkgs.linkFarm "room-cam-hand-model-code" [
    {
      name = "mp_palmdet.py";
      path = pkgs.fetchurl {
        url = "${raw}/palm_detection_mediapipe/mp_palmdet.py";
        hash = "sha256-8GzkSpt34StJ1yQWOIgp/RpIH/56UW2RTlqMbKUHEL4=";
      };
    }
    {
      name = "mp_handpose.py";
      path = pkgs.fetchurl {
        url = "${raw}/handpose_estimation_mediapipe/mp_handpose.py";
        hash = "sha256-fWe/xkX4gHSWrya485PghNchE89Sk6UgsOmQXpozGqU=";
      };
    }
    {
      name = "LICENSE";
      path = pkgs.fetchurl {
        url = "${raw}/handpose_estimation_mediapipe/LICENSE";
        hash = "sha256-WNHhf/5RCaeuKWyq/K39vmp9F28LxKsB4SpomwSZ2L0=";
      };
    }
  ];
in
pkgs.writeShellApplication {
  name = "room-cam";
  text = ''
    export PYTHONNOUSERSITE=1
    export CAMERA_FIRMWARE=${firmware}
    export CAMERA_MODEL=${model}
    export CAMERA_PALM_MODEL=${palmModel}
    export CAMERA_HAND_MODEL=${handModel}
    export CAMERA_PALM_CODE=${handCode}/mp_palmdet.py
    export CAMERA_HAND_CODE=${handCode}/mp_handpose.py
    export CAMERA_LIBUSB=${pkgs.libusb1}/lib/libusb-1.0.so
    export CAMERA_FFPLAY=${pkgs.ffmpeg}/bin/ffplay
    export CAMERA_NOTIFY=${pkgs.libnotify}/bin/notify-send
    exec ${python}/bin/python3 -B ${./.}/camera.py "$@"
  '';
}
