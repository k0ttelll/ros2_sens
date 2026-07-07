from pprint import pprint

from analysis.basic_blocks import build_basic_blocks
from analysis.block_cfg import build_block_cfg
from parser import parse_stl_mvp

code = """
START : NOP 0
A Sensor
JC END

L 1
T MW10

END : R Motor
"""

parsed = parse_stl_mvp(code)

blocks = build_basic_blocks(parsed)

edges = build_block_cfg(blocks, parsed)

print("\nBLOCKS\n")
pprint(blocks)

print("\nCFG\n")
pprint(edges)
