# servo-rancher
Optune servo driver for Rancher 1.6.

This driver supports adjusting Services deployed via Rancher in a Stack.

A Rancher Stack may contain multiple Services (components in Servo parlance). Each may be
individually modified by the adjust driver. Each service in the Stack is considered a separately
adjustable component.

# USAGE

To describe a Stack:

    ./adjust --describe <stack-name-or-id>

To adjust a Service

    ./adjust <service-name-or-id> < adjust.json

See: [`USAGE-adjust.md`](USAGE-adjust.md) for full documentation.

# CONFIGURATION

## environment

Adjust requires several configuration variables to operate. These can be provided via `config.yaml`
or environment settings. You can either place these into the environment directly, or supply
a file called `.env` in the root directory with adjust.

`.env`
```
OPTUNE_API_URL='http://rancher.api/v2-beta'
OPTUNE_API_KEY=myrancherapikey
OPTUNE_API_SECRET=myranchersecretkey
OPTUNE_PROJECT=Default
OPTUNE_STACK=my-stack
OPTUNE_CONFIG=an *optional* path to a config.yaml file
```

There is also a [`sample_config.yaml`](sample_config.yaml) file which you can tweak as needed.
If provided, the yaml file takes precidence over the environment variables. If the file is named
`config.yaml` and coxists with adjust, it will automatically be loaded.

## `config.yaml`

### Auto Discovered settings

For each service of the stack, the following settings are *automatically* available when
`adjust --describe` is run:

* `cpu`: number of reserved cores
* `mem`: memory reservation for the service
* `replicas`: number of service instances

### Environment Settings

In addition, an *optional* configuration file may be used to define which environment variables
can be modified. By default, **NO** environment variables may be changed.

The `environment` settings is a whitelist hash of the environment variables adjust is allowed to
modify. It is a strict replace of the current value, no substring matching currently occurs.
However, if the configuration provides a `units` key/value as part of the variable description,
integer values passed during an `adjust` operation will automatically be converted from Gb into the
provided units.

For example, a `config.yaml` configured with:

    MEMORY:
        units: M

Will convert an adjust JSON:

    MEMORY: 2

Into:

    MEMORY: 2048M

All of these settings will be returned when calling `adjust --describe`. Each maps to a
[`launchConfig`](https://rancher.com/docs/rancher/v1.6/en/api/v2-beta/api-resources/launchConfig/)
setting of the matching container as follows:


* `cpu` (int) -> `vcpu`
* `mem` (int) -> `memoryMb`
* `replicas` (int) -> `count`
* `environment` (map) -> `environment`

### Exclusions

A service may be excluded from operation by having an `exclude` key provided within its key/value
set. If a service is configured as such, it will be ignored upon an `adjust` if it is requested.

In addition, if a `launchConfig` `label` has been configed with `com.opsani.exclude` it will be
excluded, even if it does not have a matching `exclude` tag in the `config.yaml`.

See [`sample_config.yaml`](sample_config.yaml) for an example configuration.


## `adjust.json`

To perform an adjust, a JSON file must be supplied on STDIN. The format should be similar to other
adjust.json files.

An adjust *may* list multiple services within it. But it **must** define the service to upgrade
otherwise no upgrade will take place.

Adjust is called by providing the service name and passing JSON on stdin.

    adjust service < adjust.json

The service hash should include key/values from those defined above
(`cpu`, `mem`, `replicas`, `environment`). The first three keys should have integer values.
If environment is passed, any keys within that hash must be included in a supplied `config.yaml` or
they will be ignored.

The following sample configures the `front` service to have a single cpu and sets the `MEMORY`
environment variable to 1Gb.
```
{
    "front": {
        "cpu": 1
        "environment": {
            "MEMORY": 1
        }
    }
}
```

See [`http-test.json`](http-test.json) for an example configuration.

# TESTING

## Setting up a test enviornment

The simplest Rancher 1.6 environment is a single node non-HA configuration launched as a Docker
container.  Install docker on a current Linux system (we recommend Ubuntu 18.04 LTS), possibly
using the bash script from Docker:

```
bash <(curl -sL https://get.docker.com)
```

Note that if you continue to use a "default" user other than root, you will also want to provide
that user with docker access (e.g. for the "ubuntu" default user):

```
sudo usermod -aG docker ubuntu
```
Or use any other method that is appropriate to your operating system.

Then simply launch the Rancher service:

```
sudo docker run -d --restart=unless-stopped -p 8080:8080 rancher/server
```

At this point, you should have Rancher running on your server on port 8080 (make sure you open port
8080 on any server associated security-group or firewall settings).  But this is not enough, you
will also need to add a host to the Rancher environment in order to launch a service.  And the
simplest approach is to launch the rancher agent on the same host that his running the rancher
server, and for testing purposes this should be adequate.  There is one glitch that needs to be
resolved. In order for the rancher agent to start properly, the /etc/resolv.conf file needs to be
overwritten if it contains a pointer to the 127.0.0.0/8 network, as is currently being done in many
of the latest linux operating systems.  In order to remedy this, do the following:

```
sudo rm /etc/resolv.conf
echo nameserver 8.8.8.8 | sudo tee -  /etc/resolv.conf
```

Then you can go to the hosts page in the Rancher UI and copy the docker run command to add the host
to the system. Note that if you are running behind a firewall/NAT gateway (e.g. in Amazon) you will
need to use the public address for the host as the target for your connection request. Depending on
your gateway configuration, you may be able to discover this address with a curl request like:

```
curl -4 icanhazip.com
```

In addition to the host configuration, the system does not have user authentication enabled
initially.  For the test enviornment, we recommend using the Local configuration option
(Admin->Authentication) and creating an admin user with a password.

And finally, we need to enable the secrets service (this is a plugin for Rancher available in the
application catalog), and create and set the API key and the key and secret secrets. To load the
Secrets plugin, select the Catalog->Library from the UI. Then search for Secrets and then "select"
and "launch" the Secrets service.

Now we can create and distribute secrets to our services.  Before we do that, we need to create a
new API Key and Secret pair, which is available via the UI at API->Keys.  Create a secret pair
called servo-secret, and then note the Key and Secret.

*NOTE*: the Secret is only available in this display window and is not recorded in an accessible
location after being displayed.

Finally we can create the secrets that our servo will read. Select Infrastructure->Secrets from the
UI.  Then select Add Secret, and create a secret called api_key, and add the API key value to this
secret.  Do the same for a secret called api_secret, but install the API secret in this key.

## Launch a Test App - opsani co-http

The Opsani test app co-http can be used to provide a test target for the Opsani Optune engine within
the rancher environment. And a docker_compose and rancher_compose file are provided in the example
directory to support launching the application directly (the app can also be defined and deployed
manually).

To launch the app, select the Stacks->User from the UI, and then select Add Stack. Provide a name
(e.g. http-test) for the stack, and then either copy and paste the contents of the
docker_compose.yml and rancher_compose.yml into the respective sections of the UI, or browse to the
examples directory and upload the file contents. Select Create to build out the test app.

Note that the default service created is available on port 8090, and it will only be available on
the local rancher host unless a port mapping, security group rule, or filrewall ACL is applied to
make this port available in most cloud based VM environments (e.g. AWS).

A quick check can be made to ensure that the application is running by running a curl command on the
local Rancher host:

curl http://localhost:8090/?call=http%3A%2F%2Fback%3A8080%2F%3Fbusy%3D40\&busy=10


# DEVELOPMENT SETUP

Simple instructions if you want to set up a local development environment:

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r ./requirements.txt
```

