/* Read-only diagnostics for the RAM-only K94 test, bound to USB networking. */
#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <linux/fb.h>
#include <net/if.h>
#include <signal.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <unistd.h>

static int send_all(int fd, const void *buffer, size_t count)
{
    const char *p = buffer;
    while (count) {
        ssize_t n = send(fd, p, count, MSG_NOSIGNAL);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) return -1;
        p += n; count -= n;
    }
    return 0;
}

static void serve(int client)
{
    char request[1024], method[16], path[128], header[256];
    struct timeval timeout = {5, 0};
    setsockopt(client, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof timeout);
    setsockopt(client, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof timeout);
    size_t used = 0;
    while (used < sizeof request - 1) {
        ssize_t n = recv(client, request + used, sizeof request - 1 - used, 0);
        if (n <= 0) return;
        used += n; request[used] = 0;
        if (strstr(request, "\r\n")) break;
    }
    if (sscanf(request, "%15s %127s", method, path) != 2 || strcmp(method, "GET")) return;
    int input = -1;
    size_t length = 0;
    const char *type = "text/plain";
    if (!strcmp(path, "/status")) {
        input = open("/run/k94-status.txt", O_RDONLY);
        struct stat st;
        if (input >= 0 && !fstat(input, &st) && st.st_size >= 0 && st.st_size <= 262144)
            length = st.st_size;
        else if (input >= 0) { close(input); input = -1; }
    } else if (!strcmp(path, "/framebuffer.bin")) {
        input = open("/dev/fb0", O_RDONLY);
        struct fb_var_screeninfo v;
        struct fb_fix_screeninfo f;
        if (input >= 0 && !ioctl(input, FBIOGET_VSCREENINFO, &v) &&
            !ioctl(input, FBIOGET_FSCREENINFO, &f) &&
            v.xres == 1024 && v.yres == 768 && v.bits_per_pixel == 32 &&
            !v.xoffset && !v.yoffset && f.line_length == 4096 && f.smem_len >= 3145728) {
            length = 3145728;
            type = "application/octet-stream";
        } else if (input >= 0) { close(input); input = -1; }
    }
    if (input < 0) {
        const char *error = "HTTP/1.0 404 Not Found\r\nContent-Length: 0\r\n\r\n";
        send_all(client, error, strlen(error)); return;
    }
    int n = snprintf(header, sizeof header,
        "HTTP/1.0 200 OK\r\nContent-Type: %s\r\nContent-Length: %zu\r\nConnection: close\r\n\r\n",
        type, length);
    if (send_all(client, header, n)) { close(input); return; }
    char buffer[16384];
    while (length) {
        size_t count = length < sizeof buffer ? length : sizeof buffer;
        ssize_t got = read(input, buffer, count);
        if (got < 0 && errno == EINTR) continue;
        if (got <= 0 || send_all(client, buffer, got)) break;
        length -= got;
    }
    close(input);
}

int main(void)
{
    signal(SIGPIPE, SIG_IGN);
    int server = socket(AF_INET6, SOCK_STREAM, 0), zero = 0, one = 1;
    if (server < 0) return 1;
    if (setsockopt(server, SOL_SOCKET, SO_BINDTODEVICE, "usb0", sizeof "usb0")) return 2;
    setsockopt(server, SOL_SOCKET, SO_REUSEADDR, &one, sizeof one);
    setsockopt(server, IPPROTO_IPV6, IPV6_V6ONLY, &zero, sizeof zero);
    struct sockaddr_in6 addr = {.sin6_family = AF_INET6, .sin6_port = htons(18994)};
    if (bind(server, (struct sockaddr *)&addr, sizeof addr) || listen(server, 4)) return 3;
    for (;;) {
        int client = accept(server, NULL, NULL);
        if (client < 0) { if (errno == EINTR) continue; return 4; }
        serve(client); close(client);
    }
}
