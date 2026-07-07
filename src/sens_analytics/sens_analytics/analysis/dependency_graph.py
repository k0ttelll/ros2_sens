def build_dependency_graph(ir):

    instructions = ir["instructions"]

    instruction_cfg = ir.get("instruction_cfg", [])
    def_use = ir.get("def_use", [])

    edges = []

    # control dependencies (instruction level)
    for e in instruction_cfg:
        edges.append({
            "from": e["from"],
            "to": e["to"],
            "type": "control"
        })

    # data dependencies
    for d in def_use:
        edges.append({
            "from": d["def"],
            "to": d["use"],
            "type": "data",
            "var": d["var"]
        })

    return {
        "nodes": instructions,
        "edges": edges
    }
