#!/usr/bin/env python

from dotenv import load_dotenv
import requests
from requests.auth import HTTPBasicAuth
import sys, json, os
import datetime
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

    # This method will return what a caller may be able to do based on the
    # initialized configuration. It only supports service overrides.
    def capabilities(self, service_name=None):
        merged = self.merge(
            self.config.defaults.copy(),
            self.config.services.get(service_name, {}))
        if merged.get('exclude', None) != None or service_name in self.config.excluded:
            return {}
        return merged

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

    def uuid(self, uuid):
        uri = self.scope_uri('/apiKey', uuid, '?uuid=')
        return self.render(uri)

    def accounts(self, name=None):
        uri = self.scope_uri('/accounts', name, '?name=')
        return self.render(uri)

    def projects_uri(self, name=None, default=False):
        if default and name == None:
            name = self.config.project
        return self.scope_uri('/projects', self.project_id(name))

    def projects(self, name=None):
        return self.render(self.projects_uri(name))

    # https://rancher.com/docs/rancher/v1.5/en/api/v1/api-resources/environments/#update
    def environments(self, project_name=None, name=None, action=None, body=None):
        uri = self.scope_uri(self.projects_uri(project_name, True) + '/environments', name)
        return self.render(uri, action, body)

    def services_uri(self, project_name=None, name=None):
        return self.scope_uri(self.projects_uri(project_name, True) + '/services', self.service_id(name))

    # https://rancher.com/docs/rancher/v1.5/en/api/v1/api-resources/service/#update
    def services(self, project_name=None, name=None, action=None, body=None):
        uri = self.services_uri(project_name, name)
        return self.render(uri, action, body)

    def instances(self, project_name=None, service_name=None, name=None, action=None, body=None):
        uri = self.scope_uri(self.services_uri(project_name, service_name) + '/instances', name)
        return self.render(uri, action, body)

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
            self.print(data)
            sys.exit(3)

    # Helper to print out a dict payload
    def print(self, data):
        print(json.dumps(data, sort_keys=True, indent=4))

class Config:
    def __init__(self):
        self.access_key = self.read_key('/var/run/api_key', 'ACCESS_KEY')
        self.secret_key = self.read_key('/var/run/secret_key', 'SECRET_KEY')
        self.api_url = os.getenv('API_URL')
        self.config_file = os.getenv('CONFIG', 'config.yaml')
        try:
            with open(self.config_file, 'r') as stream:
                conf = yaml.safe_load(stream)['rancher']
                self.api_url = conf.get('api_url', self.api_url)
                self.access_key = conf.get('api_key', self.access_key)
                self.secret_key = conf.get('secret_key', self.secret_key)
                self.project = conf.get('project')
                self.stack = conf.get('stack')
                self.defaults = conf.get('default', {})
                self.services = conf.get('service', {})
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
    config = Config()
    # Pull possible parameters from the environment
    client = Client(config)

    # This is an example for a single project
    # it iterates over all services and just lists their IDs
    client.print(client.projects())
    project_id = client.projects()['data'][0]['id']

    print('Services for ' + project_id)
    for service in client.services(project_id)['data']:
        print(' ' + service['id'])

    # These are they keys we try to update
    body = {}
    body['description'] = str(datetime.datetime.utcnow())
    body['metadata'] = {}
    body['scalePolicy'] = {}
    body['scalePolicy']['min'] = 0.1
    body['scalePolicy']['max'] = 0.8
    #body['metadata']['Time'] = str(datetime.datetime.utcnow())

    service_id = client.services(project_id)['data'][0]['id']

    # Then we try to update the service
    print('Updating service' + service_id + ' with ' + str(body))
    response = client.services(project_id, service_id, body=body)

    # Print out only the keys we attempted to update
    for key in body.keys():
        print('  ' + key + ': ' + str(response[key]))

    # Perform an action. This one seems to 422.
    client.print(client.services(project_id, service_id, action='finishupgrade'))
