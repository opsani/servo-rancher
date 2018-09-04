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
There is also a `sample_config.yaml` file which you can tweak as needed. If provided, the yaml file
takes precidence over the environment variables.


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
                "template": "GC: '-XX:+UsePArallelGC -XX:ParallelGCThreads={{parameter}}'"
            },
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
    "http-slb": {}
}
```

## Adjust the 'front' service

```
$ ./adjust front < http-test.json
```
