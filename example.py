import argparse

from connectsensor import SensorClient


parser = argparse.ArgumentParser()
parser.add_argument('--username', required=True,
                    help='Kingspan account email address')
parser.add_argument('--password', required=True,
                    help='Kingspan account password')
parser.add_argument('--debug', action='store_true')

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
print("\tModel =", tanks[0].serial_number())
print("\tLevel = {0}% ({1} litres)".format(tank_level['LevelPercentage'], tank_level['LevelLitres']))
print("\tLast Read =", tank_level['ReadingDate'])

print("\nHistory:")
print(tanks[0].history())
