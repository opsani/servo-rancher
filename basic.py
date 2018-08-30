#!/usr/bin/python

import requests
from requests.auth import HTTPBasicAuth
import sys, json, os
import yaml

api_url='http://dish.kumulus.co:8080/v1'
access_key='13C577DC2D45D92EA86B'
secret_key='em8aoDg7Rybye9tmvAeN58HN7AULQQYW6sYssZoZ'
ContentType = 'application/json'
uuid_num='81a3e987-c703-4729-ad72-e894bc54124f'
account_name='admin'

# Remove proxy if set (as it might block or send unwanted requests to the proxy)
if "http_proxy" in os.environ:
    del os.environ['http_proxy']
if "https_proxy" in os.environ:
    del os.environ['https_proxy']

def getReqType( reqType, uuid_num, account_name, api_v ):
     if reqType == "uuid":
       if uuid_num:
        reqType = api_url + '/apiKey?uuid=' + uuid_num
       else:
        reqType = api_url + '/apiKey'
     elif reqType == "accounts":
       if account_name:
        reqType = api_url + '/accounts?name=' + account_name
       else:
        reqType = api_url + '/accounts'
     return reqType

# Set values
headers                 = {}
headers['Content-Type'] = ContentType
reqType                 = "accounts"
url                     = getReqType(reqType, uuid_num, account_name, api_url)

r = requests.get(url, auth=(access_key, secret_key))

data = json.loads(r.text)
print json.dumps(data, sort_keys=True,
                 indent=4 )
