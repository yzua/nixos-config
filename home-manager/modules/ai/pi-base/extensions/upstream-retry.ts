// Normalize one transient upstream failure for Pi's built-in retry policy.
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const UPSTREAM_BODY_FAILURE = "upstream_error: native upstream response body failed";

export default function (pi: ExtensionAPI) {
  pi.on("message_end", ({ message }) => {
    if (
      message.role !== "assistant" ||
      message.stopReason !== "error" ||
      message.errorMessage !== UPSTREAM_BODY_FAILURE
    ) {
      return;
    }

    // Keep the original error and all response data. Pi recognizes "network error"
    // and owns retry limits, backoff, failed-attempt omission, and cancellation.
    return {
      message: { ...message, errorMessage: `${message.errorMessage} (network error)` },
    };
  });
}
