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
#include <sys/statvfs.h>
#include <sys/resource.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#include <algorithm>
#include <string>
#include <vector>

namespace {

constexpr char kTag[] = "C28ZygoteDiag";
constexpr char kDirectory[] = "/metadata/thyme_os4_diag";
constexpr int64_t kWatchDurationMs = 8 * 60 * 1000;
constexpr int64_t kPropertyWaitMs = 2000;
constexpr size_t kEventLimit = 512 * 1024;
constexpr size_t kTailLimit = 1024 * 1024;
constexpr size_t kTailCaptureLimit = 64 * 1024;
constexpr unsigned kMaxTailCaptures = 8;
constexpr int kTailTimeoutMs = 4000;
constexpr uint64_t kMaxLogcatBytes = 24ULL * 1024 * 1024;
// Preserve space for the inherited C25 sampler (8 MiB), C28 event/tail files
// (1.5 MiB), and a little filesystem headroom (2.5 MiB).
constexpr uint64_t kLogcatReserveBytes = 12ULL * 1024 * 1024;
constexpr uint64_t kMinLogcatBytes = 256ULL * 1024;
constexpr int64_t kLogcatDurationMs = 8 * 60 * 1000;
constexpr int64_t kLogcatTerminateGraceMs = 2000;
constexpr int64_t kLogcatSyncIntervalMs = 1000;
constexpr uint64_t kLogcatSyncChunkBytes = 128ULL * 1024;
constexpr size_t kStderrCaptureLimit = 32 * 1024;

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

bool PersistRecord(int fd, const std::string& record) {
  return WriteAll(fd, record.data(), record.size()) && fsync(fd) == 0;
}

bool Append(PersistentFile* file, const std::string& data, bool sync = true) {
  if (file->fd < 0 || file->failed) return false;
  if (data.size() > file->limit - std::min(file->bytes, file->limit)) {
    if (!file->cap_written) {
      const std::string marker = "C28 file_cap_reached limit=" +
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
      file->fd = fd;
      file->limit = limit;
      file->path = path;
      return true;
    }
    if (errno != EEXIST) return false;
  }
  return false;
}

void Event(const std::string& message) {
  const int64_t uptime = BootTimeMs();
  const std::string line = "C28 uptime_ms=" + std::to_string(uptime) +
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
    dprintf(STDERR_FILENO, "C28 logcat exec failed errno=%d\n", errno);
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

bool OpenUniqueOutput(const char* stem, char* path, size_t path_size, int* fd) {
  const int64_t uptime = BootTimeMs();
  for (unsigned attempt = 0; attempt < 32; ++attempt) {
    snprintf(path, path_size, "%s/%s_%s_u%lld_p%d_%u.log", kDirectory, stem,
             UtcStamp().c_str(), static_cast<long long>(std::max<int64_t>(uptime, 0)),
             getpid(), attempt);
    const int opened = open(path, O_WRONLY | O_CREAT | O_EXCL | O_APPEND | O_CLOEXEC, 0660);
    if (opened >= 0) {
      *fd = opened;
      return true;
    }
    if (errno != EEXIST) return false;
  }
  errno = EEXIST;
  return false;
}

uint64_t LogcatByteCap(uint64_t* available_bytes, int* statvfs_errno) {
  struct statvfs space{};
  if (statvfs(kDirectory, &space) != 0) {
    *statvfs_errno = errno;
    *available_bytes = 0;
    return 0;
  }
  const uint64_t block_size = static_cast<uint64_t>(space.f_frsize);
  const uint64_t blocks = static_cast<uint64_t>(space.f_bavail);
  *available_bytes = blocks > 0 && block_size > UINT64_MAX / blocks ?
      UINT64_MAX : blocks * block_size;
  *statvfs_errno = 0;
  if (*available_bytes <= kLogcatReserveBytes) return 0;
  return std::min(kMaxLogcatBytes, *available_bytes - kLogcatReserveBytes);
}

bool DrainPipe(int fd, std::string* captured, size_t limit, bool* eof, int* read_errno) {
  char buffer[8192];
  for (;;) {
    const ssize_t count = read(fd, buffer, sizeof(buffer));
    if (count > 0) {
      if (captured != nullptr) {
        const size_t remaining = limit - std::min(captured->size(), limit);
        captured->append(buffer, std::min(static_cast<size_t>(count), remaining));
      }
      continue;
    }
    if (count == 0) {
      *eof = true;
      return true;
    }
    if (errno == EINTR) continue;
    if (errno == EAGAIN || errno == EWOULDBLOCK) return true;
    *read_errno = errno;
    *eof = true;
    return false;
  }
}

bool StartLogcat() {
  const int64_t start_uptime = BootTimeMs();
  char log_path[384]{};
  char status_path[384]{};
  int status_fd = -1;
  if (!OpenUniqueOutput("C28_logcat_status", status_path, sizeof(status_path), &status_fd)) {
    __android_log_print(ANDROID_LOG_ERROR, kTag, "logcat status open failed errno=%d", errno);
    return false;
  }
  // Persist proof that the helper entered before doing statvfs, allocating the
  // child pipes, or forking.  The init-side marker independently records start.
  char start_record[512];
  const int start_length = snprintf(start_record, sizeof(start_record),
      "C28_LOGCAT_START uptime_ms=%lld pid=%d command=/system/bin/logcat -b all -v threadtime,monotonic\n",
      static_cast<long long>(start_uptime), getpid());
  if (start_length <= 0 || static_cast<size_t>(start_length) >= sizeof(start_record) ||
      !WriteAll(status_fd, start_record, static_cast<size_t>(start_length)) || fsync(status_fd) != 0) {
    const int saved_errno = errno;
    close(status_fd);
    __android_log_print(ANDROID_LOG_ERROR, kTag,
                        "logcat immediate START write/fsync failed errno=%d", saved_errno);
    return false;
  }
  uint64_t available_bytes = 0;
  int statvfs_errno = 0;
  const uint64_t byte_cap = LogcatByteCap(&available_bytes, &statvfs_errno);
  std::string status = "C28_LOGCAT_PLAN uptime_ms=" + std::to_string(BootTimeMs()) +
      " byte_cap=" + std::to_string(byte_cap) +
      " max_byte_cap=" + std::to_string(kMaxLogcatBytes) +
      " available_bytes=" + std::to_string(available_bytes) +
      " reserve_bytes=" + std::to_string(kLogcatReserveBytes) +
      " statvfs_errno=" + std::to_string(statvfs_errno) + "\n";
  if (!PersistRecord(status_fd, status)) {
    const int saved_errno = errno;
    close(status_fd);
    __android_log_print(ANDROID_LOG_ERROR, kTag, "logcat plan write/fsync failed errno=%d", saved_errno);
    return false;
  }
  if (statvfs_errno != 0 || byte_cap < kMinLogcatBytes) {
    status = "C28_LOGCAT_END reason=" + std::string(statvfs_errno ? "statvfs_error" : "insufficient_space") +
        " uptime_ms=" + std::to_string(BootTimeMs()) + " bytes=0 exit_code=-1 signal=0\n";
    (void)PersistRecord(status_fd, status);
    close(status_fd);
    __android_log_print(ANDROID_LOG_ERROR, kTag,
                        "logcat not started cap=%llu statvfs_errno=%d",
                        static_cast<unsigned long long>(byte_cap), statvfs_errno);
    return false;
  }
  int log_fd = -1;
  if (!OpenUniqueOutput("C28_logcat", log_path, sizeof(log_path), &log_fd)) {
    const int saved_errno = errno;
    status = "C28_LOGCAT_END reason=log_file_open_error errno=" + std::to_string(saved_errno) +
        " uptime_ms=" + std::to_string(BootTimeMs()) + " bytes=0 exit_code=-1 signal=0\n";
    (void)PersistRecord(status_fd, status);
    close(status_fd);
    return false;
  }
  const std::string header = "C28_LOGCAT_CAPTURE uptime_ms=" + std::to_string(start_uptime) +
      " pid=" + std::to_string(getpid()) + " cap=" + std::to_string(byte_cap) + "\n";
  if (header.size() >= byte_cap || !WriteAll(log_fd, header.data(), header.size()) || fsync(log_fd) != 0) {
    const int saved_errno = errno;
    status = "C28_LOGCAT_END reason=log_header_write_error errno=" + std::to_string(saved_errno) +
        " uptime_ms=" + std::to_string(BootTimeMs()) + " bytes=0 exit_code=-1 signal=0\n";
    (void)PersistRecord(status_fd, status);
    close(log_fd);
    close(status_fd);
    return false;
  }
  uint64_t log_bytes = header.size();
  uint64_t last_synced_bytes = log_bytes;
  int64_t next_sync_uptime = start_uptime + kLogcatSyncIntervalMs;

  int output_pipe[2] = {-1, -1};
  int error_pipe[2] = {-1, -1};
  int exec_pipe[2] = {-1, -1};
  int gate_pipe[2] = {-1, -1};
  if (pipe(output_pipe) != 0) {
    const int saved_errno = errno;
    status = "C28_LOGCAT_END reason=pipe_error errno=" + std::to_string(saved_errno) +
        " uptime_ms=" + std::to_string(BootTimeMs()) + " bytes=" + std::to_string(log_bytes) +
        " exit_code=-1 signal=0\n";
    (void)PersistRecord(status_fd, status);
    close(log_fd);
    close(status_fd);
    return false;
  }
  if (pipe(error_pipe) != 0) {
    const int saved_errno = errno;
    close(output_pipe[0]);
    close(output_pipe[1]);
    status = "C28_LOGCAT_END reason=pipe_error errno=" + std::to_string(saved_errno) +
        " uptime_ms=" + std::to_string(BootTimeMs()) + " bytes=" + std::to_string(log_bytes) +
        " exit_code=-1 signal=0\n";
    (void)PersistRecord(status_fd, status);
    close(log_fd);
    close(status_fd);
    return false;
  }
  if (pipe(exec_pipe) != 0) {
    const int saved_errno = errno;
    for (int fd : {output_pipe[0], output_pipe[1], error_pipe[0], error_pipe[1]}) close(fd);
    status = "C28_LOGCAT_END reason=exec_pipe_error errno=" + std::to_string(saved_errno) +
        " uptime_ms=" + std::to_string(BootTimeMs()) + " bytes=" + std::to_string(log_bytes) +
        " exit_code=-1 signal=0\n";
    (void)PersistRecord(status_fd, status);
    close(log_fd);
    close(status_fd);
    return false;
  }
  if (pipe(gate_pipe) != 0) {
    const int saved_errno = errno;
    for (int fd : {output_pipe[0], output_pipe[1], error_pipe[0], error_pipe[1], exec_pipe[0], exec_pipe[1]}) close(fd);
    status = "C28_LOGCAT_END reason=gate_pipe_error errno=" + std::to_string(saved_errno) +
        " uptime_ms=" + std::to_string(BootTimeMs()) + " bytes=" + std::to_string(log_bytes) +
        " exit_code=-1 signal=0\n";
    (void)PersistRecord(status_fd, status);
    close(log_fd);
    close(status_fd);
    return false;
  }
  for (int fd : {output_pipe[0], output_pipe[1], error_pipe[0], error_pipe[1],
                 exec_pipe[0], exec_pipe[1], gate_pipe[0], gate_pipe[1]}) {
    (void)fcntl(fd, F_SETFD, FD_CLOEXEC);
  }
  const pid_t child = fork();
  if (child < 0) {
    const int saved_errno = errno;
    for (int fd : {output_pipe[0], output_pipe[1], error_pipe[0], error_pipe[1],
                   exec_pipe[0], exec_pipe[1], gate_pipe[0], gate_pipe[1]}) close(fd);
    status = "C28_LOGCAT_END reason=fork_error errno=" + std::to_string(saved_errno) +
        " uptime_ms=" + std::to_string(BootTimeMs()) + " bytes=" + std::to_string(log_bytes) +
        " exit_code=-1 signal=0\n";
    (void)WriteAll(status_fd, status.data(), status.size());
    (void)fsync(status_fd);
    close(log_fd);
    close(status_fd);
    return false;
  }
  if (child == 0) {
    close(output_pipe[0]);
    close(error_pipe[0]);
    close(exec_pipe[0]);
    close(gate_pipe[1]);
    close(log_fd);
    close(status_fd);
    char gate = 0;
    ssize_t gate_read;
    do { gate_read = read(gate_pipe[0], &gate, 1); } while (gate_read < 0 && errno == EINTR);
    close(gate_pipe[0]);
    if (gate_read != 1 || gate != 'G') _exit(125);
    if (dup2(output_pipe[1], STDOUT_FILENO) < 0 || dup2(error_pipe[1], STDERR_FILENO) < 0) {
      const int saved_errno = errno;
      (void)WriteAll(exec_pipe[1], reinterpret_cast<const char*>(&saved_errno), sizeof(saved_errno));
      dprintf(STDERR_FILENO, "C28 logcat setup failed errno=%d\n", saved_errno);
      _exit(126);
    }
    close(output_pipe[1]);
    close(error_pipe[1]);
    execl("/system/bin/logcat", "logcat", "-b", "all", "-v", "threadtime,monotonic",
          static_cast<char*>(nullptr));
    const int saved_errno = errno;
    (void)WriteAll(exec_pipe[1], reinterpret_cast<const char*>(&saved_errno), sizeof(saved_errno));
    dprintf(STDERR_FILENO, "C28 logcat exec failed errno=%d\n", saved_errno);
    _exit(127);
  }
  close(output_pipe[1]);
  close(error_pipe[1]);
  close(exec_pipe[1]);
  close(gate_pipe[0]);
  status = "C28_LOGCAT_CHILD pid=" + std::to_string(child) +
      " parent_pid=" + std::to_string(getpid()) + "\n";
  if (!PersistRecord(status_fd, status)) {
    const int saved_errno = errno;
    close(gate_pipe[1]);
    (void)kill(child, SIGKILL);
    int failed_wait_status = 0;
    while (waitpid(child, &failed_wait_status, 0) < 0 && errno == EINTR) {}
    for (int fd : {output_pipe[0], error_pipe[0], exec_pipe[0]}) close(fd);
    close(log_fd);
    close(status_fd);
    __android_log_print(ANDROID_LOG_ERROR, kTag,
                        "logcat child pid record fsync failed errno=%d", saved_errno);
    return false;
  }
  const char launch = 'G';
  if (!WriteAll(gate_pipe[1], &launch, 1)) {
    const int saved_errno = errno;
    close(gate_pipe[1]);
    (void)kill(child, SIGKILL);
    int failed_wait_status = 0;
    while (waitpid(child, &failed_wait_status, 0) < 0 && errno == EINTR) {}
    for (int fd : {output_pipe[0], error_pipe[0], exec_pipe[0]}) close(fd);
    status = "C28_LOGCAT_END reason=launch_gate_error errno=" + std::to_string(saved_errno) +
        " uptime_ms=" + std::to_string(BootTimeMs()) + " bytes=" + std::to_string(log_bytes) +
        " child_pid=" + std::to_string(child) + " exit_code=-1 signal=0\n";
    (void)PersistRecord(status_fd, status);
    close(log_fd);
    close(status_fd);
    return false;
  }
  close(gate_pipe[1]);
  int exec_errno = 0;
  ssize_t exec_result;
  do { exec_result = read(exec_pipe[0], &exec_errno, sizeof(exec_errno)); }
  while (exec_result < 0 && errno == EINTR);
  close(exec_pipe[0]);
  if (exec_result == static_cast<ssize_t>(sizeof(exec_errno))) {
    status = "C28_LOGCAT_EXEC_FAILED errno=" + std::to_string(exec_errno) +
        " child_pid=" + std::to_string(child) + "\n";
    (void)PersistRecord(status_fd, status);
  } else if (exec_result == 0) {
    status = "C28_LOGCAT_EXEC_PIPE_CLOSED child_pid=" + std::to_string(child) + "\n";
    (void)PersistRecord(status_fd, status);
  } else {
    const int saved_errno = exec_result < 0 ? errno : EIO;
    status = "C28_LOGCAT_EXEC_PIPE_ERROR errno=" + std::to_string(saved_errno) +
        " child_pid=" + std::to_string(child) + "\n";
    (void)PersistRecord(status_fd, status);
  }
  for (int fd : {output_pipe[0], error_pipe[0]}) {
    const int flags = fcntl(fd, F_GETFL, 0);
    if (flags >= 0) (void)fcntl(fd, F_SETFL, flags | O_NONBLOCK);
  }

  bool output_eof = false;
  bool error_eof = false;
  bool child_done = false;
  bool wait_status_valid = false;
  bool stopping = false;
  int wait_status = 0;
  int wait_errno = 0;
  int output_errno = 0;
  bool file_write_failed = false;
  uint64_t error_bytes = 0;
  std::string child_error;
  child_error.reserve(kStderrCaptureLimit);
  std::string stop_reason = "child_exit";
  const int64_t deadline = start_uptime + kLogcatDurationMs;
  int64_t kill_deadline = 0;
  while (!child_done || !output_eof || !error_eof) {
    const int64_t now = BootTimeMs();
    if (!stopping && now >= deadline) {
      stopping = true;
      stop_reason = "timeout";
      kill_deadline = now + kLogcatTerminateGraceMs;
      (void)kill(child, SIGTERM);
    }

    pollfd descriptors[2] = {
        {output_pipe[0], static_cast<short>(POLLIN | POLLHUP | POLLERR), 0},
        {error_pipe[0], static_cast<short>(POLLIN | POLLHUP | POLLERR), 0},
    };
    const int poll_result = poll(descriptors, 2, 100);
    if (poll_result < 0 && errno != EINTR) {
      output_errno = errno;
      stopping = true;
      stop_reason = "poll_error";
      (void)kill(child, SIGKILL);
      close(output_pipe[0]);
      close(error_pipe[0]);
      output_pipe[0] = -1;
      error_pipe[0] = -1;
      output_eof = true;
      error_eof = true;
      while (!child_done) {
        const pid_t waited = waitpid(child, &wait_status, 0);
        if (waited == child) { child_done = true; wait_status_valid = true; }
        else if (waited < 0 && errno == EINTR) continue;
        else { wait_errno = errno; child_done = true; }
      }
      break;
    }
    if (!output_eof && poll_result > 0 && descriptors[0].revents != 0) {
      char buffer[8192];
      for (;;) {
        const ssize_t count = read(output_pipe[0], buffer, sizeof(buffer));
        if (count > 0) {
          const uint64_t remaining = byte_cap - std::min(log_bytes, byte_cap);
          const size_t keep = static_cast<size_t>(std::min<uint64_t>(static_cast<uint64_t>(count), remaining));
          if (keep != 0 && !file_write_failed) {
            if (!WriteAll(log_fd, buffer, keep)) {
              output_errno = errno;
              file_write_failed = true;
              if (!stopping) {
                stopping = true;
                stop_reason = "file_write_error";
                kill_deadline = BootTimeMs() + kLogcatTerminateGraceMs;
                (void)kill(child, SIGTERM);
              }
            } else {
              log_bytes += keep;
            }
          }
          if (keep < static_cast<size_t>(count) || log_bytes >= byte_cap) {
            if (!stopping) {
              stopping = true;
              stop_reason = file_write_failed ? "file_write_error" : "byte_cap";
              kill_deadline = BootTimeMs() + kLogcatTerminateGraceMs;
              (void)kill(child, SIGTERM);
            }
            // Keep draining after the byte cap so the child cannot remain
            // blocked on a full pipe while its exit status is being collected.
            continue;
          }
          continue;
        }
        if (count == 0) { output_eof = true; break; }
        if (errno == EINTR) continue;
        if (errno == EAGAIN || errno == EWOULDBLOCK) break;
        output_errno = errno;
        output_eof = true;
        break;
      }
    }
    if (!error_eof && poll_result > 0 && descriptors[1].revents != 0) {
      const size_t before = child_error.size();
      (void)DrainPipe(error_pipe[0], &child_error, kStderrCaptureLimit, &error_eof, &output_errno);
      error_bytes += child_error.size() - before;
    }
    const int64_t sync_uptime = BootTimeMs();
    if (!file_write_failed && log_bytes > last_synced_bytes &&
        (log_bytes - last_synced_bytes >= kLogcatSyncChunkBytes || sync_uptime >= next_sync_uptime)) {
      if (fdatasync(log_fd) != 0) {
        output_errno = errno;
        file_write_failed = true;
        if (!stopping) {
          stopping = true;
          stop_reason = "file_sync_error";
          kill_deadline = sync_uptime + kLogcatTerminateGraceMs;
          (void)kill(child, SIGTERM);
        }
      } else {
        last_synced_bytes = log_bytes;
        next_sync_uptime = sync_uptime + kLogcatSyncIntervalMs;
      }
    }
    if (!child_done) {
      const pid_t waited = waitpid(child, &wait_status, WNOHANG);
      if (waited == child) { child_done = true; wait_status_valid = true; }
      else if (waited < 0 && errno != EINTR) {
        wait_errno = errno;
        child_done = true;
      }
    }
    if (stopping && !child_done && BootTimeMs() >= kill_deadline) (void)kill(child, SIGKILL);
    if (child_done && output_eof && error_eof) break;
  }
  if (output_pipe[0] >= 0) close(output_pipe[0]);
  if (error_pipe[0] >= 0) close(error_pipe[0]);
  const int64_t end_uptime = BootTimeMs();
  const int exit_code = wait_status_valid && WIFEXITED(wait_status) ? WEXITSTATUS(wait_status) : -1;
  const int signal_number = wait_status_valid && WIFSIGNALED(wait_status) ? WTERMSIG(wait_status) : 0;
  if (stop_reason == "child_exit" && (signal_number == SIGXFSZ || log_bytes >= byte_cap)) {
    stop_reason = "byte_cap";
  }
  if (fdatasync(log_fd) != 0) {
    if (output_errno == 0) output_errno = errno;
    if (stop_reason == "child_exit" || stop_reason == "timeout" || stop_reason == "byte_cap") {
      stop_reason = "final_sync_error";
    }
  }
  close(log_fd);
  status = "C28_LOGCAT_END reason=" + stop_reason + " start_uptime_ms=" +
      std::to_string(start_uptime) + " end_uptime_ms=" + std::to_string(end_uptime) +
      " elapsed_ms=" + std::to_string(std::max<int64_t>(0, end_uptime - start_uptime)) +
      " bytes=" + std::to_string(log_bytes) + " cap=" + std::to_string(byte_cap) +
      " child_exit_code=" + std::to_string(exit_code) + " child_signal=" +
      std::to_string(signal_number) + " wait_status_valid=" +
      (wait_status_valid ? "yes" : "no") + " exec_errno=" + std::to_string(exec_errno) +
      " wait_errno=" + std::to_string(wait_errno) +
      " pipe_errno=" + std::to_string(output_errno) + " stderr_captured=" +
      std::to_string(error_bytes) + " stderr=" + Clean(child_error, kStderrCaptureLimit) + "\n";
  const bool status_ok = PersistRecord(status_fd, status);
  close(status_fd);
  __android_log_print(ANDROID_LOG_INFO, kTag,
                      "logcat ended reason=%s bytes=%llu cap=%llu elapsed_ms=%lld exit=%d signal=%d status_ok=%s",
                      stop_reason.c_str(), static_cast<unsigned long long>(log_bytes),
                      static_cast<unsigned long long>(byte_cap),
                      static_cast<long long>(std::max<int64_t>(0, end_uptime - start_uptime)),
                      exit_code, signal_number, status_ok ? "yes" : "no");
  const bool expected_end = stop_reason == "timeout" || stop_reason == "byte_cap";
  const bool clean_child_end = stop_reason == "child_exit" && exit_code == 0;
  return status_ok && (expected_end || clean_child_end);
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
  const std::string begin = "\n===== C28_LOGCAT_TAIL n=" + std::to_string(*tail_count) +
      " uptime_ms=" + std::to_string(BootTimeMs()) + " trigger=" + trigger + " =====\n";
  (void)Append(&g_tails, begin);
  CaptureResult result = CaptureLogcatTail();
  const size_t remaining = kTailLimit - std::min(g_tails.bytes, kTailLimit);
  const size_t keep = std::min(result.output.size(), remaining);
  if (keep != 0) (void)Append(&g_tails, result.output.substr(0, keep));
  const std::string footer = "\nC28_TAIL_RESULT bytes=" + std::to_string(result.output.size()) +
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
  const bool event_ready = OpenUnique(&g_events, "C28_zygote_events", kEventLimit);
  if (!event_ready) __android_log_write(ANDROID_LOG_ERROR, kTag, "event file open failed");
  if (event_ready) {
    Event("START build=C28 duration_ms=" + std::to_string(kWatchDurationMs) +
          " event_file=" + g_events.path + " initial_properties=deferred");
  }
  const bool tail_ready = OpenUnique(&g_tails, "C28_zygote_tails", kTailLimit);
  if (!tail_ready) __android_log_write(ANDROID_LOG_ERROR, kTag, "tail file open failed");
  const int64_t deadline = g_start_ms + kWatchDurationMs;
  std::vector<PropertyValue> properties = {
      {"init.svc.zygote", GetProperty("init.svc.zygote")},
      {"init.svc.zygote_secondary", GetProperty("init.svc.zygote_secondary")},
      {"init.svc.c28_logcat", GetProperty("init.svc.c28_logcat")},
      {"init.svc.c25_bootdiag", GetProperty("init.svc.c25_bootdiag")},
      {"init.svc.netd", GetProperty("init.svc.netd")},
  };
  Event("INITIAL_STATE build=C28 duration_ms=" + std::to_string(kWatchDurationMs) +
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
        "init.svc.zygote", "init.svc.zygote_secondary", "init.svc.c28_logcat",
        "init.svc.c25_bootdiag", "init.svc.netd"};
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
