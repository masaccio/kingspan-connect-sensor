def response(flow):
    def banner(s: str) -> None:
        print("-" * 50, s)

    server, port = flow.server_conn.address
    if "connectsensor.com" not in server:
        return

    print(f"SERVER: {server}:{port}")

    print(f"URL: {flow.request.url}")
    print(
        flow.request.method + " " + flow.request.path + " " + flow.request.http_version
    )

    banner("Request headers:")
    for k, v in flow.request.headers.items():
        print("%-20s: %s" % (k, v))
    banner("Request:")
    print(flow.request.content)

    banner("Response headers:")
    for k, v in flow.response.headers.items():
        print("%-20s: %s" % (k, v))
    banner("JSON response:")
    print(flow.response.content)
    banner("End of request")
