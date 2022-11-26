# kingspan-connect-sensor

[![build:](https://github.com/masaccio/kingspan-connect-sensor/actions/workflows/run-all-tests.yml/badge.svg)](https://github.com/masaccio/kingspan-connect-sensor/actions/workflows/run-all-tests.yml)
[![build:](https://github.com/masaccio/kingspan-connect-sensor/actions/workflows/codeql.yml/badge.svg)](https://github.com/masaccio/kingspan-connect-sensor/actions/workflows/codeql.yml)
<!-- [![codecov](https://codecov.io/gh/masaccio/kingspan-connect-sensor/branch/main/graph/badge.svg?token=EKIUFGT05E)](https://codecov.io/gh/masaccio/kingspan-connect-sensor) -->

API to get oil tank from [Kingspan SENSiT sensors](https://www.kingspan.com/gb/en-gb/products/tank-monitoring-systems/remote-tank-monitoring/sensit-smart-wifi-tank-level-monitoring-kit)

To make use of the API, you will need the credentials you used to register with the App. You do not need other details such as the tank ID as these are already associated with your account.

## Installation

``` bash
python3 -m pip kingspan-connect-sensor
```

## Usage

*NOTE* from version 2.0.0, the API changes to use attributes rather than methods for tank parameters.

Reading documents:

``` python
from connectsensor import SensorClient

client = SensorClient()
client.login("test@example.com", "s3cret")
tanks = client.tanks
tank_level = tanks[0].level
```

The `tanks` method returns a `Tanks` object which can be queried for the status of the specific tank.

## Async Usage

From version 2.0.0, an asyncio verison of the client is available:

``` python
async with AsyncSensorClient() as client:
    await client.login("test@example.com", "s3cret")
    tanks = await client.tanks
    tank_level = await tanks[0].level
    tank_capcity = await tanks[0].capacity
    tank_percent = 100 * (tank_level / tank_percent)
    print(f"Tank is {tank_percent:.1f}% full")
```

## Tanks object

`history` returns a Pandas dataframe with all entries available from the web API, sorted by logging time. There should be one record per day. The dataframe has the following entries:

* `reading_date`: a datetime object indicating the time a measurement was made
* `level_percent`: integer percentage full
* `level_litres`: number of lites in the tank

## Scripts

Reporting on the current status of the tank using `kingspan-status`:

``` bash
% kingspan-status --username=test@example.com --password=s3cret

Home Tank:
 Capacity = 2000
 Serial Number = 20001999
 Model = Unknown
 Level = 90% (1148 litres)
 Last Read = 2021-10-09 00:42:47.947000

History:
 Reading date           %Full  Litres
 30-Jan-2021 00:29      94     1224 
 31-Jan-2021 00:59      80     1040 
 01-Feb-2021 00:29      78     1008 
 02-Feb-2021 00:59      76     986  
```

`kingspan-notifier` can be used to check the status of a tabk and report via email when the tank is likely to run out of oil.

``` bash
% kingspan-notifier --config kingspan.ini
Current level 1148 litres
No notification; 196 days oil remain
```

Command line options include:

* `--config CONFIG`: a config file in ini-format
* `--no-update`: don't update cache with new data (defaults to updating the DB cache)
* `--window WINDOW`: the number of days history to consider (default: 14 days)
* `--notice NOTICE`: the number of days before out-of-oil forecast to warn (default: 14)

An example config file is:

``` ini
[sensit]
username=test@example.com
password=s3cret
cache=/home/me/kingspan.db
start-date=2021-01-31

[smtp]
server=smtp.isp.co.uk
username=ispuser
email=test@example.com
password=smtps3cret
```

The cache is an SQLite database and will be intialised if not present.
