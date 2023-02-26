import argparse
import sys

from connectsensor import SensorClient, APIError


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--username", required=True, help="Kingspan account email address"
    )
    parser.add_argument("--password", required=True, help="Kingspan account password")
    parser.add_argument("--debug", action="store_true")

    args = parser.parse_args()

    if args.debug:
        import connectsensor.debug

    client = SensorClient()
    try:
        client.login(args.username, args.password)
    except APIError as e:
        if "Authentication Failed" in str(e):
            print(
                "Authentication Failed: invalid username or password", file=sys.stderr
            )
        else:  # pragma: no cover
            print("Unknown API error:", e.value, file=sys.stderr)
        sys.exit(1)

    for tank in client.tanks:
        tank_level = tank.level
        tank_level_percent = str(int(100 * tank.level / tank.capacity))

        print(tank.name + ":")
        print(f"\tCapacity = {tank.capacity}")
        print(f"\tSerial Number = {tank.serial_number}")
        print(f"\tModel = {tank.model}")
        print(f"\tLevel = {tank_level_percent}% ({tank.level} litres)")
        print(f"\tLast Read = {tank.last_read}")

        print("\nHistory:")
        print("\t{0:<22} {1:<6} {2:<5}".format("Reading date", "%Full", "Litres"))
        for index, measurement in tank.history.iterrows():
            print(
                "\t{0:<22} {1:<6} {2:<5}".format(
                    measurement.reading_date.strftime("%d-%b-%Y %H:%M"),
                    measurement.level_percent,
                    measurement.level_litres,
                )
            )


if __name__ == "__main__":
    # execute only if run as a script
    main()
