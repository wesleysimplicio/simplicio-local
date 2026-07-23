#include <atomic>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>

#include "dense/layer_stream.h"

namespace {

class TemporaryWeights {
public:
  explicit TemporaryWeights(const std::vector<float> &weights) {
    const auto nonce =
        std::chrono::steady_clock::now().time_since_epoch().count();
    path_ = std::filesystem::temp_directory_path() /
            ("us4-dense-stream-smoke-" + std::to_string(nonce) + ".bin");
    std::ofstream stream(path_, std::ios::binary);
    stream.write(reinterpret_cast<const char *>(weights.data()),
                 static_cast<std::streamsize>(weights.size() * sizeof(float)));
  }

  ~TemporaryWeights() {
    std::error_code ignored;
    std::filesystem::remove(path_, ignored);
  }

  const std::filesystem::path &Path() const { return path_; }

private:
  std::filesystem::path path_;
};

bool Expect(const bool condition, const char *message) {
  if (!condition) {
    std::cerr << message << "\n";
  }
  return condition;
}

bool HappyPathAndBound() {
  const TemporaryWeights fixture({
      1, 0, 0, 1, 1, 1, -1, 1, // 4x2
      1, 0, 0, 0, 0, 1, 0, 0, 1, 1, 1, 1, // 3x4
  });
  std::string error;
  auto reader = us4::DenseLayerSliceReader::Open(
      fixture.Path(), {{0, 2, 4}, {8 * sizeof(float), 4, 3}}, &error);
  if (!Expect(reader.has_value(), "tiny reader should open")) {
    return false;
  }
  const us4::DenseLayerStreamExecutor executor(
      std::move(*reader), {.rowsPerSlice = 2});
  const us4::DenseStreamResult result = executor.Run({2, 3});

  return Expect(result.Completed(), "tiny stream should complete") &&
         Expect(result.output == std::vector<float>({2, 3, 11}),
                "tiny stream output should match reference") &&
         Expect(result.metrics.slicesRead == 4,
                "tiny stream should read four slices") &&
         Expect(result.metrics.prefetchedSlices == 3,
                "all slices after the first should be prefetched") &&
         Expect(result.metrics.maximumWeightSlots == 2,
                "stream must use at most two weight slots") &&
         Expect(result.metrics.peakBufferedWeightBytesUpperBound <= 64,
                "buffer upper bound should stay within two configured slices");
}

bool CancellationIsTransactional() {
  const TemporaryWeights fixture(std::vector<float>(64, 1.0F));
  std::string error;
  auto reader = us4::DenseLayerSliceReader::Open(fixture.Path(), {{0, 8, 8}},
                                                  &error);
  if (!Expect(reader.has_value(), "cancellation reader should open")) {
    return false;
  }
  const us4::DenseLayerStreamExecutor executor(
      std::move(*reader), {.rowsPerSlice = 2});
  std::atomic<int> checks = 0;
  const us4::DenseStreamResult result =
      executor.Run(std::vector<float>(8, 1.0F),
                   [&checks]() { return checks.fetch_add(1) >= 5; });

  return Expect(result.status == us4::DenseStreamStatus::kCancelled,
                "cancelled stream should report cancellation") &&
         Expect(result.output.empty(),
                "cancelled stream must not expose partial output") &&
         Expect(result.metrics.layersCompleted == 0,
                "cancelled layer must not be counted as completed");
}

bool InvalidRangeFailsClosed() {
  const TemporaryWeights fixture({1, 2, 3});
  std::string error;
  const auto reader =
      us4::DenseLayerSliceReader::Open(fixture.Path(), {{0, 2, 2}}, &error);
  return Expect(!reader.has_value(), "truncated layer should be rejected") &&
         Expect(error.find("past") != std::string::npos,
                "truncated layer should have an explicit error");
}

} // namespace

int main() {
  return HappyPathAndBound() && CancellationIsTransactional() &&
                 InvalidRangeFailsClosed()
             ? 0
             : 1;
}
