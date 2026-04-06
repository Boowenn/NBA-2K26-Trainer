"""进程发现与附加 - 查找 NBA2K26.exe 并获取进程句柄"""

import ctypes
import ctypes.wintypes as wt
import struct
import subprocess
import os
from typing import Optional

from .memory import GameMemory, kernel32, PROCESS_ALL_ACCESS

# --- Toolhelp32 ---
TH32CS_SNAPPROCESS = 0x00000002
TH32CS_SNAPMODULE = 0x00000008
TH32CS_SNAPMODULE32 = 0x00000010

GAME_PROCESS_NAME = b"NBA2K26.exe"
GAME_PROCESS_NAME_STR = "NBA2K26.exe"


# ============================================================
# Process Discovery
# ============================================================

def find_process_psutil(name: str = GAME_PROCESS_NAME_STR) -> Optional[int]:
    """psutil - reliable process search"""
    try:
        import psutil
        target = name.lower()
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if proc.info['name'] and proc.info['name'].lower() == target:
                    return proc.info['pid']
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except ImportError:
        pass
    return None


def find_process_toolhelp(name: bytes = GAME_PROCESS_NAME) -> Optional[int]:
    """Win32 Toolhelp32 - backup process search"""
    kernel32.CreateToolhelp32Snapshot.restype = wt.HANDLE
    kernel32.CreateToolhelp32Snapshot.argtypes = [wt.DWORD, wt.DWORD]

    class PROCESSENTRY32(ctypes.Structure):
        _fields_ = [
            ("dwSize", wt.DWORD), ("cntUsage", wt.DWORD),
            ("th32ProcessID", wt.DWORD),
            ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
            ("th32ModuleID", wt.DWORD), ("cntThreads", wt.DWORD),
            ("th32ParentProcessID", wt.DWORD),
            ("pcPriClassBase", ctypes.c_long), ("dwFlags", wt.DWORD),
            ("szExeFile", ctypes.c_char * 260),
        ]

    kernel32.Process32First.restype = wt.BOOL
    kernel32.Process32First.argtypes = [wt.HANDLE, ctypes.POINTER(PROCESSENTRY32)]
    kernel32.Process32Next.restype = wt.BOOL
    kernel32.Process32Next.argtypes = [wt.HANDLE, ctypes.POINTER(PROCESSENTRY32)]

    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not snap:
        return None
    try:
        pe = PROCESSENTRY32()
        pe.dwSize = ctypes.sizeof(PROCESSENTRY32)
        if not kernel32.Process32First(snap, ctypes.byref(pe)):
            return None
        target = name.lower()
        while True:
            exe_name = pe.szExeFile.lower().strip(b'\x00')
            if exe_name == target:
                return pe.th32ProcessID
            if not kernel32.Process32Next(snap, ctypes.byref(pe)):
                break
    finally:
        kernel32.CloseHandle(snap)
    return None


def find_game_pid() -> Optional[int]:
    """Find NBA2K26.exe PID using all available methods"""
    pid = find_process_psutil()
    if pid:
        return pid
    return find_process_toolhelp()


# ============================================================
# Module Base Address
# ============================================================

def _get_base_via_peb(handle: int) -> Optional[int]:
    """Read ImageBaseAddress from PEB via NtQueryInformationProcess"""
    try:
        ntdll = ctypes.WinDLL('ntdll', use_last_error=True)

        class PROCESS_BASIC_INFORMATION(ctypes.Structure):
            _fields_ = [
                ('Reserved1', ctypes.c_void_p),
                ('PebBaseAddress', ctypes.c_void_p),
                ('Reserved2', ctypes.c_void_p * 2),
                ('UniqueProcessId', ctypes.POINTER(ctypes.c_ulong)),
                ('Reserved3', ctypes.c_void_p),
            ]

        ntdll.NtQueryInformationProcess.restype = ctypes.c_long
        ntdll.NtQueryInformationProcess.argtypes = [
            wt.HANDLE, ctypes.c_ulong, ctypes.c_void_p,
            ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong)
        ]

        pbi = PROCESS_BASIC_INFORMATION()
        ret_len = ctypes.c_ulong()
        status = ntdll.NtQueryInformationProcess(
            handle, 0, ctypes.byref(pbi),
            ctypes.sizeof(pbi), ctypes.byref(ret_len)
        )
        if status != 0 or not pbi.PebBaseAddress:
            return None

        # PEB64.ImageBaseAddress is at offset 0x10
        buf = ctypes.create_string_buffer(8)
        br = ctypes.c_size_t()
        ok = kernel32.ReadProcessMemory(
            handle, ctypes.c_void_p(pbi.PebBaseAddress + 0x10),
            buf, 8, ctypes.byref(br)
        )
        if ok and br.value == 8:
            return struct.unpack('<Q', buf.raw)[0]
    except Exception:
        pass
    return None


