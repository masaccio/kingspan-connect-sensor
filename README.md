# kingspan-connect-sensor

[![build:](https://github.com/masaccio/kingspan-connect-sensor/actions/workflows/run-all-tests.yml/badge.svg)](https://github.com/masaccio/kingspan-connect-sensor/actions/workflows/run-all-tests.yml)
[![codecov](https://codecov.io/gh/masaccio/kingspan-connect-sensor/branch/main/graph/badge.svg?token=EKIUFGT05E)](https://codecov.io/gh/masaccio/kingspan-connect-sensor)
[![PyPI Version](https://badge.fury.io/py/kingspan-connect-sensor.svg)](https://badge.fury.io/py/kingspan-connect-sensor)

API to get oil tank from [Kingspan SENSiT sensors](https://www.kingspan.com/gb/en-gb/products/tank-monitoring-systems/remote-tank-monitoring/sensit-smart-wifi-tank-level-monitoring-kit).

To make use of the API, you will need the credentials you used to register with the App. You do not need other details such as the tank ID as these are already associated with your account. The new KNECT Pro service is supported only from version 4.0.

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
    tank_capacity = await tanks[0].capacity
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
history = await tanks[0].history()
df = pd.DataFrame(history)
```

The `history` method takes optional parameters `start_date` and `end_date` which are `datetime.datetime` objects specifying the range of dates to query from the API.

## Supported APIs

The package supports both the new JSON API used by the KNECT Pro app introduced in February 2026, and the legacy SOAP API. You can select the appropriate API using the `api_version` parameter passed to the `SensorClient` and `AsyncSensorClient` constructors. Valid version options are `APIVersion.CONNECT_V1` and `APIVersion.KNECT_V1`.

**NOTE:** as of March 2026, the `APIVersion.KNECT_V1` API uses HTTP without any password encryption as the TLS endpoint is unavailable.

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

## Analytics and Forecasting

The package includes an optional `analysis` module to help calculate tank usage rates and forecast when the tank will be empty. This logic is decoupled from the core client to keep basic data fetching lightweight, and it processes the naive datetimes returned directly by the API.

```python
from connectsensor import AsyncSensorClient, APIVersion
from connectsensor.analysis import (
    calculate_forecast_empty,
    calculate_usage_rate,
    filter_history,
)

async with AsyncSensorClient(version=APIVersion.KNECT_V1) as client:
    await client.login("test@example.com", "s3cret")
    tanks = await client.tanks
    
    # Fetch the raw history points
    history = await tanks[0].history()
    
    # Filter the data down to the last 14 days
    recent_history = filter_history(history, usage_window=14)
    
    # Calculate the average daily usage (litres/day)
    rate = calculate_usage_rate(recent_history)
    
    # Estimate the number of days until the tank is empty
    days_left = calculate_forecast_empty(recent_history, rate)
    
    print(f"Usage rate: {rate:.1f} L/day")
    print(f"Estimated days to empty: {days_left} days")
```

### Analysis Utilities

* `filter_history(history, usage_window)`: Filters the raw history array to the specified number of days and sorts it chronologically.
* `calculate_usage_rate(history)`: Calculates the average daily usage in litres. This function automatically detects and ignores tank refills so they do not artificially skew your usage average.
* `calculate_forecast_empty(history, rate)`: Estimates the number of days until the tank reaches 0 litres based on the most recent tank level and the calculated usage rate.
* `TankData`: The `connectsensor.analysis` module also exports a structured `TankData` dataclass, which is highly useful for downstream consumers like Home Assistant integrations that need to bundle the raw attributes and these calculated forecasts into a single object.
