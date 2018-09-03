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
