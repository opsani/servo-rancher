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
        return self.query(uri)

    def accounts(self, name=None):
        uri = self.scope_uri('/accounts', name, '?name=')
        return self.query(uri)

    def projects_uri(self, name=None):
        return self.scope_uri('/projects', name)

    def projects(self, name=None):
        return self.query(self.projects_uri(name))

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
        uri = self.scope_uri(uri, action, '?action=')
        return self.render(uri, body)

    # https://rancher.com/docs/rancher/v1.5/en/api/v1/api-resources/service/#update
    def services(self, project_name, name=None, action=None, body=None):
        uri = self.scope_uri(self.projects_uri(project_name) + '/services', name)
        uri = self.scope_uri(uri, action, '?action=')
        return self.render(uri, body)

    def capabilities(self, project_name=None):
        return self.defaults

    def render(self, uri, body=None):
        if body:
            return self.update(uri, body)
        else:
            return self.query(uri)

    def query(self, uri):
        url = self.api_url + uri
        print(url)

        response = requests.get(url, auth=(self.access_key, self.secret_key))

        if response.status_code == 200:
            return json.loads(response.text)
        else:
            return response

    def update(self, uri, body):
        url = self.api_url + uri
        print(url)

        print("PUT "+url)
        print(body)
        response = requests.put(url, data=body, auth=(self.access_key, self.secret_key))
        print("   " + str(response))
        if response.status_code == 200:
            response_json = json.loads(response.text)
            for key in body.keys():
                print('   ' + key + ' : ' + str(response_json[key]))
        else:
            print('Oops')
            print(response.text)

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
client.print(client.services(project_id, service_id, body=body))
