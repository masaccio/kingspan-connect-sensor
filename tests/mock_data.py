from datetime import datetime

VALID_STATUS = [
    "TestTank:",
    "Capacity = 2000",
    "Serial Number = 20001000",
    "Model = TestModel",
    "Level = 50% (1000 litres)",
    "Last Read = 2021-01-31 00:59:30.987000",
    "",
    "History:",
    "Reading date           %Full  Litres",
    "25-Jan-2021 13:59      100    2000",
    "27-Jan-2021 00:59      95     1900",
    "29-Jan-2021 00:59      94     1880",
    "30-Jan-2021 00:29      94     1880",
    "31-Jan-2021 00:59      92     1840",
    "",
]

USERNAME = "test@example.com"
PASSWORD = "s3cret"

VALID_DATA = [
    [datetime(2021, 1, 25, 13, 59, 14), 100, 2000],
    [datetime(2021, 1, 27, 0, 59, 16), 95, 1900],
    [datetime(2021, 1, 29, 0, 59, 22), 94, 1880],
    [datetime(2021, 1, 30, 0, 29, 30), 94, 1880],
    [datetime(2021, 1, 31, 0, 59, 30), 92, 1840],
]

NEW_TEST_DATA = [datetime(2021, 1, 1, 13, 0, 0), 100, 2000]
