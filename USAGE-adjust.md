
## Help

```
$ ./adjust
usage: adjust [-h] [--version] [--info] [--describe [DESCRIBE]] [stackname]

Adjust Rancher Stack Settings

positional arguments:
  stackname             Name of the stack to update. Pass a capability.json
                        file to update that stack.

optional arguments:
  -h, --help            show this help message and exit
  --version             Print the current version
  --info                Print version and capabilities in JSON.
  --describe [DESCRIBE]
                        Describe actions which can be performed on a stack.
```

## List version

```
$ ./adjust --version
0.1
```

## List info

```
$ ./adjust --info
{"version": "0.1", "has_cancel": true}
```

## Describe stack

```
$ ./adjust --describe
{
    "back": {
        "cpu": {
            "value": 2
        },
        "environment": {
            "value": {}
        },
        "mem": {
            "value": 3.0
        },
        "replicas": {
            "value": 2
        }
    },
    "front": {
        "cpu": {
            "value": 1
        },
        "environment": {
            "value": {
                "GC": "-XX:+UseSerialGC",
                "MEMORY": "1024M"
            }
        },
        "mem": {
            "value": 2.0
        },
        "replicas": {
            "value": 1
        }
    },
    "http-slb": {
        "cpu": {
            "value": null
        },
        "environment": {
            "value": {}
        },
        "mem": {
            "value": null
        },
        "replicas": {
            "value": 1
        }
    }
}
```

## Adjust the 'front' service

```
$ ./adjust front < http-test.json
{
    "message": [
        "Transition: In Progress; Health: healthy"
    ],
    "msg_index": 0,
    "progress": 0,
    "stage": "upgrading"
}
{
    "message": [
        "Transition: In Progress; Health: degraded"
    ],
    "msg_index": 5,
    "progress": 25,
    "stage": "upgrading"
}
{
    "message": [
        "Transition: In Progress; Health: initializing"
    ],
    "msg_index": 7,
    "progress": 35,
    "stage": "upgrading"
}
{
    "message": [
        "Transition: None; Health: healthy"
    ],
    "msg_index": 8,
    "progress": 40,
    "stage": "upgraded"
}
```

## Adjust service with a SIGINT
```
$ ./adjust front < http-test.json
{
    "message": [
        "Transition: In Progress; Health: healthy"
    ],
    "msg_index": 0,
    "progress": 0,
    "stage": "upgrading"
}
### INTERRUPTED HERE
{
    "message": "cancelling operation on service 1s13",
    "state": "Cancelling"
}
{
    "message": "cancelling operation on service 1s13",
    "progress": 0,
    "state": "canceling-upgrade"
}
{
    "message": "cancelling operation on service 1s13",
    "progress": 0,
    "state": "canceling-upgrade"
}
{
    "message": "cancelling operation on service 1s13",
    "progress": 0,
    "state": "canceled-upgrade"
}
```
