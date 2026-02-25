import argparse
import sys

from connectsensor import KingspanAPIError, KingspanInvalidCredentials, SensorClient


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--username", required=True, help="Kingspan account email address"
    )
    parser.add_argument("--password", required=True, help="Kingspan account password")
    parser.add_argument("--debug", action="store_true")

    args = parser.parse_args()

    if args.debug:  # pragma: no branch
        import connectsensor.debug  # noqa: F401, PLC0415

    client = SensorClient()
    try:
        client.login(args.username, args.password)
    except KingspanInvalidCredentials:
        print("Authentication Failed: invalid username or password", file=sys.stderr)
        sys.exit(1)
    except KingspanAPIError as e:
        print(f"Unknown API error: {e}", file=sys.stderr)
        sys.exit(1)

    for tank in client.tanks:
        tank_level_percent = str(int(100 * tank.level / tank.capacity))

        print(tank.name + ":")
        print(f"\tCapacity = {tank.capacity}")
        print(f"\tSerial Number = {tank.serial_number}")
        print(f"\tModel = {tank.model}")
        print(f"\tLevel = {tank_level_percent}% ({tank.level} litres)")
        print(f"\tLast Read = {tank.last_read}")

        print("\nHistory:")
        print("\t{0:<22} {1:<6} {2:<5}".format("Reading date", "%Full", "Litres"))
        for _, measurement in enumerate(tank.history):
            print(
                "\t{0:<22} {1:<6} {2:<5}".format(
                    measurement["reading_date"].strftime("%d-%b-%Y %H:%M"),
                    measurement["level_percent"],
                    measurement["level_litres"],
                )
            )


if __name__ == "__main__":
    # execute only if run as a script
    main()
