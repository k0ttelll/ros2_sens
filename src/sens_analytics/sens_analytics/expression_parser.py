class ExprNode:
    """
    Node of a boolean expression tree used for STL/AWL logic parsing.
    """

    def __init__(self, type_, value=None):
        self.type = type_
        self.value = value
        self.children = []

    def to_dict(self):
        """
        Convert tree node into a serializable dictionary.
        """
        return {
            "type": self.type,
            "value": self.value,
            "children": [child.to_dict() for child in self.children]
        }


def build_expression(lines):
    """
    Build an expression tree from STL/AWL boolean logic.

    Supported operators:

        A      AND
        AN     AND NOT
        O      OR
        ON     OR NOT

        A(     AND group
        O(     OR group
        )      close group
    """

    stack = []
    root = None

    for line in lines:
        line = line.strip()

        if not line:
            continue

        parts = line.split()

        op = parts[0].upper()
        arg = " ".join(parts[1:]) if len(parts) > 1 else None

        # -------------------------
        # Open AND block
        # -------------------------

        if op == "A(":
            node = ExprNode("AND_BLOCK")

            if stack:
                stack[-1].children.append(node)
            else:
                root = node

            stack.append(node)

        # -------------------------
        # Open OR block
        # -------------------------

        elif op == "O(":
            node = ExprNode("OR_BLOCK")

            if stack:
                stack[-1].children.append(node)
            else:
                root = node

            stack.append(node)

        # -------------------------
        # Close block
        # -------------------------

        elif op == ")":
            if stack:
                stack.pop()

        # -------------------------
        # AND
        # -------------------------

        elif op == "A":
            node = ExprNode("AND", arg)

            if stack:
                stack[-1].children.append(node)
            elif root:
                root.children.append(node)
            else:
                root = node

        # -------------------------
        # AND NOT
        # -------------------------

        elif op == "AN":
            node = ExprNode("AND_NOT", arg)

            if stack:
                stack[-1].children.append(node)
            elif root:
                root.children.append(node)
            else:
                root = node

        # -------------------------
        # OR
        # -------------------------

        elif op == "O":
            node = ExprNode("OR", arg)

            if stack:
                stack[-1].children.append(node)
            elif root:
                root.children.append(node)
            else:
                root = node

        # -------------------------
        # OR NOT
        # -------------------------

        elif op == "ON":
            node = ExprNode("OR_NOT", arg)

            if stack:
                stack[-1].children.append(node)
            elif root:
                root.children.append(node)
            else:
                root = node

        # -------------------------
        # Fallback node
        # -------------------------

        else:
            node = ExprNode("VALUE", line)

            if stack:
                stack[-1].children.append(node)
            elif root:
                root.children.append(node)
            else:
                root = node

    return root


def print_tree(node, level=0):
    """
    Pretty-print tree structure for debugging.
    """

    if node is None:
        return

    indent = "  " * level

    if node.value:
        print(f"{indent}{node.type}: {node.value}")
    else:
        print(f"{indent}{node.type}")

    for child in node.children:
        print_tree(child, level + 1)


if __name__ == "__main__":

    test_lines = [
        "A(",
        "A Sensor1",
        "O Sensor2",
        ")"
    ]

    tree = build_expression(test_lines)

    print("Expression tree:\n")

    print_tree(tree)

    print("\nAs JSON:\n")

    print(tree.to_dict())
