"""快速验证 AmazingData 登录配置。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv


def main() -> int:
    """登录并立即登出；成功返回 0，失败返回 1。"""
    project_root = Path(__file__).resolve().parents[1]
    load_dotenv(project_root / ".env")

    required = ("AD_USERNAME", "AD_PASSWORD", "AD_HOST", "AD_PORT")
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        missing_names = ", ".join(missing)
        print(
            f"Missing required environment variables: {missing_names}",
            file=sys.stderr,
        )
        return 1

    try:
        port = int(os.environ["AD_PORT"])
    except ValueError:
        print("AD_PORT must be an integer", file=sys.stderr)
        return 1

    username = os.environ["AD_USERNAME"]
    password = os.environ["AD_PASSWORD"]
    host = os.environ["AD_HOST"]

    try:
        from AmazingData.login.tgw_login import login, logout

        login(username, password, host, port)
    except Exception as error:
        message = str(error)
        for secret in (password, username, host):
            if secret:
                message = message.replace(secret, "<REDACTED>")
        print(
            f"AmazingData login FAILED ({type(error).__name__}): {message}",
            file=sys.stderr,
        )
        return 1

    try:
        logout(username)
    except Exception as error:
        error_type = type(error).__name__
        print(
            f"AmazingData login succeeded, but logout FAILED ({error_type})",
            file=sys.stderr,
        )
        return 1

    print("AmazingData login OK (logged out)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
