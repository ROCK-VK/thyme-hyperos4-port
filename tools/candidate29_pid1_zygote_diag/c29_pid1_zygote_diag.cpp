#include <android/log.h>
#include <sys/resource.h>
#include <sys/stat.h>
#include <sys/statvfs.h>
#include <sys/system_properties.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#include <algorithm>
#include <string>
#include <vector>

namespace {

constexpr char kTag[] = "C29ZygoteDiag";
constexpr char kDirectory[] = "/metadata/thyme_os4_diag";
constexpr uint64_t kMaxLogcatBytes = 8ULL * 1024 * 1024;
constexpr uint64_t kLogcatReserveBytes = 2ULL * 1024 * 1024;
constexpr uint64_t kMinLogcatBytes = 256ULL * 1024;
constexpr uint64_t kMaxEventBytes = 512ULL * 1024;
constexpr int64_t kLogcatDurationMs = 60 * 1000;
constexpr int64_t kWatchDurationMs = 60 * 1000;
constexpr int64_t kPollIntervalMs = 10;
constexpr int64_t kProcScanIntervalMs = 100;

int g_event_fd = -1;
std::string g_boot_id;
std::string g_event_path;

int64_t BootTimeMs() {
  timespec ts{};
  if (clock_gettime(CLOCK_BOOTTIME, &ts) != 0) return -1;
  return static_cast<int64_t>(ts.tv_sec) * 1000 + ts.tv_nsec / 1000000;
}

std::string Clean(std::string value, size_t limit = 512) {
  for (char& ch : value) {
    if (ch == '\0' || ch == '\n' || ch == '\r' || ch == '\t' || ch == ' ') ch = '_';
  }
  if (value.size() > limit) value.resize(limit);
  return value.empty() ? "<empty>" : value;
}

std::string ReadSmallFile(const std::string& path, size_t limit = 4096) {
  int fd = open(path.c_str(), O_RDONLY | O_CLOEXEC);
  if (fd < 0) return "<open_errno=" + std::to_string(errno) + ">";
  std::string result;
  char buffer[1024];
  while (result.size() < limit) {
    const size_t want = std::min(sizeof(buffer), limit - result.size());
    const ssize_t count = read(fd, buffer, want);
    if (count > 0) result.append(buffer, static_cast<size_t>(count));
    else if (count < 0 && errno == EINTR) continue;
    else break;
  }
  close(fd);
  while (!result.empty() && (result.back() == '\n' || result.back() == '\r' || result.back() == '\0')) {
    result.pop_back();
  }
  return result;
}

std::string BootId() {
  std::string id = ReadSmallFile("/proc/sys/kernel/random/boot_id", 128);
  if (id.empty() || id[0] == '<') return "unknown";
  return Clean(id, 64);
}

std::string GetProperty(const char* key) {
  char value[PROP_VALUE_MAX] = {};
  const int length = __system_property_get(key, value);
  if (length <= 0) return "<unset>";
  return Clean(std::string(value, static_cast<size_t>(length)), 256);
}

bool WriteAll(int fd, const char* data, size_t length) {
  size_t offset = 0;
  while (offset < length) {
    const ssize_t written = write(fd, data + offset, length - offset);
    if (written > 0) offset += static_cast<size_t>(written);
    else if (written < 0 && errno == EINTR) continue;
    else return false;
  }
  return true;
}

bool WriteSync(int fd, const std::string& line) {
  return WriteAll(fd, line.data(), line.size()) && fdatasync(fd) == 0;
}

void SyncDirectory() {
  const int fd = open(kDirectory, O_RDONLY | O_DIRECTORY | O_CLOEXEC);
  if (fd >= 0) {
    (void)fsync(fd);
    close(fd);
  }
}

bool EnsureEvents() {
  if (g_event_fd >= 0) return true;
  g_boot_id = BootId();
  g_event_path = std::string(kDirectory) + "/C29_events_" + g_boot_id + ".log";
  g_event_fd = open(g_event_path.c_str(), O_WRONLY | O_CREAT | O_APPEND | O_CLOEXEC, 0660);
  if (g_event_fd < 0) return false;
  (void)fchmod(g_event_fd, 0660);
  SyncDirectory();
  return true;
}

bool Event(const char* event, const std::string& detail) {
  if (!EnsureEvents()) {
    __android_log_print(ANDROID_LOG_ERROR, kTag, "event file open failed errno=%d", errno);
    return false;
  }
  struct stat st{};
  if (fstat(g_event_fd, &st) != 0 || st.st_size < 0 ||
      static_cast<uint64_t>(st.st_size) >= kMaxEventBytes) {
    __android_log_write(ANDROID_LOG_ERROR, kTag, "event file limit or stat error");
    return false;
  }
  std::string line = "boottime_ms=" + std::to_string(BootTimeMs()) +
      " boot_id=" + g_boot_id + " event=" + Clean(event, 64) +
      " pid=" + std::to_string(getpid());
  if (!detail.empty()) line += " " + detail;
  line.push_back('\n');
  const bool ok = WriteSync(g_event_fd, line);
  if (!ok) __android_log_print(ANDROID_LOG_ERROR, kTag, "event write/sync failed errno=%d", errno);
  return ok;
}

bool OpenUnique(const char* prefix, const char* suffix, char* path, size_t path_size) {
  if (g_boot_id.empty()) g_boot_id = BootId();
  const int64_t uptime = BootTimeMs();
  const int length = snprintf(path, path_size, "%s/%s_%s_u%lld_p%d.%s", kDirectory, prefix,
                              g_boot_id.c_str(), static_cast<long long>(uptime), getpid(), suffix);
  if (length <= 0 || static_cast<size_t>(length) >= path_size) {
    errno = ENAMETOOLONG;
    return false;
  }
  return true;
}

int OpenUniqueFile(const char* prefix, const char* suffix, char* path, size_t path_size) {
  if (!OpenUnique(prefix, suffix, path, path_size)) return -1;
  const int fd = open(path, O_WRONLY | O_CREAT | O_EXCL | O_APPEND | O_CLOEXEC, 0660);
  if (fd < 0) return -1;
  (void)fchmod(fd, 0660);
  SyncDirectory();
  return fd;
}

std::string ServicePid(const char* service) {
  const std::string property = std::string("init.svc_debug_pid.") + service;
  return GetProperty(property.c_str());
}

struct WatchedProperty {
  const char* key;
  const char* service;
  const char* kind;
  std::string previous;
};

void RecordProperty(WatchedProperty* item, const std::string& current, bool initial) {
  if (current == item->previous && !initial) return;
  item->previous = current;
  std::string detail = std::string("service=") + item->service + " kind=" + item->kind +
      " value=" + current;
  if (strcmp(item->kind, "state") == 0) {
    detail += " service_pid=" + ServicePid(item->service);
  }
  (void)Event(initial ? "initial_property" : "property_change", detail);
}

void ScanSystemServer(bool* seen, pid_t* last_pid) {
  DIR* proc = opendir("/proc");
  if (proc == nullptr) return;
  dirent* entry;
  while ((entry = readdir(proc)) != nullptr) {
    char* end = nullptr;
    const long parsed = strtol(entry->d_name, &end, 10);
    if (end == entry->d_name || *end != '\0' || parsed <= 0 || parsed > INT_MAX) continue;
    const pid_t pid = static_cast<pid_t>(parsed);
    const std::string cmdline = ReadSmallFile("/proc/" + std::to_string(pid) + "/cmdline", 1024);
    if (cmdline.find("system_server") == std::string::npos) continue;
    if (!*seen) {
      *seen = true;
      *last_pid = pid;
      (void)Event("process_first_seen", "service=system_server process_pid=" + std::to_string(pid));
    } else if (*last_pid != pid) {
      *last_pid = pid;
      (void)Event("process_pid_change", "service=system_server process_pid=" + std::to_string(pid));
    }
  }
  closedir(proc);
}

int WatchServices() {
  if (!EnsureEvents()) return 1;
  (void)Event("watcher_start", "service=c29_zygote_watch state=running boot_instance=" + g_boot_id);
  std::vector<WatchedProperty> properties = {
      {"init.svc.netd", "netd", "state", ""},
      {"init.svc.zygote", "zygote", "state", ""},
      {"init.svc.zygote_secondary", "zygote_secondary", "state", ""},
      {"init.svc.c29_logcat", "c29_logcat", "state", ""},
      {"init.svc_debug_pid.zygote", "zygote", "pid", ""},
      {"init.svc_debug_pid.zygote_secondary", "zygote_secondary", "pid", ""},
      {"sys.boot_completed", "system", "boot_completed", ""},
      {"sys.powerctl", "system", "powerctl", ""},
  };
  for (auto& item : properties) RecordProperty(&item, GetProperty(item.key), true);

  bool system_server_seen = false;
  pid_t system_server_pid = -1;
  int64_t next_proc_scan = BootTimeMs();
  const int64_t deadline = BootTimeMs() + kWatchDurationMs;
  while (BootTimeMs() >= 0 && BootTimeMs() < deadline) {
    for (auto& item : properties) RecordProperty(&item, GetProperty(item.key), false);
    const int64_t now = BootTimeMs();
    if (now >= next_proc_scan) {
      ScanSystemServer(&system_server_seen, &system_server_pid);
      next_proc_scan = now + kProcScanIntervalMs;
    }
    timespec delay{0, static_cast<long>(kPollIntervalMs * 1000000)};
    while (nanosleep(&delay, &delay) != 0 && errno == EINTR) {}
  }
  (void)Event("watcher_exit", "service=c29_zygote_watch state=complete duration_ms=" +
              std::to_string(kWatchDurationMs));
  if (g_event_fd >= 0) close(g_event_fd);
  g_event_fd = -1;
  return 0;
}

bool Status(int fd, const std::string& text) {
  return WriteSync(fd, text);
}

uint64_t LogFileSize(const char* path) {
  struct stat st{};
  if (stat(path, &st) != 0 || st.st_size < 0) return 0;
  return static_cast<uint64_t>(st.st_size);
}

int RunLogcat() {
  char status_path[PATH_MAX] = {};
  const int status_fd = OpenUniqueFile("C29_logcat_status", "txt", status_path,
                                       sizeof(status_path));
  if (status_fd < 0) {
    __android_log_print(ANDROID_LOG_ERROR, kTag, "status file open failed errno=%d", errno);
    return 1;
  }
  const int64_t start_ms = BootTimeMs();
  const std::string start = "C29_LOGCAT_START boot_id=" + BootId() +
      " boottime_ms=" + std::to_string(start_ms) + " helper_pid=" +
      std::to_string(getpid()) + " command=/system/bin/logcat -b all -v threadtime,monotonic\n";
  if (!Status(status_fd, start)) {
    const int saved = errno;
    close(status_fd);
    __android_log_print(ANDROID_LOG_ERROR, kTag, "START sync failed errno=%d", saved);
    return 1;
  }
  (void)Event("logger_start", "service=c29_logcat helper_pid=" + std::to_string(getpid()));

  struct statvfs space{};
  if (statvfs(kDirectory, &space) != 0) {
    const int saved = errno;
    (void)Status(status_fd, "C29_LOGCAT_END reason=statvfs_error errno=" +
                 std::to_string(saved) + "\n");
    close(status_fd);
    return 1;
  }
  const uint64_t available = static_cast<uint64_t>(space.f_bavail) * space.f_frsize;
  const uint64_t available_for_logcat =
      available > kLogcatReserveBytes ? available - kLogcatReserveBytes : uint64_t{0};
  const uint64_t cap = std::min<uint64_t>(kMaxLogcatBytes, available_for_logcat);
  if (cap < kMinLogcatBytes) {
    (void)Status(status_fd, "C29_LOGCAT_END reason=insufficient_space available=" +
                 std::to_string(available) + " cap=" + std::to_string(cap) + "\n");
    (void)Event("logger_exit", "service=c29_logcat reason=insufficient_space");
    close(status_fd);
    return 1;
  }

  char log_path[PATH_MAX] = {};
  const int log_reserve_fd = OpenUniqueFile("C29_logcat", "txt", log_path, sizeof(log_path));
  if (log_reserve_fd < 0) {
    const int saved = errno;
    (void)Status(status_fd, "C29_LOGCAT_END reason=log_file_open_error errno=" +
                 std::to_string(saved) + "\n");
    (void)Event("logger_exit", "service=c29_logcat reason=log_file_open_error errno=" +
                std::to_string(saved));
    close(status_fd);
    return 1;
  }
  close(log_reserve_fd);

  int gate[2] = {-1, -1};
  int exec_pipe[2] = {-1, -1};
  if (pipe(gate) != 0 || pipe(exec_pipe) != 0) {
    const int saved = errno;
    if (gate[0] >= 0) { close(gate[0]); close(gate[1]); }
    if (exec_pipe[0] >= 0) { close(exec_pipe[0]); close(exec_pipe[1]); }
    (void)Status(status_fd, "C29_LOGCAT_END reason=pipe_error errno=" +
                 std::to_string(saved) + "\n");
    close(status_fd);
    return 1;
  }
  (void)fcntl(exec_pipe[1], F_SETFD, FD_CLOEXEC);
  const pid_t child = fork();
  if (child < 0) {
    const int saved = errno;
    for (int fd : {gate[0], gate[1], exec_pipe[0], exec_pipe[1]}) close(fd);
    (void)Status(status_fd, "C29_LOGCAT_END reason=fork_error errno=" +
                 std::to_string(saved) + "\n");
    close(status_fd);
    return 1;
  }
  if (child == 0) {
    close(gate[1]);
    close(exec_pipe[0]);
    char release = 0;
    ssize_t got;
    do { got = read(gate[0], &release, 1); } while (got < 0 && errno == EINTR);
    close(gate[0]);
    if (got != 1 || release != 'G') _exit(125);
    const rlim_t limit = static_cast<rlim_t>(cap);
    const rlimit file_limit{limit, limit};
    if (setrlimit(RLIMIT_FSIZE, &file_limit) != 0) {
      const int saved = errno;
      (void)WriteAll(exec_pipe[1], reinterpret_cast<const char*>(&saved), sizeof(saved));
      _exit(126);
    }
    execl("/system/bin/logcat", "logcat", "-b", "all", "-v", "threadtime,monotonic",
          "-f", log_path, static_cast<char*>(nullptr));
    const int saved = errno;
    (void)WriteAll(exec_pipe[1], reinterpret_cast<const char*>(&saved), sizeof(saved));
    _exit(127);
  }
  close(gate[0]);
  close(exec_pipe[1]);
  const std::string child_record = "C29_LOGCAT_CHILD child_pid=" + std::to_string(child) +
      " helper_pid=" + std::to_string(getpid()) + " cap=" + std::to_string(cap) +
      " log_path=" + log_path + "\n";
  (void)Status(status_fd, child_record);
  (void)Event("logger_child", "service=c29_logcat child_pid=" + std::to_string(child));
  const char release = 'G';
  if (!WriteAll(gate[1], &release, 1)) {
    const int saved = errno;
    close(gate[1]);
    close(exec_pipe[0]);
    (void)kill(child, SIGKILL);
    int ignored = 0;
    while (waitpid(child, &ignored, 0) < 0 && errno == EINTR) {}
    (void)Status(status_fd, "C29_LOGCAT_END reason=launch_gate_error errno=" +
                 std::to_string(saved) + "\n");
    close(status_fd);
    return 1;
  }
  close(gate[1]);

  int exec_errno = 0;
  ssize_t exec_result;
  do { exec_result = read(exec_pipe[0], &exec_errno, sizeof(exec_errno)); }
  while (exec_result < 0 && errno == EINTR);
  const int exec_read_errno = exec_result < 0 ? errno : 0;
  close(exec_pipe[0]);
  const bool exec_failed = exec_result == static_cast<ssize_t>(sizeof(exec_errno));
  if (exec_failed) {
    (void)Status(status_fd, "C29_LOGCAT_EXEC_FAILED errno=" + std::to_string(exec_errno) +
                 " child_pid=" + std::to_string(child) + "\n");
  } else if (exec_result == 0) {
    (void)Status(status_fd, "C29_LOGCAT_EXEC_OK child_pid=" + std::to_string(child) + "\n");
  } else {
    (void)Status(status_fd, "C29_LOGCAT_EXEC_PIPE_ERROR errno=" +
                 std::to_string(exec_read_errno) + " child_pid=" + std::to_string(child) + "\n");
  }

  int wait_status = 0;
  bool wait_valid = false;
  int wait_errno = 0;
  const int64_t deadline = BootTimeMs() + kLogcatDurationMs;
  while (BootTimeMs() >= 0 && BootTimeMs() < deadline) {
    const pid_t waited = waitpid(child, &wait_status, WNOHANG);
    if (waited == child) { wait_valid = true; break; }
    if (waited < 0 && errno != EINTR) { wait_errno = errno; break; }
    timespec delay{0, 100000000};
    while (nanosleep(&delay, &delay) != 0 && errno == EINTR) {}
  }
  std::string stop_reason = "duration_limit";
  if (wait_valid) stop_reason = exec_failed ? "exec_failed" : "child_exit";
  else if (wait_errno != 0) stop_reason = "wait_error";
  if (!wait_valid && wait_errno == 0) {
    (void)kill(child, SIGTERM);
    const int64_t term_deadline = BootTimeMs() + 2000;
    while (BootTimeMs() >= 0 && BootTimeMs() < term_deadline) {
      const pid_t waited = waitpid(child, &wait_status, WNOHANG);
      if (waited == child) { wait_valid = true; break; }
      if (waited < 0 && errno != EINTR) { wait_errno = errno; break; }
      timespec delay{0, 100000000};
      while (nanosleep(&delay, &delay) != 0 && errno == EINTR) {}
    }
    if (!wait_valid && wait_errno == 0) {
      (void)kill(child, SIGKILL);
      while (waitpid(child, &wait_status, 0) < 0) {
        if (errno == EINTR) continue;
        wait_errno = errno;
        break;
      }
      if (wait_errno == 0) wait_valid = true;
      stop_reason = "timeout_kill";
    } else if (wait_valid) {
      stop_reason = "timeout_term";
    }
  }

  int exit_code = -1;
  int signal_number = 0;
  if (wait_valid && WIFEXITED(wait_status)) exit_code = WEXITSTATUS(wait_status);
  if (wait_valid && WIFSIGNALED(wait_status)) signal_number = WTERMSIG(wait_status);
  const uint64_t bytes = LogFileSize(log_path);
  const std::string end = "C29_LOGCAT_END reason=" + stop_reason +
      " boottime_ms=" + std::to_string(BootTimeMs()) + " bytes=" + std::to_string(bytes) +
      " cap=" + std::to_string(cap) + " child_pid=" + std::to_string(child) +
      " wait_status_valid=" + (wait_valid ? "yes" : "no") +
      " exit_code=" + std::to_string(exit_code) + " signal=" + std::to_string(signal_number) +
      " exec_errno=" + std::to_string(exec_errno) + " wait_errno=" +
      std::to_string(wait_errno) + "\n";
  const bool status_ok = Status(status_fd, end);
  (void)Event("logger_exit", "service=c29_logcat reason=" + stop_reason +
              " child_pid=" + std::to_string(child) + " exit_code=" +
              std::to_string(exit_code) + " signal=" + std::to_string(signal_number));
  close(status_fd);
  __android_log_print(ANDROID_LOG_INFO, kTag, "logcat end reason=%s bytes=%llu exit=%d signal=%d status_ok=%s",
                      stop_reason.c_str(), static_cast<unsigned long long>(bytes), exit_code,
                      signal_number, status_ok ? "yes" : "no");
  return status_ok ? 0 : 1;
}

}  // namespace

int main(int argc, char** argv) {
  if (argc != 2) {
    __android_log_write(ANDROID_LOG_ERROR, kTag, "expected --watch or --logcat");
    return 64;
  }
  if (strcmp(argv[1], "--watch") == 0) return WatchServices();
  if (strcmp(argv[1], "--logcat") == 0) return RunLogcat();
  __android_log_write(ANDROID_LOG_ERROR, kTag, "unknown mode");
  return 64;
}
