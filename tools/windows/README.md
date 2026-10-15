# Windows setup — SM-S918N GZIF read-only device validation

Use **Windows PowerShell 5.1+** for the phone connection. The native root
payload and ELF/BTF reconstruction tools remain **Linux/WSL2** work and must
not run until the firmware contract and module compatibility are verified.

## 1. Install ADB on Windows

Download the official Android SDK Platform-Tools for Windows:
https://developer.android.com/tools/releases/platform-tools

Extract the ZIP, for example to: `C:\Android\platform-tools`. In PowerShell:

```powershell
cd C:\Android\platform-tools
.\adb.exe version
```

If Windows does not recognize the Samsung phone, install a **trusted Samsung
USB driver** from the device manufacturer, check the cable/port and reconnect.

## 2. Connect the phone safely

On the **SM-S918N**: Settings > About phone > Software information > tap Build
number seven times to enable Developer options (if not already enabled).
Then enable **USB debugging** in Developer options. Unlock the phone and
approve the PC's USB debugging authorization popup.

```powershell
cd C:\Android\platform-tools
.\adb.exe devices
```

One row must end in `device` (not `unauthorized`). Do not post your
ADB device serial number publicly.

No root, bootloader unlock, firmware flashing, USB debugging workaround,
or SELinux change is required for this preflight.

## 3. Run the preflight from this repository checkout

Use the **port/s918n-gzif-android17** branch. From its repository root:

```powershell
powershell.exe -NoProfile -File .\tools\windows\verify-s918n-gzif.ps1 -AdbPath "C:\Android\platform-tools\adb.exe"
```

If Windows blocks the locally reviewed script because it was downloaded,
review its source and remove only that file's downloaded-file mark with
`Unblock-File -LiteralPath .\tools\windows\verify-s918n-gzif.ps1`,
then rerun it. **Do not** disable Windows security or the system-wide
PowerShell execution policy.

The script checks:

- Model `SM-S918N`, device `dm3q`, Android `17`.
- Exact incremental build, fingerprint, kernel release and uname version.
- Current SELinux status (read only).

It does not request or record serial numbers, device IDs or personal data.
It stores the results by default in
`%TEMP%\s918n-gzif-device-check.json`.

Exit codes: `0` identity matches, `2` mismatch, `1` ADB error/other failure.
A positive identity result does **not** certify that the root payload works.
If mismatched, **do not** build or deploy a port for this fingerprint.

## 4. Optional Linux environment on Windows (later build stage)

When ready for BOPE ELF/BTF toolchain work, in **administrator** PowerShell:

```powershell
wsl --install -d Ubuntu
```

Reboot if prompted. Official WSL instructions:
https://learn.microsoft.com/en-us/windows/wsl/install

Build dependencies include `pahole`, `llvm-nm`, kallsyms-finder,
vmlinux-to-elf and the Android NDK version specified by the upstream BOPE
documentation. WSL2 does not need direct USB device access for offline
analysis of an extracted boot image; continue using Windows-native ADB for
the phone's read-only preflight.

**Not ready to flash or root:** A firmware-specific BOPE contract and KernelSU
module must still pass symbol extraction, ABI audits and controlled device
testing. The GZIF target must not be marked supported before then.
