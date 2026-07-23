#include "dense/layer_stream.h"

#include <algorithm>
#include <chrono>
#include <fstream>
#include <future>
#include <limits>
#include <utility>

namespace us4 {

namespace {

using Clock = std::chrono::steady_clock;

std::uint64_t ElapsedNanoseconds(const Clock::time_point start) {
  return static_cast<std::uint64_t>(
      std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now() - start)
          .count());
}

bool MultiplyWouldOverflow(const std::uint64_t left,
                           const std::uint64_t right) {
  return right != 0 &&
         left > std::numeric_limits<std::uint64_t>::max() / right;
}

bool IsCancelled(const std::function<bool()> &cancelled) {
  return cancelled && cancelled();
}

std::uint64_t SliceBytes(const DenseLayerDescriptor &layer,
                         const std::size_t rows) {
  return static_cast<std::uint64_t>(rows) *
         static_cast<std::uint64_t>(layer.inputWidth) * sizeof(float);
}

} // namespace

std::optional<DenseLayerSliceReader>
DenseLayerSliceReader::Open(const std::filesystem::path &path,
                            std::vector<DenseLayerDescriptor> layers,
                            std::string *error) {
  std::error_code sizeError;
  const std::uintmax_t fileSize = std::filesystem::file_size(path, sizeError);
  if (sizeError) {
    if (error != nullptr) {
      *error = "dense weight file is unavailable: " + path.string();
    }
    return std::nullopt;
  }
  if (fileSize > std::numeric_limits<std::uint64_t>::max()) {
    if (error != nullptr) {
      *error = "dense weight file is too large to address";
    }
    return std::nullopt;
  }
  if (layers.empty()) {
    if (error != nullptr) {
      *error = "dense stream requires at least one layer";
    }
    return std::nullopt;
  }

  const std::uint64_t fileSizeBytes = static_cast<std::uint64_t>(fileSize);
  for (const DenseLayerDescriptor &layer : layers) {
    if (layer.inputWidth == 0 || layer.outputWidth == 0) {
      if (error != nullptr) {
        *error = "dense layer dimensions must be non-zero";
      }
      return std::nullopt;
    }
    const std::uint64_t inputWidth =
        static_cast<std::uint64_t>(layer.inputWidth);
    const std::uint64_t outputWidth =
        static_cast<std::uint64_t>(layer.outputWidth);
    if (MultiplyWouldOverflow(inputWidth, outputWidth) ||
        MultiplyWouldOverflow(inputWidth * outputWidth, sizeof(float))) {
      if (error != nullptr) {
        *error = "dense layer byte range overflows";
      }
      return std::nullopt;
    }
    const std::uint64_t layerBytes =
        inputWidth * outputWidth * sizeof(float);
    if (layer.fileOffsetBytes > fileSizeBytes ||
        layerBytes > fileSizeBytes - layer.fileOffsetBytes) {
      if (error != nullptr) {
        *error = "dense layer range extends past the weight file";
      }
      return std::nullopt;
    }
  }

  DenseLayerSliceReader reader;
  reader.path_ = path;
  reader.fileSizeBytes_ = fileSizeBytes;
  reader.layers_ = std::move(layers);
  return reader;
}

