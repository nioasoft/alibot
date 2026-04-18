"""Diagnostics for unexpected child-process creation on macOS."""

from __future__ import annotations

import multiprocessing.process
import os
import platform
import subprocess
import threading
import traceback

from loguru import logger

_INSTALLED = False
_ORIGINAL_POPEN_INIT = subprocess.Popen.__init__
_ORIGINAL_PROCESS_START = multiprocessing.process.BaseProcess.start


def _should_enable() -> bool:
    if platform.system() != "Darwin":
        return False
    return os.getenv("ALIBOT_FORK_DEBUG", "1").lower() not in {"0", "false", "no", "off"}


def _stack_dump() -> str:
    return "".join(traceback.format_stack(limit=25)[:-2]).rstrip()


def _thread_label() -> str:
    current = threading.current_thread()
    return f"{current.name}#{current.ident}"


def _patched_popen_init(self, *args, **kwargs):
    cmd = args[0] if args else kwargs.get("args")
    logger.warning(
        "fork-debug subprocess.Popen pid={} thread={} cmd={!r}\n{}",
        os.getpid(),
        _thread_label(),
        cmd,
        _stack_dump(),
    )
    return _ORIGINAL_POPEN_INIT(self, *args, **kwargs)


def _patched_process_start(self):
    logger.warning(
        "fork-debug multiprocessing.start pid={} thread={} process={!r}\n{}",
        os.getpid(),
        _thread_label(),
        self,
        _stack_dump(),
    )
    return _ORIGINAL_PROCESS_START(self)


def install_fork_debugging() -> bool:
    global _INSTALLED
    if _INSTALLED or not _should_enable():
        return False

    subprocess.Popen.__init__ = _patched_popen_init
    multiprocessing.process.BaseProcess.start = _patched_process_start
    _INSTALLED = True
    logger.info("Installed fork-debug instrumentation for subprocess and multiprocessing")
    return True
