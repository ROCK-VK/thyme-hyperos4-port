#include <android/log.h>
#include <sys/resource.h>
#include <sys/stat.h>
#include <sys/statvfs.h>
#include <sys/system_properties.h>
#include <sys/types.h>
#include <sys/wait.h>
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

constexpr char kTag[] = "C30Diag";
constexpr char kDirectory[] = "/metadata/thyme_os4_diag";
constexpr uint64_t kMaxLogcatBytes = 8ULL * 1024 * 1024;
constexpr uint64_t kLogcatReserveBytes = 2ULL * 1024 * 1024;
constexpr uint64_t kMinLogcatBytes = 256ULL * 1024;
constexpr int64_t kLogcatDurationMs = 60 * 1000;
constexpr int64_t kWatchDurationMs = 8 * 60 * 1000;
constexpr int64_t kPollIntervalMs = 10;

std::string g_boot_id;
std::string g_event_path;
int g_event_fd = -1;
bool g_event_failed = false;

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

bool WriteAll(int fd, const char* data, size_t length, size_t* written_total = nullptr) {
  size_t offset = 0;
  while (offset < length) {
    const ssize_t written = write(fd, data + offset, length - offset);
    if (written > 0) offset += static_cast<size_t>(written);
    else if (written < 0 && errno == EINTR) continue;
    else {
      if (written == 0) errno = EIO;
      if (written_total != nullptr) *written_total = offset;
      return false;
    }
  }
  if (written_total != nullptr) *written_total = offset;
  return true;
}

bool AppendSync(int fd, const std::string& line) {
  if (!WriteAll(fd, line.data(), line.size())) return false;
  return fdatasync(fd) == 0;
}

std::string UniquePath(const char* prefix, const char* suffix) {
  if (g_boot_id.empty()) g_boot_id = BootId();
  return std::string(kDirectory) + "/" + prefix + "_" + g_boot_id + "." + suffix;
}

int OpenUnique(const char* prefix, const char* suffix, std::string* path,
               int flags = O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC) {
  *path = UniquePath(prefix, suffix);
  const int fd = open(path->c_str(), flags, 0660);
  if (fd < 0) return -1;
  if (fchmod(fd, 0660) != 0) {
    const int saved = errno;
    close(fd);
    errno = saved;
    return -1;
  }
  return fd;
}

bool CanaryWrite(const char* name, bool sync_data) {
  std::string path;
  const int fd = OpenUnique(name, "txt", &path);
  if (fd < 0) {
    const int saved = errno;
    __android_log_print(ANDROID_LOG_ERROR, kTag,
        "canary=%s stage=open result=fail errno=%d path=%s", name, saved, path.c_str());
    return false;
  }
  const std::string body = "boot_id=" + g_boot_id + " boottime_ms=" +
      std::to_string(BootTimeMs()) + " pid=" + std::to_string(getpid()) + "\n";
  size_t written = 0;
  const bool write_ok = WriteAll(fd, body.data(), body.size(), &written);
  const int write_errno = write_ok ? 0 : errno;
  bool sync_ok = true;
  int sync_errno = 0;
  if (write_ok && sync_data && fdatasync(fd) != 0) {
    sync_ok = false;
    sync_errno = errno;
  }
  const int close_rc = close(fd);
  const int close_errno = close_rc == 0 ? 0 : errno;
  __android_log_print(write_ok && sync_ok && close_rc == 0 ? ANDROID_LOG_INFO : ANDROID_LOG_ERROR,
      kTag, "canary=%s stage=write result=%s bytes=%zu/%zu write_errno=%d fdatasync=%s sync_errno=%d close_errno=%d",
      name, write_ok ? "ok" : "fail", written, body.size(), write_errno,
      sync_data ? (sync_ok ? "ok" : "fail") : "not_requested", sync_errno, close_errno);
  return write_ok && sync_ok && close_rc == 0;
}

