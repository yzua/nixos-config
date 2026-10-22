"""Volatile PS5 camera firmware upload via the community-documented USB protocol."""

import ctypes as C
import hashlib
from pathlib import Path

FIRMWARE_SHA256 = "42ce5f7033a1115988cada3ebb8e0a143e8b241661f203a12275354dd2ba0bf6"
DEVICE = "/dev/v4l/by-id/usb-Omnivision_Technologies__Inc._USB_Camera-OV580-video-index0"


def transfers(payload):
    """Yield EP0 vendor writes, followed by the RAM firmware activation command."""
    for offset in range(0, len(payload), 512):
        yield offset & 0xFFFF, 0x14 + (offset >> 16), payload[offset : offset + 512]
    yield 0x2200, 0x8018, b"\x5b"


def upload(firmware_path, library_path):
    payload = Path(firmware_path).read_bytes()
    if len(payload) != 68948 or hashlib.sha256(payload).hexdigest() != FIRMWARE_SHA256:
        raise RuntimeError("Refusing unrecognized PS5 camera firmware.")
    usb = C.CDLL(library_path)
    pointer = C.c_void_p
    signatures = {
        "init": ([C.POINTER(pointer)], C.c_int),
        "exit": ([pointer], None),
        "open_device_with_vid_pid": ([pointer, C.c_uint16, C.c_uint16], pointer),
        "close": ([pointer], None),
        "kernel_driver_active": ([pointer, C.c_int], C.c_int),
        "detach_kernel_driver": ([pointer, C.c_int], C.c_int),
        "claim_interface": ([pointer, C.c_int], C.c_int),
        "release_interface": ([pointer, C.c_int], C.c_int),
        "control_transfer": (
            [pointer, C.c_uint8, C.c_uint8, C.c_uint16, C.c_uint16, pointer, C.c_uint16, C.c_uint],
            C.c_int,
        ),
        "error_name": ([C.c_int], C.c_char_p),
    }
    for name, (args, result) in signatures.items():
        function = getattr(usb, "libusb_" + name)
        function.argtypes, function.restype = args, result

    def check(result):
        if result < 0:
            raise RuntimeError(f"Camera USB error: {usb.libusb_error_name(result).decode()}")
        return result

    context = pointer()
    check(usb.libusb_init(C.byref(context)))
    handle = None
    claimed = False
    try:
        handle = usb.libusb_open_device_with_vid_pid(context, 0x05A9, 0x0580)
        if not handle:
            raise RuntimeError(
                "Cannot open the PS5 camera bootloader. Connect it directly to USB 3; "
                "activate the NixOS camera permissions and log into the local desktop."
            )
        active = check(usb.libusb_kernel_driver_active(handle, 0))
        if active:
            check(usb.libusb_detach_kernel_driver(handle, 0))
        check(usb.libusb_claim_interface(handle, 0))
        claimed = True
        for value, index, chunk in transfers(payload):
            buffer = C.create_string_buffer(chunk)
            result = usb.libusb_control_transfer(
                handle, 0x40, 0, value, index, buffer, len(chunk), 2000
            )
            # Only the final activation may disconnect the bootloader normally.
            if result == -4 and (value, index) == (0x2200, 0x8018):
                break
            check(result)
            if result != len(chunk):
                raise RuntimeError("Incomplete camera firmware transfer; unplug and retry.")
    finally:
        if handle:
            if claimed:
                usb.libusb_release_interface(handle, 0)
            usb.libusb_close(handle)
        usb.libusb_exit(context)
