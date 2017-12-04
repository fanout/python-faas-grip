# FaaS GRIP

Author: Justin Karneges <justin@fanout.io>

Function-as-a-service backends are not well-suited for handling long-lived connections, such as HTTP streams or WebSockets, because the function invocations are meant to be short-lived. The FaaS GRIP library makes it easy to delegate long-lived connection management to [Fanout Cloud](https://fanout.io/cloud/). This way, backend functions only need to be invoked when there is connection activity, rather than having to run for the duration of each connection.

This library is intended for use with AWS Lambda and AWS API Gateway. Support for other FaaS backends may be added in the future.

# Setup

Install this module:

```sh
pip install faas-grip
```

Set the `GRIP_URL` environment variable containing your Fanout Cloud settings, of the form:

```
https://api.fanout.io/realm/your-realm?iss=your-realm&key=base64:your-realm-key
```

Next, set up an API and resource in AWS API Gateway to point to your Lambda function, using a Lambda Proxy Integration. If you wish to support WebSockets, be sure to add `application/websocket-events` as a Binary media type.

Finally, edit the Fanout Cloud domain origin server (SSL) to point to the host and port of the AWS API Gateway Invoke URL.

Now whenever an HTTP request or WebSocket connection is made to your Fanout Cloud domain, your Lambda function will be able to control it.

# Usage

## WebSockets

Fanout Cloud converts incoming WebSocket connection activity into a series of HTTP requests to your backend. The requests are formatted using WebSocket-over-HTTP protocol, which this library will parse for you. Call `lambda_get_websocket` with the incoming Lambda event and it'll return a `WebSocketContext` object:

```py
ws = lambda_get_websocket(event)
```

The `WebSocketContext` is a pseudo-socket object. You can call methods on it such as `accept()`, `send()`, `recv()`, and `close()`.

For example, here's a chat-like service that accepts all connection requests, and any messages received are broadcasted out. Clients can choose a nickname by sending `/nick <name>`.

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

        if message.startswith('/nick '):
            nick = message[6:]
            ws.meta['nick'] = nick
            ws.send('nickname set to [%s]' % nick)
        else:
            # send the message to all clients
            nick = ws.meta.get('nick') or 'anonymous'
            publish('room', WebSocketMessageFormat('%s: %s' % (nick, message)))

    return ws.to_response()
```

The while loop is deceptive. It looks like it's looping for the lifetime of the WebSocket connection, but what it's really doing is looping through a batch of WebSocket messages that was just received via HTTP. Often this will be one message, and so the loop performs one iteration and then exits. Similarly, the `ws` object only exists for the duration of the handler invocation, rather than for the lifetime of the connection as you might expect. It may look like socket code, but it's all an illusion. :tophat:

## HTTP streaming

To serve an HTTP streaming connection, respond with `Grip-Hold` and `Grip-Channel` headers:

```py
def handler(event, context):
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'text/plain',
            'Grip-Hold': 'stream',
            'Grip-Channel': 'mychannel'
        },
        'body': 'stream opened, prepare yourself!\n'
    }
```

This will return some initial data to the client and leave the connection open, subscribed to `mychannel`.

To publish data:

```py
from gripcontrol import HttpStreamFormat
from faas_grip import publish

publish('mychannel', HttpStreamFormat('some data\n'))
```

## HTTP long-polling

To hold a request open as a long-polling request, respond with `Grip-Hold` and `Grip-Channel` headers:

```py
def handler(event, context):
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'text/plain',
            'Grip-Hold': 'response',
            'Grip-Channel': 'mychannel'
        },
        'body': 'request timed out\n'
    }
```

This will hang the request until data is published to the channel, or until the request times out. On timeout, the response will be released to the client.

To publish data:

```py
from gripcontrol import HttpResponseFormat
from faas_grip import publish

publish('mychannel', HttpResponseFormat('some data\n'))
```

# Resources

* [Generic Realtime Intermediary Protocol](http://pushpin.org/docs/protocols/grip/)
* [WebSocket-over-HTTP protocol](http://pushpin.org/docs/protocols/websocket-over-http/)
