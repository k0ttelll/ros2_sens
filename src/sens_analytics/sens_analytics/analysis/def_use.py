def build_def_use(use_def):

    result = []

    defs = use_def.get("def", {})
    uses = use_def.get("use", {})

    for var, def_list in defs.items():
        for d in def_list:
            for u in uses.get(var, []):
                result.append({
                    "var": var,
                    "def": d,
                    "use": u
                })

    return result
