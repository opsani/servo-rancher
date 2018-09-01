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
## These elements are required
# Config group for rancher based adjust driver
rancher:
# Rancher Environment(UI) or Project(API) name
  project: "Default"
# Target Rancher Stack name
  stack: "http-test"
## These elements are optional
# API key - if not passed as a secret via rancher (api_key)
  api_key: "api_key"
# API secret key - if not passed as a secret via rancher (api_secret)
  api_secret: "api_secret"
# Default parameters for any otherwise undefined resource
  default:
    environment:
      MEMORY:
        min: 4096
        max: 16384
        step: 64
# Template parameter to define transformation needed between Optune and end device
        template: "{{name|toupper}}: '{{parameter}}M'"
# Docker standard parameters would be set in the "compose" section
    container:
# Options are cpu, memory, and replicas
      cpu:
        min: 500
# Service section for specific service targets/hints
  service:
# Name of service is also the group key
    front:
# Parameter section to modify, allowed values are 'environment' and 'compose'
      environment:
# Example to highlight another templated environment variable
        GC:
          template: "{{name}}: '-XX:+UsePArallelGC -XX:ParallelGCThreads={{parameter}}'"
# Services to exclude
    http-slb:
      exclude: true
```

NOTE: MEMORY environment variable defines the java Memory allocation, and will inform the minimum memory available in the reservation parameter if both are present by including a 20% overhead above the MEMORY parameter for the memory-reservation.

Limitations:
- works on default "docker compose" scale, compute, and memory parameters
- it is currently possible to pass one environment variable: MEMORY

# Testing:

## Setting up a test enviornment

The simplest Rancher 1.6 environment is a single node non-HA configuration launched as a Docker container.  Install docker on a current Linux system (we recommend Ubuntu 18.04 LTS), possibly using the bash script from Docker:

```
bash <(curl -sL https://get.docker.com)
```

Note that if you continue to use a "default" user other than root, you will also want to provide that user with docker access (e.g. for the "ubuntu" default user):

```
sudo usermod -aG docker ubuntu
```
Or use any other method that is appropriate to your operating system.

Then simply launch the Rancher service:

```
sudo docker run -d --restart=unless-stopped -p 8080:8080 rancher/server
```

At this point, you should have Rancher running on your server on port 8080 (make sure you open port 8080 on any server associated security-group or firewall settings).  But this is not enough, you will also need to add a host to the Rancher environment in order to launch a service.  And the simplest approach is to launch the rancher agent on the same host that his running the rancher server, and for testing purposes this should be adequate.  There is one glitch that needs to be resolved. In order for the rancher agent to start properly, the /etc/resolv.conf file needs to be overwritten if it contains a pointer to the 127.0.0.0/8 network, as is currently being done in many of the latest linux operating systems.  In order to remedy this, do the following:

```
sudo rm /etc/resolv.conf
echo nameserver 8.8.8.8 | sudo tee -  /etc/resolv.conf
```

Then you can go to the hosts page in the Rancher UI and copy the docker run command to add the host to the system. Note that if you are running behind a firewall/NAT gateway (e.g. in Amazon) you will need to use the public address for the host as the target for your connection request. Depending on your gateway configuration, you may be able to discover this address with a curl request like:

```
curl -4 icanhazip.com
```

In addition to the host configuration, the system does not have user authentication enabled initially.  For the test enviornment, we recommend using the Local configuration option (Admin->Authentication) and creating an admin user with a password.

And finally, we need to enable the secrets service (this is a plugin for Rancher available in the application catalog), and create and set the API key and the key and secret secrets. To load the Secrets plugin, select the Catalog->Library from the UI. Then search for Secrets and then "select" and "launch" the Secrets service.

Now we can create and distribute secrets to our services.  Before we do that, we need to create a new API Key and Secret pair, which is available via the UI at API->Keys.  Create a secret pair called servo-secret, and then note the Key and Secret.

*NOTE*: the Secret is only available in this display window and is not recorded in an accessible location after being displayed.

Finally we can create the secrets that our servo will read. Select Infrastructure->Secrets from the UI.  Then select Add Secret, and create a secret called api_key, and add the API key value to this secret.  Do the same for a secret called api_secret, but install the API secret in this key.

## Launch a Test App - opsani co-http

The Opsani test app co-http can be used to provide a test target for the Opsani Optune engine within the rancher environment. And a docker_compose and rancher_compose file are provided in the example directory to support launching the application directly (the app can also be defined and deployed manually).

To launch the app, select the Stacks->User from the UI, and then select Add Stack. Provide a name (e.g. http-test) for the stack, and then either copy and paste the contents of the docker_compose.yml and rancher_compose.yml into the respective sections of the UI, or browse to the examples directory and upload the file contents. Select Create to build out the test app.

Note that the default service created is available on port 8090, and it will only be available on the local rancher host unless a port mapping, security group rule, or filrewall ACL is applied to make this port available in most cloud based VM environments (e.g. AWS).

A quick check can be made to ensure that the application is running by running a curl command on the local Rancher host:

curl http://localhost:8090/?call=http%3A%2F%2Fback%3A8080%2F%3Fbusy%3D40\&busy=10
