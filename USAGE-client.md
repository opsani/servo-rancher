## List all projects

```
$ ./client.py --projects
http://rancher.kumulus.co:8080/v1/projects
{
    "Default": "1a5"
}
```

## List project information

```
$ ./client.py --projects 1a5
http://rancher.kumulus.co:8080/v1/projects
http://rancher.kumulus.co:8080/v1/projects/1a5
{
    "data": {
        "fields": {
            "createdStackIds": [
                1,
                2,
                3,
                4
            ],
            "orchestration": "cattle",
            "servicesPortRange": {
                "endPort": 65535,
                "startPort": 49153
            },
            "startedStackIds": [
                1,
                2,
                3,
                4
            ]
        }
    },
    "id": "1a5",
    "name": "Default"
}
```

## List all services for the configured project

```
$ ./client.py --services
http://rancher.kumulus.co:8080/v1/projects
http://rancher.kumulus.co:8080/v1/projects/1a5/services
{
    "back": "1s9",
    "cni-driver": "1s2",
    "front": "1s8",
    "healthcheck": "1s3",
    "http-slb": "1s11",
    "ipsec": "1s5",
    "metadata": "1s6",
    "network-manager": "1s1",
    "scheduler": "1s4",
    "secrets-driver": "1s7"
}
```

## List all instances for a given service

```
$ ./client.py --services front
http://rancher.kumulus.co:8080/v1/projects
http://rancher.kumulus.co:8080/v1/projects/1a5/services
http://rancher.kumulus.co:8080/v1/projects/1a5/services/1s8
{
    "id": "1s8",
    "instanceIds": [
        "1i30"
    ],
    "name": "front"
}
```

## List instance information

```
$ ./client.py --instances front 1i30
http://rancher.kumulus.co:8080/v1/projects
http://rancher.kumulus.co:8080/v1/projects/1a5/services
http://rancher.kumulus.co:8080/v1/projects/1a5/services/1s8/instances/front
{
    "compose": {
        "cpu": {
            "min": 500
        }
    },
    "environment": {
        "MEMORY": "2048M"
    }
}
```

## List default capabilities

```
$ ./client.py --capabilities
{
    "compose": {
        "cpu": {
            "min": 500
        }
    },
    "environment": {
        "MEMORY": {
            "max": 16384,
            "min": 4096,
            "step": 64,
            "template": "MEMORY: '{{parameter}}M'"
        }
    }
}
```

## List capabilities for a service

```
$ ./client.py --capabilities front
{
    "compose": {
        "cpu": {
            "min": 500
        }
    },
    "environment": {
        "GC": {
            "template": "GC: '-XX:+UsePArallelGC -XX:ParallelGCThreads={{parameter}}'"
        },
        "MEMORY": {
            "max": 16384,
            "min": 4096,
            "step": 64,
            "template": "MEMORY: '{{parameter}}M'"
        }
    }
}
```

## List capabilities for a service which is excluded

```
$ ./client.py --capabilities http-slb
{}
```
