## Configuration

You need to supply the configuration to adjust to get going. It doesn't need a config.yaml but it
does need environment settings. You can either place these into the environment directly, or supply
an file called `.env` in the root directory with adjust.

.env
```
OPTUNE_API_URL='http://rancher.api/v2-beta'
OPTUNE_API_KEY=myrancherapikey
OPTUNE_API_SECRET=myranchersecretkey
OPTUNE_PROJECT=Default
OPTUNE_CONFIG=an *optional* path to a config.yaml file
```
There is also a [`sample_config.yaml`](sample_config.yaml) file which you can tweak as needed.
If provided, the yaml file takes precidence over the environment variables.


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
$ ./adjust --describe http-test
{
    "back": {
        "environment": {
            "MEMORY": {
                "max": 16384,
                "min": 512,
                "step": 64,
                "template": "MEMORY: '{{parameter}}M'"
            }
        },
        "memoryMb": {
            "max": 16384,
            "min": 512,
            "step": 64
        },
        "vcpu": {
            "max": 10,
            "min": 1
        }
    },
    "front": {
        "environment": {
            "GC": {
                "template": "GC: '-XX:+UsePArallelGC -XX:ParallelGCThreads=10'"
            },
            "MEMORY": {
                "max": 16384,
                "min": 512,
                "step": 64,
                "template": "MEMORY: '1024M'"
            }
        },
        "memoryMb": {
            "max": 16384,
            "min": 512,
            "step": 64
        },
        "vcpu": {
            "max": 10,
            "min": 1
        }
    },
    "http-slb": {}
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
GET http://rancher.kumulus.co:8080/v2-beta/projects/1a5/services/1s13
{
    "message": [
        "Transition: In Progress; Health: degraded"
    ],
    "msg_index": 5,
    "progress": 25,
    "stage": "upgrading"
}
GET http://rancher.kumulus.co:8080/v2-beta/projects/1a5/services/1s13
{
    "message": [
        "Transition: In Progress; Health: initializing"
    ],
    "msg_index": 7,
    "progress": 35,
    "stage": "upgrading"
}
GET http://rancher.kumulus.co:8080/v2-beta/projects/1a5/services/1s13
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
GET http://rancher.kumulus.co:8080/v2-beta/projects/1a5/services/1s13
{
    "message": "cancelling operation on service 1s13",
    "progress": 0,
    "state": "canceling-upgrade"
}
GET http://rancher.kumulus.co:8080/v2-beta/projects/1a5/services/1s13
{
    "message": "cancelling operation on service 1s13",
    "progress": 0,
    "state": "canceled-upgrade"
}
```
