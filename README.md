# FaaS GRIP

Author: Justin Karneges <justin@fanout.io>

Function-as-a-service backends are not well-suited for handling long-lived connections (such as HTTP streaming or WebSockets) because the function invocations are meant to be short-lived. The FaaS GRIP library is useful for delegating long-lived connection management to Fanout Cloud. This way, the backend function can be invoked to handle events such as new incoming connections or WebSocket messages, without having to remain running for the entire duration of each connection.

Currently the only FaaS backend supported is Amazon Lambda.

## Install

You can install from PyPi:

```sh
pip install faas-grip
```

Or from this repository:

```sh
python setup.py install
```

# Sample usage

Set the `GRIP_URL` environment variable containing Fanout Cloud settings, of the form:

```
https://api.fanout.io/realm/your-realm?iss=your-realm&key=base64:your-realm-key
```

Next, set up an API and resource in AWS API Gateway to point to your Lambda function, using a Lambda Proxy Integration, and add `application/websocket-events` as a Binary media type.

Finally, edit the Fanout Cloud domain origin server (SSL) to point to the host and port of the AWS API Gateway Invoke URL.

Now your backend function will be able to handle requests proxied from Fanout Cloud as well as publish data to be relayed out to listening clients.

For example, here is a service that accepts all WebSocket connection requests, and any messages received are broadcasted to all connections:

```py
from gripcontrol import WebSocketMessageFormat
from faas_grip import lambda_get_websocket, publish

def handler(event, context):
    try:
        ws = lambda_get_websocket(event)
    except ValueError:
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'text/plain'},
            'body': 'Not a WebSocket-over-HTTP request\n'
        }

    # if this is a new connection, accept it and subscribe it to a channel
    if ws.is_opening():
        ws.accept()
        ws.subscribe('room')

    # here we loop over any messages
    while ws.can_recv():
        message = ws.recv()

        # if return value is None, then the connection is closed
        if message is None:
            ws.close()
            break

        # send the message to all clients
        publish('room', WebSocketMessageFormat(message))

    return ws.to_response()
```

The while loop is deceptive. It looks like it's looping for the lifetime of the WebSocket connection, but what it's really doing is looping through a batch of WebSocket messages that was just received via HTTP. Often this will be one message, and so the loop performs one iteration and then exits. Similarly, the `ws` object only exists for the duration of the handler invocation, rather than for the lifetime of the connection as you might expect. It may look like socket code, but it's all an illusion. :tophat:

# Resources

* [Generic Realtime Intermediary Protocol](http://pushpin.org/docs/protocols/grip/)
* [WebSocket-over-HTTP protocol](http://pushpin.org/docs/protocols/websocket-over-http/)
