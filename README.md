# kingspan-connect-sensor

API to get oil tank from [Kingspan SENSiT sensors](https://www.kingspan.com/gb/en-gb/products/tank-monitoring-systems/remote-tank-monitoring/sensit-smart-wifi-tank-level-monitoring-kit)

To make use of the API, you will need the credentials you used to register with the App. You do not need other details such as the tank ID as these are already associated with your account.

## Installation

```
python3 -m pip kingspan-connect-sensor
```

## Usage

Reading documents:

``` python
from connectsensor import SensorClient

client = SensorClient()
client.login("test@example.com", "s3cret")
tanks = client.tanks()
```

The `tanks` method returns a `Tanks` object which can be queried for the status of the specific tank.

## Tanks object

`history` returns a Pandas dataframe with all entries available from the web API, sorted by logging time. There should be one record per day. The dataframe has the following entries:

* `reading_date`: a datetime object indicating the time a measurement was made
* `level_percent`: integer percentage full
* `level_litres`: number of lites in the tank

## Scripts

Reporting on the curren status of the tank using `kingspan-status`:

```
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

```
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

```
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