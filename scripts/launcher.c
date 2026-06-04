// claw-launcher: 用私有 API responsibility_spawnattrs_setdisclaim 让被 spawn 的子进程
// 成为自己的 TCC responsible 进程(脱离父 app 归因)，同时继承 fd 保 stdio。
// 用法: claw-launcher <prog> [args...]
#include <stdio.h>
#include <stdlib.h>
#include <spawn.h>
#include <dlfcn.h>
#include <sys/wait.h>

extern char **environ;
typedef int (*disclaim_fn)(posix_spawnattr_t *, int);

int main(int argc, char **argv) {
    if (argc < 2) { fprintf(stderr, "usage: claw-launcher <prog> [args...]\n"); return 2; }
    posix_spawnattr_t attr;
    posix_spawnattr_init(&attr);
    disclaim_fn disclaim = (disclaim_fn)dlsym(RTLD_DEFAULT, "responsibility_spawnattrs_setdisclaim");
    if (!disclaim) { fprintf(stderr, "[claw-launcher] disclaim symbol missing\n"); return 3; }
    disclaim(&attr, 1);
    pid_t pid;
    int sp = posix_spawn(&pid, argv[1], NULL, &attr, &argv[1], environ);
    if (sp != 0) { fprintf(stderr, "[claw-launcher] posix_spawn rc=%d\n", sp); return 4; }
    int status;
    waitpid(pid, &status, 0);
    posix_spawnattr_destroy(&attr);
    return WIFEXITED(status) ? WEXITSTATUS(status) : 1;
}
