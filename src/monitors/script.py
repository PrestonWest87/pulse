import subprocess
import time
from src.monitors import BaseMonitor, MonitorResult, register_monitor


@register_monitor
class ScriptMonitor(BaseMonitor):
    type_id = "script"
    name = "Script/Command"
    description = "Run an arbitrary command or script and check the exit code and output"
    config_schema = {
        "command": {"type": "string", "label": "Command to run", "required": True},
        "expected_exit_code": {"type": "number", "label": "Expected exit code", "default": 0, "required": False},
        "timeout": {"type": "number", "label": "Timeout (seconds)", "default": 30, "required": False},
        "check_stdout": {"type": "string", "label": "Text to find in stdout (optional)", "required": False},
    }

    def check(self) -> MonitorResult:
        command = self.config.get("command", "")
        expected_code = int(self.config.get("expected_exit_code", 0))
        timeout = int(self.config.get("timeout", 30))
        check_stdout = self.config.get("check_stdout", "")

        if not command:
            return MonitorResult(status="error", error="No command configured")

        try:
            start = time.time()
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=timeout
            )
            elapsed = (time.time() - start) * 1000

            stdout = result.stdout.strip()
            stderr = result.stderr.strip()
            summary = stdout[:200] if stdout else (stderr[:200] if stderr else f"Exit code {result.returncode}")

            if result.returncode != expected_code:
                return MonitorResult(
                    status="down",
                    response_time_ms=round(elapsed, 1),
                    error=f"Exit code {result.returncode} (expected {expected_code})",
                    response_summary=summary
                )

            if check_stdout and check_stdout not in stdout:
                return MonitorResult(
                    status="degraded",
                    response_time_ms=round(elapsed, 1),
                    error=f"Expected text '{check_stdout}' not found in stdout",
                    response_summary=summary
                )

            return MonitorResult(
                status="up",
                response_time_ms=round(elapsed, 1),
                response_summary=summary
            )
        except subprocess.TimeoutExpired:
            return MonitorResult(status="down", error=f"Command timed out after {timeout}s")
        except Exception as e:
            return MonitorResult(status="error", error=str(e))
