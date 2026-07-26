"""Generate markdown parameter-reference tables from a BTLx XSD schema.

The XSD is the machine-readable half of the BTLx spec (the PDF manual is the
graphical half). This script extracts, per processing: parameters, wire types,
value ranges, defaults, and required/optional status — so the reference tables
in ../references/ are regenerable, never hand-maintained.

Usage:
    python generate_reference.py <path-to-BTLx_X_Y_Z.xsd> [-o OUTPUT.md]
    python generate_reference.py --list <path-to-xsd>   # names only (for diffs)

The vendor XSDs are archived at C:/repos/data-models-reverse-engineering/BTLx/
schema_xsd/ (not committed here; the website is design2machine's only channel).
"""

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

XS = "{http://www.w3.org/2001/XMLSchema}"


def doc_of(node):
    """First xs:documentation text under node, whitespace-collapsed."""
    d = node.find(f"{XS}annotation/{XS}documentation")
    if d is None or d.text is None:
        return ""
    return re.sub(r"\s+", " ", d.text).strip()


class Schema:
    def __init__(self, xsd_path):
        self.path = Path(xsd_path)
        text = self.path.read_text(encoding="utf-8")
        self.version = self._version_from_comments(text)
        self.root = ET.fromstring(text)
        self.simple_types = {
            t.get("name"): t for t in self.root.findall(f"{XS}simpleType")
        }
        self.complex_types = {
            t.get("name"): t for t in self.root.findall(f"{XS}complexType")
        }
        self.groups = {g.get("name"): g for g in self.root.findall(f"{XS}group")}
        self.attribute_groups = {
            g.get("name"): g for g in self.root.findall(f"{XS}attributeGroup")
        }

    @staticmethod
    def _version_from_comments(text):
        m = re.search(r"<!--\s*BTLx\s+([\d.]+)\s*-->", text)
        return m.group(1) if m else "unknown"

    # ---- simple-type resolution -------------------------------------------

    def resolve_simple(self, type_name):
        """Resolve a (possibly chained) named simpleType to {base, facets}."""
        info = {"base": type_name, "min": None, "max": None, "enums": [], "doc": ""}
        seen = set()
        name = type_name
        while name in self.simple_types and name not in seen:
            seen.add(name)
            node = self.simple_types[name]
            if not info["doc"]:
                info["doc"] = doc_of(node)
            restriction = node.find(f"{XS}restriction")
            if restriction is None:
                break
            self._read_facets(restriction, info)
            name = restriction.get("base", "")
            info["base"] = name
        return info

    @staticmethod
    def _read_facets(restriction, info):
        for facet in restriction:
            tag = facet.tag.replace(XS, "")
            value = facet.get("value")
            if tag in ("minInclusive", "minExclusive") and info["min"] is None:
                info["min"] = value + ("" if tag == "minInclusive" else " (excl)")
            elif tag in ("maxInclusive", "maxExclusive") and info["max"] is None:
                info["max"] = value + ("" if tag == "maxInclusive" else " (excl)")
            elif tag == "enumeration":
                info["enums"].append(value)

    def type_cell(self, type_name, inline_parent=None):
        """Human-readable 'type (constraints)' cell for a type reference."""
        if inline_parent is not None:  # anonymous inline simpleType
            restriction = inline_parent.find(f"{XS}simpleType/{XS}restriction")
            if restriction is not None:
                info = {"min": None, "max": None, "enums": [], "doc": ""}
                self._read_facets(restriction, info)
                info["base"] = restriction.get("base", "?")
                return self._format_info(info)
            return "?"
        if type_name in self.simple_types:
            return self._format_info(self.resolve_simple(type_name), type_name)
        if type_name in self.complex_types:
            return f"complex → see `{type_name}`"
        return (type_name or "?").replace("xs:", "")

    def inline_complex_cell(self, element):
        """Describe an element's anonymous inline complexType, if any."""
        inline = element.find(f"{XS}complexType")
        if inline is None:
            return None
        parts = []
        ext = inline.find(f"{XS}complexContent/{XS}extension")
        if ext is not None and ext.get("base"):
            parts.append(f"extends `{ext.get('base')}`")
        agroups = [
            ag.get("ref")
            for ag in inline.iter(f"{XS}attributeGroup")
            if ag.get("ref")
        ]
        if agroups:
            parts.append("+ " + ", ".join(f"`{g}`" for g in dict.fromkeys(agroups)))
        children = sorted(
            {el.get("name") for el in inline.iter(f"{XS}element") if el.get("name")}
        )
        if children:
            shown = ", ".join(children[:8])
            more = ", …" if len(children) > 8 else ""
            parts.append(f"children: {shown}{more}")
        return "inline complex" + (f" ({'; '.join(parts)})" if parts else "")

    @staticmethod
    def _format_info(info, name=None):
        base = (info["base"] or "?").replace("xs:", "")
        parts = []
        if info["enums"]:
            shown = ", ".join(info["enums"][:6])
            more = f", … ({len(info['enums'])} values)" if len(info["enums"]) > 6 else ""
            parts.append(f"enum: {shown}{more}")
        if info["min"] is not None or info["max"] is not None:
            lo = info["min"] if info["min"] is not None else "−∞"
            hi = info["max"] if info["max"] is not None else "∞"
            parts.append(f"{lo} … {hi}")
        label = f"`{name}` ({base})" if name else base
        return f"{label}: {'; '.join(parts)}" if parts else label

    # ---- processing extraction --------------------------------------------

    def processing_list(self):
        """(element_name, type_name) pairs from the ProcessingElements group."""
        group = self.groups.get("ProcessingElements")  # 2.2.0+
        if group is None:
            group = self.complex_types.get("ProcessingsType")  # 1.0.0–2.1.0
        if group is None:
            sys.exit("no ProcessingElements group or ProcessingsType found")
        return [
            (e.get("name"), e.get("type"))
            for e in group.iter(f"{XS}element")
            if e.get("name") not in ("Processings", "ProcessingGroup")
        ]

    def base_chain(self, type_name):
        """Extension chain [type, base, base-of-base, ...]."""
        chain = []
        while type_name in self.complex_types:
            chain.append(type_name)
            ext = self.complex_types[type_name].find(
                f"{XS}complexContent/{XS}extension"
            )
            if ext is None:
                break
            type_name = ext.get("base")
        return chain

    def own_members(self, type_name):
        """(elements, attributes) declared directly on a complexType."""
        node = self.complex_types.get(type_name)
        if node is None:
            return [], []
        ext = node.find(f"{XS}complexContent/{XS}extension")
        scope = ext if ext is not None else node
        elements = []
        for seq in scope.findall(f"{XS}sequence") + scope.findall(f"{XS}choice"):
            elements.extend(self._walk_particles(seq))
        attributes = scope.findall(f"{XS}attribute")
        for agroup_ref in scope.findall(f"{XS}attributeGroup"):
            attributes.extend(self.expand_attribute_group(agroup_ref.get("ref")))
        return elements, attributes

    def expand_attribute_group(self, name):
        node = self.attribute_groups.get(name)
        if node is None:
            return []
        attrs = list(node.findall(f"{XS}attribute"))
        for nested in node.findall(f"{XS}attributeGroup"):
            attrs.extend(self.expand_attribute_group(nested.get("ref")))
        return attrs

    def _walk_particles(self, container, in_choice=False):
        out = []
        for child in container:
            tag = child.tag.replace(XS, "")
            if tag == "element":
                out.append((child, in_choice))
            elif tag in ("sequence", "choice"):
                out.extend(self._walk_particles(child, in_choice or tag == "choice"))
            elif tag == "group":
                ref = self.groups.get(child.get("ref", ""))
                if ref is not None:
                    for grp_child in ref:
                        gtag = grp_child.tag.replace(XS, "")
                        if gtag in ("sequence", "choice"):
                            out.extend(
                                self._walk_particles(grp_child, gtag == "choice")
                            )
        return out


