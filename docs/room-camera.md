# Room Cam: local viewing, person alerts, and hand data

The desktop profile provides three on-demand applications:

- **Room Cam**: full-resolution 1920×1080, 30 fps local live view.
- **Room Person Monitor**: person boxes and desktop notifications. The annotated
  preview runs at up to 15 fps; CPU inference samples up to twice per second.
- **Room Hand Tracker**: a hand-skeleton preview plus a dedicated terminal
  dashboard with motion, finger, pinch, and tentative gesture measurements.
  It emits data only: **no mute, volume, keyboard, mouse, or other control actions**.

Search for these names in the application launcher, or run:

```sh
room-cam
room-cam --monitor
room-cam --hands
```

Press **Q** or close the preview window to stop; **F** toggles fullscreen.
For terminal-only hand tracking, use **Ctrl+C**. Close one view before opening
another. OBS and other webcam applications can also occupy the camera.
No camera process starts automatically at login.

The application was initially called PS5 Camera; Room Cam replaces those
launcher entries and the old `ps5-camera` command. The hardware is still a
PS5 HD Camera, and its hardware-specific NixOS permission module retains that name.

## Hand-motion playground

The preview runs independently at up to 30 fps; a latest-frame inference worker
samples up to 20 times per second, limited by CPU speed. Start with an open hand
in good lighting and fingers separated. Once acquired, the hand-pose model
follows its previous palm landmarks, allowing a closed fist to remain tracked
without requiring a new open-palm detection on every sample. Each accepted pose
is fresh inference; old landmarks are never returned as current detections.

When searching, the detector checks the full image and one rotating overlapping
768×768 crop. This gives small hands about 2.5× the detector sampling of the
full-room view, but cannot restore missing image detail. The terminal reports
palm width in pixels and warns below 35px; distant finger gestures still depend
on lighting, camera placement, and how large the hand appears. Hold an open hand
briefly to acquire it, then try a fist, pointing, victory sign, and pinch.

```sh
# Dashboard and skeleton preview:
room-cam --hands

# Dashboard only:
room-cam --hands --no-preview

# Machine-readable JSON Lines on stdout, without a preview:
room-cam --hands --json --no-preview
```

The hand launcher opens the configured Ghostty terminal plus the preview.
If the terminal exits before a preview appears, run the command in an existing
terminal to read the error. Close the person monitor before starting hand tracking.

The JSON stream is intended as the data interface for future controls. For
example, inspect a compact subset without saving it:

```sh
room-cam --hands --json --no-preview | jq -c '{
  sequence,
  hands: [.hands[] | {track_id, gesture, pinch_ratio, center_norm, velocity_norm_per_s}]
}'
```

The application never saves telemetry itself. Redirecting stdout to a file
would deliberately save it; terminal applications may also retain scrollback.
The interactive dashboard uses an alternate screen rather than continuously
adding landmark data to scrollback. JSON output contains no terminal escape codes.

### JSON contract, version 1

Each `hand_frame` event includes:

- `schema_version`, `type`, and an increasing output `sequence`.
- `inference_sequence`: source inference number; may repeat for an expiry update.
- `tracking_stale` and `sample_age_ms`: results older than 350 ms are explicitly
  invalidated with `hands: []`, including when no new inference has completed.
  The terminal and preview apply the same expiry policy. Read capture timestamps
  too: a blocked downstream consumer can delay delivery after emission.
- `capture_monotonic_ns`: the frame's local monotonic receive timestamp, not wall
  clock time. It is useful for time differences only on the same machine/boot.
- `image`: capture width 1920, height 1080, and `mirrored: false`.
- `inference_ms`: time spent in palm/hand neural inference.
- `hands`: zero, one, or two accepted hands. An empty array means no accepted
  hand in that sample, not an instruction to retain a previous gesture.

Each hand includes:

- `track_id`: a short-lived nearest-position association, **not identity**.
  IDs can change after loss and may swap when hands cross. Tracks expire after
  0.75 seconds without an accepted detection.
- `source`: `palm_acquisition` or `tracked_pose`. `palm_score` is null for tracked
  poses because they have no fresh palm-detector score.
- `hand_presence_score`, `handedness_right_score_raw`:
  model scores, not calibrated guarantees. Handedness is the raw model value;
  it is not labelled as anatomical left/right because the model's selfie
  convention needs physical validation with this unmirrored camera.
- `bbox_xyxy_px`, `landmarks_image_xyz`: bounding box and 21 floating-point
  landmark triples. Landmark order is wrist 0, thumb 1–4, index 5–8, middle
  9–12, ring 13–16, little finger 17–20.
- Image x grows rightward, y downward. Image z is learned wrist-relative,
  pixel-like depth; it is **not meters or distance from the camera**.
- `landmarks_norm`: x/1920, y/1080, z/1920. Predictions are not clipped, so
  normalized values can fall outside 0–1 near image edges.
- `center_norm`: mean of wrist and four finger-base positions, normalized by
  image dimensions. `velocity_norm_per_s` measures its image-space movement
  in fractions of frame width/height per second—not physical room movement.
- `motion_valid`: false on first observation, after any missed hand sample,
  or across a gap exceeding 0.25 seconds. Velocity resets to zero in these cases
  so reacquisition does not look like a swipe.
- `fingers_extended`, `finger_count`: rotation/scale-independent 2D geometric
  heuristics, not a separately trained gesture classifier.