bool CanaryAppend() {
  std::string path;
  const int create_fd = OpenUnique("C30_CANARY_APPEND", "txt", &path);
  if (create_fd < 0) {
    const int saved = errno;
    __android_log_print(ANDROID_LOG_ERROR, kTag,
        "canary=append stage=create_open result=fail errno=%d path=%s", saved, path.c_str());
    return false;
  }
  const std::string first = "stage=create boot_id=" + g_boot_id + " boottime_ms=" +
      std::to_string(BootTimeMs()) + " pid=" + std::to_string(getpid()) + "\n";
  size_t first_written = 0;
  bool ok = WriteAll(create_fd, first.data(), first.size(), &first_written);
  const int first_write_errno = ok ? 0 : errno;
  int first_sync_errno = 0;
  if (ok && fdatasync(create_fd) != 0) { ok = false; first_sync_errno = errno; }
  const int first_close = close(create_fd);
  const int first_close_errno = first_close == 0 ? 0 : errno;
  __android_log_print(ok && first_close == 0 ? ANDROID_LOG_INFO : ANDROID_LOG_ERROR,
      kTag, "canary=append stage=initial_write_fdatasync result=%s bytes=%zu/%zu write_errno=%d sync_errno=%d close_errno=%d",
      ok && first_close == 0 ? "ok" : "fail", first_written, first.size(),
      first_write_errno, first_sync_errno, first_close_errno);
  if (!ok || first_close != 0) return false;

  const int append_fd = open(path.c_str(), O_WRONLY | O_APPEND | O_CLOEXEC);
  if (append_fd < 0) {
    const int saved = errno;
    __android_log_print(ANDROID_LOG_ERROR, kTag,
        "canary=append stage=append_open result=fail errno=%d", saved);
    return false;
  }
  const std::string second = "stage=append boot_id=" + g_boot_id + " boottime_ms=" +
      std::to_string(BootTimeMs()) + " pid=" + std::to_string(getpid()) + "\n";
  size_t second_written = 0;
  ok = WriteAll(append_fd, second.data(), second.size(), &second_written);
  const int second_write_errno = ok ? 0 : errno;
  int second_sync_errno = 0;
  if (ok && fdatasync(append_fd) != 0) { ok = false; second_sync_errno = errno; }
  const int second_close = close(append_fd);
  const int second_close_errno = second_close == 0 ? 0 : errno;
  __android_log_print(ok && second_close == 0 ? ANDROID_LOG_INFO : ANDROID_LOG_ERROR,
      kTag, "canary=append stage=second_line_fdatasync result=%s bytes=%zu/%zu write_errno=%d sync_errno=%d close_errno=%d",
      ok && second_close == 0 ? "ok" : "fail", second_written, second.size(),
      second_write_errno, second_sync_errno, second_close_errno);
  return ok && second_close == 0;
}

bool RunCanaries() {
  g_boot_id = BootId();
  __android_log_print(ANDROID_LOG_INFO, kTag,
      "canaries_begin boot_id=%s boottime_ms=%lld pid=%d", g_boot_id.c_str(),
      static_cast<long long>(BootTimeMs()), getpid());
  if (!CanaryWrite("C30_CANARY_WRITE", false)) return false;
  if (!CanaryWrite("C30_CANARY_FDATASYNC", true)) return false;
  if (!CanaryAppend()) return false;
  __android_log_write(ANDROID_LOG_INFO, kTag, "all three metadata canaries passed; diagnostics may start");
  return true;
}

bool EnsureEventFile() {
  g_event_path = UniquePath("C30_events", "log");
  g_event_fd = open(g_event_path.c_str(), O_WRONLY | O_CREAT | O_EXCL | O_APPEND | O_CLOEXEC, 0660);
  if (g_event_fd < 0) {
    const int saved = errno;
    __android_log_print(ANDROID_LOG_ERROR, kTag,
        "event open failed errno=%d path=%s", saved, g_event_path.c_str());
    return false;
  }
  if (fchmod(g_event_fd, 0660) != 0) {
    const int saved = errno;
    __android_log_print(ANDROID_LOG_ERROR, kTag, "event fchmod failed errno=%d", saved);
    return false;
  }
  return true;
}

bool Event(const char* name, const std::string& detail) {
  if (g_event_fd < 0 || g_event_failed) return false;
  std::string line = "boottime_ms=" + std::to_string(BootTimeMs()) +
      " boot_id=" + g_boot_id + " event=" + Clean(name, 64) +
      " pid=" + std::to_string(getpid());
  if (!detail.empty()) line += " " + detail;
  line.push_back('\n');
  if (!AppendSync(g_event_fd, line)) {
    const int saved = errno;
    g_event_failed = true;
    __android_log_print(ANDROID_LOG_ERROR, kTag,
        "event write/fdatasync failed errno=%d event=%s", saved, name);
    return false;
  }
  return true;
}

