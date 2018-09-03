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

load_dotenv()

# Remove proxy if set (as it might block or send unwanted requests to the proxy)
if "http_proxy" in os.environ:
    del os.environ['http_proxy']
if "https_proxy" in os.environ:
    del os.environ['https_proxy']

# Client is the base class which just does queries
class Client:
    # Init can be passed in the API info
    # but if you have the same values in your config, that will override them
    def __init__(self, config=None):
        self.config = config
        self.headers = {}
        self.headers['Content-Type'] = 'application/json'
        self.name_mappings = {}

    def names_to_ids(self, response):
        hash = {}
        for datum in response['data']:
            hash[datum['name']] = datum['id']
        return hash

    def name_to_id(self, name, key, function):
        if name == None:
            return None
        if self.name_mappings.get(key) == None:
            self.name_mappings[key] = self.names_to_ids(function())

        return self.name_mappings[key].get(name, name)

    def project_id(self, name):
        return self.name_to_id(name, 'project', lambda: self.projects())

    def service_id(self, name):
        return self.name_to_id(name, 'service', lambda: self.services())

    def stack_id(self, name):
        return self.name_to_id(name, 'stack', lambda: self.stacks())

    # This method will return what a caller may be able to do based on the
    # initialized configuration. It only supports service overrides.
    def capabilities(self, service_name=None):
        merged = self.merge(
            self.config.services_defaults.copy(),
            self.config.services.get(service_name, {}))
        if merged.get('exclude', None) != None or service_name in self.config.excluded:
            return {}
        return merged

    # Recursive deep dictionary merge
    def merge(self, source, destination):
        for key, value in source.items():
            if isinstance(value, dict):
                # get node or create one
                node = destination.setdefault(key, {})
                self.merge(value, node)
            else:
                destination[key] = value
        return destination

    # constructs a URI if given some options
    # most URIs will take /foo and /foo/{id}
    # this helper does the right thing if you have an {id} (in the above case) or not
    def scope_uri(self, base, option=None, delim='/'):
        if option:
            base = base + delim + option
        return base

    # https://rancher.com/docs/rancher/v1.6/en/api/v2-beta/api-resources/apiKey/
    def uuid(self, uuid):
        uri = self.scope_uri('/apiKey', uuid, '?uuid=')
        return self.render(uri)

    # https://rancher.com/docs/rancher/v1.6/en/api/v2-beta/api-resources/account/
    def accounts(self, name=None):
        uri = self.scope_uri('/accounts', name, '?name=')
        return self.render(uri)

    def projects_uri(self, name=None, default=False):
        if default and name == None:
            name = self.config.project
        return self.scope_uri('/projects', self.project_id(name))

    # https://rancher.com/docs/rancher/v1.6/en/api/v2-beta/api-resources/project/
    def projects(self, name=None):
        return self.render(self.projects_uri(name))

    def services_uri(self, project_name=None, name=None):
        return self.scope_uri(self.projects_uri(project_name, True) + '/services', self.service_id(name))

    def prepare_service_upgrade(self, service_name, body):
        service = self.services(name=service_name)
        launchConfig = service.get('launchConfig', {})
        launchConfig = self.merge(launchConfig, body)
        return {'inServiceStrategy': {
                'type': 'inServiceUpgradeStrategy',
                'batchSize': 1,
                'intervalMillis': 2000,
                'startFirst': False,
                'launchConfig': launchConfig,
                'secondaryLaunchConfigs': [] } }

    def handle_signal(self, signum, frame):
        service_locals = frame.f_locals.get('service')
        service_id = service_locals.get('id')
        self.print({ 'message': 'cancelling operation on service {}'.format(service_id), 'state': 'Cancelling' })
        self.cancel_upgrade(service_id)

    # We've detected we need to cancel. Gracefully wait for the cancel to complete, then rollback.
    def cancel_upgrade(self, service_id):
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

    # Wait until the service is fully upgraded
    def wait_for_upgrade(self, service_name):
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

    # https://rancher.com/docs/rancher/v1.6/en/api/v2-beta/api-resources/service/
    def services(self, project_name=None, name=None, action=None, body=None):
        uri = self.services_uri(project_name, name)
        if body:
            body = self.prepare_service_upgrade(name, body)
            action = 'upgrade'
            service = self.services(name=name)
            # only try to upgrade if the service is active
            if service.get('state') == 'active':
                self.render(uri, action, body)
            self.wait_for_upgrade(name)

            # this commits
            return self.services(name=name, action='finishupgrade')
        return self.render(uri, action)

    def stacks_uri(self, project_name=None, name=None):
        return self.scope_uri(self.projects_uri(project_name, True) + '/stacks', self.stack_id(name))

    # https://rancher.com/docs/rancher/v1.6/en/api/v2-beta/api-resources/stack/
    def stacks(self, project_name=None, name=None, action=None, body=None):
        uri = self.stacks_uri(project_name, name)
        return self.render(uri, action, body)

    def instances(self, project_name=None, service_name=None, name=None, action=None, body=None):
        uri = self.scope_uri(self.services_uri(project_name, service_name) + '/instances', name)
        return self.render(uri, action, body)

    # Describes what launchConfig parameters can be tweaked for the given stack
    def describe(self, stack_name=None):
        if stack_name == None:
            stack_name = self.config.stack
        response = {}
        stack = self.stacks(name=stack_name)
        for service_id in stack.get('serviceIds'):
            service = self.services(name=service_id)
            svc_name = service.get('name')
            response[svc_name] = {}
            capabilities = self.capabilities(svc_name)
            for capability in capabilities:
                response[svc_name][capability] = capabilities.get(capability)
        return response

    # Render is the workhorse. It takes a URI and optional action or body
    # if there is an action, a POST is made to the URI for that action
    # if there is a body, a PUT is made to the URI with that body
    # if there is neither, a GET is made to the URI
    # in all cases, we return a dict of the JSON response (even on errors)
    #
    # Possible Actions:
    #   * activateservices
    #   * cancelrollback
    #   * cancelupgrade
    #   * deactivateservices
    #   * exportconfig
    #   * finishupgrade
    #   * rollback
    def render(self, uri, action=None, body=None):
        url = self.config.api_url + uri

        auth = (self.config.access_key, self.config.secret_key)

        if action:
            url = url + '?action=' + action
            print("POST {}".format(url), file=sys.stderr) # DEBUG URL info to stderr
            #self.print(body, file=sys.stderr)
            response = requests.post(url, json=body, auth=auth, headers=self.headers)
        elif body:
            print("PUT {}".format(url), file=sys.stderr) # DEBUG URL info to stderr
            response = requests.put(url, json=body, auth=auth, headers=self.headers)
        else:
            print("GET {}".format(url), file=sys.stderr,) # DEBUG URL info to stderr
            response = requests.get(url, auth=auth, headers=self.headers)

        data = json.loads(response.text)
        try:
            response.raise_for_status()
            return data
        except requests.exceptions.HTTPError as http_error:
            self.print(response.status_code)
            self.print(data, file=sys.stderr)
            error = { 'error': response.status_code, 'class': 'failure', 'message:': data.get('message') }
            self.print(error)
            sys.exit(3)

    # Helper to print out a dict payload
    def print(self, data, file=sys.stdout):
        print(json.dumps(data, sort_keys=True, indent=4), file=file)

