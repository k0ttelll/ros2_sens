from analysis.reaching_definitions import build_reaching_definitions
from parser import parse_stl_mvp

code = """
L MW10
T MW20

L MW20
T MW30
"""

result = parse_stl_mvp(code)

reaching = build_reaching_definitions(
    result["instructions"]
)

from pprint import pprint

pprint(reaching)
