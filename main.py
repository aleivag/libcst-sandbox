import js
import libcst as cst

from functools import singledispatchmethod, singledispatch
from contextlib import contextmanager

#########
#  Current State
########


MODULE = None
POS = {}
IDDICT = {}

RENDER_BODY_ELEMENT_ID = "render-body"


def load():
    link_element = js.document.createElement('link')
    link_element.rel = 'stylesheet'
    link_element.href = 'https://cdn.jsdelivr.net/npm/monaco-editor@0.41.0/min/vs/editor/editor.main.css'

    script_element = js.document.createElement('script')
    script_element.src = 'https://cdn.jsdelivr.net/npm/monaco-editor@0.41.0/min/vs/loader.js'
    script_element.setAttribute("onload", "load()")

    js.document.head.appendChild(link_element)
    js.document.head.appendChild(script_element)


IGNORE_NODES = (
    cst.TrailingWhitespace, cst.SimpleWhitespace, cst.Newline

)


def render_cst(module_text: str, **kwargs) -> None:
    global MODULE, POS, IDDICT

    wrapper = cst.metadata.MetadataWrapper(cst.parse_module(module_text))
    POS = {
        k: v
        for k, v in wrapper.resolve(cst.metadata.PositionProvider).items()
        if not isinstance(k, IGNORE_NODES)
    }
    MODULE = wrapper.module
    IDDICT = dict(node2id(MODULE, "$"))

    render_module_object(MODULE, js.document.getElementById(RENDER_BODY_ELEMENT_ID))


def get_node_id_by_pos(line, column) -> None:
    render_pannel = js.document.getElementById(RENDER_BODY_ELEMENT_ID)
    node = find_closes_node_to_pos(line, column)
    return IDDICT[node]


####

@singledispatch
def node2id(node, id_prefix):
    yield from []


@node2id.register(list)
@node2id.register(set)
@node2id.register(tuple)
def _(e: list, id_prefix: str):
    for n, elem in enumerate(e):
        yield from node2id(elem, f"{id_prefix}[{n}]")
        # yield self.text("".join(self.display_as_html(elem, )))


@node2id.register(cst.CSTNode)
def _(node, id_prefix: str):
    id_prefix = f"{id_prefix}({type(node).__name__})"
    yield node, id_prefix

    for attr in node.__dataclass_fields__:
        yield from [
            inner
            for inner in node2id(getattr(node, attr), id_prefix=f"{id_prefix}.{attr}")
            if inner
        ]


def find_closes_node_to_pos(target_line: int, target_column: int):
    global POS

    best_line_so_far = -1
    best_column_so_far = -1

    best_node = None

    for node, v in sorted(
            POS.items(),
            key=lambda x: (x[1].start.line, x[1].start.column, -x[1].end.line, -x[1].end.column)):
        if v.start.line > target_line:
            break
        if v.start.line > best_line_so_far:
            best_node = node
            best_line_so_far = v.start.line
            best_column_so_far = -1
            continue

        if v.start.column > target_column:
            continue

        if v.start.column >= best_column_so_far:
            best_node = node
            best_column_so_far = v.start.column
            continue
    return best_node


####

def kill_whitespace():
    global POS, IDDICT
    list(map(POS.pop, [
        pos
        for pos in POS
        if isinstance(pos, cst.SimpleWhitespace) or isinstance(pos, cst.Newline)
    ]))
    list(map(IDDICT.pop, [
        pos
        for pos in IDDICT
        if isinstance(pos, cst.SimpleWhitespace)
    ]))


class DisplayNodes:
    def __init__(self, root_node):
        self.root_node = root_node
        self.indent_level = 0
        self.indent_str = " " * 2

    def as_html(self):
        yield """<style>
  .cstnode {
    padding: 10px;
    display: inline;
    transition: background-color 0.3s ease;
  }


  .hghlight {
    // border: 2px solid orange; /* Add a border to highlight the div */

    
    // position: absolute; /* Position the inner div absolutely inside the container */
    top: -10px; /* Adjust the top position to create the effect of a border */
    left: -10px; /* Adjust the left position to create the effect of a border */
    padding: 10px; /* Add padding to create space between the inner and outer div */
    background-color: rgba(173, 216, 230, 0.5); /* Semi-transparent light blue background */
  }


  .cstnodename {
    color: rgb(17, 102, 119);
  }

  .pystr {color: rgb(170, 17, 17)}
  .pynone {color: rgb(119, 0, 136)}
  .pynum {color: rgb(17, 102, 68)}
</style>"""

        yield from self.display_as_html(self.root_node, id_prefix="$")

    def text(self, msg):
        return (self.indent_str * self.indent_level) + msg

    @contextmanager
    def indent(self):
        self.indent_level += 1
        yield
        self.indent_level -= 1

    @singledispatchmethod
    def display_as_html(self, e, id_prefix: str):
        if e == None:
            yield "<span class='pynone'>None</span>"
        else:
            yield repr(e)

    @display_as_html.register(str)
    def _(self, e, id_prefix: str):
        yield "<span class='pystr'>"
        yield repr(e)
        yield "</span>"

    @display_as_html.register(int)
    @display_as_html.register(float)
    def _(self, e, id_prefix: str):
        yield "<span class='pynum'>"
        yield repr(e)
        yield "</span>"

    @display_as_html.register(list)
    @display_as_html.register(set)
    @display_as_html.register(tuple)
    def _(self, e: list, id_prefix: str):
        o, c = str(type(e)())
        if not len(e):
            yield f"{o}{c}"
            return

        yield f"{o}\n"
        with self.indent():
            for n, elem in enumerate(e):
                yield self.text("".join(self.display_as_html(elem, f"{id_prefix}[{n}]")))
                yield ",\n"
        yield self.text(c)

    @display_as_html.register(cst.CSTNode)
    def _(self, e, id_prefix: str):
        global MODULE, POS, IDDICT
        id_ = f"{id_prefix}.{type(e).__name__}"
        pos = POS.get(e)
        onclick = ""
        if pos:
            jsRange = f"{{startLineNumber: {pos.start.line}, startColumn: {pos.start.column+1}, endLineNumber: {pos.end.line}, endColumn: {pos.end.column+1}}}"
            onclick = f"onclick='didCstClick(arguments[0], {jsRange})'"
        yield f"<div class='cstnode' id='{IDDICT[e]}' {onclick}>"
        yield "<span class='cstnodename'>"
        yield type(e).__name__
        yield "</span>"
        yield "(\n"
        with self.indent():
            for attr in e.__dataclass_fields__:
                yield self.text(attr)
                yield "="
                yield from self.display_as_html(getattr(e, attr), id_prefix=id_)
                yield ",\n"

        yield self.text(")")
        yield "</div>"


def render_module_object(module, output):
    output.innerHTML = "".join(
        [
            "<pre>",
            *DisplayNodes(module).as_html(),
            "</pre>",
        ]
    )


load()
