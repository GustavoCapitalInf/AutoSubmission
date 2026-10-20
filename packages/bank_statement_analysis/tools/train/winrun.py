"""winrun.py — run ONE command under a Windows Job Object: a committed-memory
cap, a wall-clock timeout, a free-memory floor, and one durable telemetry line.

    python tools/train/winrun.py --cap-gb 6 --timeout 1800 --floor-gb 1.0 \
        --log <telemetry.jsonl> --label pinned-replay -- python -m tools.x ...

This is the Windows analogue of the guards the Linux host ran every batch-8
instrument under (W3 §HYGIENE8 H6, §FROSTOZK FZ12: `ulimit -v`, `timeout`, a
`MemAvailable` floor, peak RSS of the reaped children):

* the cap is `JOB_OBJECT_LIMIT_JOB_MEMORY` — an allocation that would take the
  job past it FAILS (a `MemoryError` inside a Python child) instead of taking
  the host, which is exactly what `RLIMIT_AS` did for mutant O21;
* `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` — no orphan survives this process;
* the timeout terminates the whole job (every descendant), never one pid;
* `PeakJobMemoryUsed` is the peak committed memory of every process that was
  ever in the job — the number the records call "peak RSS";
* the floor refuses to START when available physical memory is below it,
  because a 15 GB host with a browser open is not an idle 32 GB host.

The child's stdout/stderr are inherited (redirect them to the run's own log).
Exit code: the child's; 124 = timeout (job terminated); 125 = refused, free
memory under the floor; 126 = not Windows, or the job could not be set up.
The telemetry line is appended to `--log` as JSON and echoed to stderr as
`WINRUN … EXIT=<code>`.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import subprocess
import sys
import time
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path

JOB_OBJECT_LIMIT_JOB_MEMORY = 0x00000200
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
JobObjectBasicAccountingInformation = 1
JobObjectExtendedLimitInformation = 9

EXIT_TIMEOUT = 124
EXIT_REFUSED_FLOOR = 125
EXIT_SETUP = 126


class IO_COUNTERS(ctypes.Structure):
    _fields_ = [(name, ctypes.c_ulonglong) for name in (
        "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
        "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]


class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


class JOBOBJECT_BASIC_ACCOUNTING_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("TotalUserTime", ctypes.c_longlong),
        ("TotalKernelTime", ctypes.c_longlong),
        ("ThisPeriodTotalUserTime", ctypes.c_longlong),
        ("ThisPeriodTotalKernelTime", ctypes.c_longlong),
        ("TotalPageFaultCount", wintypes.DWORD),
        ("TotalProcesses", wintypes.DWORD),
        ("ActiveProcesses", wintypes.DWORD),
        ("TotalTerminatedProcesses", wintypes.DWORD),
    ]


class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", wintypes.DWORD),
        ("dwMemoryLoad", wintypes.DWORD),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def _kernel32():
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    k32.CreateJobObjectW.restype = wintypes.HANDLE
    k32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    k32.SetInformationJobObject.restype = wintypes.BOOL
    k32.QueryInformationJobObject.argtypes = [
        wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    k32.QueryInformationJobObject.restype = wintypes.BOOL
    k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    k32.AssignProcessToJobObject.restype = wintypes.BOOL
    k32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    k32.TerminateJobObject.restype = wintypes.BOOL
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    k32.CloseHandle.restype = wintypes.BOOL
    k32.GlobalMemoryStatusEx.argtypes = [ctypes.POINTER(MEMORYSTATUSEX)]
    k32.GlobalMemoryStatusEx.restype = wintypes.BOOL
    return k32


def memory_status(k32) -> tuple[int, int]:
    """(available physical bytes, total physical bytes)."""
    status = MEMORYSTATUSEX()
    status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    if not k32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise ctypes.WinError(ctypes.get_last_error())
    return int(status.ullAvailPhys), int(status.ullTotalPhys)


def _mb(n: int | float) -> float:
    return round(n / (1024 * 1024), 1)


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cap-gb", type=float, default=6.0,
                        help="committed-memory cap for the whole job (default 6 GB)")
    parser.add_argument("--timeout", type=float, default=3600.0,
                        help="wall-clock seconds before the job is terminated (default 3600)")
    parser.add_argument("--floor-gb", type=float, default=1.0,
                        help="refuse to start when available physical memory is below this (default 1 GB)")
    parser.add_argument("--log", type=Path, default=None, help="append one JSON telemetry line here")
    parser.add_argument("--label", default="", help="a name for the telemetry line")
    parser.add_argument("command", nargs=argparse.REMAINDER,
                        help="the command, after `--`")
    args = parser.parse_args(argv)
    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        parser.error("no command given after `--`")
    if sys.platform != "win32":
        print("winrun: Windows only (Job Objects); on Linux use ulimit -v / timeout", file=sys.stderr)
        return EXIT_SETUP

    k32 = _kernel32()
    avail_before, total = memory_status(k32)
    floor = int(args.floor_gb * 1024 ** 3)
    record = {
        "label": args.label,
        "command": command,
        "cwd": os.getcwd(),
        "start_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "cap_mb": _mb(args.cap_gb * 1024 ** 3),
        "timeout_s": args.timeout,
        "avail_before_mb": _mb(avail_before),
        "total_mb": _mb(total),
    }
    if avail_before < floor:
        record.update(exit=EXIT_REFUSED_FLOOR, refused=f"available {_mb(avail_before)} MB < floor {_mb(floor)} MB")
        return _finish(args.log, record)

    job = k32.CreateJobObjectW(None, None)
    if not job:
        record.update(exit=EXIT_SETUP, error=f"CreateJobObjectW: {ctypes.get_last_error()}")
        return _finish(args.log, record)
    limits = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    limits.BasicLimitInformation.LimitFlags = (
        JOB_OBJECT_LIMIT_JOB_MEMORY | JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE)
    limits.JobMemoryLimit = int(args.cap_gb * 1024 ** 3)
    if not k32.SetInformationJobObject(job, JobObjectExtendedLimitInformation,
                                       ctypes.byref(limits), ctypes.sizeof(limits)):
        record.update(exit=EXIT_SETUP, error=f"SetInformationJobObject: {ctypes.get_last_error()}")
        k32.CloseHandle(job)
        return _finish(args.log, record)

    started = time.monotonic()
    try:
        proc = subprocess.Popen(command)
    except OSError as exc:
        record.update(exit=EXIT_SETUP, error=f"spawn: {exc}")
        k32.CloseHandle(job)
        return _finish(args.log, record)
    # The child is assigned before it can have spawned anything of its own
    # (a Python interpreter takes tens of milliseconds to reach user code);
    # every later descendant inherits the job.
    if not k32.AssignProcessToJobObject(job, wintypes.HANDLE(int(proc._handle))):
        error = ctypes.get_last_error()
        proc.kill()
        proc.wait()
        record.update(exit=EXIT_SETUP,
                      error=f"AssignProcessToJobObject: {error} (nested job refused?)")
        k32.CloseHandle(job)
        return _finish(args.log, record)

    timed_out = False
    try:
        code = proc.wait(timeout=args.timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        k32.TerminateJobObject(job, EXIT_TIMEOUT)
        proc.wait()
        code = EXIT_TIMEOUT
    wall = time.monotonic() - started

    peak = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    accounting = JOBOBJECT_BASIC_ACCOUNTING_INFORMATION()
    returned = wintypes.DWORD(0)
    k32.QueryInformationJobObject(job, JobObjectExtendedLimitInformation,
                                  ctypes.byref(peak), ctypes.sizeof(peak), ctypes.byref(returned))
    k32.QueryInformationJobObject(job, JobObjectBasicAccountingInformation,
                                  ctypes.byref(accounting), ctypes.sizeof(accounting), ctypes.byref(returned))
    avail_after, _ = memory_status(k32)
    k32.CloseHandle(job)

    record.update(
        exit=code,
        timed_out=timed_out,
        wall_s=round(wall, 1),
        peak_job_mb=_mb(peak.PeakJobMemoryUsed),
        peak_process_mb=_mb(peak.PeakProcessMemoryUsed),
        processes=int(accounting.TotalProcesses),
        avail_after_mb=_mb(avail_after),
        end_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    return _finish(args.log, record)


def _finish(log: Path | None, record: dict) -> int:
    if log is not None:
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
    summary = " ".join(
        f"{key}={record[key]}" for key in (
            "label", "wall_s", "peak_job_mb", "processes", "avail_before_mb", "avail_after_mb",
            "timed_out", "refused", "error") if key in record)
    print(f"WINRUN {summary} EXIT={record['exit']}", file=sys.stderr, flush=True)
    return int(record["exit"])


if __name__ == "__main__":
    sys.exit(run())