struct WatchedProperty {
  const char* key;
  const char* kind;
  std::string previous;
};

void RecordProperty(WatchedProperty* item, bool initial) {
  const std::string current = GetProperty(item->key);
  if (!initial && current == item->previous) return;
  item->previous = current;
  const std::string detail = std::string("kind=") + item->kind +
      " property=" + item->key + " value=" + current;
  (void)Event(initial ? "initial_property" : "property_change", detail);
}

struct Logger {
  pid_t pid = -1;
  int status_fd = -1;
  int log_fd = -1;
  int reader_fd = -1;
  std::string status_path;
  std::string log_path;
  std::string stderr_path;
  std::string pending_line;
  uint64_t cap = 0;
  off_t read_offset = 0;
  int64_t start_ms = 0;
  pid_t system_server_pid = -1;
  bool system_server_seen = false;
  bool active = false;
};

bool ParsePositivePid(const std::string& value, pid_t* pid) {
  if (value.empty()) return false;
  char* end = nullptr;
  errno = 0;
  const long parsed = strtol(value.c_str(), &end, 10);
  if (errno != 0 || end == value.c_str() || *end != '\0' || parsed <= 0 || parsed > INT_MAX) {
    return false;
  }
  *pid = static_cast<pid_t>(parsed);
  return true;
}

std::string Trim(std::string value) {
  const size_t first = value.find_first_not_of(" \t\r\n");
  if (first == std::string::npos) return {};
  const size_t last = value.find_last_not_of(" \t\r\n");
  return value.substr(first, last - first + 1);
}

std::vector<std::string> SplitWhitespace(const std::string& value) {
  std::vector<std::string> parts;
  size_t cursor = 0;
  while (cursor < value.size()) {
    cursor = value.find_first_not_of(" \t\r\n", cursor);
    if (cursor == std::string::npos) break;
    const size_t end = value.find_first_of(" \t\r\n", cursor);
    parts.push_back(value.substr(cursor, end == std::string::npos ? end : end - cursor));
    if (end == std::string::npos) break;
    cursor = end;
  }
  return parts;
}

bool ParseSystemServerPid(const std::string& line, pid_t* pid, const char** source) {
  const size_t start_event = line.find("am_proc_start:");
  if (start_event != std::string::npos && line.find("system_server", start_event) != std::string::npos) {
    const size_t open = line.find('[', start_event);
    const size_t close = open == std::string::npos ? std::string::npos : line.find(']', open + 1);
    if (close != std::string::npos) {
      std::vector<std::string> fields;
      size_t cursor = open + 1;
      while (cursor < close) {
        const size_t comma = line.find(',', cursor);
        const size_t end = comma == std::string::npos || comma > close ? close : comma;
        fields.push_back(Trim(line.substr(cursor, end - cursor)));
        cursor = end + 1;
      }
      if (fields.size() >= 4 && fields[3] == "system_server" &&
          ParsePositivePid(fields[1], pid)) {
        *source = "logcat_am_proc_start";
        return true;
      }
    }
  }

  const std::vector<std::string> fields = SplitWhitespace(line);
  if (fields.size() < 6) return false;
  const size_t pid_index = fields[0].find('-') != std::string::npos ? 2 : 1;
  const size_t tag_index = pid_index + 3;
  if (fields.size() <= tag_index || fields[tag_index] != "SystemServer:") return false;
  if (!ParsePositivePid(fields[pid_index], pid)) return false;
  *source = "logcat_SystemServer_tag";
  return true;
}

void ObserveSystemServerPid(Logger* logger, pid_t pid, const char* source) {
  if (pid <= 0) return;
  if (!logger->system_server_seen) {
    logger->system_server_seen = true;
    logger->system_server_pid = pid;
    (void)Event("system_server_first_seen", "process_pid=" + std::to_string(pid) +
        " source=" + source);
  } else if (logger->system_server_pid != pid) {
    logger->system_server_pid = pid;
    (void)Event("system_server_pid_change", "process_pid=" + std::to_string(pid) +
        " source=" + source);
  }
}

