#pragma once

#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <functional>
#include <optional>
#include <string>
#include <vector>

namespace us4 {

struct DenseLayerDescriptor {
  std::uint64_t fileOffsetBytes = 0;
  std::size_t inputWidth = 0;
  std::size_t outputWidth = 0;
};

enum class DenseStreamStatus {
  kCompleted,
  kCancelled,
  kInvalidArgument,
  kIoError,
};

struct DenseSliceRead {
  DenseStreamStatus status = DenseStreamStatus::kIoError;
  std::vector<float> weights;
  std::uint64_t readNanoseconds = 0;
  std::string error;
};

class DenseLayerSliceReader {
public:
  static std::optional<DenseLayerSliceReader>
  Open(const std::filesystem::path &path,
       std::vector<DenseLayerDescriptor> layers, std::string *error = nullptr);

  DenseSliceRead Read(std::size_t layerIndex, std::size_t firstRow,
                      std::size_t rowCount,
                      const std::function<bool()> &cancelled = {}) const;

  const std::vector<DenseLayerDescriptor> &Layers() const { return layers_; }

private:
  std::filesystem::path path_;
  std::uint64_t fileSizeBytes_ = 0;
  std::vector<DenseLayerDescriptor> layers_;
};

struct DenseStreamOptions {
  std::size_t rowsPerSlice = 1;
};

struct DenseStreamMetrics {
  std::size_t layersCompleted = 0;
  std::size_t slicesRead = 0;
  std::size_t prefetchedSlices = 0;
  std::size_t maximumWeightSlots = 0;
  std::uint64_t bytesRead = 0;
  std::uint64_t peakBufferedWeightBytesUpperBound = 0;
  std::uint64_t readNanoseconds = 0;
  std::uint64_t prefetchWaitNanoseconds = 0;
  std::uint64_t computeNanoseconds = 0;
  std::uint64_t wallNanoseconds = 0;
};

struct DenseStreamResult {
  DenseStreamStatus status = DenseStreamStatus::kInvalidArgument;
  std::vector<float> output;
  DenseStreamMetrics metrics;
  std::string error;

  bool Completed() const { return status == DenseStreamStatus::kCompleted; }
};

class DenseLayerStreamExecutor {
public:
  DenseLayerStreamExecutor(DenseLayerSliceReader reader,
                           DenseStreamOptions options);

  DenseStreamResult
  Run(const std::vector<float> &input,
      const std::function<bool()> &cancelled = {}) const;

private:
  DenseLayerSliceReader reader_;
  DenseStreamOptions options_;
};

const char *DenseStreamStatusName(DenseStreamStatus status);

} // namespace us4