DenseSliceRead
DenseLayerSliceReader::Read(const std::size_t layerIndex,
                            const std::size_t firstRow,
                            const std::size_t rowCount,
                            const std::function<bool()> &cancelled) const {
  DenseSliceRead result;
  const Clock::time_point readStart = Clock::now();
  if (IsCancelled(cancelled)) {
    result.status = DenseStreamStatus::kCancelled;
    result.readNanoseconds = ElapsedNanoseconds(readStart);
    return result;
  }
  if (layerIndex >= layers_.size() || rowCount == 0) {
    result.status = DenseStreamStatus::kInvalidArgument;
    result.error = "dense slice coordinates are invalid";
    result.readNanoseconds = ElapsedNanoseconds(readStart);
    return result;
  }

  const DenseLayerDescriptor &layer = layers_[layerIndex];
  if (firstRow >= layer.outputWidth ||
      rowCount > layer.outputWidth - firstRow) {
    result.status = DenseStreamStatus::kInvalidArgument;
    result.error = "dense slice rows extend past the layer";
    result.readNanoseconds = ElapsedNanoseconds(readStart);
    return result;
  }

  const std::uint64_t byteCount = SliceBytes(layer, rowCount);
  const std::uint64_t rowOffset = SliceBytes(layer, firstRow);
  if (rowOffset > fileSizeBytes_ - layer.fileOffsetBytes ||
      byteCount > fileSizeBytes_ - layer.fileOffsetBytes - rowOffset) {
    result.status = DenseStreamStatus::kIoError;
    result.error = "dense slice range extends past the weight file";
    result.readNanoseconds = ElapsedNanoseconds(readStart);
    return result;
  }

  std::ifstream file(path_, std::ios::binary);
  if (!file) {
    result.status = DenseStreamStatus::kIoError;
    result.error = "unable to open dense weight file";
    result.readNanoseconds = ElapsedNanoseconds(readStart);
    return result;
  }
  file.seekg(static_cast<std::streamoff>(layer.fileOffsetBytes + rowOffset));
  if (!file) {
    result.status = DenseStreamStatus::kIoError;
    result.error = "unable to seek to dense slice";
    result.readNanoseconds = ElapsedNanoseconds(readStart);
    return result;
  }

  result.weights.resize(static_cast<std::size_t>(byteCount / sizeof(float)));
  file.read(reinterpret_cast<char *>(result.weights.data()),
            static_cast<std::streamsize>(byteCount));
  if (!file) {
    result.status = DenseStreamStatus::kIoError;
    result.weights.clear();
    result.error = "dense slice read was truncated";
    result.readNanoseconds = ElapsedNanoseconds(readStart);
    return result;
  }
  if (IsCancelled(cancelled)) {
    result.status = DenseStreamStatus::kCancelled;
    result.weights.clear();
    result.readNanoseconds = ElapsedNanoseconds(readStart);
    return result;
  }

  result.status = DenseStreamStatus::kCompleted;
  result.readNanoseconds = ElapsedNanoseconds(readStart);
  return result;
}

DenseLayerStreamExecutor::DenseLayerStreamExecutor(
    DenseLayerSliceReader reader, const DenseStreamOptions options)
    : reader_(std::move(reader)), options_(options) {}

