import re

SPRING_START_RE = re.compile(r"^\s*spring\s+-:>\s*\{\s*$")
SPRING_END_RE = re.compile(r"^\s*\}\s*$")
