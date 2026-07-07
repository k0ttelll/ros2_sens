def build_instruction_cfg(data):
    """
    Build instruction-level CFG.

    Supports:
        build_instruction_cfg(ir)
        build_instruction_cfg(instructions)

    Returns:
    [
        {"from": ..., "to": ..., "kind": ...}
    ]
    """

    if not data:
        return []

    # -------------------------
    # IR from parser
    # -------------------------
    if isinstance(data, dict):

        cfg_edges = data.get("cfg_edges", [])

        return [
            {
                "from": edge["from"],
                "to": edge["resolved_target_id"],
                "kind": edge["kind"]
            }
            for edge in cfg_edges
            if edge.get("resolved_target_id") is not None
        ]

    # -------------------------
    # Plain instruction list
    # -------------------------
    instructions = data

    edges = []

    for idx in range(len(instructions) - 1):

        current = instructions[idx]
        nxt = instructions[idx + 1]

        edges.append({
            "from": current["id"],
            "to": nxt["id"],
            "kind": "fallthrough"
        })

    return edges