def _get_base_via_toolhelp(pid: int) -> Optional[int]:
    """Get module base via Toolhelp32 snapshot"""
    class MODULEENTRY32(ctypes.Structure):
        _fields_ = [
            ("dwSize", wt.DWORD), ("th32ModuleID", wt.DWORD),
            ("th32ProcessID", wt.DWORD), ("GlblcntUsage", wt.DWORD),
            ("ProccntUsage", wt.DWORD),
            ("modBaseAddr", ctypes.POINTER(ctypes.c_byte)),
            ("modBaseSize", wt.DWORD), ("hModule", wt.HMODULE),
            ("szModule", ctypes.c_char * 256),
            ("szExePath", ctypes.c_char * 260),
        ]

    kernel32.Module32First.restype = wt.BOOL
    kernel32.Module32First.argtypes = [wt.HANDLE, ctypes.POINTER(MODULEENTRY32)]
    kernel32.Module32Next.restype = wt.BOOL
    kernel32.Module32Next.argtypes = [wt.HANDLE, ctypes.POINTER(MODULEENTRY32)]

    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid)
    if not snap:
        return None
    try:
        me = MODULEENTRY32()
        me.dwSize = ctypes.sizeof(MODULEENTRY32)
        if not kernel32.Module32First(snap, ctypes.byref(me)):
            return None
        target = GAME_PROCESS_NAME.lower()
        while True:
            if me.szModule.lower().strip(b'\x00') == target:
                return ctypes.cast(me.modBaseAddr, ctypes.c_void_p).value
            if not kernel32.Module32Next(snap, ctypes.byref(me)):
                break
    except Exception:
        pass
    finally:
        kernel32.CloseHandle(snap)
    return None


def _get_base_via_enum_modules(handle: int) -> Optional[int]:
    """Get base via EnumProcessModulesEx (psapi)"""
    try:
        psapi = ctypes.WinDLL('psapi', use_last_error=True)
        MAX_MODS = 1024
        hMods = (wt.HMODULE * MAX_MODS)()
        cbNeeded = wt.DWORD()

        psapi.EnumProcessModulesEx.restype = wt.BOOL
        psapi.EnumProcessModulesEx.argtypes = [
            wt.HANDLE, ctypes.POINTER(wt.HMODULE * MAX_MODS),
            wt.DWORD, ctypes.POINTER(wt.DWORD), wt.DWORD
        ]
        ok = psapi.EnumProcessModulesEx(
            handle, ctypes.byref(hMods), ctypes.sizeof(hMods),
            ctypes.byref(cbNeeded), 0x03  # LIST_MODULES_ALL
        )
        if ok and cbNeeded.value > 0:
            return hMods[0]  # First module = main exe
    except Exception:
        pass
    return None


def _verify_pe_header(handle: int, base: int) -> bool:
    """Verify address points to a valid PE by checking MZ signature"""
    buf = ctypes.create_string_buffer(2)
    br = ctypes.c_size_t()
    ok = kernel32.ReadProcessMemory(
        handle, ctypes.c_void_p(base), buf, 2, ctypes.byref(br)
    )
    return ok and br.value == 2 and buf.raw[:2] == b'MZ'


def _can_read_memory(handle: int, address: int) -> bool:
    """Test if we can actually read from an address"""
    buf = ctypes.create_string_buffer(1)
    br = ctypes.c_size_t()
    return bool(kernel32.ReadProcessMemory(
        handle, ctypes.c_void_p(address), buf, 1, ctypes.byref(br)
    ))


