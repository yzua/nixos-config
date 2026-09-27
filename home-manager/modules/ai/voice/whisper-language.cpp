// Choose Arabic or English with Whisper's language probabilities on the GPU.
#include <whisper.h>
#include <ggml-backend.h>

#include <cstdint>
#include <fstream>
#include <iostream>
#include <iterator>
#include <string>
#include <vector>

static uint16_t u16(const std::vector<uint8_t> &b, size_t p) {
    return uint16_t(b[p]) | (uint16_t(b[p + 1]) << 8);
}

static uint32_t u32(const std::vector<uint8_t> &b, size_t p) {
    return uint32_t(b[p]) | (uint32_t(b[p + 1]) << 8) |
           (uint32_t(b[p + 2]) << 16) | (uint32_t(b[p + 3]) << 24);
}

int main(int argc, char **argv) {
    if (argc != 3) {
        std::cerr << "usage: choose-language MODEL WAV\n";
        return 2;
    }
    std::ifstream file(argv[2], std::ios::binary);
    if (!file) return 2;
    std::vector<uint8_t> bytes((std::istreambuf_iterator<char>(file)), {});
    if (bytes.size() < 44 || std::string(bytes.begin(), bytes.begin() + 4) != "RIFF" ||
        std::string(bytes.begin() + 8, bytes.begin() + 12) != "WAVE") return 2;

    bool valid_format = false;
    std::vector<float> samples;
    for (size_t p = 12; p + 8 <= bytes.size();) {
        const uint32_t size = u32(bytes, p + 4);
        const size_t start = p + 8;
        if (size > bytes.size() - start) return 2;
        const std::string type(bytes.begin() + p, bytes.begin() + p + 4);
        if (type == "fmt " && size >= 16) {
            valid_format = u16(bytes, start) == 1 && u16(bytes, start + 2) == 1 &&
                           u32(bytes, start + 4) == 16000 && u16(bytes, start + 14) == 16;
        } else if (type == "data") {
            if (size % 2) return 2;
            samples.reserve(size / 2);
            for (size_t i = start; i < start + size; i += 2)
                samples.push_back(static_cast<int16_t>(u16(bytes, i)) / 32768.0f);
        }
        p = start + size + (size & 1);
    }
    if (!valid_format || samples.empty()) return 2;

    auto params = whisper_context_default_params();
    params.use_gpu = true;
    ggml_backend_load_all();
    whisper_context *ctx = whisper_init_from_file_with_params_no_state(argv[1], params);
    if (!ctx) return 3;
    whisper_state *state = whisper_init_state(ctx);
    if (!state) { whisper_free(ctx); return 3; }
    const int threads = 4;
    int status = whisper_pcm_to_mel_with_state(ctx, state, samples.data(), int(samples.size()), threads);
    std::vector<float> probs(whisper_lang_max_id() + 1, 0.0f);
    const int top = status ? -1 : whisper_lang_auto_detect_with_state(ctx, state, 0, threads, probs.data());
    if (top < 0) status = 1;
    if (!status) {
        const float ar = probs.at(whisper_lang_id("ar"));
        const float en = probs.at(whisper_lang_id("en"));
        // Short Arabic requests with English app names can score English higher.
        // Keep English for clearly English speech, but allow a plausible Arabic
        // score when it is within a factor of five of English.
        const bool arabic = ar >= en || (ar >= 0.01f && ar >= 0.2f * en);
        std::cout << (arabic ? "ar" : "en") << '\n';
    }
    whisper_free_state(state);
    whisper_free(ctx);
    return status ? 3 : 0;
}
