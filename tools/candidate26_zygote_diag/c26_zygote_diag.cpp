#include <android/log.h>
#include <sys/system_properties.h>

#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#include <algorithm>
#include <string>
#include <vector>

namespace {

constexpr char kTag[] = "C26ZygoteDiag";
constexpr char kDirectory[] = "/metadata/thyme_os4_diag";
constexpr int64_t kWatchDurationMs = 15 * 60 * 1000;
constexpr int64_t kPropertyWaitMs = 2000;
constexpr size_t kEventLimit = 512 * 1024;
constexpr size_t kTailLimit = 1024 * 1024;
constexpr size_t kTailCaptureLimit = 64 * 1024;
constexpr unsigned kMaxTailCaptures = 8;
constexpr int kTailTimeoutMs = 4000;

struct PersistentFile {
  int fd = -1;
  size_t bytes = 0;
  size_t limit = 0;
  bool cap_written = false;
  bool failed = false;
  std::string path;
};

struct PropertyValue {
  const char* key;
  std::string value;
};

PersistentFile g_events;
PersistentFile g_tails;
int64_t g_start_ms = 0;

int64_t BootTimeMs() {
  timespec ts{};
  if (clock_gettime(CLOCK_BOOTTIME, &ts) != 0) return -1;
  return static_cast<int64_t>(ts.tv_sec) * 1000 + ts.tv_nsec / 1000000;
}

std::string UtcStamp() {
  const time_t now = time(nullptr);
  tm utc{};
  if (gmtime_r(&now, &utc) == nullptr) return "epoch-unknown";
  char value[32];
  strftime(value, sizeof(value), "%Y%m%dT%H%M%SZ", &utc);
  return value;
}

std::string Clean(const std::string& input, size_t limit = 2048) {
  std::string out;
  out.reserve(std::min(input.size(), limit));
  for (unsigned char ch : input) {
    if (out.size() >= limit) break;
    if (ch == '\n' || ch == '\r' || ch == '\t' || ch == '\0') {
      out.push_back(' ');
    } else if (ch >= 0x20 && ch != 0x7f) {
      out.push_back(static_cast<char>(ch));
    } else {
      out.push_back('?');
    }
  }
  return out;
}

bool WriteAll(int fd, const char* data, size_t length) {
  size_t offset = 0;
  while (offset < length) {
    const ssize_t written = write(fd, data + offset, length - offset);
    if (written < 0) {
      if (errno == EINTR) continue;
      return false;
    }
    if (written == 0) return false;
    offset += static_cast<size_t>(written);
  }
  return true;
}

bool Append(PersistentFile* file, const std::string& data, bool sync = true) {
  if (file->fd < 0 || file->failed) return false;
  if (data.size() > file->limit - std::min(file->bytes, file->limit)) {
    if (!file->cap_written) {
      const std::string marker = "C26 file_cap_reached limit=" +
                                 std::to_string(file->limit) + "\n";
      const size_t remaining = file->limit - std::min(file->bytes, file->limit);
      if (marker.size() <= remaining && WriteAll(file->fd, marker.data(), marker.size()) &&
          fdatasync(file->fd) == 0) {
        file->bytes += marker.size();
      }
      file->cap_written = true;
    }
    return false;
  }
  if (!WriteAll(file->fd, data.data(), data.size())) {
    file->failed = true;
    return false;
  }
  file->bytes += data.size();
  if (sync && fdatasync(file->fd) != 0) {
    file->failed = true;
    return false;
  }
  return true;
}

bool OpenUnique(PersistentFile* file, const char* stem, size_t limit) {
  struct stat dir_stat{};
  if (lstat(kDirectory, &dir_stat) != 0 || !S_ISDIR(dir_stat.st_mode)) return false;
  const int64_t uptime = BootTimeMs();
  for (unsigned attempt = 0; attempt < 32; ++attempt) {
    char path[384];
    snprintf(path, sizeof(path), "%s/%s_%s_u%lld_p%d_%u.log", kDirectory, stem,
             UtcStamp().c_str(), static_cast<long long>(std::max<int64_t>(uptime, 0)),
             getpid(), attempt);
    const int fd = open(path, O_WRONLY | O_CREAT | O_EXCL | O_APPEND | O_CLOEXEC, 0660);
    if (fd >= 0) {
      (void)fchmod(fd, 0660);
      file->fd = fd;
      file->limit = limit;
      file->path = path;
      struct stat st{};
      if (fstat(fd, &st) == 0) file->bytes = static_cast<size_t>(st.st_size);
      return true;
    }
    if (errno != EEXIST) return false;
  }
  return false;
}

void Event(const std::string& message) {
  const int64_t uptime = BootTimeMs();
  const std::string line = "C26 uptime_ms=" + std::to_string(uptime) +
                           " elapsed_ms=" +
                           std::to_string(uptime >= g_start_ms ? uptime - g_start_ms : 0) +
                           " " + Clean(message) + "\n";
  (void)Append(&g_events, line);
  (void)__android_log_write(ANDROID_LOG_INFO, kTag, line.c_str());
}

std::string GetProperty(const char* key) {
  char value[PROP_VALUE_MAX] = {};
  const int length = __system_property_get(key, value);
  if (length <= 0) return "<unset>";
  return Clean(std::string(value, static_cast<size_t>(length)), 256);
}

std::string ReadSmallFile(const std::string& path, size_t limit) {
  const int fd = open(path.c_str(), O_RDONLY | O_CLOEXEC);
  if (fd < 0) return "<open_errno=" + std::to_string(errno) + ">";
  std::string value;
  char buffer[1024];
  int read_error = 0;
  while (value.size() < limit) {
    const size_t ask = std::min(sizeof(buffer), limit - value.size());
    const ssize_t n = read(fd, buffer, ask);
    if (n < 0 && errno == EINTR) continue;
    if (n < 0) {
      read_error = errno;
      break;
    }
    if (n == 0) break;
    value.append(buffer, static_cast<size_t>(n));
  }
  close(fd);
  if (value.empty() && read_error != 0) {
    return "<empty_or_read_errno=" + std::to_string(read_error) + ">";
  }
  return Clean(value, limit);
}

std::string ZygoteProcSnapshot() {
  DIR* proc = opendir("/proc");
  if (proc == nullptr) return "proc_open_errno=" + std::to_string(errno);
  std::string output;
  unsigned matched = 0;
  unsigned unreadable = 0;
  dirent* entry = nullptr;
  while ((entry = readdir(proc)) != nullptr && matched < 6) {
    char* end = nullptr;
    const long pid = strtol(entry->d_name, &end, 10);
    if (end == entry->d_name || *end != '\0' || pid <= 0) continue;
    const std::string base = "/proc/" + std::to_string(pid);
    const std::string cmdline = ReadSmallFile(base + "/cmdline", 1024);
    if (cmdline.find("app_process") == std::string::npos ||
        cmdline.find("--zygote") == std::string::npos) {
      if (cmdline.find("<open_errno=") != std::string::npos) ++unreadable;
      continue;
    }
    output += " proc_pid=" + std::to_string(pid) + " cmdline=" + cmdline;
    const std::string status = ReadSmallFile(base + "/status", 4096);
    size_t begin = 0;
    while (begin < status.size()) {
      const size_t endline = status.find('\n', begin);
      const std::string line = status.substr(begin, endline == std::string::npos ?
          status.size() - begin : endline - begin);
      if (line.rfind("Name:", 0) == 0 || line.rfind("State:", 0) == 0 ||
          line.rfind("Pid:", 0) == 0 || line.rfind("PPid:", 0) == 0 ||
          line.rfind("VmRSS:", 0) == 0 || line.rfind("Threads:", 0) == 0) {
        output += " status_" + Clean(line, 128);
      }
      if (endline == std::string::npos) break;
      begin = endline + 1;
    }
    ++matched;
  }
  closedir(proc);
  if (matched == 0) output += " proc_zygote_processes=none";
  output += " proc_unreadable=" + std::to_string(unreadable);
  return output;
}

struct CaptureResult {
  std::string output;
  int exit_code = -1;
  int signal = 0;
  int spawn_errno = 0;
  bool timed_out = false;
  bool truncated = false;
};

CaptureResult CaptureLogcatTail() {
  CaptureResult result;
  int pipes[2];
  if (pipe(pipes) != 0) {
    result.spawn_errno = errno;
    return result;
  }
  (void)fcntl(pipes[0], F_SETFD, FD_CLOEXEC);
  (void)fcntl(pipes[1], F_SETFD, FD_CLOEXEC);
  const pid_t child = fork();
  if (child < 0) {
    result.spawn_errno = errno;
    close(pipes[0]);
    close(pipes[1]);
    return result;
  }
  if (child == 0) {
    (void)setpgid(0, 0);
    close(pipes[0]);
    if (dup2(pipes[1], STDOUT_FILENO) < 0 || dup2(pipes[1], STDERR_FILENO) < 0) _exit(126);
    close(pipes[1]);
    execl("/system/bin/logcat", "logcat", "-b", "crash", "-b", "system", "-b", "main",
          "-d", "-t", "80", "-v", "threadtime,monotonic", static_cast<char*>(nullptr));
    dprintf(STDERR_FILENO, "C26 logcat exec failed errno=%d\n", errno);
    _exit(127);
  }
  (void)setpgid(child, child);
  close(pipes[1]);
  const int old_flags = fcntl(pipes[0], F_GETFL, 0);
  if (old_flags >= 0) (void)fcntl(pipes[0], F_SETFL, old_flags | O_NONBLOCK);
  const int64_t deadline = BootTimeMs() + kTailTimeoutMs;
  bool eof = false;
  bool child_done = false;
  int wait_status = 0;
  char buffer[4096];
  while (!eof || !child_done) {
    const int64_t now = BootTimeMs();
    if (now >= deadline) {
      result.timed_out = true;
      (void)kill(-child, SIGKILL);
      (void)kill(child, SIGKILL);
      eof = true;
      close(pipes[0]);
      if (!child_done) {
        while (waitpid(child, &wait_status, 0) < 0 && errno == EINTR) {}
        child_done = true;
      }
      break;
    }
    pollfd pfd{pipes[0], static_cast<short>(POLLIN | POLLHUP | POLLERR), 0};
    const int wait_ms = static_cast<int>(std::max<int64_t>(1, std::min<int64_t>(100, deadline - now)));
    const int poll_rc = poll(&pfd, 1, wait_ms);
    if (poll_rc > 0 && (pfd.revents & (POLLIN | POLLHUP | POLLERR))) {
      for (;;) {
        const ssize_t n = read(pipes[0], buffer, sizeof(buffer));
        if (n > 0) {
          const size_t available = kTailCaptureLimit - std::min(result.output.size(), kTailCaptureLimit);
          const size_t keep = std::min(static_cast<size_t>(n), available);
          result.output.append(buffer, keep);
          if (keep < static_cast<size_t>(n)) {
            result.truncated = true;
            (void)kill(-child, SIGKILL);
            (void)kill(child, SIGKILL);
          }
          continue;
        }
        if (n == 0) eof = true;
        else if (errno != EAGAIN && errno != EWOULDBLOCK && errno != EINTR) eof = true;
        break;
      }
    }
    if (!child_done) {
      const pid_t waited = waitpid(child, &wait_status, WNOHANG);
      if (waited == child) child_done = true;
      else if (waited < 0 && errno != EINTR) {
        result.spawn_errno = errno;
        child_done = true;
      }
    }
  }
  if (!result.timed_out) close(pipes[0]);
  if (child_done && WIFEXITED(wait_status)) result.exit_code = WEXITSTATUS(wait_status);
  else if (child_done && WIFSIGNALED(wait_status)) result.signal = WTERMSIG(wait_status);
  return result;
}

bool StartLogcat() {
  const int64_t uptime = BootTimeMs();
  char path[384];
  snprintf(path, sizeof(path), "%s/C26_logcat_%s_u%lld_p%d.txt", kDirectory,
           UtcStamp().c_str(), static_cast<long long>(std::max<int64_t>(uptime, 0)), getpid());
  char marker_path[384];
  snprintf(marker_path, sizeof(marker_path), "%s/C26_logcat_start_%s_u%lld_p%d.txt", kDirectory,
           UtcStamp().c_str(), static_cast<long long>(std::max<int64_t>(uptime, 0)), getpid());
  const int marker = open(marker_path, O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC, 0660);
  if (marker < 0) {
    __android_log_print(ANDROID_LOG_ERROR, kTag, "logcat marker open failed errno=%d", errno);
    return false;
  }
  (void)fchmod(marker, 0660);
  const std::string header = "C26_LOGCAT_START uptime_ms=" + std::to_string(uptime) +
      " pid=" + std::to_string(getpid()) + " path=" + path +
      " command=/system/bin/logcat -b all -v threadtime,monotonic -r 1024 -n 3\n";
  const bool marker_ok = WriteAll(marker, header.data(), header.size()) && fdatasync(marker) == 0;
  close(marker);
  if (!marker_ok) {
    __android_log_write(ANDROID_LOG_ERROR, kTag, "logcat start marker write failed");
    return false;
  }
  execl("/system/bin/logcat", "logcat", "-b", "all", "-v", "threadtime,monotonic",
        "-f", path, "-r", "1024", "-n", "3", static_cast<char*>(nullptr));
  const int saved_errno = errno;
  __android_log_print(ANDROID_LOG_ERROR, kTag, "logcat exec failed errno=%d", saved_errno);
  return false;
}

std::string PropertySummary(const std::vector<PropertyValue>& values) {
  std::string output;
  for (const PropertyValue& property : values) {
    output += " " + std::string(property.key) + "=" + property.value;
  }
  return output;
}

void CaptureTail(unsigned* tail_count, const char* trigger) {
  if (*tail_count >= kMaxTailCaptures) {
    Event(std::string("TAIL_SKIPPED trigger=") + trigger + " reason=max_captures");
    return;
  }
  ++*tail_count;
  if (g_tails.fd < 0) {
    Event(std::string("TAIL_UNAVAILABLE trigger=") + trigger + " reason=file_open_failed");
    return;
  }
  const std::string begin = "\n===== C26_LOGCAT_TAIL n=" + std::to_string(*tail_count) +
      " uptime_ms=" + std::to_string(BootTimeMs()) + " trigger=" + trigger + " =====\n";
  (void)Append(&g_tails, begin);
  CaptureResult result = CaptureLogcatTail();
  const size_t remaining = kTailLimit - std::min(g_tails.bytes, kTailLimit);
  const size_t keep = std::min(result.output.size(), remaining);
  if (keep != 0) (void)Append(&g_tails, result.output.substr(0, keep));
  const std::string footer = "\nC26_TAIL_RESULT bytes=" + std::to_string(result.output.size()) +
      " kept=" + std::to_string(keep) + " exit=" + std::to_string(result.exit_code) +
      " signal=" + std::to_string(result.signal) + " spawn_errno=" +
      std::to_string(result.spawn_errno) + " timeout=" + (result.timed_out ? "yes" : "no") +
      " truncated=" + (result.truncated || keep < result.output.size() ? "yes" : "no") + "\n";
  (void)Append(&g_tails, footer);
  Event(std::string("TAIL_CAPTURED trigger=") + trigger + " n=" +
        std::to_string(*tail_count) + " output_bytes=" +
        std::to_string(result.output.size()) + " exit=" + std::to_string(result.exit_code) +
        " signal=" + std::to_string(result.signal) + " timeout=" +
        (result.timed_out ? "yes" : "no") + " truncated=" +
        (result.truncated || keep < result.output.size() ? "yes" : "no"));
}

int WatchZygote() {
  g_start_ms = BootTimeMs();
  (void)umask(0007);
  const bool event_ready = OpenUnique(&g_events, "C26_zygote_events", kEventLimit);
  const bool tail_ready = OpenUnique(&g_tails, "C26_zygote_tails", kTailLimit);
  if (!event_ready) __android_log_write(ANDROID_LOG_ERROR, kTag, "event file open failed");
  if (!tail_ready) __android_log_write(ANDROID_LOG_ERROR, kTag, "tail file open failed");
  const int64_t deadline = g_start_ms + kWatchDurationMs;
  std::vector<PropertyValue> properties = {
      {"init.svc.zygote", GetProperty("init.svc.zygote")},
      {"init.svc.zygote_secondary", GetProperty("init.svc.zygote_secondary")},
      {"init.svc.c26_logcat", GetProperty("init.svc.c26_logcat")},
      {"init.svc.c25_bootdiag", GetProperty("init.svc.c25_bootdiag")},
      {"init.svc.netd", GetProperty("init.svc.netd")},
      {"init.svc_debug_pid.zygote", GetProperty("init.svc_debug_pid.zygote")},
      {"init.svc_debug_pid.zygote_secondary", GetProperty("init.svc_debug_pid.zygote_secondary")},
  };
  Event("START build=C26 duration_ms=" + std::to_string(kWatchDurationMs) +
        " event_file=" + (event_ready ? g_events.path : "unavailable") +
        " tail_file=" + (tail_ready ? g_tails.path : "unavailable") +
        PropertySummary(properties));
  unsigned tails = 0;
  unsigned property_changes = 0;
  uint32_t serial = __system_property_area_serial();
  int64_t next_heartbeat = g_start_ms + 60 * 1000;
  while (BootTimeMs() < deadline) {
    timespec timeout{static_cast<time_t>(kPropertyWaitMs / 1000),
                     static_cast<long>((kPropertyWaitMs % 1000) * 1000000)};
    uint32_t new_serial = serial;
    (void)__system_property_wait(nullptr, serial, &new_serial, &timeout);
    serial = new_serial;
    const char* keys[] = {
        "init.svc.zygote", "init.svc.zygote_secondary", "init.svc.c26_logcat",
        "init.svc.c25_bootdiag", "init.svc.netd", "init.svc_debug_pid.zygote",
        "init.svc_debug_pid.zygote_secondary"};
    for (PropertyValue& property : properties) {
      const std::string current = GetProperty(property.key);
      if (current == property.value) continue;
      const std::string previous = property.value;
      property.value = current;
      ++property_changes;
      std::string line = "PROPERTY_CHANGE key=" + std::string(property.key) +
          " old=" + previous + " new=" + current + PropertySummary(properties);
      const bool zygote_key = strcmp(property.key, keys[0]) == 0 || strcmp(property.key, keys[1]) == 0;
      if (zygote_key) line += ZygoteProcSnapshot();
      Event(line);
      if (zygote_key && (current == "restarting" || current == "stopped")) {
        CaptureTail(&tails, property.key);
      }
    }
    const int64_t now = BootTimeMs();
    if (now >= next_heartbeat) {
      Event("HEARTBEAT property_changes=" + std::to_string(property_changes) +
            " tail_captures=" + std::to_string(tails) + PropertySummary(properties));
      next_heartbeat = now + 60 * 1000;
    }
  }
  Event("COMPLETE duration_ms=" + std::to_string(kWatchDurationMs) +
        " property_changes=" + std::to_string(property_changes) +
        " tail_captures=" + std::to_string(tails));
  if (g_events.fd >= 0) close(g_events.fd);
  if (g_tails.fd >= 0) close(g_tails.fd);
  return event_ready ? 0 : 1;
}

}  // namespace

int main(int argc, char** argv) {
  if (argc != 2) {
    __android_log_write(ANDROID_LOG_ERROR, kTag, "expected --watch or --logcat");
    return 64;
  }
  if (strcmp(argv[1], "--watch") == 0) return WatchZygote();
  if (strcmp(argv[1], "--logcat") == 0) return StartLogcat() ? 0 : 1;
  __android_log_write(ANDROID_LOG_ERROR, kTag, "unknown mode");
  return 64;
}
