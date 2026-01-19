import re

GYGE_DECL_RE = re.compile(r"^\s*gyge\s+([A-Za-z_]\w*)\s+-:>\s+(.+?)\s*;\s*$")
