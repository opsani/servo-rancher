#!/usr/bin/env python

from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth
import argparse
import datetime
import errno
import requests
import signal
import sys, json, os
import time
import yaml
import pdb

load_dotenv()

# Remove proxy if set (as it might block or send unwanted requests to the proxy)
if "http_proxy" in os.environ:
    del os.environ['http_proxy']
if "https_proxy" in os.environ:
    del os.environ['https_proxy']

# Client is a partial implementation of the Rancher API
class RancherClient:
    """ """
    # valid mem units: E, P, T, G, M, K, Ei, Pi, Ti, Gi, Mi, Ki
    # nb: 'm' suffix found after setting 0.7Gi
    MUMAP = {"E":-3,  "P":-2,  "T":-1,  "G":0,  "M":1,  "K":2, "m":3}

    # Init can be passed in the API info
    # but if you have the same values in your config, that will override them
    def __init__(self, config=None):
        self.config = config
        self.headers = { 'Content-Type': 'application/json' }
        self.name_mappings = {}      # Cache for human name to rancher id. eg. front = 1s5

    def g_to_unit(self, size, convert_to):
        '''
        Converts a size value in G to another size
        :param size: the size in G of the value to be converted
        :param convert_to: the units to convert to
        :returns: the converted size or the original value if unsupported.
        '''
        for units , power in self.MUMAP.items():
            if convert_to.startswith(units):
                size = ( float(size) * 1024 ** power )
                break
        return float(size) if size < 1 else int(size)

    def names_to_ids(self, response):
        """
        Pulls all names and their related ids into a returned hash
        :param response:
        :returns: hash of name to id mappings
        """
        hash = {}
        for datum in response['data']:
            hash[datum['name']] = datum['id']
        return hash

    def name_to_id(self, name, type, function):
        """
        Given a name looks up the id of that name
        :param name: the name to look up
        :param type: the type of object we are looking up (project/stack/service)
        :param function: an api function to call which will return the list of objects
        :returns: the id requested or the originally requested name (so we support ids as well)
        """
        if name == None:
            return None
        if self.name_mappings.get(type) == None:
            self.name_mappings[type] = self.names_to_ids(function())

        return self.name_mappings[type].get(name, name)

    def project_id(self, name):
        """
        Converts a project name to its id
        :param name: the name of the project
        :returns: the id of the project
        """
        return self.name_to_id(name, 'project', lambda: self.projects())

    def service_id(self, name):
        """
        Converts a service name to its id
        :param name: the name of the service
        :returns: the id of the service
        """
        return self.name_to_id(name, 'service' + self.config.stack, lambda: self.services())

    def stack_id(self, name):
        """
        Converts a stack name to its id
        :param name: the name of the stack
        :returns: the id of the stack
        """
        return self.name_to_id(name, 'stack', lambda: self.stacks())

    def capabilities(self, service_name=None):
        """
        Returns a service's adjustable parameters
        :param service_name:  (Default value = None)
        :returns:: the adjustable parametesrs for the provided service
        """
        service = self.config.services_config.get(service_name, {})
        if service is None:
            service = {}
        merged = {
            'settings': self.config.services_defaults,
            'environment': service.get('environment', {})
        }
        if merged.get('exclude', None) != None:
            return None
        return merged

    def merge(self, source = {}, destination = {}):
        """
        Python's default dict merge is shallow. This is a recursive deep dictionary merge
        :param source:  The dictionary to merge from
        :param destination: The dictionary to merge into
        :returns: a merged hash
        """
        destination = {} if destination is None else destination
        for key, value in source.items():
            if isinstance(value, dict):
                # get node or create one
                node = destination.setdefault(key, {})
                self.merge(value, node)
            else:
                destination[key] = value
        return destination

    def scope_uri(self, base, option=None):
        """
        Constructs a URI if given some options. Most URIs will take /foo and /foo/{id}
        This helper does the right thing if you have an {id} (in the above case) or not
        :param base: The base uri ('/projects')
        :param option: an optional object param (a project id)  (Default value = None)
        :returns: a constrcted URI like /projects/1s5
        """
        if option:
            base = base + '/' + option
        return base

    def projects_uri(self, name=None):
        """
        https://rancher.com/docs/rancher/v1.6/en/api/v2-beta/api-resources/project/
        :param name: the requested project name (Default value = None)
        :param default: if True, will use the configured default project  (Default value = False)
        :returns: the uri to a project
        """
        return self.scope_uri('/projects', self.project_id(name))

    # https://rancher.com/docs/rancher/v1.6/en/api/v2-beta/api-resources/project/
    def projects(self, name=None):
        """
        :param name:  (Default value = None)
        :returns: the project or all projects
        """
        return self.render(self.projects_uri(name))

    def services_uri(self, project_name=None, stack_name=None, name=None):
        """
        :param project_name:  (Default value = None)
        :param name:  (Default value = None)
        :returns: the service or all services
        """
        if project_name == None:
            project_name = self.config.project
        if stack_name == None:
            stack_name = self.config.stack
        prefix = self.projects_uri(project_name) if name else self.stacks_uri(project_name, stack_name)
        return self.scope_uri(prefix + '/services', self.service_id(name))

    def services(self, project_name=None, stack_name=None, name=None, action=None, body=None):
        """
        Allows for querying and upgrading of services.
        https://rancher.com/docs/rancher/v1.6/en/api/v2-beta/api-resources/service/
        :param project_name: Project the service is in (Default value = None)
        :param name: The name of the service (Default value = None)
        :param action: An action to perform on the service (Default value = None)
        :param body: A new launchConfig hash (Default value = None)
        :returns: A dict of the API response.
        """
        if self.excluded(name):
            raise PermissionError('{} is not allowed to be modified due to exclusion rules'.format(name))

        uri = self.services_uri(project_name, stack_name, name)
        if body and action == 'upgrade':
            strategy = self.prepare_service_upgrade(name, body)
            service = self.services(name=name)
            # only try to upgrade if the service is active
            if service.get('state') == 'active':
                self.render(uri, action=action, body=strategy)
            self.wait_for_upgrade(name)

            # this commits
            response = self.services(name=name, action='finishupgrade')
            print("finished")
            # now we can scale the service if needed
            scale_target = self.dig(body, ['settings', 'replicas', 'value'])
            if service.get('scale') != scale_target:
                return self.services(project_name=project_name, stack_name=stack_name, name=name, action=None, body={'id': service.get('id'), 'scale': scale_target})
            else:
                return response
        else:
            return self.render(uri, action, body=body)

    def stacks_uri(self, project_name=None, name=None):
        """
        :param project_name:  (Default value = None)
        :param name:  (Default value = None)
        """
        if project_name == None:
            project_name = self.config.project
        prefix = '' if name else self.projects_uri(project_name)
        return self.scope_uri(self.projects_uri(project_name) + '/stacks', self.stack_id(name))

    # https://rancher.com/docs/rancher/v1.6/en/api/v2-beta/api-resources/stack/
    def stacks(self, project_name=None, name=None, action=None, body=None):
        """
        :param project_name:  (Default value = None)
        :param name:  (Default value = None)
        :param action:  (Default value = None)
        :param body:  (Default value = None)
        """
        uri = self.stacks_uri(project_name, name)
        return self.render(uri, action, body)

    def filter_environment(self, service_name, environment = {}):
        """
        Filters out any environment variables which are not configured in our config.yaml.
        If a config variable has a 'units' option, then it will convert an integer value from
        Gb (servo's base unit) into the requested units.
        :param service_name: The service on which we are working
        :param environment: The launchConfig environment changes (Defaule value = {})
        :returns: An dictionary environment filtred based on our config rules
        """
        allowed_env = self.config.services_config.get(service_name, {}).get('environment', {})

        for key in list(environment.keys()):
            value = allowed_env.get(key, {})
            units = value.get('units') if isinstance(value, dict) else None
            if key not in allowed_env.keys():
                del environment[key]
            elif units:
                size = self.g_to_unit(environment[key], units)
                environment[key] = str(size) + units

        return environment

    def map_servo_to_rancher(self, service):
        """
        Maps servo keys to keys which rancher understands
        {
            "settings": {
                "vcpu": 1
            },
            "environment": {
                "KEY": "VALUE"
            }
        }
        """
        rancher = { 'environment': {} }

        settings = self.dig(service,  ['settings'])
        for setting in settings.keys():
            if setting == 'cpu':
                rancher['vcpu'] = self.dig(settings, [setting, 'value'])
            elif setting == 'replicas':
                rancher['scale'] = self.dig(settings, [setting, 'value'])
            elif setting == 'mem':
                value = self.dig(settings, [setting, 'value'])
                rancher['memoryMb'] = value * 1024 # convert mem GiB into memoryMb
            else:
                rancher['environment'][setting] = self.dig(settings, [setting, 'value'])


        return rancher

    def prepare_service_upgrade(self, service_name, body):
        """
        Builds a request for the service upgrade call.
        https://rancher.com/docs/rancher/v1.6/en/api/v2-beta/api-resources/service/#upgrade
        :param service_name: The name of the service to upgrade
        :param body: dictionary of the upgrade options
        :raises: PermissionError if the service is labelled 'com.opsani.exclude'
        :returns: A dictionary for the proper inService upgrade and launchConfig
        """
        if not body:
            return {}

        service = self.services(name=service_name)
        launchConfig = service.get('launchConfig', {})

        if 'com.opsani.exclude' in launchConfig.get('labels', {}).keys():
            raise PermissionError('{} is not allowed to be modified due to exclusion rules'.format(service_name))

        body = self.map_servo_to_rancher(body)
        body['environment'] = self.filter_environment(service_name, body.get('environment', {}))

        mergedLaunchConfig = self.merge(body, launchConfig)

        return {'inServiceStrategy': {
                'type': 'inServiceUpgradeStrategy',
                'batchSize': 1,
                'intervalMillis': 2000,
                'startFirst': False,
                'launchConfig': mergedLaunchConfig,
                'secondaryLaunchConfigs': [] } }

    def handle_signal(self, signum, frame):
        """
        Handles interrupts during upgrade. Will gracefully cancel an upgrade.
        :param signum: The signal which happened
        :param frame: The memory frame in which it happened
        """
        service_locals = frame.f_locals.get('service', {})
        service_id = service_locals.get('id')
        self.print({ 'message': 'cancelling operation on service {}'.format(service_id), 'state': 'Cancelling' })
        self.cancel_upgrade(service_id)

    def cancel_upgrade(self, service_id):
        """
        Gracefully cancel an upgrade, then rollback. Will avoid double cancellations. Provides
        progress messages to stdin. Upon rollback, the process will exit.
        https://rancher.com/docs/rancher/v1.6/en/api/v2-beta/api-resources/service/#cancelupgrade
        https://rancher.com/docs/rancher/v1.6/en/api/v2-beta/api-resources/service/#rollback
        :param service_id: Service id whose upgrade should be cancelled
        """
        service = self.services(name=service_id)
        state = service.get('state')

        # don't cancel again if we're already cancelling
        if state != 'canceled-upgrade':
            self.services(name=service_id, action='cancelupgrade')

        while state != 'canceled-upgrade' and state != 'active':
            service = self.services(name=service_id)
            state = service.get('state')
            self.print({
                'progress': 0,
                'message': 'cancelling operation on service {}'.format(service_id),
                'state': state })

        self.services(name=service_id, action='rollback')
        exit(1)

    def wait_for_upgrade(self, service_name):
        """
        Wait until the service is fully upgraded. Provides updates to STDIN. Allows cancellation
        upon interrupt.
        :param service_name: Name of the service upgrading
        """
        signal.signal(signal.SIGUSR1, self.handle_signal)
        signal.signal(signal.SIGINT, self.handle_signal)

        idx = 0
        state = 'upgrade'
        while state != 'upgraded' and state != 'active':
            service = self.services(name=service_name)
            state = service.get('state')
            message = "Transition: {}; Health: {}".format(
                service.get('transitioningMessage', ''),
                service.get('healthState')),
            self.print({
                "progress": idx*5,
                "message": message,
                "msg_index": idx,
                "stage": state})
            idx += 1

            # in case the service was in the middle of a cancellation when we started
            if state == 'canceled-upgrade':
                self.cancel_upgrade(service_name)

            time.sleep(2)

    def dig(self, dict, keys):
        for key in keys:
            value = dict.get(key, None)
            if value is None:
                return {}
            else:
                dict = value
        return value

    def describe_environment(self, service):
        launch_env = self.dig(service, ['launchConfig', 'environment'])
        environment = self.dig(self.capabilities(service.get('name')), ['environment'])
        response = {}
        for key in environment:
            response[key] = environment.get(key, {})
            response[key]['value'] = launch_env.get(key)
        return self.pop_none(response)

    def pop_none(self, dict):
        if dict is None:
            return None
        for key in list(dict.keys()):
            if dict.get(key, {}).get('value') is None:
                dict.pop(key)
        return dict if dict else None

    def describe_settings(self, service):
        launch_config = self.dig(service, ['launchConfig'])
        response = {}
        for key in self.config.services_defaults:
            servo_key = self.config.rancher_to_servo.get(key, key)
            response[servo_key] = self.config.services_defaults[key]
            if key == 'scale':
                val = service[key]
            else:
                val = launch_config[key]
            if key == 'memoryMb' and val is not None:
                val = val / 1024 # convert from memoryMb to mem in GiB
            response[servo_key]['value'] = val
        return self.pop_none(response)

    def describe(self, stack_name=None):
        """
        Describes the services in a stack based on (possibly) provided parameters
        :param stack_name:  (Default value = None)
        :returns: the modifiable parameters.
        """
        response = {}
        stack = self.services(stack_name = stack_name)
        for service in stack.get('data', []):
            svc_name = service.get('name')
            if self.excluded(svc_name):
                continue
            response[svc_name] = {
                'settings': self.merge(self.describe_settings(service), self.describe_environment(service))
            }
        return { 'application': { 'components': response} }

    def excluded(self, svc_name):
        return self.dig(self.config.services_config, [svc_name, 'exclude'])

    def render(self, uri, action=None, body=None):
        """
        Render is the workhorse. It takes a URI and optional action or body
        If there is an action, a POST is made to the URI for that action
        If there is a body, a POST is made to the URI with that body
        If there is neither, a GET is made to the URI
        In all cases, we return a dict of the JSON response (even on errors)
        Upon exception, it will print an error message and exit.
        Possible Actions:
        * activateservices
        * cancelrollback
        * cancelupgrade
        * deactivateservices
        * exportconfig
        * finishupgrade
        * rollback

        :param uri: to operate on
        :param action: suggests a POST operation  (Default value = None)
        :param body: suggests a PUT operation (Default value = None)
        :returns: the API response as a dict
        """
        url = self.config.api_url + uri

        auth = (self.config.access_key, self.config.secret_key)

        if action:
            url = url + '?action=' + action
            print("POST {}".format(url), file=sys.stderr) # DEBUG URL info to stderr
            #self.print(body, file=sys.stderr)
            response = requests.post(url, json=body, auth=auth, headers=self.headers)
        elif body:
            print("PUT {}".format(url), file=sys.stderr) # DEBUG URL info to stderr
            self.print(body)
            response = requests.put(url, json=body, auth=auth, headers=self.headers)
        else:
            print("GET {}".format(url), file=sys.stderr) # DEBUG URL info to stderr
            response = requests.get(url, auth=auth, headers=self.headers)

        # check for error and report/terminate if failed
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as http_error:
            print("Rachner API call failed, status code {}, response:\n---\n{}\n---\n".format(
                response.status_code, response.text), file=sys.stderr)
            try:
                message = json.loads(response.text)['message']
            except Exception:
                message = response.text     # cannot be parsed as JSON, treat as text
            error = { 'error': response.status_code, 'class': 'failure', 'message': message }
            self.print(error)
            sys.exit(3)

        # try to parse response, report error if it fails
        try:
            data = json.loads(response.text)
        except Exception as e:
            message = "Failed to parse Rancher API response as JSON: {}\nContents:\n---\n{}\n---\n".format(str(e), response.text)
            print(message, file=sys.stderr)
            error = { 'error': 500, 'class': 'failure', 'message': message }
            self.print(error)
            sys.exit(3)

        return data

    def print(self, data, file=sys.stdout):
        """
        Helper to print out a dict payload
        :param data:
        :param file:  (Default value = sys.stdout)
        Note that each payload must be printed on a single line, so no indent/pretty print allowed
        """
        print(json.dumps(data, sort_keys=True), file=file)