def get_module_base(pid: int, handle: int) -> Optional[int]:
    """Get main module base address - tries multiple methods"""
    # Method 1: Toolhelp32
    base = _get_base_via_toolhelp(pid)
    if base and _verify_pe_header(handle, base):
        return base

    # Method 2: EnumProcessModulesEx
    base = _get_base_via_enum_modules(handle)
    if base and _verify_pe_header(handle, base):
        return base

    # Method 3: PEB
    base = _get_base_via_peb(handle)
    if base and _verify_pe_header(handle, base):
        return base

    return None


# ============================================================
# EAC Detection
# ============================================================

def is_eac_running() -> bool:
    """Check if EasyAntiCheat service/process is active"""
    try:
        import psutil
        for proc in psutil.process_iter(['name']):
            try:
                name = (proc.info['name'] or "").lower()
                if "easyanticheat" in name or "eac_" in name:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except ImportError:
        pass
    return False


def check_memory_access(pid: int) -> bool:
    """Check if we can actually read the game's memory"""
    handle = kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
    if not handle:
        return False
    try:
        # Try reading PEB
        can_read = _get_base_via_peb(handle) is not None
        return can_read
    finally:
        kernel32.CloseHandle(handle)


def get_game_exe_path() -> Optional[str]:
    """Get the path to NBA2K26.exe"""
    try:
        import psutil
        pid = find_game_pid()
        if pid:
            proc = psutil.Process(pid)
            return proc.exe()
    except Exception:
        pass
    # Fallback: check common locations
    common = [
        r"C:\SteamLibrary\steamapps\common\NBA 2K26\NBA2K26.exe",
        r"C:\Program Files (x86)\Steam\steamapps\common\NBA 2K26\NBA2K26.exe",
        r"D:\SteamLibrary\steamapps\common\NBA 2K26\NBA2K26.exe",
    ]
    for p in common:
        if os.path.exists(p):
            return p
    return None


def kill_game_process() -> bool:
    """Kill any running NBA2K26.exe process"""
    try:
        result = subprocess.run(
            ["taskkill", "/F", "/IM", "NBA2K26.exe"],
            capture_output=True, timeout=10
        )
        return result.returncode == 0
    except Exception:
        return False


def _get_game_dir_from_exe(exe_path: str) -> str:
    return os.path.dirname(exe_path)


# EAC files that need to be disabled (relative to game directory)
_EAC_FILES_TO_DISABLE = [
    r"data\epic_online_service\eossdk-win64-shipping.dll",
    r"EasyAntiCheat\EasyAntiCheat_EOS_Setup.exe",
    r"start_protected_game.exe",
]

_BACKUP_SUFFIX = ".disabled_by_trainer"


def disable_eac_files(game_dir: str) -> tuple[bool, list[str]]:
    """Rename EAC-related files so the game can't load them.

    Returns:
        (any_renamed, list of status messages)
    """
    messages = []
    any_renamed = False
    for rel_path in _EAC_FILES_TO_DISABLE:
        src = os.path.join(game_dir, rel_path)
        dst = src + _BACKUP_SUFFIX
        if os.path.exists(dst):
            messages.append(f"Already disabled: {rel_path}")
            any_renamed = True
            continue
        if os.path.exists(src):
            try:
                os.rename(src, dst)
                messages.append(f"Disabled: {rel_path}")
                any_renamed = True
            except PermissionError:
                messages.append(f"FAILED (access denied): {rel_path}")
            except Exception as e:
                messages.append(f"FAILED ({e}): {rel_path}")
        else:
            messages.append(f"Not found (skip): {rel_path}")
    return any_renamed, messages


def restore_eac_files(game_dir: str) -> list[str]:
    """Restore EAC files that were disabled by the trainer."""
    messages = []
    for rel_path in _EAC_FILES_TO_DISABLE:
        src = os.path.join(game_dir, rel_path) + _BACKUP_SUFFIX
        dst = os.path.join(game_dir, rel_path)
        if os.path.exists(src):
            try:
                os.rename(src, dst)
                messages.append(f"Restored: {rel_path}")
            except Exception as e:
                messages.append(f"Restore failed ({e}): {rel_path}")
    return messages


