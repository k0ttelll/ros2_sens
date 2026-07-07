from pprint import pprint

from analysis.dataflow import build_use_def
from parser import parse_stl_mvp

code = """
L MW10
T MW20

A Sensor1
= Motor1
"""

result = parse_stl_mvp(code)

df = build_use_def(
    result["instructions"]
)

print("\nUSE\n")
pprint(df["use"])

print("\nDEF\n")
pprint(df["def"])