class RancherConfig:
    """
    Handles configuration for the Client.
    The client needs to know the API connection information. This can come from
    * config.yaml
    * a secrets file (in the case of the API Key and API Secret)
    * an environment variable
    Precedence is in the order of config.yaml > secret file > environment variable.
    """
    def __init__(self):
        self.access_key = self.read_key('/var/secrets/api_key', 'OPTUNE_API_KEY')
        self.secret_key = self.read_key('/var/secrets/api_secret', 'OPTUNE_API_SECRET')

        conf = self.read_config(os.getenv('OPTUNE_CONFIG', 'config.yaml'))
        self.access_key = conf.get('api_key', self.access_key)
        self.secret_key = conf.get('api_secret', self.secret_key)
        self.api_url = conf.get('api_url', os.getenv('OPTUNE_API_URL'))
        self.project = conf.get('project', os.getenv('OPTUNE_PROJECT'))
        self.stack = conf.get('stack', os.getenv('OPTUNE_STACK'))
        self.services_config = conf.get('services', {})
        self.rancher_to_servo = { 'vcpu': 'cpu', 'memoryMb': 'mem', 'scale': 'replicas' }
        self.services_defaults = { 'vcpu': { 'min': 0.1, 'max': 3.5, 'type': 'range' },
                                   'memoryMb': { 'min': 0.25, 'max': 4, 'type': 'range'},
                                   'scale': { 'min': 1, 'max': 10, 'type': 'range' } }

        # append Rancher API endpoint
        assert not self.api_url.endswith('v2-beta'), "Rancher API URL must not contain the v2-beta endpoint string"
        if not self.api_url.endswith('/'):
            self.api_url += '/'
        self.api_url += 'v2-beta'


    def read_config(self, filename):
        """
        Reads a YAML configuration file.
        :param filename:
        :returns: the configuration as a dict.
        """
        try:
            with open(filename, 'r') as stream:
                return yaml.safe_load(stream)['rancher']
        except IOError as e:
            if e.errno == errno.ENOENT:
                return {}
            raise ConfigError("cannot read configuration from {}:{}".format(config, e.strerror))
        except yaml.error.YAMLError as e:
            raise ConfigError("syntax error in {}: {}".format(config, str(e)))

    def read_key(self, filename, default_env=None):
        """
        Attempts to read a config key from a file. The first line of the file should be the key
        the user wants to read.
        :param filename: The location of the file
        :param default_env: An environment variable to default to (Default value = None)
        :returns: the suggested key
        """
        try:
            file = open(filename, 'r')
            return file.readline().rstrip('\n')
        except:
            return os.getenv(default_env)

