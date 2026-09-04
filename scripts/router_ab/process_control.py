"""Bounded CLI execution in an owned POSIX process group."""

import os
import signal
import subprocess


def _signal_group(pid, signum):
    try:
        os.killpg(pid, signum)
    except ProcessLookupError:
        pass


def run_process(command, *, input, timeout, env=None, cleanup_timeout=1.0):
    """Capture text output; on timeout terminate descendants and retain partial streams.

    The new session makes the child's PID its process-group ID. Signals target
    only that group, even if the wrapper exits before its native child. Children
    that deliberately leave the group are outside this lifecycle guarantee.
    """
    if os.name != "posix":
        raise OSError("Owned process-group execution requires POSIX")
    with subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        start_new_session=True,
    ) as process:
        try:
            stdout, stderr = process.communicate(input=input, timeout=timeout)
        except subprocess.TimeoutExpired:
            _signal_group(process.pid, signal.SIGTERM)
            try:
                stdout, stderr = process.communicate(timeout=cleanup_timeout)
            except subprocess.TimeoutExpired as partial:
                stdout, stderr = partial.output, partial.stderr
            finally:
                # A descendant can close its pipes and outlive the wrapper.
                # Always signal the group, not only when communicate times out.
                _signal_group(process.pid, signal.SIGKILL)
            try:
                stdout, stderr = process.communicate(timeout=cleanup_timeout)
            except subprocess.TimeoutExpired as partial:
                stdout, stderr = partial.output, partial.stderr
                # Do not wait on pipes inherited by a process outside our group.
                process.stdout.close()
                process.stderr.close()
                process.wait(timeout=cleanup_timeout)
            raise subprocess.TimeoutExpired(command, timeout, output=stdout, stderr=stderr) from None
        except BaseException:
            _signal_group(process.pid, signal.SIGKILL)
            process.wait(timeout=cleanup_timeout)
            raise
        return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