void ConsumeLogcatBytes(Logger* logger, bool final = false) {
  if (logger->reader_fd >= 0) {
    char buffer[8192];
    while (true) {
      const ssize_t count = pread(logger->reader_fd, buffer, sizeof(buffer), logger->read_offset);
      if (count < 0 && errno == EINTR) continue;
      if (count <= 0) break;
      logger->read_offset += count;
      logger->pending_line.append(buffer, static_cast<size_t>(count));
      size_t newline;
      while ((newline = logger->pending_line.find('\n')) != std::string::npos) {
        const std::string line = logger->pending_line.substr(0, newline);
        logger->pending_line.erase(0, newline + 1);
        pid_t pid = -1;
        const char* source = "unknown";
        if (ParseSystemServerPid(line, &pid, &source)) ObserveSystemServerPid(logger, pid, source);
      }
      if (logger->pending_line.size() > 65536) {
        (void)Event("logcat_parser_line_discarded", "reason=overlong bytes=" +
            std::to_string(logger->pending_line.size()));
        logger->pending_line.clear();
      }
    }
  }
  if (final && !logger->pending_line.empty()) {
    pid_t pid = -1;
    const char* source = "unknown";
    if (ParseSystemServerPid(logger->pending_line, &pid, &source)) ObserveSystemServerPid(logger, pid, source);
    logger->pending_line.clear();
  }
}

bool Status(Logger* logger, const std::string& value) {
  if (logger->status_fd < 0) return false;
  if (AppendSync(logger->status_fd, value)) return true;
  const int saved = errno;
  __android_log_print(ANDROID_LOG_ERROR, kTag, "logcat status write/fdatasync failed errno=%d", saved);
  return false;
}

uint64_t FileSizeFd(int fd) {
  struct stat st{};
  if (fd < 0 || fstat(fd, &st) != 0 || st.st_size < 0) return 0;
  return static_cast<uint64_t>(st.st_size);
}