# Basic CLI for client.py
class RancherClientCli:
    """ """
    def pull_data_objects(self, data):
        """
        :param data:
        """
        hash = {}
        for datum in data['data']:
            hash[datum['name']] = datum['id']
        return hash

    def env_data(self, data, capabilities):
        """
        :param data:
        :param capabilities:
        """
        hash = {}
        for capability in capabilities.keys():
            hash[capability] = data.get(capability, capabilities[capability])
        return hash

    def handle_command(self, id, function, keys):
        """
        :param id:
        :param function:
        :param keys:
        """
        try:
            r = function(id)
        except (Exception) as e:
            print(e, file=sys.stderr)
            print(json.dumps({"error":e.__class__.__name__, "class":"failure", "message":str(e)}))
            sys.exit(3)

        if id == None: # List names
            return self.pull_data_objects(r)
        elif len(keys) == 0:
            return r
        else:
            hash = {}
            for key in keys:
                hash[key] = r.get(key)
            return hash

    def __init__(self, *args, **kwargs):
        self.config = RancherConfig()
        self.client = RancherClient(self.config)

        self.parser = argparse.ArgumentParser(description='Adjust Rancher Stack Settings')
        self.parser.add_argument('--projects', nargs='?', help='List projects with no args or the projects stacks with args.', action='append')
        self.parser.add_argument('--stacks', nargs='?', help='List stacks with no args or the stacks services with args.', action='append')
        self.parser.add_argument('--services', nargs='?', help='List services with no args or the services instances with args.', action='append')

    def run(self):
        """ """
        args = self.parser.parse_args()
        if args.projects:
            r = self.handle_command(args.projects[0], lambda id :self.client.projects(id), ['id', 'name', 'data'])
            self.client.print(r)
        elif args.services:
            r = self.handle_command(args.services[0], lambda id :self.client.services(name=id), ['id', 'name', 'launchConfig'])
            self.client.print(r)
        elif args.stacks:
            r = self.handle_command(args.stacks[0], lambda id :self.client.stacks(name=id), ['id', 'name', 'serviceIds'])
            self.client.print(r)
        else:
            self.parser.print_help()

if __name__ == "__main__":
    cli = RancherClientCli()
    cli.run()
