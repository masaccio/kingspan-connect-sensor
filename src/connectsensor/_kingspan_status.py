import argparse

from connectsensor import SensorClient


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
    client.login(args.username, args.password)

    tanks = client.tanks()
    tank_level = tanks[0].level()

    print(tanks[0].name() + ":")
    print("\tCapacity =", tanks[0].capacity())
    print("\tSerial Number =", tanks[0].serial_number())
    print("\tModel =", tanks[0].model())
    print(
        "\tLevel = {0}% ({1} litres)".format(
            tank_level["LevelPercentage"], tank_level["LevelLitres"]
        )
    )
    print("\tLast Read =", tank_level["ReadingDate"])

    print("\nHistory:")
    print("\t{0:<22} {1:<6} {2:<5}".format("Reading date", "%Full", "Litres"))
    for index, measurement in tanks[0].history().iterrows():
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
