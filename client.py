#!/usr/bin/env python

from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth
import argparse
import datetime
import requests
import sys, json, os
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

    # https://rancher.com/docs/rancher/v1.6/en/api/v2-beta/api-resources/service/
    def services(self, project_name=None, name=None, action=None, body=None):
        uri = self.services_uri(project_name, name)
        return self.render(uri, action, body)

    def stacks_uri(self, project_name=None, name=None):
        return self.scope_uri(self.projects_uri(project_name, True) + '/stacks', self.stack_id(name))

    # https://rancher.com/docs/rancher/v1.6/en/api/v2-beta/api-resources/stack/
    def stacks(self, project_name=None, name=None, action=None, body=None):
        uri = self.stacks_uri(project_name, name)
        return self.render(uri, action, body)

    def instances(self, project_name=None, service_name=None, name=None, action=None, body=None):
        uri = self.scope_uri(self.services_uri(project_name, service_name) + '/instances', name)
        return self.render(uri, action, body)

    # Describes what parameters can be tweaked for the given stack
    def describe(self, stack_name=None):
        if stack_name == None:
            stack_name = self.config.stack
        response = {}
        stack = self.stacks(name=stack_name)
        for service_id in stack.get('serviceIds'):
            service = self.services(name=service_id)
            svc_name = service.get('name')
            response[svc_name] = {}
            for capability in self.capabilities(svc_name):
                response[svc_name][capability] = service.get(capability)
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
        print(url, file=sys.stderr) # DEBUG URL info to stderr

        auth = (self.config.access_key, self.config.secret_key)

        if action:
            url = url + '?action=' + action
            response = requests.post(url, auth=auth)
        elif body:
            response = requests.put(url, data=body, auth=auth)
        else:
            response = requests.get(url, auth=auth)

        data = json.loads(response.text)
        if response.status_code == requests.codes.ok:
            return data
        else:
            error = { 'error': response.status_code, 'class': 'failure', 'message:': data['message']}
            self.print(error)
            sys.exit(3)

    # Helper to print out a dict payload
    def print(self, data):
        print(json.dumps(data, sort_keys=True, indent=4))

class Config:
    def __init__(self):
        self.access_key = self.read_key('/var/secrets/api_key', 'OPTUNE_API_KEY')
        self.secret_key = self.read_key('/var/secrets/api_secret', 'OPTUNE_API_SECRET')
        self.api_url = os.getenv('OPTUNE_API_URL')
        self.config_file = os.getenv('OPTUNE_CONFIG', 'config.yaml')
        try:
            with open(self.config_file, 'r') as stream:
                conf = yaml.safe_load(stream)['rancher']
                self.api_url = conf.get('api_url', self.api_url)
                self.access_key = conf.get('api_key', self.access_key)
                self.secret_key = conf.get('api_secret', self.secret_key)
                self.project = conf.get('project')
                self.stack = conf.get('stack')
                self.services = conf.get('service', {})
                self.services_defaults = self.services.get('defaults', {})
                self.excluded = conf.get('excluded', [])
        except IOError as e:
            if e.errno == errno.ENOENT:
                return {} # only if 'file not found'
            raise ConfigError("cannot read configuration from {}:{}".format(config, e.strerror))
        except yaml.error.YAMLError as e:
            raise ConfigError("syntax error in {}: {}".format(config, str(e)))

    def read_key(self, filename, default_env=None):
        try:
            file = open(filename, 'r')
            return file.readline().rstrip('\n')
        except:
            return os.getenv(default_env)


if __name__ == "__main__":
    def pull_data_objects(data):
        hash = {}
        for datum in r['data']:
            hash[datum['name']] = datum['id']
        return hash

    def env_data(data, capabilities):
        hash = {}
        for capability in capabilities.keys():
            hash[capability] = data.get(capability, capabilities[capability])
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
        project_id = args.projects[0]
        try:
            r = client.projects(project_id)
        except (Exception) as e:
            print(json.dumps({"error":e.__class__.__name__, "class":"failure", "message":str(e)}))
            sys.exit(3)

        if project_id == None: # List project names
            r = pull_data_objects(r)
        else:
            hash = {}
            for key in ['id', 'name', 'data']:
                hash[key] = r.get(key)
            r = hash

        client.print(r)
    elif args.services:
        service_id = args.services[0]
        try:
            r = client.services(name=service_id)
        except (Exception) as e:
            print(json.dumps({"error":e.__class__.__name__, "class":"failure", "message":str(e)}))
            sys.exit(3)

        if service_id == None: # List service names
            r = pull_data_objects(r)
        else:
            hash = {}
            for key in ['id', 'name', 'instanceIds']:
                hash[key] = r.get(key)
            r = hash

        client.print(r)

    elif args.stacks:
        stack_id = args.stacks[0]
        try:
            r = client.stacks(name=stack_id)
        except (Exception) as e:
            print(json.dumps({"error":e.__class__.__name__, "class":"failure", "message":str(e)}))
            sys.exit(3)

        if stack_id == None: # List service names
            r = pull_data_objects(r)
        else:
            hash = {}
            for key in ['id', 'name', 'serviceIds']:
                hash[key] = r.get(key)
            r = hash

        client.print(r)

    elif args.instances:
        service_id = args.service
        instance_id = args.instances[0]
        try:
            r = client.instances(service_name=service_id, name=instance_id)
        except (Exception) as e:
            print(json.dumps({"error":e.__class__.__name__, "class":"failure", "message":str(e)}))
            sys.exit(3)

        if instance_id == None: # List instance names
            r = pull_data_objects(r)
        else:
            r = env_data(r['data'][0], client.capabilities(service_id))

        client.print(r)
    else:
        parser.print_help()
