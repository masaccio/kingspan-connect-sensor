# kingspan-connect-sensor

[![build:](https://github.com/masaccio/kingspan-connect-sensor/actions/workflows/run-all-tests.yml/badge.svg)](https://github.com/masaccio/kingspan-connect-sensor/actions/workflows/run-all-tests.yml)
[![build:](https://github.com/masaccio/kingspan-connect-sensor/actions/workflows/codeql.yml/badge.svg)](https://github.com/masaccio/kingspan-connect-sensor/actions/workflows/codeql.yml)
<!-- [![codecov](https://codecov.io/gh/masaccio/kingspan-connect-sensor/branch/main/graph/badge.svg?token=EKIUFGT05E)](https://codecov.io/gh/masaccio/kingspan-connect-sensor) -->

API to get oil tank from [Kingspan SENSiT sensors](https://www.kingspan.com/gb/en-gb/products/tank-monitoring-systems/remote-tank-monitoring/sensit-smart-wifi-tank-level-monitoring-kit)

To make use of the API, you will need the credentials you used to register with the App. You do not need other details such as the tank ID as these are already associated with your account. 

The new KNECT Pro service is supported only from version 4.0.

## Installation

``` bash
python3 -m pip kingspan-connect-sensor
```

## Usage

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

As of version 3.0, `history` no longer returns a Pandas dataframe to simplify package dependencies. Instead, an list of dicts is returned, where each list element is a sample from the web API, sorted by logging time. There should be one record per day. Each dict has the following keys:

* `reading_date`: a datetime object indicating the time a measurement was made
* `level_percent`: integer percentage full
* `level_litres`: number of lites in the tank

You can construct a Pandas dataframe simply using:

``` python
tanks = await client.tanks
history = await tanks[0].history
df = pd.DataFrame(history)
```

## Scripts

As of version 4.0, the notifier and export script have been removed as integrations like Home Assistant provide much better functionality. Reporting on the current status of the tank can still be performed `kingspan-status`:

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