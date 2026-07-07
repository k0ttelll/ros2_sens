def build_block_cfg(blocks, parsed):
    """
    Build CFG between basic blocks.
    """

    edges = []

    instruction_to_block = {}

    for block in blocks:
        for inst in block["instructions"]:
            instruction_to_block[inst["id"]] = block["id"]

    seen = set()

    for edge in parsed["cfg_edges"]:

        src_inst = edge["from"]
        dst_inst = edge["resolved_target_id"]

        if dst_inst is None:
            continue

        src_block = instruction_to_block.get(src_inst)
        dst_block = instruction_to_block.get(dst_inst)

        if src_block is None or dst_block is None:
            continue

        if src_block == dst_block:
            continue

        pair = (src_block, dst_block, edge["kind"])

        if pair in seen:
            continue

        seen.add(pair)

        edges.append({
            "from_block": src_block,
            "to_block": dst_block,
            "kind": edge["kind"]
        })

    return edges