class Config:
    def __init__(self):
        self.access_key = self.read_key('/var/secrets/api_key', 'OPTUNE_API_KEY')
        self.secret_key = self.read_key('/var/secrets/api_secret', 'OPTUNE_API_SECRET')

        conf = self.read_config(os.getenv('OPTUNE_CONFIG', 'config.yaml'))
        self.access_key = conf.get('api_key', self.access_key)
        self.secret_key = conf.get('api_secret', self.secret_key)
        self.api_url = conf.get('api_url', os.getenv('OPTUNE_API_URL'))
        self.project = conf.get('project', os.getenv('OPTUNE_PROJECT'))
        self.stack = conf.get('stack')
        self.services = conf.get('service', {})
        self.services_defaults = self.services.get('defaults', {
            'environment': None,
            'cpu': None,
            'memory': None,
            'scale': None } )
        self.excluded = conf.get('excluded', [])

    def read_config(self, filename):
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
        try:
            file = open(filename, 'r')
            return file.readline().rstrip('\n')
        except:
            return os.getenv(default_env)

# Basic CLI for client.py
if __name__ == "__main__":
    def pull_data_objects(data):
        hash = {}
        for datum in data['data']:
            hash[datum['name']] = datum['id']
        return hash

    def env_data(data, capabilities):
        hash = {}
        for capability in capabilities.keys():
            hash[capability] = data.get(capability, capabilities[capability])
        return hash

    def handle_command(id, function, keys):
        try:
            r = function(id)
        except (Exception) as e:
            print(e, file=sys.stderr)
            print(json.dumps({"error":e.__class__.__name__, "class":"failure", "message":str(e)}))
            sys.exit(3)

        if id == None: # List names
            return pull_data_objects(r)
        elif len(keys) == 0:
            return r
        else:
            hash = {}
            for key in keys:
                hash[key] = r.get(key)
            return hash

    config = Config()
    client = Client(config)

    parser = argparse.ArgumentParser(description='Adjust Rancher Stack Settings')
    parser.add_argument('--projects', nargs='?', help='List projects with no args or the projects stacks with args.', action='append')
    parser.add_argument('--stacks', nargs='?', help='List stacks with no args or the stacks services with args.', action='append')
    parser.add_argument('--services', nargs='?', help='List services with no args or the services instances with args.', action='append')
    parser.add_argument('--service', help='Used with instances to print the instances of a service.')
    parser.add_argument('--instances', nargs='?', help='List services with no args or the services instances with args.', action='append')

    args = parser.parse_args()
    if args.projects:
        r = handle_command(args.projects[0], lambda id :client.projects(id), ['id', 'name', 'data'])
        client.print(r)
    elif args.services:
        r = handle_command(args.services[0], lambda id :client.services(name=id), ['id', 'name', 'launchConfig'])
        client.print(r)
    elif args.stacks:
        r = handle_command(args.stacks[0], lambda id :client.stacks(name=id), ['id', 'name', 'serviceIds'])
        client.print(r)
    elif args.instances:
        instance_id = args.instances[0]
        r = handle_command([args.service, instance_id], lambda ids :client.instances(service_name=ids[0], name=ids[1]), [])
        if instance_id == None: # List instance names
            r = pull_data_objects(r)
        else:
            r = env_data(r['data'][0], client.capabilities(args.service))
        client.print(r)
    else:
        parser.print_help()
