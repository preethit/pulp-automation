from pulp import namespace
import yaml

# load inventory globals
with open('inventory.yml') as fd:
    globals().update(namespace.load_ns(yaml.load(fd)))