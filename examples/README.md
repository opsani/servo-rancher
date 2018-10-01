# Example

## Example stack, `http-test`

Rancher and docker files required to create the stack:

* `rancher-compose.yml`
* `docker-compose.yml`

Sample Optune servo config file: `config.yaml`

## Adjustment test response files

* `http-test-a.json` and `http-test-b.json`
* `http-test-memory-front.json`

Example environment file to use when testing driver:

export OPTUNE_API_KEY=12345...
export OPTUNE_API_SECRET=abcdef....
export OPTUNE_CONFIG=examples/config.yaml
