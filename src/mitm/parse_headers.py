from bs4 import BeautifulSoup

def response(flow):
    server, port = flow.server_conn.address
    # Ignore Azure Service Bus calls to kconnectproductionnamespace
    if server != 'www.connectsensor.com':
        return None

    print("URL " +flow.request.url)
    print(flow.request.method + " " + flow.request.path + " " + flow.request.http_version)

    print("-"*50 + "request headers:")
    for k, v in flow.request.headers.items():
        print("%-20s: %s" % (k, v))
    print("-"*50 + "XML request:")
    print(BeautifulSoup(flow.request.content, "xml").prettify())

    print("-"*50 + "response headers:")
    for k, v in flow.response.headers.items():
        print("%-20s: %s" % (k, v))
    print("-"*50 + "XML response:")
    print(BeautifulSoup(flow.response.content, "xml").prettify())
