#include <gtest/gtest.h>

#include <filesystem>
#include <string>

#include "core/backend_selector.h"
#include "core/model_asset.h"
#include "core/runtime_mode.h"

TEST(ErrorPathsContractTest, LoadModelAssetFailsForMissingPath) {
  us4::ModelAsset asset;
  std::string error;
  const std::filesystem::path missing =
      std::filesystem::temp_directory_path() / "us4-does-not-exist.us4manifest";

  EXPECT_FALSE(us4::LoadModelAsset(missing, asset, &error));
  EXPECT_FALSE(error.empty());
}

TEST(ErrorPathsContractTest, ParseBackendTypeRejectsUnknownValue) {
  EXPECT_FALSE(us4::ParseBackendType("nope").has_value());
  EXPECT_FALSE(us4::ParseBackendType("").has_value());
}

TEST(ErrorPathsContractTest, ParseBackendTypeAcceptsCanonicalAliases) {
  EXPECT_EQ(us4::ParseBackendType("scalar"), us4::BackendType::kScalarCpu);
  EXPECT_EQ(us4::ParseBackendType("cpu"), us4::BackendType::kScalarCpu);
  EXPECT_EQ(us4::ParseBackendType("NEON"), us4::BackendType::kNeon);
  EXPECT_EQ(us4::ParseBackendType("metal"), us4::BackendType::kMetal);
  EXPECT_EQ(us4::ParseBackendType("ane"), us4::BackendType::kAne);
}

TEST(ErrorPathsContractTest, ParseRuntimeModeRejectsUnknownValue) {
  EXPECT_FALSE(us4::ParseRuntimeMode("turbo").has_value());
  EXPECT_FALSE(us4::ParseRuntimeMode("").has_value());
}

TEST(ErrorPathsContractTest, ParseRuntimeModeNormalizesSeparatorsAndCase) {
  EXPECT_EQ(us4::ParseRuntimeMode("balanced-plus"),
            us4::RuntimeMode::kBalancedPlus);
  EXPECT_EQ(us4::ParseRuntimeMode("MICRO_PLUS"), us4::RuntimeMode::kMicroPlus);
  EXPECT_EQ(us4::ParseRuntimeMode("Full"), us4::RuntimeMode::kFull);
}