DenseStreamResult DenseLayerStreamExecutor::Run(
    const std::vector<float> &input,
    const std::function<bool()> &cancelled) const {
  DenseStreamResult result;
  const Clock::time_point wallStart = Clock::now();
  const auto finish = [&result, wallStart](const DenseStreamStatus status,
                                           std::string error = {}) {
    result.status = status;
    result.error = std::move(error);
    result.metrics.wallNanoseconds = ElapsedNanoseconds(wallStart);
    if (status != DenseStreamStatus::kCompleted) {
      result.output.clear();
    }
  };

  if (options_.rowsPerSlice == 0 || input.empty() ||
      reader_.Layers().empty()) {
    finish(DenseStreamStatus::kInvalidArgument,
           "dense stream input and rows-per-slice must be non-zero");
    return result;
  }

  std::size_t expectedInputWidth = input.size();
  for (const DenseLayerDescriptor &layer : reader_.Layers()) {
    if (layer.inputWidth != expectedInputWidth) {
      finish(DenseStreamStatus::kInvalidArgument,
             "dense layer dimensions do not form a valid chain");
      return result;
    }
    expectedInputWidth = layer.outputWidth;
  }
  if (IsCancelled(cancelled)) {
    finish(DenseStreamStatus::kCancelled);
    return result;
  }

  std::vector<float> activation = input;
  std::future<DenseSliceRead> carriedPrefetch;
  for (std::size_t layerIndex = 0; layerIndex < reader_.Layers().size();
       ++layerIndex) {
    const DenseLayerDescriptor &layer = reader_.Layers()[layerIndex];
    std::vector<float> nextActivation(layer.outputWidth, 0.0F);
    const std::size_t firstRows =
        std::min(options_.rowsPerSlice, layer.outputWidth);
    DenseSliceRead active;
    if (carriedPrefetch.valid()) {
      const Clock::time_point waitStart = Clock::now();
      active = carriedPrefetch.get();
      result.metrics.prefetchWaitNanoseconds += ElapsedNanoseconds(waitStart);
    } else {
      active = reader_.Read(layerIndex, 0, firstRows, cancelled);
    }
    if (active.status != DenseStreamStatus::kCompleted) {
      finish(active.status, std::move(active.error));
      return result;
    }

    std::size_t firstRow = 0;
    std::size_t activeRows = firstRows;
    while (true) {
      const std::size_t nextFirstRow = firstRow + activeRows;
      const bool hasNextSlice = nextFirstRow < layer.outputWidth;
      const bool hasNextLayer =
          !hasNextSlice && layerIndex + 1 < reader_.Layers().size();
      const bool hasPrefetch = hasNextSlice || hasNextLayer;
      const std::size_t nextLayerIndex =
          hasNextSlice ? layerIndex : layerIndex + 1;
      const std::size_t nextRow = hasNextSlice ? nextFirstRow : 0;
      std::size_t nextRows = 0;
      std::future<DenseSliceRead> prefetched;
      if (hasPrefetch) {
        const DenseLayerDescriptor &nextLayer =
            reader_.Layers()[nextLayerIndex];
        nextRows = std::min(options_.rowsPerSlice,
                            nextLayer.outputWidth - nextRow);
        prefetched = std::async(
            std::launch::async,
            [this, nextLayerIndex, nextRow, nextRows]() {
              return reader_.Read(nextLayerIndex, nextRow, nextRows);
            });
        ++result.metrics.prefetchedSlices;
      }

      const std::uint64_t activeBytes =
          static_cast<std::uint64_t>(active.weights.size()) * sizeof(float);
      const std::uint64_t pendingBytes = hasPrefetch
                                             ? SliceBytes(reader_.Layers()
                                                              [nextLayerIndex],
                                                          nextRows)
                                             : 0;
      result.metrics.peakBufferedWeightBytesUpperBound =
          std::max(result.metrics.peakBufferedWeightBytesUpperBound,
                   activeBytes + pendingBytes);
      result.metrics.maximumWeightSlots =
          std::max(result.metrics.maximumWeightSlots,
                   static_cast<std::size_t>(hasPrefetch ? 2 : 1));
      ++result.metrics.slicesRead;
      result.metrics.bytesRead += activeBytes;
      result.metrics.readNanoseconds += active.readNanoseconds;

      const Clock::time_point computeStart = Clock::now();
      for (std::size_t row = 0; row < activeRows; ++row) {
        if (IsCancelled(cancelled)) {
          if (hasPrefetch) {
            prefetched.wait();
          }
          result.metrics.computeNanoseconds +=
              ElapsedNanoseconds(computeStart);
          finish(DenseStreamStatus::kCancelled);
          return result;
        }
        float sum = 0.0F;
        const std::size_t weightBase = row * layer.inputWidth;
        for (std::size_t column = 0; column < layer.inputWidth; ++column) {
          sum += active.weights[weightBase + column] * activation[column];
        }
        nextActivation[firstRow + row] = sum;
      }
      result.metrics.computeNanoseconds += ElapsedNanoseconds(computeStart);

      if (!hasPrefetch) {
        break;
      }
      if (nextLayerIndex != layerIndex) {
        carriedPrefetch = std::move(prefetched);
        break;
      }
      const Clock::time_point waitStart = Clock::now();
      DenseSliceRead next = prefetched.get();
      result.metrics.prefetchWaitNanoseconds += ElapsedNanoseconds(waitStart);
      if (next.status != DenseStreamStatus::kCompleted) {
        finish(next.status, std::move(next.error));
        return result;
      }
      firstRow = nextRow;
      activeRows = nextRows;
      active = std::move(next);
    }

    if (IsCancelled(cancelled)) {
      if (carriedPrefetch.valid()) {
        carriedPrefetch.wait();
      }
      finish(DenseStreamStatus::kCancelled);
      return result;
    }
    activation = std::move(nextActivation);
    ++result.metrics.layersCompleted;
  }

  result.output = std::move(activation);
  finish(DenseStreamStatus::kCompleted);
  return result;
}

const char *DenseStreamStatusName(const DenseStreamStatus status) {
  switch (status) {
  case DenseStreamStatus::kCompleted:
    return "completed";
  case DenseStreamStatus::kCancelled:
    return "cancelled";
  case DenseStreamStatus::kInvalidArgument:
    return "invalid_argument";
  case DenseStreamStatus::kIoError:
    return "io_error";
  }
  return "unknown";
}

} // namespace us4
