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

    tanks = client.tanks
    tank_level = tanks[0].level
    tank_level_percent = str(int(100 * tanks[0].level / tanks[0].capacity))

    print(tanks[0].name + ":")
    print(f"\tCapacity = {tanks[0].capacity}")
    print(f"\tSerial Number = {tanks[0].serial_number}")
    print(f"\tModel = {tanks[0].model}")
    print(f"\tLevel = {tank_level_percent}% ({tanks[0].level} litres)")
    print(f"\tLast Read = {tanks[0].last_read}")

    print("\nHistory:")
    print("\t{0:<22} {1:<6} {2:<5}".format("Reading date", "%Full", "Litres"))
    for index, measurement in tanks[0].history.iterrows():
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
