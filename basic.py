#!/usr/bin/env python

from dotenv import load_dotenv
import requests
from requests.auth import HTTPBasicAuth
import sys, json, os
import yaml

load_dotenv()

# Remove proxy if set (as it might block or send unwanted requests to the proxy)
if "http_proxy" in os.environ:
    del os.environ['http_proxy']
if "https_proxy" in os.environ:
    del os.environ['https_proxy']

class Client:
    def __init__(self, api_url, access_key, secret_key):
        self.api_url = api_url
        self.access_key = access_key
        self.secret_key = secret_key

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

    def environments_uri(self, project_name=None, name=None, action=None):
        uri = self.scope_uri(self.projects_uri(project_name) + '/environments', name)
        return self.scope_uri(uri, action, '?action=')

    def environments(self, project_name, name=None, action=None):
        return self.query(self.environments_uri(project_name, name, action))

    def exportconfig(self, project_name, env_name):
        response = self.environments(project_name, env_name, 'exportconfig')
        return response['rancherCompose'] + response['dockerCompose']

    def query(self, uri):
        headers = {}
        headers['Content-Type'] = 'application/json'
        url = self.api_url + uri
        print(url)
        response = requests.get(url, auth=(self.access_key, self.secret_key))

        if response.status_code == 200:
            return json.loads(response.text)
        else:
            return response

    def print(self, data):
        print(json.dumps(data, sort_keys=True, indent=4))

with open("config.yaml", 'r') as stream:
    try:
        print(yaml.safe_load(stream))
    except yaml.YAMLError as exc:
        print(exc)

client = Client(os.getenv('API_URL'), os.getenv('ACCESS_KEY'), os.getenv('SECRET_KEY'))

print("PROJECTS:")
r = client.exportconfig('1a5', '1st19')
print(r)
