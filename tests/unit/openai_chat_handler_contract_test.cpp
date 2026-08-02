#include <cstdlib>
#include <filesystem>
#include <stop_token>
#include <string>

#include <gtest/gtest.h>

#include "net/openai_chat_handler.h"

namespace us4 {
namespace {

class ScopedRuntimeAdmission {
public:
  ScopedRuntimeAdmission()
      : localInference_(Capture("US4_LOCAL_INFERENCE")),
        runtimePolicy_(Capture("US4_RUNTIME_POLICY")),
        runtimeLease_(Capture("US4_RUNTIME_LEASE")) {
    Set("US4_LOCAL_INFERENCE", "enabled");
    Set("US4_RUNTIME_POLICY", "admitted");
    Set("US4_RUNTIME_LEASE", "contract-test-lease");
  }

  ~ScopedRuntimeAdmission() {
    Restore(localInference_);
    Restore(runtimePolicy_);
    Restore(runtimeLease_);
  }

  ScopedRuntimeAdmission(const ScopedRuntimeAdmission &) = delete;
  ScopedRuntimeAdmission &operator=(const ScopedRuntimeAdmission &) = delete;

private:
  struct SavedValue {
    const char *name;
    bool present;
    std::string value;
  };

  static SavedValue Capture(const char *name) {
    const char *value = std::getenv(name);
    return {.name = name,
            .present = value != nullptr,
            .value = value != nullptr ? value : ""};
  }

  static void Set(const char *name, const char *value) {
#ifdef _WIN32
    (void)::_putenv_s(name, value);
#else
    (void)::setenv(name, value, 1);
#endif
  }

  static void Unset(const char *name) {
#ifdef _WIN32
    (void)::_putenv_s(name, "");
#else
    (void)::unsetenv(name);
#endif
  }

  static void Restore(const SavedValue &saved) {
    if (saved.present) {
      Set(saved.name, saved.value.c_str());
    } else {
      Unset(saved.name);
    }
  }