def render_processing(schema, element_name, type_name, referenced):
    node = schema.complex_types.get(type_name)
    lines = [f"## {element_name}", ""]
    if node is not None:
        doc = doc_of(node)
        if doc:
            lines.append(f"> {doc}")
            lines.append("")
    elements, attributes = schema.own_members(type_name)
    rows = []
    for attr in attributes:
        rows.append(
            (
                f"`@{attr.get('name')}`",
                schema.type_cell(attr.get("type"), attr if attr.get("type") is None else None),
                "—",
                "yes" if attr.get("use") == "required" else "no",
                doc_of(attr),
            )
        )
    for el, in_choice in elements:
        name = el.get("name")
        el_type = el.get("type")
        if el_type and el_type in schema.complex_types:
            referenced.add(el_type)
        type_cell = schema.inline_complex_cell(el) or schema.type_cell(
            el_type, el if el_type is None else None
        )
        required = el.get("minOccurs", "1") != "0" and not in_choice
        many = el.get("maxOccurs", "1") not in ("0", "1")
        note = doc_of(el)
        if in_choice:
            note = ("choice; " + note).rstrip("; ")
        if many:
            note = ("repeatable; " + note).rstrip("; ")
        rows.append(
            (
                f"`{name}`",
                type_cell,
                el.get("default", "—"),
                "yes" if required else "no",
                note,
            )
        )
    if rows:
        lines.append("| Parameter | Type / range | Default | Required | Notes |")
        lines.append("|---|---|---|---|---|")
        for row in rows:
            lines.append("| " + " | ".join(cell or "" for cell in row) + " |")
    else:
        lines.append("*(no own parameters — inherits the shared base only)*")
    lines.append("")
    return lines


