"""进程发现与附加 - 查找 NBA2K26.exe 并获取进程句柄"""

import ctypes
import ctypes.wintypes as wt
from typing import Optional

from .memory import GameMemory, kernel32, PROCESS_ALL_ACCESS

# --- Toolhelp32 ---
TH32CS_SNAPPROCESS = 0x00000002
TH32CS_SNAPMODULE = 0x00000008
TH32CS_SNAPMODULE32 = 0x00000010

INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value & 0xFFFFFFFFFFFFFFFF


class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wt.DWORD),
        ("cntUsage", wt.DWORD),
        ("th32ProcessID", wt.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
        ("th32ModuleID", wt.DWORD),
        ("cntThreads", wt.DWORD),
        ("th32ParentProcessID", wt.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wt.DWORD),
        ("szExeFile", ctypes.c_char * 260),
    ]


class MODULEENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wt.DWORD),
        ("th32ModuleID", wt.DWORD),
        ("th32ProcessID", wt.DWORD),
        ("GlblcntUsage", wt.DWORD),
        ("ProccntUsage", wt.DWORD),
        ("modBaseAddr", ctypes.POINTER(ctypes.c_byte)),
        ("modBaseSize", wt.DWORD),
        ("hModule", wt.HMODULE),
        ("szModule", ctypes.c_char * 256),
        ("szExePath", ctypes.c_char * 260),
    ]


kernel32.CreateToolhelp32Snapshot.restype = wt.HANDLE
kernel32.CreateToolhelp32Snapshot.argtypes = [wt.DWORD, wt.DWORD]
kernel32.Process32First.restype = wt.BOOL
kernel32.Process32First.argtypes = [wt.HANDLE, ctypes.POINTER(PROCESSENTRY32)]
kernel32.Process32Next.restype = wt.BOOL
kernel32.Process32Next.argtypes = [wt.HANDLE, ctypes.POINTER(PROCESSENTRY32)]
kernel32.Module32First.restype = wt.BOOL
kernel32.Module32First.argtypes = [wt.HANDLE, ctypes.POINTER(MODULEENTRY32)]
kernel32.Module32Next.restype = wt.BOOL
kernel32.Module32Next.argtypes = [wt.HANDLE, ctypes.POINTER(MODULEENTRY32)]

GAME_PROCESS_NAME = b"NBA2K26.exe"


def find_process(name: bytes = GAME_PROCESS_NAME) -> Optional[int]:
    """查找进程，返回 PID。支持进程名的子串匹配。"""
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap == INVALID_HANDLE_VALUE:
        return None
    try:
        pe = PROCESSENTRY32()
        pe.dwSize = ctypes.sizeof(PROCESSENTRY32)
        if not kernel32.Process32First(snap, ctypes.byref(pe)):
            return None
        while True:
            exe_name = pe.szExeFile.lower().strip(b'\x00')
            target = name.lower()
            if exe_name == target or exe_name.endswith(target):
                return pe.th32ProcessID
            if not kernel32.Process32Next(snap, ctypes.byref(pe)):
                break
    finally:
        kernel32.CloseHandle(snap)
    return None


def find_process_psutil(name: str = "NBA2K26.exe") -> Optional[int]:
    """使用 psutil 查找进程（备用方案）"""
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


def get_module_base(pid: int, module_name: bytes = GAME_PROCESS_NAME) -> Optional[int]:
    """获取指定模块的基地址"""
    snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid)
    if snap == INVALID_HANDLE_VALUE:
        return None
    try:
        me = MODULEENTRY32()
        me.dwSize = ctypes.sizeof(MODULEENTRY32)
        if not kernel32.Module32First(snap, ctypes.byref(me)):
            return None
        while True:
            mod_name = me.szModule.lower().strip(b'\x00')
            target = module_name.lower()
            if mod_name == target or mod_name.endswith(target):
                # 正确获取模块基址：将 POINTER(c_byte) 转为整数地址
                base_addr = ctypes.cast(me.modBaseAddr, ctypes.c_void_p).value
                return base_addr
            if not kernel32.Module32Next(snap, ctypes.byref(me)):
                break
    finally:
        kernel32.CloseHandle(snap)
    return None


def get_module_base_psutil(pid: int) -> Optional[int]:
    """使用 psutil 获取主模块基址（备用方案）"""
    try:
        import psutil
        proc = psutil.Process(pid)
        # 主执行文件的内存映射的第一个地址
        for mmap in proc.memory_maps():
            if "nba2k26" in mmap.path.lower():
                # RSS 地址不是基址，需要用 Win32 API
                break
    except Exception:
        pass
    return None


def attach_to_game() -> Optional[GameMemory]:
    """查找并附加到 NBA 2K26 进程，返回 GameMemory 实例"""
    # 先用 Win32 API 查找
    pid = find_process()
    # 备用：psutil
    if pid is None:
        pid = find_process_psutil()
    if pid is None:
        return None

    handle = kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
    if not handle:
        return None

    base = get_module_base(pid)
    if base is None:
        kernel32.CloseHandle(handle)
        return None

    return GameMemory(handle, base)


def is_process_running(name: bytes = GAME_PROCESS_NAME) -> bool:
    """检查游戏进程是否在运行"""
    if find_process(name) is not None:
        return True
    return find_process_psutil(name.decode('ascii', errors='ignore')) is not None
