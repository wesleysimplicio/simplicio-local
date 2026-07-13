#include <cstdint>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <string>

#include <gtest/gtest.h>

#include "core/gguf_reader.h"

namespace us4 {
namespace {

template <typename T> void AppendRaw(std::string *out, const T &value) {
  out->append(reinterpret_cast<const char *>(&value), sizeof(T));
}

void AppendString(std::string *out, const std::string &text) {
  AppendRaw(out, static_cast<std::uint64_t>(text.size()));
  out->append(text);
}

// Builds a minimal, otherwise-valid GGUF file with a single F32 tensor
// whose shape is `dims`, no metadata entries. Used to exercise
// ReadFloat32's own bounds checking independent of Open()'s already-tested
// header parsing.
std::string BuildGgufWithTensorShape(const std::vector<std::uint64_t> &dims) {
  std::string bytes;
  bytes.append("GGUF", 4);
  AppendRaw(&bytes, static_cast<std::uint32_t>(3)); // version
  AppendRaw(&bytes, static_cast<std::uint64_t>(1)); // tensor_count
  AppendRaw(&bytes, static_cast<std::uint64_t>(0)); // metadata_kv_count

  AppendString(&bytes, "lm_head.weight");
  AppendRaw(&bytes, static_cast<std::uint32_t>(dims.size()));
  for (const std::uint64_t dim : dims) {
    AppendRaw(&bytes, dim);
  }
  AppendRaw(&bytes, static_cast<std::uint32_t>(GgufReader::kGgmlTypeF32));
  AppendRaw(&bytes, static_cast<std::uint64_t>(0)); // byte offset
  return bytes;
}

std::filesystem::path WriteTempGguf(const std::string &bytes,
                                    const std::string &suffix) {
  const std::filesystem::path path =
      std::filesystem::temp_directory_path() /
      ("gguf-reader-contract-test-" + suffix + ".gguf");
  std::ofstream file(path, std::ios::binary | std::ios::trunc);
  file.write(bytes.data(), static_cast<std::streamsize>(bytes.size()));
  return path;
}

std::filesystem::path FixtureDir() {
  return std::filesystem::path(US4_SOURCE_DIR) / "tests" / "fixtures" / "gguf";
}

// Issue #81.2b: the runtime must parse the real GGUF binary container
// (magic, version, tensor/metadata counts, tensor info array, aligned data
// section) instead of treating the extension as a hint and never opening
// the file.
TEST(GgufReaderContractTest, RejectsPlaceholderTextFile) {
  const std::filesystem::path placeholder =
      std::filesystem::path(US4_SOURCE_DIR) / "tests" / "fixtures" / "models" /
      "qwen-0.5b" / "toy-qwen.gguf";
  std::string error;
  const auto reader = GgufReader::Open(placeholder, &error);
  EXPECT_FALSE(reader.has_value());
  EXPECT_FALSE(error.empty());
}

TEST(GgufReaderContractTest, ParsesRealHeaderAndShapes) {
  std::string error;
  const auto reader = GgufReader::Open(FixtureDir() / "toy_real.gguf", &error);
  ASSERT_TRUE(reader.has_value()) << error;
  EXPECT_EQ(reader->TensorCount(), 2U);

  const auto *embedding = reader->Find("embedding.weight");
  ASSERT_NE(embedding, nullptr);
  EXPECT_EQ(embedding->ggmlType, GgufReader::kGgmlTypeF32);
  EXPECT_EQ(embedding->shape, (std::vector<std::size_t>{4, 3}));

  const auto *lmHead = reader->Find("lm_head.weight");
  ASSERT_NE(lmHead, nullptr);
  EXPECT_EQ(lmHead->shape, (std::vector<std::size_t>{3, 4}));
}

TEST(GgufReaderContractTest, ReadsRealFloat32TensorBytes) {
  std::string error;
  const auto reader = GgufReader::Open(FixtureDir() / "toy_real.gguf", &error);
  ASSERT_TRUE(reader.has_value()) << error;

  const std::vector<float> embedding =
      reader->ReadFloat32("embedding.weight", &error);
  ASSERT_EQ(embedding.size(), 12U) << error;
  const std::vector<float> expectedEmbedding = {
      0.1F, 0.2F, 0.3F, 1.1F, 1.2F, 1.3F, 2.1F, 2.2F, 2.3F, 3.1F, 3.2F, 3.3F,
  };
  for (std::size_t i = 0; i < expectedEmbedding.size(); ++i) {
    EXPECT_NEAR(embedding[i], expectedEmbedding[i], 1e-6F);
  }

  const std::vector<float> lmHead = reader->ReadFloat32("lm_head.weight");
  ASSERT_EQ(lmHead.size(), 12U);
  EXPECT_FLOAT_EQ(lmHead[0], 0.5F);
  EXPECT_FLOAT_EQ(lmHead[11], -3.0F);
}

TEST(GgufReaderContractTest, MissingTensorReportsExplicitError) {
  const auto reader = GgufReader::Open(FixtureDir() / "toy_real.gguf");
  ASSERT_TRUE(reader.has_value());
  std::string error;
  const std::vector<float> missing =
      reader->ReadFloat32("does.not.exist", &error);
  EXPECT_TRUE(missing.empty());
  EXPECT_FALSE(error.empty());
}

// Issue #81.13: a fuzz run against ReadFloat32 found that a tensor shape
// whose product overflows size_t (or merely exceeds
// std::vector<float>::max_size() without overflowing) threw an uncaught
// std::length_error, aborting the process instead of returning the usual
// explicit error -- a DoS on adversarial/malformed model files. This locks
// that fix in as a regular unit test, not just something the fuzzer might
// rediscover.
TEST(GgufReaderContractTest,
     OverflowingTensorShapeReportsErrorInsteadOfCrashing) {
  const std::filesystem::path path = WriteTempGguf(
      BuildGgufWithTensorShape({0xFFFFFFFFFFFFFFFFULL, 2ULL}), "overflow");
  std::string openError;
  const auto reader = GgufReader::Open(path, &openError);
  ASSERT_TRUE(reader.has_value()) << openError;

  std::string error;
  const std::vector<float> values =
      reader->ReadFloat32("lm_head.weight", &error);
  EXPECT_TRUE(values.empty());
  EXPECT_FALSE(error.empty());
  std::filesystem::remove(path);
}

TEST(GgufReaderContractTest,
     ExcessivelyLargeTensorShapeReportsErrorInsteadOfCrashing) {
  // Doesn't overflow size_t on its own, but multiplying by sizeof(float)
  // does exceed std::vector<float>::max_size() -- a distinct failure mode
  // from the raw overflow case above.
  const std::filesystem::path path = WriteTempGguf(
      BuildGgufWithTensorShape({0x1FFFFFFFFFFFFFFFULL, 2ULL}), "toolarge");
  std::string openError;
  const auto reader = GgufReader::Open(path, &openError);
  ASSERT_TRUE(reader.has_value()) << openError;

  std::string error;
  const std::vector<float> values =
      reader->ReadFloat32("lm_head.weight", &error);
  EXPECT_TRUE(values.empty());
  EXPECT_FALSE(error.empty());
  std::filesystem::remove(path);
}

} // namespace
} // namespace us4
