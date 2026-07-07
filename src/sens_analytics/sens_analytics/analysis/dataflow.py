def build_use_def(instructions):

    use = {}
    defs = {}

    for inst in instructions:
        op = inst["opcode"]
        var = inst.get("operand")
        i = inst["id"]

        if op in ["L", "A"]:
            if var:
                use.setdefault(var, []).append(i)

        elif op in ["T", "=", "S", "R"]:
            if var:
                defs.setdefault(var, []).append(i)

    return {
        "use": use,
        "def": defs
    }
