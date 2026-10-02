/* Signal only a verified guest process through a Linux pidfd; no PID fallback. */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/syscall.h>
#include <unistd.h>

static int read_file(const char *path, char *buffer, size_t length) {
  int fd = open(path, O_RDONLY | O_CLOEXEC);
  if (fd < 0) return -1;
  ssize_t count = read(fd, buffer, length - 1);
  close(fd);
  if (count < 0 || (size_t)count == length - 1) return -1;
  buffer[count] = '\0';
  return 0;
}

int main(int argc, char **argv) {
  if (argc != 5) return 2;
  char *end;
  errno = 0;
  long pid = strtol(argv[1], &end, 10);
  if (errno || *end || pid < 2 || pid > 2147483647) return 2;
  int fd = syscall(SYS_pidfd_open, (int)pid, 0);
  if (fd < 0) return 3;
  char path[80], buffer[8192];
  int result = 4;
  if (read_file("/proc/sys/kernel/random/boot_id", buffer, sizeof(buffer))) goto done;
  buffer[strcspn(buffer, "\n")] = '\0';
  if (strcmp(buffer, argv[3])) goto done;
  snprintf(path, sizeof(path), "/proc/%ld/cmdline", pid);
  if (read_file(path, buffer, sizeof(buffer)) || strcmp(buffer, argv[4])) goto done;
  snprintf(path, sizeof(path), "/proc/%ld/stat", pid);
  if (read_file(path, buffer, sizeof(buffer))) goto done;
  char *fields = strrchr(buffer, ')');
  if (!fields) goto done;
  char *save, *field = strtok_r(fields + 1, " \n", &save);
  for (int index = 0; field && index < 19; index++) field = strtok_r(NULL, " \n", &save);
  if (!field || strcmp(field, argv[2])) goto done;
  result = syscall(SYS_pidfd_send_signal, fd, SIGTERM, NULL, 0) ? 5 : 0;
done:
  close(fd);
  return result;
}
