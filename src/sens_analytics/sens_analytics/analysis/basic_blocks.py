def build_basic_blocks(parsed):
    instructions = parsed["instructions"]

    if not instructions:
        return []

    leaders = {0}

    # jump targets
    for edge in parsed["cfg_edges"]:
        target = edge["resolved_target_id"]
        if target is not None:
            leaders.add(target)

    # instruction after conditional jump
    for inst in instructions:
        if inst["opcode"] == "JC":
            if inst["id"] + 1 < len(instructions):
                leaders.add(inst["id"] + 1)

    leaders = sorted(leaders)

    blocks = []

    for i, start in enumerate(leaders):
        end = leaders[i + 1] if i + 1 < len(leaders) else len(instructions)

        blocks.append({
            "id": len(blocks),
            "start": start,
            "end": end - 1,
            "instructions": instructions[start:end]
        })

    return blocks


def build_block_cfg(blocks, parsed):
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

        key = (src_block, dst_block, edge["kind"])

        if key in seen:
            continue

        seen.add(key)

        edges.append({
            "from_block": src_block,
            "to_block": dst_block,
            "kind": edge["kind"]
        })

    return edges
