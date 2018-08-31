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

class Client:
    def __init__(self, api_url=None, access_key=None, secret_key=None, project=None, config='./config.yaml'):
        with open(config, 'r') as stream:
            conf = yaml.safe_load(stream)['rancher']
            self.api_url = conf.get('api_url', api_url)
            self.access_key = conf.get('api_key', access_key)
            self.secret_key = conf.get('secret_key', secret_key)
            self.project = conf.get('project', project)
            self.stack = conf.get('stack')
            self.defaults = conf.get('default')
            self.headers = {}
            self.headers['Content-Type'] = 'application/json'

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

    def projects_uri(self, name=None):
        return self.scope_uri('/projects', name)

    def projects(self, name=None):
        return self.render(self.projects_uri(name))

    # Actions:
    #   * activateservices
    #   * cancelrollback
    #   * cancelupgrade
    #   * deactivateservices
    #   * exportconfig
    #   * finishupgrade
    #   * rollback
    # https://rancher.com/docs/rancher/v1.5/en/api/v1/api-resources/environments/#update
    def environments(self, project_name, name=None, action=None, body=None):
        uri = self.scope_uri(self.projects_uri(project_name) + '/environments', name)
        return self.render(uri, action, body)

    # https://rancher.com/docs/rancher/v1.5/en/api/v1/api-resources/service/#update
    def services(self, project_name, name=None, action=None, body=None):
        uri = self.scope_uri(self.projects_uri(project_name) + '/services', name)
        return self.render(uri, action, body)

    def capabilities(self, project_name=None):
        return self.defaults

    def render(self, uri, action=None, body=None):
        url = self.api_url + uri
        print(url)

        if action:
            url = url + '?action=' + action
            response = requests.post(url, auth=(self.access_key, self.secret_key))
        elif body:
            response = requests.put(url, data=body, auth=(self.access_key, self.secret_key))
        else:
            response = requests.get(url, auth=(self.access_key, self.secret_key))

        return json.loads(response.text)

    def print(self, data):
        print(json.dumps(data, sort_keys=True, indent=4))

client = Client(
    os.getenv('API_URL'),
    os.getenv('ACCESS_KEY'),
    os.getenv('SECRET_KEY'),
    'config.yaml')

#for project in client.projects()['data']:
#    project_id = project['id']
#    print('Project: ' + project_id)
#    for env in client.environments(project_id)['data']:
#        env_id = env['id']
#        print('Environment: ' + env_id)
#        print(env['environment'])
#
#        body = {}
#        body['environment'] = {}
#        body['environment']['FOO'] = 'BAR'
#        client.environments(project_id, env_id, body=body)

body = {}
body['description'] = str(datetime.datetime.utcnow())
body['metadata'] = {}
body['scalePolicy'] = {}
body['scalePolicy']['min'] = 0.1
body['scalePolicy']['max'] = 0.8
#body['metadata']['Time'] = str(datetime.datetime.utcnow())

project_id = '1a5'
service_id = '1s37'

print('Services for ' + project_id)
for service in client.services(project_id)['data']:
    print(' ' + service['id'])

print('Updating service' + service_id + ' with ' + str(body))
response = client.services(project_id, service_id, body=body)

for key in body.keys():
    print('  ' + key + ': ' + str(response[key]))

client.print(client.services(project_id, service_id, action='finishupgrade'))