bool StartLogcat(Logger* logger) {
  struct statvfs space{};
  if (statvfs(kDirectory, &space) != 0) {
    __android_log_print(ANDROID_LOG_ERROR, kTag, "logcat statvfs failed errno=%d", errno);
    return false;
  }
  const uint64_t available = static_cast<uint64_t>(space.f_bavail) * space.f_frsize;
  const uint64_t cap = std::min<uint64_t>(kMaxLogcatBytes,
      available > kLogcatReserveBytes ? available - kLogcatReserveBytes : 0);
  if (cap < kMinLogcatBytes) {
    __android_log_print(ANDROID_LOG_ERROR, kTag,
        "logcat skipped for low metadata space available=%llu cap=%llu",
        static_cast<unsigned long long>(available), static_cast<unsigned long long>(cap));
    (void)Event("logcat_skipped", "reason=insufficient_metadata_space available=" +
        std::to_string(available) + " cap=" + std::to_string(cap));
    return false;
  }
  logger->cap = cap;
  logger->status_fd = OpenUnique("C30_logcat_status", "txt", &logger->status_path,
      O_WRONLY | O_CREAT | O_EXCL | O_APPEND | O_CLOEXEC);
  if (logger->status_fd < 0) {
    __android_log_print(ANDROID_LOG_ERROR, kTag, "logcat status open failed errno=%d", errno);
    return false;
  }
  logger->log_fd = OpenUnique("C30_logcat", "txt", &logger->log_path,
      O_WRONLY | O_CREAT | O_EXCL | O_APPEND | O_CLOEXEC);
  if (logger->log_fd < 0) {
    __android_log_print(ANDROID_LOG_ERROR, kTag, "logcat output open failed errno=%d", errno);
    (void)Status(logger, "C30_LOGCAT_END reason=output_open_failed errno=" +
        std::to_string(errno) + "\n");
    return false;
  }
  logger->reader_fd = open(logger->log_path.c_str(), O_RDONLY | O_CLOEXEC);
  if (logger->reader_fd < 0) {
    const int saved = errno;
    (void)Status(logger, "C30_LOGCAT_READER_FAILED errno=" + std::to_string(saved) + "\n");
    __android_log_print(ANDROID_LOG_ERROR, kTag, "logcat parser reader open failed errno=%d", saved);
  }
  const int stderr_fd = OpenUnique("C30_logcat_stderr", "txt", &logger->stderr_path,
      O_WRONLY | O_CREAT | O_EXCL | O_APPEND | O_CLOEXEC);
  if (stderr_fd < 0) {
    __android_log_print(ANDROID_LOG_ERROR, kTag, "logcat stderr open failed errno=%d", errno);
    (void)Status(logger, "C30_LOGCAT_END reason=stderr_open_failed errno=" +
        std::to_string(errno) + "\n");
    return false;
  }
  logger->start_ms = BootTimeMs();
  const std::string start = "C30_LOGCAT_START boot_id=" + g_boot_id +
      " boottime_ms=" + std::to_string(logger->start_ms) +
      " helper_pid=" + std::to_string(getpid()) + " cap=" + std::to_string(cap) +
      " buffers=crash,system,main,events duration_ms=60000 rotation=no\n";
  if (!Status(logger, start)) {
    close(stderr_fd);
    return false;
  }
  int exec_pipe[2] = {-1, -1};
  if (pipe(exec_pipe) != 0) {
    const int saved = errno;
    close(stderr_fd);
    (void)Status(logger, "C30_LOGCAT_END reason=pipe_failed errno=" + std::to_string(saved) + "\n");
    return false;
  }
  (void)fcntl(exec_pipe[1], F_SETFD, FD_CLOEXEC);
  const pid_t child = fork();
  if (child < 0) {
    const int saved = errno;
    close(stderr_fd);
    close(exec_pipe[0]);
    close(exec_pipe[1]);
    (void)Status(logger, "C30_LOGCAT_END reason=fork_failed errno=" + std::to_string(saved) + "\n");
    return false;
  }
  if (child == 0) {
    close(exec_pipe[0]);
    const rlimit file_limit{static_cast<rlim_t>(cap), static_cast<rlim_t>(cap)};
    if (setrlimit(RLIMIT_FSIZE, &file_limit) != 0) {
      const int saved = errno;
      (void)WriteAll(exec_pipe[1], reinterpret_cast<const char*>(&saved), sizeof(saved));
      _exit(126);
    }
    if (dup2(logger->log_fd, STDOUT_FILENO) < 0 || dup2(stderr_fd, STDERR_FILENO) < 0) {
      const int saved = errno;
      (void)WriteAll(exec_pipe[1], reinterpret_cast<const char*>(&saved), sizeof(saved));
      _exit(126);
    }
    close(stderr_fd);
    const int flags = fcntl(logger->log_fd, F_GETFD);
    if (flags >= 0) (void)fcntl(logger->log_fd, F_SETFD, flags & ~FD_CLOEXEC);
    execl("/system/bin/logcat", "logcat", "-b", "crash", "-b", "system", "-b", "main",
        "-b", "events", "-v", "threadtime,monotonic", static_cast<char*>(nullptr));
    const int saved = errno;
    (void)WriteAll(exec_pipe[1], reinterpret_cast<const char*>(&saved), sizeof(saved));
    _exit(127);
  }
  close(stderr_fd);
  close(exec_pipe[1]);
  logger->pid = child;
  logger->active = true;
  const std::string child_line = "C30_LOGCAT_CHILD child_pid=" + std::to_string(child) +
      " helper_pid=" + std::to_string(getpid()) + " output=" + logger->log_path +
      " stderr=" + logger->stderr_path + "\n";
  (void)Status(logger, child_line);
  int exec_errno = 0;
  ssize_t exec_bytes;
  do { exec_bytes = read(exec_pipe[0], &exec_errno, sizeof(exec_errno)); }
  while (exec_bytes < 0 && errno == EINTR);
  const int pipe_errno = exec_bytes < 0 ? errno : 0;
  close(exec_pipe[0]);
  if (exec_bytes == static_cast<ssize_t>(sizeof(exec_errno))) {
    (void)Status(logger, "C30_LOGCAT_EXEC_FAILED errno=" + std::to_string(exec_errno) + "\n");
    __android_log_print(ANDROID_LOG_ERROR, kTag, "logcat exec failed errno=%d", exec_errno);
  } else if (exec_bytes == 0) {
    (void)Status(logger, "C30_LOGCAT_EXEC_OK child_pid=" + std::to_string(child) + "\n");
  } else {
    (void)Status(logger, "C30_LOGCAT_EXEC_PIPE_ERROR errno=" + std::to_string(pipe_errno) + "\n");
  }
  Event("logcat_start", "child_pid=" + std::to_string(child) + " cap=" + std::to_string(cap));
  return true;
}

