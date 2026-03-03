# API is HTTP and sends the username and password in the clear
API_SERVER = "sensorapi.connectsensor.com"
API_PORT = 8087
API_BASE_URL = f"http://{API_SERVER}:{API_PORT}"

HTTP_UNAUTHORIZED = 401

# The JWT appears to be hard-coded into the application rather than securely returned
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJUaGVNb2JpbGVBcHAiLCJyb2xlIjoiVGhlTW9iaWxlQXBwIiwiZXhwIjoxNzg2ODk4NTM3LCJpc3MiOiJTZW5zb3JBUEkgQXV0aFNlcnZlciIsImF1ZCI6IlNlbnNvckFQSSBVc2VycyJ9.PW-NP46vP9pP5Da87KIzsN6ZWIA3vOI4XbqxHWVuTOY"  # noqa: E501, S105, cspell:disable-line
