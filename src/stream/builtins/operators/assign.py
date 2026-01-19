import re

ASSIGN_RE = re.compile(r"^\s*(season|drift)\s+-:>\s*([A-Za-z_]\w*)\s*;\s*$")
