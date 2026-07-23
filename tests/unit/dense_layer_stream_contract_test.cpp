#include <gtest/gtest.h>

#include <atomic>
#include <chrono>
#include <filesystem>
#include <fstream>
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
            ("us4-dense-stream-test-" + std::to_string(nonce) + ".bin");
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

std::optional<us4::DenseLayerSliceReader>
OpenReader(const std::filesystem::path &path,
           std::vector<us4::DenseLayerDescriptor> layers) {
  std::string error;
  auto reader =
      us4::DenseLayerSliceReader::Open(path, std::move(layers), &error);
  EXPECT_TRUE(reader.has_value()) << error;
  return reader;
}

} // namespace

TEST(DenseLayerSliceReaderContractTest, ReadsOnlyRequestedRows) {
  const TemporaryWeights fixture({1, 2, 3, 4, 5, 6});
  auto reader = OpenReader(fixture.Path(), {{0, 2, 3}});
  ASSERT_TRUE(reader.has_value());

  const us4::DenseSliceRead slice = reader->Read(0, 1, 1);

  EXPECT_EQ(slice.status, us4::DenseStreamStatus::kCompleted);
  EXPECT_EQ(slice.weights, (std::vector<float>{3, 4}));
}

TEST(DenseLayerSliceReaderContractTest, RejectsRangesPastFileAtOpen) {
  const TemporaryWeights fixture({1, 2, 3});
  std::string error;
  const auto reader =
      us4::DenseLayerSliceReader::Open(fixture.Path(), {{0, 2, 2}}, &error);

  EXPECT_FALSE(reader.has_value());
  EXPECT_NE(error.find("past"), std::string::npos);
}

TEST(DenseLayerStreamContractTest, ComputesTinyNetworkWithTwoWeightSlots) {
  const TemporaryWeights fixture({
      1, 0, 0, 1, 1, 1, -1, 1, // 4x2
      1, 0, 0, 0, 0, 1, 0, 0, 1, 1, 1, 1, // 3x4
  });
  auto reader =
      OpenReader(fixture.Path(), {{0, 2, 4}, {8 * sizeof(float), 4, 3}});
  ASSERT_TRUE(reader.has_value());
  const us4::DenseLayerStreamExecutor executor(
      std::move(*reader), {.rowsPerSlice = 2});

  const us4::DenseStreamResult result = executor.Run({2, 3});

  ASSERT_TRUE(result.Completed()) << result.error;
  EXPECT_EQ(result.output, (std::vector<float>{2, 3, 11}));
  EXPECT_EQ(result.metrics.layersCompleted, 2);
  EXPECT_EQ(result.metrics.slicesRead, 4);
  EXPECT_EQ(result.metrics.prefetchedSlices, 3);
  EXPECT_EQ(result.metrics.maximumWeightSlots, 2);
  EXPECT_EQ(result.metrics.bytesRead, 80);
  EXPECT_LE(result.metrics.peakBufferedWeightBytesUpperBound, 64);
}

TEST(DenseLayerStreamContractTest, CancellationNeverReturnsPartialOutput) {
  std::vector<float> weights(64, 1.0F);
  const TemporaryWeights fixture(weights);
  auto reader =
      OpenReader(fixture.Path(), {{0, 8, 8}});
  ASSERT_TRUE(reader.has_value());
  const us4::DenseLayerStreamExecutor executor(
      std::move(*reader), {.rowsPerSlice = 2});
  std::atomic<int> checks = 0;

  const us4::DenseStreamResult result =
      executor.Run(std::vector<float>(8, 1.0F),
                   [&checks]() { return checks.fetch_add(1) >= 5; });

  EXPECT_EQ(result.status, us4::DenseStreamStatus::kCancelled);
  EXPECT_TRUE(result.output.empty());
  EXPECT_LT(result.metrics.layersCompleted, 1);
}

TEST(DenseLayerStreamContractTest, InvalidLayerChainReturnsNoOutput) {
  const TemporaryWeights fixture(std::vector<float>(12, 1.0F));
  auto reader =
      OpenReader(fixture.Path(), {{0, 2, 2}, {4 * sizeof(float), 4, 2}});
  ASSERT_TRUE(reader.has_value());
  const us4::DenseLayerStreamExecutor executor(
      std::move(*reader), {.rowsPerSlice = 1});

  const us4::DenseStreamResult result = executor.Run({1, 1});

  EXPECT_EQ(result.status, us4::DenseStreamStatus::kInvalidArgument);
  EXPECT_TRUE(result.output.empty());
  EXPECT_EQ(result.metrics.bytesRead, 0);
}