  SavedValue localInference_;
  SavedValue runtimePolicy_;
  SavedValue runtimeLease_;
};

std::filesystem::path RepoRoot() {
#ifdef US4_SOURCE_DIR
  return std::filesystem::path(US4_SOURCE_DIR);
#else
  return std::filesystem::path(__FILE__)
      .parent_path()
      .parent_path()
      .parent_path();
#endif
}

TEST(OpenAiChatHandlerContractTest, RejectsMalformedJsonBody) {
  std::string error;
  const auto request = ParseChatCompletionRequestBody("not json", &error);
  EXPECT_FALSE(request.has_value());
  EXPECT_FALSE(error.empty());
}

TEST(OpenAiChatHandlerContractTest, RejectsBodyWithoutUserMessage) {
  std::string error;
  const auto request = ParseChatCompletionRequestBody(
      R"({"model":"qwen-0.5b","messages":[]})", &error);
  EXPECT_FALSE(request.has_value());
  EXPECT_FALSE(error.empty());
}

TEST(OpenAiChatHandlerContractTest, ParsesModelPromptAndMaxTokens) {
  std::string error;
  const auto request = ParseChatCompletionRequestBody(
      R"({"model":"qwen-0.5b","max_tokens":5,)"
      R"("messages":[{"role":"system","content":"ignored"},)"
      R"({"role":"user","content":"hello there"}]})",
      &error);
  ASSERT_TRUE(request.has_value()) << error;
  EXPECT_EQ(request->model, "qwen-0.5b");
  EXPECT_EQ(request->prompt, "hello there");
  EXPECT_EQ(request->maxTokens, 5U);
  EXPECT_FALSE(request->stream);
}

TEST(OpenAiChatHandlerContractTest,
     ParsesStreamFlagAndMaxCompletionTokensAlias) {
  std::string error;
  const auto request = ParseChatCompletionRequestBody(
      R"({"model":"qwen-0.5b","max_completion_tokens":7,"stream":true,)"
      R"("messages":[{"role":"user","content":"stream this"}]})",
      &error);
  ASSERT_TRUE(request.has_value()) << error;
  EXPECT_EQ(request->maxTokens, 7U);
  EXPECT_TRUE(request->stream);
}

TEST(OpenAiChatHandlerContractTest, ParsesSeedAndStopSequences) {
  std::string error;
  const auto request = ParseChatCompletionRequestBody(
      R"({"model":"qwen-0.5b","seed":42,"stop":["END","STOP"],)"
      R"("messages":[{"role":"user","content":"seeded"}]})",
      &error);
  ASSERT_TRUE(request.has_value()) << error;
  ASSERT_TRUE(request->seed.has_value());
  EXPECT_EQ(*request->seed, 42U);
  ASSERT_EQ(request->stopSequences.size(), 2U);
  EXPECT_EQ(request->stopSequences[0], "END");
  EXPECT_EQ(request->stopSequences[1], "STOP");
}

TEST(OpenAiChatHandlerContractTest, RejectsInvalidSeedAndStop) {
  std::string error;
  EXPECT_FALSE(ParseChatCompletionRequestBody(
                   R"({"model":"qwen-0.5b","seed":-1,"messages":[])})",
                   &error)
                   .has_value());
  EXPECT_FALSE(ParseChatCompletionRequestBody(
                   R"({"model":"qwen-0.5b","stop":[""],"messages":[])})",
                   &error)
                   .has_value());
}

TEST(OpenAiChatHandlerContractTest, UnknownModelReturnsExplicitError) {
  ChatCompletionRequest request;
  request.model = "does-not-exist";
  request.prompt = "hi";
  const ChatCompletionResponse response = HandleChatCompletion(request);
  EXPECT_FALSE(response.ok);
  EXPECT_FALSE(response.errorMessage.empty());
}

// Issue #81.10: the native handler must answer from this runtime's own
// Generate() pipeline with real weights when a real model_path is given --
// not a canned/mocked response.
TEST(OpenAiChatHandlerContractTest,
     RealModelPathDrivesRealWeightsThroughNativeHandler) {
  // HandleChatCompletion is intentionally fail-closed unless the caller has
  // an explicit Runtime policy admission and lease. Keep this integration
  // test hermetic while exercising the admitted real-weight path.
  const ScopedRuntimeAdmission admission;

  ChatCompletionRequest request;
  request.model = "qwen-0.5b";
  request.prompt = "alpha";
  request.maxTokens = 1;
  request.modelPath = (RepoRoot() / "tests" / "fixtures" / "models" /
                       "toy-dense-real" / "toy-dense-real.safetensors")
                          .string();

  const ChatCompletionResponse response = HandleChatCompletion(request);
  ASSERT_TRUE(response.ok) << response.errorMessage;
  EXPECT_TRUE(response.usedRealWeights);
  EXPECT_EQ(response.promptTokens, 1U);
  EXPECT_EQ(response.completionTokens, 1U);
  EXPECT_GE(response.latencyMs, 0.0);
  EXPECT_GE(response.tokensPerSecond, 0.0);
  // Same external-oracle prediction as the #85 CLI/Playwright evidence:
  // embedding("alpha") one-hot over these real weights argmaxes to "delta".
  EXPECT_EQ(response.content, "delta");

  request.stopSequences = {"lta"};
  const ChatCompletionResponse stopped = HandleChatCompletion(request);
  ASSERT_TRUE(stopped.ok) << stopped.errorMessage;
  EXPECT_EQ(stopped.content, "de");

  const std::string responseJson =
      BuildChatCompletionResponseJson(response, "req-1");
  EXPECT_NE(responseJson.find("\"used_real_weights\":true"), std::string::npos);
  EXPECT_NE(responseJson.find("\"prompt_tokens\":1"), std::string::npos);
  EXPECT_NE(responseJson.find("\"tokens_per_second\""), std::string::npos);
  EXPECT_NE(responseJson.find("simplicio.local-inference-receipt/v1"), std::string::npos);
  EXPECT_NE(responseJson.find("\"content\":\"delta\""), std::string::npos);

  std::stop_source cancelled;
  cancelled.request_stop();
  const ChatCompletionResponse cancelledResponse =
      HandleChatCompletion(request, cancelled.get_token());
  EXPECT_TRUE(cancelledResponse.cancelled);
  EXPECT_FALSE(cancelledResponse.ok);

  const std::string chunkJson =
      BuildChatCompletionChunkJson("req-1", response.modelName, "delta", false);
  EXPECT_NE(chunkJson.find("\"object\":\"chat.completion.chunk\""),
            std::string::npos);
  EXPECT_NE(chunkJson.find("\"content\":\"delta\""), std::string::npos);
  EXPECT_NE(chunkJson.find("\"finish_reason\":null"), std::string::npos);
}

} // namespace
} // namespace us4