def stop_eac_service() -> list[str]:
    """Stop EAC services and kill EAC processes."""
    messages = []

    # Kill EAC processes
    for proc_name in ["EasyAntiCheat.exe", "EasyAntiCheat_EOS.exe",
                       "EasyAntiCheat_Setup.exe", "start_protected_game.exe"]:
        try:
            r = subprocess.run(["taskkill", "/F", "/IM", proc_name],
                               capture_output=True, timeout=10)
            if r.returncode == 0:
                messages.append(f"Killed {proc_name}")
        except Exception:
            pass

    # Stop EAC services
    for svc in ["EasyAntiCheat", "EasyAntiCheat_EOS", "EasyAntiCheatSys"]:
        try:
            r = subprocess.run(["sc", "stop", svc], capture_output=True, timeout=10)
            if r.returncode == 0:
                messages.append(f"Stopped service {svc}")
        except Exception:
            pass
    return messages


def launch_game_without_eac() -> tuple[bool, str]:
    """Full procedure: kill game, stop EAC services, disable EAC files, relaunch.

    Returns:
        (success, message)
    """
    import time
    steps = []

    # Step 1: Kill existing game
    pid = find_game_pid()
    if pid:
        kill_game_process()
        steps.append("1. Killed existing game")
        time.sleep(2)

    # Step 2: Find game exe first (need game dir for file operations)
    exe = _find_game_exe()
    if not exe:
        return False, "Cannot find NBA2K26.exe"
    game_dir = _get_game_dir_from_exe(exe)

    # Step 3: Stop EAC services
    svc_msgs = stop_eac_service()
    if svc_msgs:
        steps.append(f"2. {'; '.join(svc_msgs)}")
    time.sleep(1)

    # Step 4: Disable EAC files (the critical step!)
    disabled, file_msgs = disable_eac_files(game_dir)
    steps.append(f"3. Files: {'; '.join(file_msgs)}")

    # Step 5: Launch game
    try:
        subprocess.Popen([exe], cwd=game_dir)
        steps.append(f"4. Launched {os.path.basename(exe)}")
        return True, "\n".join(steps)
    except Exception as e:
        return False, "\n".join(steps) + f"\nLaunch failed: {e}"


def _find_game_exe() -> Optional[str]:
    """Search for NBA2K26.exe in common locations"""
    # If game is running, get its path
    exe = get_game_exe_path()
    if exe and os.path.exists(exe):
        return exe

    import sys
    search_paths = []

    # Same directory as trainer
    if getattr(sys, 'frozen', False):
        trainer_dir = os.path.dirname(sys.executable)
    else:
        trainer_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    search_paths.append(os.path.join(trainer_dir, "NBA2K26.exe"))
    search_paths.append(os.path.join(os.path.dirname(trainer_dir), "NBA2K26.exe"))

    search_paths.extend([
        r"C:\SteamLibrary\steamapps\common\NBA 2K26\NBA2K26.exe",
        r"D:\SteamLibrary\steamapps\common\NBA 2K26\NBA2K26.exe",
        r"C:\Program Files (x86)\Steam\steamapps\common\NBA 2K26\NBA2K26.exe",
    ])

    for p in search_paths:
        if os.path.exists(p):
            return p
    return None


# ============================================================
# Main Attach
# ============================================================

def attach_to_game() -> tuple[Optional[GameMemory], str]:
    """Attach to NBA 2K26 process.

    Returns:
        (GameMemory or None, status_message)
    """
    pid = find_game_pid()
    if pid is None:
        return None, "NOT_FOUND"

    handle = kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
    if not handle:
        return None, "OPEN_FAILED"

    base = get_module_base(pid, handle)
    if base is not None:
        return GameMemory(handle, base), "OK"

    # Memory access blocked - likely EAC
    kernel32.CloseHandle(handle)

    if is_eac_running():
        return None, "EAC_BLOCKED"

    # Can open process but can't read memory
    return None, "MEMORY_ACCESS_DENIED"


def is_process_running() -> bool:
    """Check if game is running"""
    return find_game_pid() is not None