def render(schema):
    processings = schema.processing_list()
    referenced = set()
    out = [
        f"# BTLx {schema.version} — processing parameter reference",
        "",
        f"> GENERATED from `{schema.path.name}` by `scripts/generate_reference.py` — do not hand-edit.",
        "> Units: millimeters, degrees, kilograms (schema-wide convention).",
        "> Geometric meaning of parameters lives in the PDF manual and",
        "> `references/btlx-concepts.md`; this file is the wire contract only.",
        "",
        f"{len(processings)} processings. Every processing also carries the",
        "shared base parameters listed at the end.",
        "",
        "## Processing index",
        "",
    ]
    out.extend(f"- [{name}](#{name.lower()})" for name, _ in processings)
    out.append("")
    for name, type_name in processings:
        out.extend(render_processing(schema, name, type_name, referenced))

    out.extend(["---", "", "# Shared base (all processings)", ""])
    chain = schema.base_chain(processings[0][1])
    for base in chain[1:]:  # skip the concrete type itself
        out.extend(render_processing(schema, f"(base) {base}", base, referenced))

    if referenced:
        out.extend(["---", "", "# Auxiliary complex types referenced above", ""])
        done = set(chain)
        queue = sorted(referenced - done)
        while queue:
            aux = queue.pop(0)
            if aux in done:
                continue
            done.add(aux)
            new_refs = set()
            out.extend(render_processing(schema, f"`{aux}`", aux, new_refs))
            queue.extend(sorted(new_refs - done - set(queue)))

    if schema.attribute_groups:
        out.extend(
            [
                "---",
                "",
                "# Attribute groups (carried by contour segment elements)",
                "",
            ]
        )
        for name, node in schema.attribute_groups.items():
            out.append(f"## `{name}`")
            out.append("")
            doc = doc_of(node)
            if doc:
                out.extend([f"> {doc}", ""])
            out.append("| Attribute | Type / range | Default |")
            out.append("|---|---|---|")
            for attr in schema.expand_attribute_group(name):
                out.append(
                    f"| `@{attr.get('name')}` "
                    f"| {schema.type_cell(attr.get('type'), attr if attr.get('type') is None else None)} "
                    f"| {attr.get('default', '—')} |"
                )
            out.append("")
    return "\n".join(out) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xsd", help="path to a BTLx_X_Y_Z.xsd")
    parser.add_argument("-o", "--output", help="output .md path (default: stdout)")
    parser.add_argument(
        "--list", action="store_true", help="print processing names only"
    )
    args = parser.parse_args()

    schema = Schema(args.xsd)
    if args.list:
        for name, _ in schema.processing_list():
            print(name)
        return
    markdown = render(schema)
    if args.output:
        Path(args.output).write_text(markdown, encoding="utf-8")
        print(f"wrote {args.output} ({markdown.count(chr(10))} lines)")
    else:
        print(markdown)


if __name__ == "__main__":
    main()
