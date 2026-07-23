#include <chrono>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <vector>

#include "dense/layer_stream.h"

namespace {

std::filesystem::path TinyFixturePath() {
  const auto nonce = std::chrono::steady_clock::now().time_since_epoch().count();
  return std::filesystem::temp_directory_path() /
         ("us4-dense-stream-" + std::to_string(nonce) + ".bin");
}

bool WriteFloats(const std::filesystem::path &path,
                 const std::vector<float> &weights) {
  std::ofstream stream(path, std::ios::binary);
  stream.write(reinterpret_cast<const char *>(weights.data()),
               static_cast<std::streamsize>(weights.size() * sizeof(float)));
  return static_cast<bool>(stream);
}

} // namespace

int main() {
  const std::filesystem::path fixture = TinyFixturePath();
  const std::vector<float> weights = {
      1, 0, 0, 1, 1, 1, -1, 1, // 4x2
      1, 0, 0, 0, 1, 0, 0, 0, 1, // 3x3
      2, 0, 0, 0, 2, 0, // 2x3
  };
  if (!WriteFloats(fixture, weights)) {
    std::cerr << "failed to create tiny dense-stream fixture\n";
    return 1;
  }

  const std::vector<us4::DenseLayerDescriptor> layers = {
      {0, 2, 4},
      {8 * sizeof(float), 4, 3},
      {17 * sizeof(float), 3, 2},
  };
  std::string error;
  auto reader = us4::DenseLayerSliceReader::Open(fixture, layers, &error);
  if (!reader.has_value()) {
    std::filesystem::remove(fixture);
    std::cerr << error << "\n";
    return 1;
  }

  const us4::DenseLayerStreamExecutor executor(
      std::move(*reader), us4::DenseStreamOptions{.rowsPerSlice = 2});
  const us4::DenseStreamResult result = executor.Run({2.0F, 3.0F});
  std::filesystem::remove(fixture);

  const bool outputMatches =
      result.output.size() == 2 &&
      std::abs(result.output[0] - 4.0F) < 1e-6F &&
      std::abs(result.output[1] - 6.0F) < 1e-6F;
  std::cout << "mode=demo-dense"
            << " fixture=tiny-generated"
            << " production_claim=false"
            << " status=" << us4::DenseStreamStatusName(result.status)
            << " layers_completed=" << result.metrics.layersCompleted
            << " slices_read=" << result.metrics.slicesRead
            << " prefetched_slices=" << result.metrics.prefetchedSlices
            << " maximum_weight_slots="
            << result.metrics.maximumWeightSlots
            << " bytes_read=" << result.metrics.bytesRead
            << " peak_buffered_weight_bytes_upper_bound="
            << result.metrics.peakBufferedWeightBytesUpperBound
            << " read_ns=" << result.metrics.readNanoseconds
            << " prefetch_wait_ns="
            << result.metrics.prefetchWaitNanoseconds
            << " compute_ns=" << result.metrics.computeNanoseconds
            << " wall_ns=" << result.metrics.wallNanoseconds << "\n";
  return result.Completed() && outputMatches ? 0 : 1;
}
