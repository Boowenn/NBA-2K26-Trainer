"""Win32 内存读写层 - 使用 ctypes 封装 ReadProcessMemory / WriteProcessMemory"""

import ctypes
import ctypes.wintypes as wt
import struct
from typing import Optional

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

# --- Win32 Constants ---
PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_VM_OPERATION = 0x0008
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_ALL_ACCESS = 0x1F0FFF

# --- Win32 Function Signatures ---
kernel32.OpenProcess.restype = wt.HANDLE
kernel32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]

kernel32.CloseHandle.restype = wt.BOOL
kernel32.CloseHandle.argtypes = [wt.HANDLE]

kernel32.ReadProcessMemory.restype = wt.BOOL
kernel32.ReadProcessMemory.argtypes = [
    wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t)
]

kernel32.WriteProcessMemory.restype = wt.BOOL
kernel32.WriteProcessMemory.argtypes = [
    wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t)
]


class GameMemory:
    """游戏进程内存读写"""

    def __init__(self, handle: int, base_address: int):
        self.handle = handle
        self.base_address = base_address

    def close(self):
        if self.handle:
            kernel32.CloseHandle(self.handle)
            self.handle = None

    # --- Raw Read/Write ---

    def read_bytes(self, address: int, size: int) -> Optional[bytes]:
        buf = ctypes.create_string_buffer(size)
        bytes_read = ctypes.c_size_t(0)
        ok = kernel32.ReadProcessMemory(
            self.handle, ctypes.c_void_p(address), buf, size, ctypes.byref(bytes_read)
        )
        if not ok:
            return None
        return buf.raw[:bytes_read.value]

    def write_bytes(self, address: int, data: bytes) -> bool:
        buf = ctypes.create_string_buffer(data)
        bytes_written = ctypes.c_size_t(0)
        ok = kernel32.WriteProcessMemory(
            self.handle, ctypes.c_void_p(address), buf, len(data),
            ctypes.byref(bytes_written)
        )
        return bool(ok)

    # --- Typed Reads ---

    def read_int8(self, address: int) -> Optional[int]:
        data = self.read_bytes(address, 1)
        return struct.unpack("<b", data)[0] if data else None

    def read_uint8(self, address: int) -> Optional[int]:
        data = self.read_bytes(address, 1)
        return struct.unpack("<B", data)[0] if data else None

    def read_int16(self, address: int) -> Optional[int]:
        data = self.read_bytes(address, 2)
        return struct.unpack("<h", data)[0] if data and len(data) == 2 else None

    def read_uint16(self, address: int) -> Optional[int]:
        data = self.read_bytes(address, 2)
        return struct.unpack("<H", data)[0] if data and len(data) == 2 else None

    def read_int32(self, address: int) -> Optional[int]:
        data = self.read_bytes(address, 4)
        return struct.unpack("<i", data)[0] if data and len(data) == 4 else None

    def read_uint32(self, address: int) -> Optional[int]:
        data = self.read_bytes(address, 4)
        return struct.unpack("<I", data)[0] if data and len(data) == 4 else None

    def read_int64(self, address: int) -> Optional[int]:
        data = self.read_bytes(address, 8)
        return struct.unpack("<q", data)[0] if data and len(data) == 8 else None

    def read_uint64(self, address: int) -> Optional[int]:
        data = self.read_bytes(address, 8)
        return struct.unpack("<Q", data)[0] if data and len(data) == 8 else None

    def read_float(self, address: int) -> Optional[float]:
        data = self.read_bytes(address, 4)
        return struct.unpack("<f", data)[0] if data and len(data) == 4 else None

    # --- Typed Writes ---

    def write_int8(self, address: int, value: int) -> bool:
        return self.write_bytes(address, struct.pack("<b", value))

    def write_uint8(self, address: int, value: int) -> bool:
        return self.write_bytes(address, struct.pack("<B", value))

    def write_int16(self, address: int, value: int) -> bool:
        return self.write_bytes(address, struct.pack("<h", value))

    def write_uint16(self, address: int, value: int) -> bool:
        return self.write_bytes(address, struct.pack("<H", value))

    def write_int32(self, address: int, value: int) -> bool:
        return self.write_bytes(address, struct.pack("<i", value))

    def write_uint32(self, address: int, value: int) -> bool:
        return self.write_bytes(address, struct.pack("<I", value))

    def write_int64(self, address: int, value: int) -> bool:
        return self.write_bytes(address, struct.pack("<q", value))

    def write_uint64(self, address: int, value: int) -> bool:
        return self.write_bytes(address, struct.pack("<Q", value))

    def write_float(self, address: int, value: float) -> bool:
        return self.write_bytes(address, struct.pack("<f", value))

    # --- String ---

    def read_wstring(self, address: int, max_len: int = 64) -> Optional[str]:
        data = self.read_bytes(address, max_len * 2)
        if not data:
            return None
        try:
            null_idx = data.index(b'\x00\x00')
            if null_idx % 2 == 1:
                null_idx += 1
            data = data[:null_idx]
        except ValueError:
            pass
        return data.decode("utf-16-le", errors="replace")

    def write_wstring(self, address: int, value: str, fixed_len: int = 64) -> bool:
        encoded = value.encode("utf-16-le")
        padded = encoded[:fixed_len * 2].ljust(fixed_len * 2, b'\x00')
        return self.write_bytes(address, padded)

    def read_ascii(self, address: int, max_len: int = 64) -> Optional[str]:
        data = self.read_bytes(address, max_len)
        if not data:
            return None
        try:
            null_idx = data.index(b'\x00')
            data = data[:null_idx]
        except ValueError:
            pass
        return data.decode("ascii", errors="replace")

    # --- Bitfield ---

    def read_bitfield(self, address: int, bit_start: int, bit_length: int) -> Optional[int]:
        byte_offset = bit_start // 8
        total_bits = bit_start % 8 + bit_length
        total_bytes = (total_bits + 7) // 8
        data = self.read_bytes(address + byte_offset, total_bytes)
        if not data:
            return None
        val = int.from_bytes(data, byteorder="little")
        shift = bit_start % 8
        mask = (1 << bit_length) - 1
        return (val >> shift) & mask

    def write_bitfield(self, address: int, bit_start: int, bit_length: int, value: int) -> bool:
        byte_offset = bit_start // 8
        total_bits = bit_start % 8 + bit_length
        total_bytes = (total_bits + 7) // 8
        data = self.read_bytes(address + byte_offset, total_bytes)
        if not data:
            return False
        val = int.from_bytes(data, byteorder="little")
        shift = bit_start % 8
        mask = (1 << bit_length) - 1
        val = (val & ~(mask << shift)) | ((value & mask) << shift)
        new_data = val.to_bytes(total_bytes, byteorder="little")
        return self.write_bytes(address + byte_offset, new_data)

    # --- Pointer Chain ---

    def resolve_pointer_chain(self, base: int, offsets: list[int]) -> Optional[int]:
        addr = base
        for i, offset in enumerate(offsets):
            if i < len(offsets) - 1:
                ptr = self.read_uint64(addr + offset)
                if ptr is None or ptr == 0:
                    return None
                addr = ptr
            else:
                addr = addr + offset
        return addr
