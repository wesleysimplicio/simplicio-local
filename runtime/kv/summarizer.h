#pragma once

#include <vector>

namespace us4 {

class Summarizer {
public:
  std::vector<float> Summarize(const std::vector<float> &values) const;
  std::vector<float> SummarizeRows(const std::vector<float> &values,
                                   std::size_t rowWidth) const;
};

} // namespace us4
