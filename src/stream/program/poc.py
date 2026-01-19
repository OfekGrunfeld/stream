import re

PIPELINE_RE = re.compile(r'^\s*"([^"]*)"\s*->\s*([A-Za-z_]\w*)\s*$')