void FinishLogcat(Logger* logger, const char* reason, bool terminate_child) {
  if (logger->active) {
    int wait_status = 0;
    bool waited = false;
    int wait_errno = 0;
    if (terminate_child) (void)kill(logger->pid, SIGTERM);
    const int64_t deadline = BootTimeMs() + (terminate_child ? 2000 : 100);
    while (BootTimeMs() >= 0 && BootTimeMs() <= deadline) {
      const pid_t result = waitpid(logger->pid, &wait_status, WNOHANG);
      if (result == logger->pid) { waited = true; break; }
      if (result < 0 && errno != EINTR) { wait_errno = errno; break; }
      timespec delay{0, 50000000};
      while (nanosleep(&delay, &delay) != 0 && errno == EINTR) {}
    }
    std::string final_reason = reason;
    if (!waited && terminate_child && wait_errno == 0) {
      (void)kill(logger->pid, SIGKILL);
      while (waitpid(logger->pid, &wait_status, 0) < 0) {
        if (errno == EINTR) continue;
        wait_errno = errno;
        break;
      }
      if (wait_errno == 0) waited = true;
      final_reason = "timeout_kill";
    } else if (waited && terminate_child) {
      final_reason = "timeout_term";
    }
    ConsumeLogcatBytes(logger, true);
    int exit_code = -1;
    int signal_number = 0;
    if (waited && WIFEXITED(wait_status)) exit_code = WEXITSTATUS(wait_status);
    if (waited && WIFSIGNALED(wait_status)) signal_number = WTERMSIG(wait_status);
    const uint64_t bytes = FileSizeFd(logger->log_fd);
    const std::string end = "C30_LOGCAT_END reason=" + final_reason +
        " boottime_ms=" + std::to_string(BootTimeMs()) + " bytes=" + std::to_string(bytes) +
        " cap=" + std::to_string(logger->cap) + " child_pid=" + std::to_string(logger->pid) +
        " wait_status_valid=" + (waited ? "yes" : "no") +
        " exit_code=" + std::to_string(exit_code) + " signal=" + std::to_string(signal_number) +
        " wait_errno=" + std::to_string(wait_errno) + " stderr=" + logger->stderr_path + "\n";
    (void)Status(logger, end);
    if (logger->log_fd >= 0) (void)fdatasync(logger->log_fd);
    close(logger->log_fd);
    logger->log_fd = -1;
    if (logger->reader_fd >= 0) { close(logger->reader_fd); logger->reader_fd = -1; }
    logger->active = false;
    (void)Event("logcat_exit", "reason=" + final_reason + " child_pid=" +
        std::to_string(logger->pid) + " exit_code=" + std::to_string(exit_code) +
        " signal=" + std::to_string(signal_number));
    __android_log_print(ANDROID_LOG_INFO, kTag,
        "logcat stopped reason=%s bytes=%llu exit=%d signal=%d wait_errno=%d",
        final_reason.c_str(), static_cast<unsigned long long>(bytes), exit_code,
        signal_number, wait_errno);
  }
  if (logger->status_fd >= 0) {
    close(logger->status_fd);
    logger->status_fd = -1;
  }
}