- `palm_width_px`: index-base to little-finger-base distance in image pixels.
- `pinch_ratio`: thumb-tip to index-tip distance divided by palm width.
  `pinch_active` engages below 0.25 and stays engaged until 0.4, reducing flicker.
  These are initial thresholds, not personal calibration.
- `gesture_raw`: `open_palm`, `fist`, `pinch`, `pointing`, `victory`, or `unknown`.
  `gesture` requires the same candidate for at least 0.2 seconds; `gesture_changed`
  marks a debounced change. The previous stable label can remain during that
  confirmation interval; consumers should also inspect raw state and freshness.

Use this playground to choose intentional gestures and thresholds before adding
any control action. Future mute/volume integration should explicitly arm controls,
reject stale/lost samples, and debounce one-shot actions. No such integration is
configured now. Occlusion, fast motion, edge-on hands, and finger overlap can
produce wrong landmarks or labels. Tracking rejects collapsed/out-of-frame palms,
large scale/position jumps, duplicate hands, and previous crops older than 350 ms;
failed pose inference triggers reacquisition instead of freezing the last hand.
New acquisitions require hand-presence score 0.8; tracking an acquired hand permits
0.65, with the geometric guards above. Periodic detector scans look for new hands.

## Connection and activation

Connect the PS5 HD Camera directly to USB 3.x. Before loading firmware it
identifies as `05a9:0580`; afterward it reappears as UVC `05a9:058c`.
The application uses its persistent `/dev/v4l/by-id/` link rather than assuming
it is always `/dev/video0`.

The NixOS module grants bootloader access only to the active local seat user
through a narrowly scoped udev `uaccess` rule. No broad USB permissions,
additional groups, privileged uploader, or background service are used.
The app uploads pinned brightness-fix firmware **on demand** if needed, checking
its size and SHA-256 before USB writes. Unplugging clears the RAM firmware;
the next launch reloads it. This setup expects one PS5 camera, not several
indistinguishable devices. Never run the viewer as root.

From the repository root, review and activate the selected outputs:

```sh
just check
just home-preview
just home-switch
just preview
just switch
```

After the first NixOS activation, unplug/replug the camera to apply the new
bootloader permissions. Until system activation, an already loaded camera
can be viewed, but firmware reload may fail for lack of USB access.
See the root README for output selection and guarded-preview requirements.

## Person alerts and privacy

Person detection uses the pinned Apache-2.0 OpenCV Zoo YOLOX-S model with CPU-only
OpenCV DNN inference. It recognizes the COCO **person** class; it does not identify
faces or establish identity across frames. A person must appear across one second
of consecutive positive samples before an alert. Five seconds without a detection
rearms arrival state; notifications have a minimum 60-second cooldown. A person
present at startup also triggers an alert. Desktop Do Not Disturb may hide popups.

```sh
room-cam --monitor --confidence 0.6 --cooldown 120
```

This is not a dependable alarm or life-safety system. The computer must remain
awake and the app running; minimizing is fine, closing stops detection.

No frames, clips, thumbnails, or detection history are saved. No server, cloud
service, telemetry uploader, firewall port, or remote access is configured.
Hand telemetry is emitted only to the invoking terminal/stdout. Other native
applications running as the same user may still access the webcam; unplugging
or covering both lenses is the strongest privacy switch.

Dependencies/model/firmware download only at Nix build time, not at runtime.
The camera's standard firmware produced near-black output in hardware tests;
the pinned community gamma fix resolved it. 1080p at 15 fps stalled in testing;
use the verified capture mode of 1080p at 30 fps. The preview does not downscale.

## Verification and provenance

```sh
python3 -B tests/room-camera.py
python3 -B tests/hand-motion.py
nix run .#room-cam -- --check-model
nix run .#room-cam -- --hands --check-model
nix run .#room-cam -- --test-frames 30
nix run .#room-cam -- --hands --json --test-frames 10
```

Offline suites use fake USB transfers, clocks, geometry, and real temporary pipe
consumers—not hardware or notifications. Model checks use synthetic input.
Live checks capture/infer in memory and exit without a window or saved images.

Pinned upstream sources:

- [Firmware protocol and brightness fix](https://github.com/zweiler2/PS5_Camera_Loader/tree/6df56c6c2a0e6b5e4e782c56458e5f9d8525b837)
- [Original community brightness-fix attachment](https://github.com/psxdev/OrbisEyeCam/issues/10#issuecomment-1571621824)
- [YOLOX model and preprocessing](https://github.com/opencv/opencv_zoo/tree/48b10fa505aeb51fbd127fc60a5c660040e823b7/models/object_detection_yolox)
- [MediaPipe palm model and Python wrapper](https://github.com/opencv/opencv_zoo/tree/48b10fa505aeb51fbd127fc60a5c660040e823b7/models/palm_detection_mediapipe)
- [MediaPipe hand-pose model, wrapper, and Apache-2.0 license](https://github.com/opencv/opencv_zoo/tree/48b10fa505aeb51fbd127fc60a5c660040e823b7/models/handpose_estimation_mediapipe)

Hand tracking uses the FP32 models (~8 MB combined) and the unmodified, hash-pinned
upstream Python wrappers; their license is retained alongside the wrapper files.
No MediaPipe framework or GPU build is required. Model SHA-256 values match the
upstream Git LFS pointers and are enforced by Nix. Firmware remains an unofficial
community binary, cross-checked against its original attachment.
