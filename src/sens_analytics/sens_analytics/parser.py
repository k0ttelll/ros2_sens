import re

try:
    from .expression_parser import build_expression
except ImportError:
    from expression_parser import build_expression

def parse_stl_mvp(code: str) -> dict:
    if not code:
        return {
            "warnings": [],
            "labels": {},
            "instructions": [],
            "cfg_edges": []
        }

    lines = code.split("\n")

    instructions = []
    labels_map = {}
    cfg_edges = []
    warnings = []

    pattern = re.compile(
        r'^\s*(?:(\w+)\s*:\s*)?([^\s]+)?(\s+.*)?$'
    )

    for idx, line in enumerate(lines):
        raw_line = line.strip()

        if not raw_line:
            continue

        if "//" in raw_line:
            raw_line = raw_line.split("//")[0].strip()

            if not raw_line:
                continue

        match = pattern.match(raw_line)

        if not match:
            warnings.append({
                "line": idx + 1,
                "type": "unparsed_line",
                "message": f"Could not parse line structure: '{line.strip()}'"
            })
            continue

        label, opcode, operand = match.group(1), match.group(2), match.group(3)

        inst_id = len(instructions)

        if label:
            if label in labels_map:
                warnings.append({
                    "line": idx + 1,
                    "type": "duplicate_label",
                    "message": f"Label '{label}' is already defined at instruction ID {labels_map[label]}"
                })
            else:
                labels_map[label] = inst_id

        if operand:
            operand = operand.strip()

        if opcode in ["A(", "O(", ")", "NOT", "SAVE"] or (
            opcode and opcode.endswith("(")
        ):
            warnings.append({
                "line": idx + 1,
                "type": "complex_syntax_stub",
                "message": f"Opcode '{opcode}' lacks expression-tree context for deeper Data-Flow."
            })

        instructions.append({
            "id": inst_id,
            "line": idx + 1,
            "label": label,
            "opcode": opcode,
            "operand": operand if operand else None
        })

    for inst in instructions:
        curr_id = inst["id"]
        opcode = inst["opcode"]
        operand = inst["operand"]

        if opcode in ["JU", "JC"]:
            kind = "jump" if opcode == "JU" else "branch_true"

            if operand not in labels_map:
                warnings.append({
                    "line": inst["line"],
                    "type": "unresolved_jump_target",
                    "message": f"Instruction '{opcode} {operand}' points to a non-existent label."
                })

                cfg_edges.append({
                    "from": curr_id,
                    "target_label": operand,
                    "resolved_target_id": None,
                    "kind": f"{opcode.lower()}_unresolved_target"
                })

            else:
                cfg_edges.append({
                    "from": curr_id,
                    "target_label": operand,
                    "resolved_target_id": labels_map[operand],
                    "kind": kind
                })

            if opcode == "JC" and curr_id + 1 < len(instructions):
                cfg_edges.append({
                    "from": curr_id,
                    "target_label": None,
                    "resolved_target_id": curr_id + 1,
                    "kind": "fallthrough"
                })

        else:
            if curr_id + 1 < len(instructions):
                cfg_edges.append({
                    "from": curr_id,
                    "target_label": None,
                    "resolved_target_id": curr_id + 1,
                    "kind": "fallthrough"
                })

    return {
        "warnings": warnings,
        "labels": labels_map,
        "instructions": instructions,
        "cfg_edges": cfg_edges
    }

class Parser:
    """Facade used by the ROS service to build an equipment-level PDG.

    The package keeps the copied STL parser functions as the parsing authority.
    This class adds the service-facing method expected by Sens and materializes a
    NetworkX graph whose nodes are STL equipment tags and whose edges carry the
    Siemens block/network metadata required by downstream tools.
    """

    _INPUT_OPCODES = {"A", "AN", "O", "ON", "L"}
    _OUTPUT_OPCODES = {"=", "S", "R", "T"}
    _STRUCTURAL_OPCODES = {
        "NETWORK",
        "TITLE",
        "FUNCTION",
        "FUNCTION_BLOCK",
        "ORGANIZATION_BLOCK",
        "DATA_BLOCK",
        "BEGIN",
        "END_FUNCTION",
        "END_FUNCTION_BLOCK",
        "END_ORGANIZATION_BLOCK",
        "END_DATA_BLOCK",
    }
    _BLOCK_RE = re.compile(
        r'^\s*(?:FUNCTION|FUNCTION_BLOCK|ORGANIZATION_BLOCK|FC|FB|OB)\s+"?([A-Za-z_][\w$]*)"?',
        re.IGNORECASE,
    )
    _NETWORK_RE = re.compile(r"^\s*NETWORK(?:\s+(\d+))?\b", re.IGNORECASE)

    def parse_string_to_pdg(self, code: str):
        """Parse STL source text into an equipment dependency nx.DiGraph."""

        import networkx as nx

        if not code or not code.strip():
            raise ValueError("stl_code_text is empty")

        ir = parse_stl_mvp(code)
        contexts = self._extract_line_context(code)
        graph = nx.DiGraph()

        active_sources = []
        current_key = None

        for instruction in ir.get("instructions", []):
            opcode = self._normalize_opcode(instruction.get("opcode"))
            operand = self._normalize_operand(instruction.get("operand"))
            context = contexts.get(
                instruction.get("line"),
                {"block_name": "FC_Unknown", "network_number": 0},
            )
            instruction_key = (context["block_name"], context["network_number"])

            if current_key is not None and instruction_key != current_key:
                active_sources = []
            current_key = instruction_key

            if not opcode or opcode in self._STRUCTURAL_OPCODES:
                continue

            if opcode in self._INPUT_OPCODES and operand:
                active_sources.append((operand, opcode))
                graph.add_node(operand)
                continue

            if opcode in self._OUTPUT_OPCODES and operand:
                graph.add_node(operand)
                for source, src_opcode in active_sources:
                    if source == operand:
                        continue
                    graph.add_edge(
                        source,
                        operand,
                        block_name=context["block_name"],
                        network_number=context["network_number"],
                        input_opcode=src_opcode,
                    )

                if opcode == "T":
                    active_sources = []

        return graph

    def parse(self, code: str):
        """Compatibility alias for callers that use a generic parse method."""

        return self.parse_string_to_pdg(code)

    def _extract_line_context(self, code: str):
        block_name = "FC_Unknown"
        network_number = 0
        implicit_network = 0
        contexts = {}

        for line_number, raw_line in enumerate(code.splitlines(), start=1):
            line = raw_line.split("//", 1)[0].strip()
            if not line:
                continue

            block_match = self._BLOCK_RE.match(line)
            if block_match:
                block_name = block_match.group(1)
                network_number = 0
                implicit_network = 0

            network_match = self._NETWORK_RE.match(line)
            if network_match:
                if network_match.group(1):
                    network_number = int(network_match.group(1))
                else:
                    implicit_network += 1
                    network_number = implicit_network

            contexts[line_number] = {
                "block_name": block_name,
                "network_number": network_number,
            }

        return contexts

    @staticmethod
    def _normalize_opcode(opcode) -> str:
        return str(opcode or "").strip().upper()

    @staticmethod
    def _normalize_operand(operand) -> str:
        value = str(operand or "").strip()
        if not value:
            return ""
        return value.split("//", 1)[0].strip().strip('"')

