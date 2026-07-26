import argparse
import os
import sys
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def _environment_key(job: str) -> str:
    return f"MONITORING_PING_URL_{job.upper().replace('-', '_')}"


def _event_url(base_url: str, event: str) -> str:
    parsed = urlsplit(base_url)
    if parsed.scheme != "https" and not (
        parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
    ):
        raise ValueError("monitoring ping URL must use HTTPS (HTTP is allowed only for loopback)")
    if not parsed.netloc or parsed.username or parsed.password:
        raise ValueError("monitoring ping URL must be an absolute URL without userinfo")
    suffix = {"start": "/start", "success": "", "failure": "/fail"}[event]
    return base_url.rstrip("/") + suffix


def report(job: str, event: str, *, timeout: float = 10) -> bool:
    base_url = os.getenv(_environment_key(job))
    if not base_url:
        return False
    target = _event_url(base_url, event)
    request = Request(target, data=b"", method="POST", headers={"User-Agent": "family-hub-monitor/1"})
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - URL is administrator-controlled configuration
        if not 200 <= response.status < 300:
            raise RuntimeError(f"monitoring endpoint returned HTTP {response.status}")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Report a systemd job event to an optional monitoring ping URL")
    parser.add_argument("--job", required=True)
    parser.add_argument("--event", choices=("start", "success", "failure"))
    parser.add_argument("--result", help="systemd SERVICE_RESULT; success maps to a success ping")
    arguments = parser.parse_args()
    event = arguments.event or ("success" if arguments.result == "success" else "failure")
    try:
        report(arguments.job, event)
    except (OSError, RuntimeError, URLError, ValueError) as error:
        print(f"Monitoring ping failed for {arguments.job}: {type(error).__name__}", file=sys.stderr)


if __name__ == "__main__":
    main()
