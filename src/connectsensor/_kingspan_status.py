"""CLI script to retrieve and print Kingspan tank status."""

import argparse
import logging
import sys
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from datetime import datetime

from connectsensor import (
    APIVersion,
    KingspanAPIError,
    KingspanInvalidCredentialsError,
    SensorClient,
)


class PasswordFilter(logging.Filter):  # pylint: disable=too-few-public-methods
    """Filter to redact passwords from log messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Replace the word password with secret in log records."""
        record.msg = record.msg.replace("password", "secret")
        return True


def enable_debug_logging() -> None:
    """Configure and enable debug logging."""
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(levelname)s:%(name)s:%(message)s")
    handler.setFormatter(formatter)
    handler.addFilter(PasswordFilter())
    logger = logging.getLogger("connectsensor")
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    logger.propagate = False


def main() -> None:
    """Run the Kingspan status CLI."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--username",
        required=True,
        help="Kingspan account email address",
    )
    parser.add_argument("--password", required=True, help="Kingspan account password")
    parser.add_argument(
        "--api-version",
        choices=APIVersion.__members__.keys(),
        default="KNECT_V1",
        help="Which API to use from Kingspan (default: KNECT_V1)",
    )
    parser.add_argument("--debug", action="store_true")

    args = parser.parse_args()

    if args.debug:
        enable_debug_logging()

    client = SensorClient(APIVersion[args.api_version])
    try:
        client.login(args.username, args.password)
    except KingspanInvalidCredentialsError:
        print("Authentication Failed: invalid username or password", file=sys.stderr)
        sys.exit(1)
    except KingspanAPIError as e:
        print(f"Kingspan API error: {e}", file=sys.stderr)
        sys.exit(1)

    for tank in client.tanks:
        tank_level_percent = str(int(100 * tank.level / tank.capacity))

        print(f"{tank.name}:")
        print(f"\tCapacity = {tank.capacity}")
        print(f"\tSerial Number = {tank.serial_number}")
        print(f"\tModel = {tank.model}")
        print(f"\tLevel = {tank_level_percent}% ({tank.level} litres)")
        print(f"\tLast Read = {tank.last_read}")

        print("\nHistory:")
        print(f"\t{'Reading date':<22} {'%Full':<6} {'Litres':<5}")
        for _, measurement in enumerate(tank.history()):
            reading_date = cast("datetime", measurement["reading_date"])
            date_str = reading_date.strftime("%d-%b-%Y %H:%M")
            level_pct = measurement["level_percent"]
            level_litres = measurement["level_litres"]

            print(f"\t{date_str:<22} {level_pct:<6} {level_litres:<5}")


if __name__ == "__main__":  # pragma: no cover
    # execute only if run as a script
    main()
