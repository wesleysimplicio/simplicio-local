#include "kv/summarizer.h"

namespace us4 {

std::vector<float>
Summarizer::Summarize(const std::vector<float> &values) const {
  if (values.empty()) {
    return {};
  }
  float sum = 0.0F;
  for (const float value : values) {
    sum += value;
  }
  return {sum / static_cast<float>(values.size())};
}

std::vector<float> Summarizer::SummarizeRows(const std::vector<float> &values,
                                             const std::size_t rowWidth) const {
  if (values.empty() || rowWidth == 0 || (values.size() % rowWidth) != 0) {
    return {};
  }

  const std::size_t rowCount = values.size() / rowWidth;
  std::vector<float> summary(rowWidth, 0.0F);
  for (std::size_t row = 0; row < rowCount; ++row) {
    for (std::size_t col = 0; col < rowWidth; ++col) {
      summary[col] += values[row * rowWidth + col];
    }
  }

  for (float &value : summary) {
    value /= static_cast<float>(rowCount);
  }
  return summary;
}

} // namespace us4
