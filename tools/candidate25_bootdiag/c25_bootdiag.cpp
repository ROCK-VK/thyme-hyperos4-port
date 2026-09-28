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
#include <cctype>
#include <string>
#include <vector>

namespace {

constexpr char kTag[] = "C25BootDiag";
constexpr char kDirectory[] = "/metadata/thyme_os4_diag";
constexpr size_t kMaxFileBytes = 512 * 1024;
constexpr size_t kMaxDirectoryBytes = 8 * 1024 * 1024;
constexpr int64_t kDurationMs = 15 * 60 * 1000;
constexpr int64_t kSampleIntervalMs = 15 * 1000;
constexpr int64_t kDumpIntervalMs = 60 * 1000;
constexpr int kCommandTimeoutMs = 4000;
constexpr size_t kCommandCaptureLimit = 128 * 1024;
constexpr size_t kMaxLinesPerCommand = 10;
constexpr size_t kMaxLineLength = 200;

int g_fd = -1;
size_t g_file_bytes = 0;
size_t g_file_limit = kMaxFileBytes;
bool g_file_failed = false;
bool g_cap_reported = false;
bool g_cap_logged = false;
int64_t g_start_ms = 0;
unsigned g_sample_count = 0;
unsigned g_dump_count = 0;

int64_t BootTimeMs() {
  timespec ts{};
  if (clock_gettime(CLOCK_BOOTTIME, &ts) != 0) return -1;
  return static_cast<int64_t>(ts.tv_sec) * 1000 + ts.tv_nsec / 1000000;
}

std::string Clean(const std::string& input, size_t max_len = kMaxLineLength) {
  std::string out;
  out.reserve(std::min(input.size(), max_len));
  for (unsigned char ch : input) {
    if (out.size() >= max_len) break;
    if (ch == '\n' || ch == '\r' || ch == '\t') {
      out.push_back(' ');
    } else if (ch >= 0x20 && ch != 0x7f) {
      out.push_back(static_cast<char>(ch));
    } else {
      out.push_back('?');
    }
  }
  return out;
}

bool WriteAll(int fd, const char* data, size_t len) {
  size_t offset = 0;
  while (offset < len) {
    const ssize_t written = write(fd, data + offset, len - offset);
    if (written < 0) {
      if (errno == EINTR) continue;
      return false;
    }
    if (written == 0) return false;
    offset += static_cast<size_t>(written);
  }
  return true;
}

bool WritePersistent(const std::string& line) {
  if (g_fd < 0 || g_file_failed) return false;
  const size_t needed = line.size() + 1;
  const size_t limit = std::min(g_file_limit, kMaxFileBytes);
  if (needed > limit - std::min(g_file_bytes, limit)) {
    const size_t remaining = limit - std::min(g_file_bytes, limit);
    if (!g_cap_reported && remaining >= 48) {
      char cap[96];
      const int length = snprintf(cap, sizeof(cap),
                                  "C25 file_cap_reached bytes_limit=%zu\n", limit);
      if (length > 0 && static_cast<size_t>(length) <= remaining &&
          WriteAll(g_fd, cap, static_cast<size_t>(length)) && fdatasync(g_fd) == 0) {
        g_file_bytes += static_cast<size_t>(length);
      } else {
        g_file_failed = true;
      }
    }
    g_cap_reported = true;
    return false;
  }
  if (!WriteAll(g_fd, line.data(), line.size()) || !WriteAll(g_fd, "\n", 1)) {
    g_file_failed = true;
    return false;
  }
  g_file_bytes += needed;
  if (fdatasync(g_fd) != 0) {
    g_file_failed = true;
    return false;
  }
  return true;
}

std::string WithElapsed(const std::string& message) {
  const int64_t now = BootTimeMs();
  char prefix[80];
  snprintf(prefix, sizeof(prefix), "C25 elapsed_ms=%lld ",
           static_cast<long long>(now >= g_start_ms ? now - g_start_ms : 0));
  return std::string(prefix) + Clean(message, 1400);
}

void Emit(const std::string& message) {
  const std::string line = WithElapsed(message);
  const bool persisted = WritePersistent(line);
  const int log_rc = __android_log_write(ANDROID_LOG_INFO, kTag, line.c_str());
  if (log_rc < 0 && persisted) {
    (void)WritePersistent("C25 logd_write_failed rc=" + std::to_string(log_rc));
  }
  if (!persisted && !g_file_failed && g_fd >= 0 && g_cap_reported && !g_cap_logged) {
    (void)__android_log_write(ANDROID_LOG_WARN, kTag, "persistent_file_cap_reached");
    g_cap_logged = true;
  }
}

std::string UtcStamp() {
  const time_t now = time(nullptr);
  tm tm_utc{};
  if (gmtime_r(&now, &tm_utc) == nullptr) return "epoch-unknown";
  char buffer[32];
  strftime(buffer, sizeof(buffer), "%Y%m%dT%H%M%SZ", &tm_utc);
  return buffer;
}

bool PreparePersistentFile() {
  struct stat dir_stat{};
  if (lstat(kDirectory, &dir_stat) != 0 || !S_ISDIR(dir_stat.st_mode)) {
    __android_log_print(ANDROID_LOG_ERROR, kTag,
                        "persistent_directory_unavailable errno=%d", errno);
    return false;
  }

  DIR* dir = opendir(kDirectory);
  if (dir == nullptr) {
    __android_log_print(ANDROID_LOG_ERROR, kTag,
                        "persistent_directory_open_failed errno=%d", errno);
    return false;
  }
  size_t existing_bytes = 0;
  dirent* entry = nullptr;
  while ((entry = readdir(dir)) != nullptr) {
    if (strncmp(entry->d_name, "C25_bootdiag_", 13) != 0) continue;
    char path[512];
    snprintf(path, sizeof(path), "%s/%s", kDirectory, entry->d_name);
    struct stat st{};
    if (lstat(path, &st) == 0 && S_ISREG(st.st_mode)) {
      const size_t file_bytes = static_cast<size_t>(std::max<off_t>(0, st.st_size));
      if (file_bytes >= kMaxDirectoryBytes - std::min(existing_bytes, kMaxDirectoryBytes)) {
        existing_bytes = kMaxDirectoryBytes;
        break;
      }
      existing_bytes += file_bytes;
    }
  }
  closedir(dir);
  if (existing_bytes >= kMaxDirectoryBytes) {
    __android_log_print(ANDROID_LOG_ERROR, kTag,
                        "persistent_directory_cap_reached existing_bytes=%zu",
                        existing_bytes);
    return false;
  }
  g_file_limit = std::min(kMaxFileBytes, kMaxDirectoryBytes - existing_bytes);
  if (g_file_limit < 1024) {
    __android_log_print(ANDROID_LOG_ERROR, kTag,
                        "persistent_directory_space_too_small remaining_bytes=%zu",
                        g_file_limit);
    return false;
  }

  char path[512];
  snprintf(path, sizeof(path), "%s/C25_bootdiag_%s_%d.log", kDirectory,
           UtcStamp().c_str(), getpid());
  g_fd = open(path, O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC, 0660);
  if (g_fd < 0) {
    __android_log_print(ANDROID_LOG_ERROR, kTag,
                        "persistent_file_open_failed errno=%d path=%s", errno,
                        path);
    return false;
  }
  (void)fchmod(g_fd, 0660);
  struct stat file_stat{};
  if (fstat(g_fd, &file_stat) == 0) g_file_bytes = static_cast<size_t>(file_stat.st_size);
  return true;
}

std::string Property(const char* key) {
  char value[PROP_VALUE_MAX] = {};
  const int length = __system_property_get(key, value);
  if (length <= 0) return "<empty-or-unreadable>";
  return Clean(std::string(value, static_cast<size_t>(length)), 128);
}

struct ProcessTarget {
  const char* name;
  const char* needle;
};

constexpr ProcessTarget kTargets[] = {
    {"system_server", "system_server"},
    {"zygote64", "zygote64"},
    {"surfaceflinger", "surfaceflinger"},
    {"bootanimation", "bootanimation"},
    {"systemui", "com.android.systemui"},
    {"miui_systemui", "com.miui.systemui"},
    {"miui_home", "com.miui.home"},
    {"launcher", "com.miui.launcher"},
    {"setupwizard", "setupwizard"},
    {"provision", "com.android.provision"},
};

std::string ScanPids(int* unreadable, int* errors) {
  *unreadable = 0;
  *errors = 0;
  DIR* proc = opendir("/proc");
  if (proc == nullptr) {
    *errors = errno;
    return "proc-open-failed";
  }
  std::vector<std::vector<int>> pids(sizeof(kTargets) / sizeof(kTargets[0]));
  dirent* entry = nullptr;
  while ((entry = readdir(proc)) != nullptr) {
    char* end = nullptr;
    const long pid = strtol(entry->d_name, &end, 10);
    if (end == entry->d_name || *end != '\0' || pid <= 0) continue;
    char path[64];
    snprintf(path, sizeof(path), "/proc/%ld/cmdline", pid);
    const int fd = open(path, O_RDONLY | O_CLOEXEC);
    if (fd < 0) {
      if (errno == EACCES || errno == EPERM) ++*unreadable;
      else if (errno != ENOENT) ++*errors;
      continue;
    }
    char cmdline[768];
    const ssize_t n = read(fd, cmdline, sizeof(cmdline) - 1);
    const int read_errno = errno;
    close(fd);
    if (n <= 0) {
      if (n < 0 && (read_errno == EACCES || read_errno == EPERM)) ++*unreadable;
      continue;
    }
    for (ssize_t i = 0; i < n; ++i) if (cmdline[i] == '\0') cmdline[i] = ' ';
    cmdline[n] = '\0';
    for (size_t i = 0; i < sizeof(kTargets) / sizeof(kTargets[0]); ++i) {
      if (strstr(cmdline, kTargets[i].needle) != nullptr && pids[i].size() < 8) {
        pids[i].push_back(static_cast<int>(pid));
      }
    }
  }
  closedir(proc);
  std::string output;
  for (size_t i = 0; i < sizeof(kTargets) / sizeof(kTargets[0]); ++i) {
    output += " pid.";
    output += kTargets[i].name;
    output += "=";
    if (pids[i].empty()) {
      output += "none";
    } else {
      for (size_t j = 0; j < pids[i].size(); ++j) {
        if (j) output += ",";
        output += std::to_string(pids[i][j]);
      }
    }
  }
  return output;
}

struct QueryResult {
  std::string output;
  int exit_code = -1;
  int signal = 0;
  int spawn_errno = 0;
  bool timed_out = false;
  bool truncated = false;
};

QueryResult RunCommand(const std::vector<std::string>& args) {
  QueryResult result;
  if (args.empty()) {
    result.spawn_errno = EINVAL;
    return result;
  }
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
    std::vector<char*> argv;
    argv.reserve(args.size() + 1);
    for (const std::string& item : args) argv.push_back(const_cast<char*>(item.c_str()));
    argv.push_back(nullptr);
    execv(argv[0], argv.data());
    dprintf(STDERR_FILENO, "execv failed errno=%d\n", errno);
    _exit(127);
  }
  (void)setpgid(child, child);
  close(pipes[1]);
  const int flags = fcntl(pipes[0], F_GETFL, 0);
  if (flags >= 0) (void)fcntl(pipes[0], F_SETFL, flags | O_NONBLOCK);
  const int64_t deadline = BootTimeMs() + kCommandTimeoutMs;
  bool eof = false;
  bool child_done = false;
  int wait_status = 0;
  char chunk[4096];
  while (!eof || !child_done) {
    const int64_t now = BootTimeMs();
    if (now >= deadline && (!child_done || !eof)) {
      result.timed_out = true;
      (void)kill(-child, SIGKILL);
      (void)kill(child, SIGKILL);
      close(pipes[0]);
      eof = true;
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
        const ssize_t n = read(pipes[0], chunk, sizeof(chunk));
        if (n > 0) {
          const size_t available = kCommandCaptureLimit - std::min(result.output.size(), kCommandCaptureLimit);
          const size_t keep = std::min(static_cast<size_t>(n), available);
          result.output.append(chunk, keep);
          if (keep < static_cast<size_t>(n)) result.truncated = true;
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

bool ContainsAny(const std::string& line, const std::vector<std::string>& needles) {
  std::string lower = line;
  std::transform(lower.begin(), lower.end(), lower.begin(),
                 [](unsigned char ch) { return static_cast<char>(tolower(ch)); });
  for (const std::string& needle : needles) {
    if (lower.find(needle) != std::string::npos) return true;
  }
  return false;
}

void Dump(const char* label, const std::vector<std::string>& args,
          const std::vector<std::string>& filters) {
  std::string command;
  for (const std::string& arg : args) {
    if (!command.empty()) command.push_back(' ');
    command += arg;
  }
  Emit(std::string("DUMP_START label=") + label + " timeout_ms=" +
       std::to_string(kCommandTimeoutMs) + " command=" + command);
  QueryResult result = RunCommand(args);
  int denied = 0;
  int service_not_found = 0;
  unsigned kept = 0;
  size_t begin = 0;
  while (begin < result.output.size()) {
    size_t end = result.output.find('\n', begin);
    if (end == std::string::npos) end = result.output.size();
    const std::string line = result.output.substr(begin, end - begin);
    if (ContainsAny(line, {"permission denied", "permission denial", "avc: denied"})) ++denied;
    if (ContainsAny(line, {"service not found", "can't find service", "cannot find service"})) ++service_not_found;
    if (kept < kMaxLinesPerCommand && ContainsAny(line, filters)) {
      Emit(std::string("DUMP_LINE label=") + label + " text=" + Clean(line));
      ++kept;
    }
    begin = end + 1;
  }
  Emit(std::string("DUMP_RESULT label=") + label +
       " exit=" + std::to_string(result.exit_code) +
       " signal=" + std::to_string(result.signal) +
       " timeout=" + (result.timed_out ? "yes" : "no") +
       " spawn_errno=" + std::to_string(result.spawn_errno) +
       " output_bytes=" + std::to_string(result.output.size()) +
       " truncated=" + (result.truncated ? "yes" : "no") +
       " permission_denied_lines=" + std::to_string(denied) +
       " service_not_found_lines=" + std::to_string(service_not_found) +
       " matched_lines=" + std::to_string(kept));
  ++g_dump_count;
}

void Sample() {
  ++g_sample_count;
  const int64_t up = BootTimeMs();
  std::string record = "SAMPLE n=" + std::to_string(g_sample_count) +
                       " uptime_ms=" + std::to_string(up);
  constexpr const char* kProperties[] = {
      "sys.boot_completed", "service.bootanim.exit", "init.svc.bootanim",
      "init.svc.surfaceflinger", "init.svc.zygote", "init.svc.zygote_secondary",
      "init.svc.vold", "init.svc.netd"};
  for (const char* key : kProperties) record += std::string(" ") + key + "=" + Property(key);
  int unreadable = 0;
  int errors = 0;
  record += ScanPids(&unreadable, &errors);
  record += " pid_scan_unreadable=" + std::to_string(unreadable);
  record += " pid_scan_errors=" + std::to_string(errors);
  Emit(record);
}

void DumpFrameworkAndDisplay() {
  Dump("window", {"/system/bin/dumpsys", "window"},
       {"msystembooted", "mdisplayenabled", "mbootanimationstopped", "mcurrentfocus",
        "mfocusedapp", "mwakefulness", "enablescreen", "screen enabled", "boot animation",
        "error", "exception", "imihwcextension"});
  Dump("activity", {"/system/bin/dumpsys", "activity", "activities"},
       {"mbooted", "mbooting", "msystemready", "mbootcompleted", "topresumedactivity",
        "mresumedactivity", "homeactivity", "setupwizard", "systemui", "boot_completed",
        "error", "exception"});
  Dump("surfaceflinger", {"/system/bin/dumpsys", "SurfaceFlinger"},
       {"display", "active", "physical", "hwc", "present", "fence", "vsync", "power",
        "composition", "bootanimation", "layer", "error", "exception"});
  Dump("display", {"/system/bin/dumpsys", "display"},
       {"displaydeviceinfo", "mstate", "state=", "enabled", "physical", "active",
        "brightness", "error", "exception"});
  Dump("sf_layers", {"/system/bin/dumpsys", "SurfaceFlinger", "--list"},
       {"bootanimation", "boot animation", "error", "not found"});
  Dump("home", {"/system/bin/cmd", "package", "resolve-activity", "--brief", "-a",
                 "android.intent.action.MAIN", "-c", "android.intent.category.HOME"},
       {"activity", "name", "error", "not found", "permission"});
}

void SleepUntil(int64_t target_ms) {
  for (;;) {
    const int64_t now = BootTimeMs();
    if (now < 0 || now >= target_ms) return;
    const int64_t remaining = target_ms - now;
    timespec req{static_cast<time_t>(remaining / 1000),
                 static_cast<long>((remaining % 1000) * 1000000)};
    if (nanosleep(&req, nullptr) == 0 || errno != EINTR) return;
  }
}

}  // namespace

int main() {
  g_start_ms = BootTimeMs();
  (void)umask(0007);
  const bool file_ready = PreparePersistentFile();
  if (!file_ready) {
    __android_log_write(ANDROID_LOG_ERROR, kTag,
                        "C25 persistent file unavailable; continuing logd channel only");
  }
  Emit(std::string("START build=C25 duration_ms=") + std::to_string(kDurationMs) +
       " sample_interval_ms=" + std::to_string(kSampleIntervalMs) +
       " dump_interval_ms=" + std::to_string(kDumpIntervalMs) +
       " file_limit_bytes=" + std::to_string(g_file_limit) +
       " file=" + (file_ready ? "open" : "unavailable"));
  if (g_fd >= 0 && fdatasync(g_fd) != 0) {
    __android_log_write(ANDROID_LOG_ERROR, kTag, "C25 START fdatasync failed");
  }

  int64_t next_sample = BootTimeMs();
  int64_t next_dump = next_sample;
  const int64_t deadline = g_start_ms + kDurationMs;
  while (BootTimeMs() < deadline) {
    int64_t now = BootTimeMs();
    if (now >= next_sample) {
      Sample();
      next_sample = BootTimeMs() + kSampleIntervalMs;
    }
    now = BootTimeMs();
    if (now >= next_dump && now < deadline) {
      DumpFrameworkAndDisplay();
      next_dump = BootTimeMs() + kDumpIntervalMs;
    }
    now = BootTimeMs();
    const int64_t next = std::min(deadline, std::min(next_sample, next_dump));
    if (now < next) SleepUntil(next);
  }

  Emit("COMPLETE uptime_ms=" + std::to_string(BootTimeMs()) +
       " samples=" + std::to_string(g_sample_count) +
       " dumps=" + std::to_string(g_dump_count));
  if (g_fd >= 0) {
    (void)fdatasync(g_fd);
    close(g_fd);
    g_fd = -1;
  }
  return 0;
}
