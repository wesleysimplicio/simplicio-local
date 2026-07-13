#include "net/native_http_server.h"

#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <unistd.h>

#include <cctype>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <sstream>

#include "adapters/adapter_registry.h"
#include "net/openai_chat_handler.h"

namespace us4 {

namespace {

constexpr std::size_t kMaxRequestBytes = 1U << 20; // 1 MiB, plenty for chat.

bool ReadLine(int clientFd, std::string *line) {
  line->clear();
  char ch = '\0';
  while (true) {
    const ssize_t bytesRead = ::read(clientFd, &ch, 1);
    if (bytesRead <= 0) {
      return false;
    }
    if (ch == '\n') {
      if (!line->empty() && line->back() == '\r') {
        line->pop_back();
      }
      return true;
    }
    line->push_back(ch);
    if (line->size() > kMaxRequestBytes) {
      return false;
    }
  }
}

struct ParsedRequest {
  std::string method;
  std::string path;
  std::size_t contentLength = 0;
  std::string body;
};

bool ReadHttpRequest(int clientFd, ParsedRequest *request) {
  std::string requestLine;
  if (!ReadLine(clientFd, &requestLine) || requestLine.empty()) {
    return false;
  }
  std::istringstream requestLineStream(requestLine);
  requestLineStream >> request->method >> request->path;

  std::string headerLine;
  while (ReadLine(clientFd, &headerLine) && !headerLine.empty()) {
    const std::string lowerPrefix = "content-length:";
    std::string lowered = headerLine;
    for (char &ch : lowered) {
      ch = static_cast<char>(std::tolower(static_cast<unsigned char>(ch)));
    }
    if (lowered.rfind(lowerPrefix, 0) == 0) {
      const std::string valueText = headerLine.substr(lowerPrefix.size());
      request->contentLength = static_cast<std::size_t>(
          std::strtoul(valueText.c_str(), nullptr, 10));
    }
  }

  if (request->contentLength > kMaxRequestBytes) {
    return false;
  }
  request->body.resize(request->contentLength);
  std::size_t totalRead = 0;
  while (totalRead < request->contentLength) {
    const ssize_t bytesRead = ::read(clientFd, request->body.data() + totalRead,
                                     request->contentLength - totalRead);
    if (bytesRead <= 0) {
      return false;
    }
    totalRead += static_cast<std::size_t>(bytesRead);
  }
  return true;
}

void WriteHttpResponse(int clientFd, const int statusCode,
                       const std::string &statusText, const std::string &body) {
  std::ostringstream response;
  response << "HTTP/1.1 " << statusCode << " " << statusText << "\r\n"
           << "Content-Type: application/json\r\n"
           << "Content-Length: " << body.size() << "\r\n"
           << "Connection: close\r\n"
           << "\r\n"
           << body;
  const std::string responseText = response.str();
  std::size_t totalWritten = 0;
  while (totalWritten < responseText.size()) {
    const ssize_t bytesWritten =
        ::write(clientFd, responseText.data() + totalWritten,
                responseText.size() - totalWritten);
    if (bytesWritten <= 0) {
      break; // best-effort: client disconnected mid-response.
    }
    totalWritten += static_cast<std::size_t>(bytesWritten);
  }
}

std::string BuildModelsListJson() {
  std::ostringstream json;
  json << "{\"object\":\"list\",\"data\":[";
  bool first = true;
  for (const IUS4V6Adapter *adapter : ListAdapters()) {
    if (!first) {
      json << ",";
    }
    first = false;
    json << "{\"id\":\"" << adapter->ModelName() << "\",\"object\":\"model\"}";
  }
  json << "]}";
  return json.str();
}

void HandleClient(int clientFd, std::size_t requestCounter) {
  ParsedRequest request;
  if (!ReadHttpRequest(clientFd, &request)) {
    WriteHttpResponse(clientFd, 400, "Bad Request",
                      "{\"error\":{\"message\":\"malformed HTTP request\"}}");
    return;
  }

  if (request.method == "GET" && request.path == "/v1/models") {
    WriteHttpResponse(clientFd, 200, "OK", BuildModelsListJson());
    return;
  }

  if (request.method == "POST" && request.path == "/v1/chat/completions") {
    std::string parseError;
    const auto chatRequest =
        ParseChatCompletionRequestBody(request.body, &parseError);
    if (!chatRequest.has_value()) {
      WriteHttpResponse(clientFd, 400, "Bad Request",
                        "{\"error\":{\"message\":\"" + parseError + "\"}}");
      return;
    }
    const ChatCompletionResponse chatResponse =
        HandleChatCompletion(*chatRequest);
    const std::string requestId =
        "us4-native-" + std::to_string(requestCounter);
    const int statusCode = chatResponse.ok ? 200 : 404;
    const std::string statusText = chatResponse.ok ? "OK" : "Not Found";
    WriteHttpResponse(clientFd, statusCode, statusText,
                      BuildChatCompletionResponseJson(chatResponse, requestId));
    return;
  }

  WriteHttpResponse(clientFd, 404, "Not Found",
                    "{\"error\":{\"message\":\"unknown route\"}}");
}

} // namespace

int RunNativeHttpServer(const NativeServeOptions &options) {
  const int listenFd = ::socket(AF_INET, SOCK_STREAM, 0);
  if (listenFd < 0) {
    std::cerr << "us4-cli serve --native: socket() failed\n";
    return 1;
  }

  const int reuseAddr = 1;
  ::setsockopt(listenFd, SOL_SOCKET, SO_REUSEADDR, &reuseAddr,
               sizeof(reuseAddr));

  sockaddr_in address{};
  address.sin_family = AF_INET;
  address.sin_port = htons(static_cast<std::uint16_t>(options.port));
  if (::inet_pton(AF_INET, options.host.c_str(), &address.sin_addr) != 1) {
    std::cerr << "us4-cli serve --native: invalid host '" << options.host
              << "'\n";
    ::close(listenFd);
    return 1;
  }

  if (::bind(listenFd, reinterpret_cast<sockaddr *>(&address),
             sizeof(address)) != 0) {
    std::cerr << "us4-cli serve --native: bind() failed on " << options.host
              << ":" << options.port << "\n";
    ::close(listenFd);
    return 1;
  }

  if (::listen(listenFd, /*backlog=*/16) != 0) {
    std::cerr << "us4-cli serve --native: listen() failed\n";
    ::close(listenFd);
    return 1;
  }

  std::cerr << "us4-cli serve --native: listening on " << options.host << ":"
            << options.port << " (native runtime, no external process)\n";

  std::size_t requestCounter = 0;
  while (true) {
    const int clientFd = ::accept(listenFd, nullptr, nullptr);
    if (clientFd < 0) {
      continue;
    }
    ++requestCounter;
    HandleClient(clientFd, requestCounter);
    ::close(clientFd);
  }
}

} // namespace us4
