"""Windows Job Object helper: ensure spawned children die with the parent.

When the supervisor process is killed for any reason (Task Manager, closed
console, hard crash), child Python processes spawned via ``multiprocessing``
or ``subprocess`` would otherwise survive — orphaning the camera handle.

Assigning each child to a Job Object that has the
``JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`` flag tells Windows to terminate
every member of the job when the last handle to the job is closed —
which happens automatically when the parent process exits.

This is a no-op on non-Windows platforms.
"""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
_JobObjectExtendedLimitInformation = 9

_PROCESS_SET_QUOTA = 0x0100
_PROCESS_TERMINATE = 0x0001


class _IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_uint64),
        ("WriteOperationCount", ctypes.c_uint64),
        ("OtherOperationCount", ctypes.c_uint64),
        ("ReadTransferCount", ctypes.c_uint64),
        ("WriteTransferCount", ctypes.c_uint64),
        ("OtherTransferCount", ctypes.c_uint64),
    ]


class _JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", ctypes.c_uint32),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", ctypes.c_uint32),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", ctypes.c_uint32),
        ("SchedulingClass", ctypes.c_uint32),
    ]


class _JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", _IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


class KillOnCloseJob:
    """A Windows job object that terminates members on parent exit."""

    def __init__(self) -> None:
        self._handle: int | None = None
        if sys.platform != "win32":
            return
        kernel32 = ctypes.windll.kernel32
        kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        handle = kernel32.CreateJobObjectW(None, None)
        if not handle:
            return
        info = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        ok = kernel32.SetInformationJobObject(
            handle,
            _JobObjectExtendedLimitInformation,
            ctypes.byref(info),
            ctypes.sizeof(info),
        )
        if not ok:
            kernel32.CloseHandle(handle)
            return
        self._handle = handle

    @property
    def is_active(self) -> bool:
        return self._handle is not None

    def assign(self, pid: int) -> bool:
        """Add the process *pid* to this job. Best-effort; returns False on failure."""
        if self._handle is None or sys.platform != "win32":
            return False
        kernel32 = ctypes.windll.kernel32
        kernel32.OpenProcess.restype = wintypes.HANDLE
        h_proc = kernel32.OpenProcess(
            _PROCESS_SET_QUOTA | _PROCESS_TERMINATE,
            False,
            int(pid),
        )
        if not h_proc:
            return False
        try:
            return bool(kernel32.AssignProcessToJobObject(self._handle, h_proc))
        finally:
            kernel32.CloseHandle(h_proc)

    def close(self) -> None:
        if self._handle is None or sys.platform != "win32":
            return
        ctypes.windll.kernel32.CloseHandle(self._handle)
        self._handle = None