void PollLogcat(Logger* logger) {
  if (!logger->active) return;
  ConsumeLogcatBytes(logger);
  int status = 0;
  const pid_t result = waitpid(logger->pid, &status, WNOHANG);
  if (result == logger->pid) {
    // The child is already reaped; record it by temporarily retaining the status.
    ConsumeLogcatBytes(logger, true);
    const int exit_code = WIFEXITED(status) ? WEXITSTATUS(status) : -1;
    const int signal_number = WIFSIGNALED(status) ? WTERMSIG(status) : 0;
    const std::string end = "C30_LOGCAT_END reason=child_exit boottime_ms=" +
        std::to_string(BootTimeMs()) + " bytes=" + std::to_string(FileSizeFd(logger->log_fd)) +
        " cap=" + std::to_string(logger->cap) + " child_pid=" + std::to_string(logger->pid) +
        " wait_status_valid=yes exit_code=" + std::to_string(exit_code) +
        " signal=" + std::to_string(signal_number) + " stderr=" + logger->stderr_path + "\n";
    (void)Status(logger, end);
    if (logger->log_fd >= 0) { (void)fdatasync(logger->log_fd); close(logger->log_fd); logger->log_fd = -1; }
    if (logger->reader_fd >= 0) { close(logger->reader_fd); logger->reader_fd = -1; }
    if (logger->status_fd >= 0) { close(logger->status_fd); logger->status_fd = -1; }
    logger->active = false;
    (void)Event("logcat_exit", "reason=child_exit child_pid=" + std::to_string(logger->pid) +
        " exit_code=" + std::to_string(exit_code) + " signal=" + std::to_string(signal_number));
    __android_log_print(ANDROID_LOG_INFO, kTag,
        "logcat child exit code=%d signal=%d", exit_code, signal_number);
    return;
  }
  if (result < 0 && errno != EINTR) {
    __android_log_print(ANDROID_LOG_ERROR, kTag, "logcat waitpid failed errno=%d", errno);
    FinishLogcat(logger, "wait_error", true);
    return;
  }
  const bool capped = FileSizeFd(logger->log_fd) >= logger->cap;
  const bool timed_out = BootTimeMs() - logger->start_ms >= kLogcatDurationMs;
  if (capped || timed_out) FinishLogcat(logger, capped ? "size_limit" : "duration_limit", true);
}

int WatchServices() {
  if (!RunCanaries()) {
    __android_log_write(ANDROID_LOG_ERROR, kTag,
        "diagnostic stopped before watcher/logcat because a metadata canary failed");
    return 20;
  }
  if (!EnsureEventFile()) return 21;
  if (!Event("watcher_start", "state=running watch_ms=" + std::to_string(kWatchDurationMs))) return 22;

  Logger logger{};
  if (!StartLogcat(&logger)) {
    if (logger.status_fd >= 0) {
      (void)Status(&logger, "C30_LOGCAT_END reason=start_failed\n");
      close(logger.status_fd);
      logger.status_fd = -1;
    }
    if (logger.log_fd >= 0) { close(logger.log_fd); logger.log_fd = -1; }
    __android_log_write(ANDROID_LOG_ERROR, kTag, "persistent logcat could not start; property watcher continues");
    (void)Event("logcat_unavailable", "reason=start_failed");
  }
  std::vector<WatchedProperty> properties = {
      {"init.svc.zygote", "init_service", ""},
      {"init.svc.zygote_secondary", "init_service", ""},
      {"init.svc.netd", "init_service", ""},
      {"sys.boot_completed", "boot_completed", ""},
      {"sys.powerctl", "powerctl", ""},
  };
  for (auto& item : properties) RecordProperty(&item, true);

  const int64_t start = BootTimeMs();
  const int64_t deadline = start + kWatchDurationMs;
  while (BootTimeMs() >= 0 && BootTimeMs() < deadline && !g_event_failed) {
    for (auto& item : properties) RecordProperty(&item, false);
    PollLogcat(&logger);
    timespec delay{0, static_cast<long>(kPollIntervalMs * 1000000)};
    while (nanosleep(&delay, &delay) != 0 && errno == EINTR) {}
  }
  if (logger.active) FinishLogcat(&logger, g_event_failed ? "event_write_failure" : "duration_limit", true);
  ConsumeLogcatBytes(&logger, true);
  if (!logger.system_server_seen) {
    (void)Event("system_server_logcat_observation", "result=not_seen logcat_bytes=" +
        std::to_string(logger.read_offset));
  }
  if (logger.reader_fd >= 0) { close(logger.reader_fd); logger.reader_fd = -1; }
  if (logger.log_fd >= 0) { close(logger.log_fd); logger.log_fd = -1; }
  if (logger.status_fd >= 0) { close(logger.status_fd); logger.status_fd = -1; }
  if (!g_event_failed) (void)Event("watcher_exit", "state=complete elapsed_ms=" +
      std::to_string(BootTimeMs() - start));
  if (g_event_fd >= 0) { close(g_event_fd); g_event_fd = -1; }
  return g_event_failed ? 23 : 0;
}

}  // namespace

int main() {
  __android_log_print(ANDROID_LOG_INFO, kTag,
      "helper_start boot_id=%s boottime_ms=%lld pid=%d", BootId().c_str(),
      static_cast<long long>(BootTimeMs()), getpid());
  return WatchServices();
}
