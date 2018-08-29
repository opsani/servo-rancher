# servo-k8s
Optune servo driver for Rancher (v1.6)

This driver supports an application deployed via Rancher as a Stack.

A Rancher Stack may contain multiple containers, each of which may individually be modified by the adjust driver.
Each container in the Stack is considered a separately adjustable component.

For each component of the application, the following settings are automatically available when 'adjust --info' is run:
* scale (number of container instances)
* memory reservation
* milli-cpu reservation
* environment variables

A configuration file must be present to define scale of variable modification config.yaml, any custom component settings in it are also returned by 'adjust --info' and map to environment variables of the matching container.

Currently the following parameters are supported:

environment variables:
* MEMORY: defines the java heap size in Kilobytes

"Docker Compose" variables:
* cpu-reservation: millicpu share of the CPU resources
* memory-reservation: memory reserved reserved in bytes/1024 (scale parameter will adjust)

The following is an example config.yaml document, with examples of the available settings:
```
rancher:
  mode:
  project: "Default"
  default:
    environment:
      MEMORY:
        min: 4096
        max: 16384
        step: 64
        scale: M
    compose:
      memory-reservation:
        min: 4096
        max: 16384
        step: 256
        multiplier: '1024'
      scale:
        min: 1
        max: 10
        step: 1

  stack:
    name: "http-test"
    service:
      all:
        envrionment:
          MEMORY:
            min: 4096
            max: 16384
            step: 64
            scale: M
        compose:
          cpu-reservation:
            min: 50
            max: 2000
            step: 50
          memory-reservation:
            min: 4096
            max: 16384
            step: 256
            multiplier: '1024'
          scale:
            min: 1
            max: 10
            step: 1
      excluded:
        - front-slb
      front:
        environment:
          MEMORY:
            min: 4096
            max: 16384
            step: 64
            scale: M
          GC:
            values:
              Serial:
                -XX:+UseSerialGC
              Parallel:
                -XX:+UsePArallelGC -XX:ParallelGCThreads=10
              CMS:
                -XX:+UseConcMarkSweepGC -XX:+UseParNewGC -XX:+CMSParallelRemarkEnabled -XX:CMSInitiatingOccupancyFraction=50 -XX:+UseCMSInitiatingOccupancyOnly
              G1:
                -XX:+UnlockExperimentalVMOptions -XX:+UseG1GC
        compose:
          memory-reservation:
            min: 4096
            max: 16384
            step: 256
            multiplier: '1024'
          scale:
            min: 1
            max: 10
            step: 1
      back:
        environment:
          MEMORY:
            min: 4096
            max: 16384
            step: 64
            scale: M
        compose:
          cpu-reservation:
            min: 50
            max: 2000
            step: 50
          scale:
            min: 1
            max: 10
            step: 1
```

NOTE: MEMORY environment variable defines the java Memory allocation, and will inform the minimum memory available in the reservation parameter if both are present by including a 20% overhead above the MEMORY parameter for the memory-reservation.

Limitations:
- works on default "docker compose" compute and memory parameters
- it is currently possible to pass one environment variable: memory
- GARBAGECOLLECTOR variable is not available, but will initially only support change in type, not internal values
