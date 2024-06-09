import libcst as cst

from functools import singledispatchmethod, singledispatch
from contextlib import contextmanager

from pyweb import pydom
from pyodide.ffi.wrappers import add_event_listener
from pyscript.js_modules.monaco import editor
from pyscript import document
from pyscript.ffi import create_proxy, to_js
from js import localStorage, Array

DEFAULT_CONTENT = """
def foo[T](bar: T | None = None) -> T | None:
    if bar is None:
        return None
    # increment
    return bar + 1
"""
EDITOR_CONTENT_KEY = "libcst-me-editor-content"
RENDER_BODY_ELEMENT_ID = "render-body"

MODULE = None
POS = {}
IDDICT: dict[cst.CSTNode, str] = {}

IGNORE_NODES = (cst.TrailingWhitespace, cst.SimpleWhitespace, cst.Newline)


def render_cst(editor) -> None:
    content = editor.getModel().getValue()
    localStorage.setItem(EDITOR_CONTENT_KEY, content)

    global MODULE, POS, IDDICT

    wrapper = cst.metadata.MetadataWrapper(cst.parse_module(content))
    POS = {
        k: v
        for k, v in wrapper.resolve(cst.metadata.PositionProvider).items()
        if not isinstance(k, IGNORE_NODES)
    }
    MODULE = wrapper.module
    IDDICT = dict(node2id(MODULE, "$"))

    render_module_object(
        editor, MODULE, document.getElementById(RENDER_BODY_ELEMENT_ID)
    )


last_decorations = None


def did_cst_click(event, position, editor) -> None:
    event.stopPropagation()
    range = {
        "startLineNumber": position.start.line,
        "startColumn": position.start.column + 1,
        "endLineNumber": position.end.line,
        "endColumn": position.end.column + 1,
    }
    remove_highlights()
    global last_decorations
    last_decorations = editor.createDecorationsCollection(
        Array.from_([to_js({"options": {"className": "hghlight"}, "range": range})])
    )


def remove_highlights() -> None:
    global last_decorations
    if last_decorations is not None:
        last_decorations.clear()
    if (highlights := pydom[".hghlight"]) is not None:
        for item in highlights:
            item.remove_class("hghlight")


def scroll_to_cst_node(editor) -> None:
    position = editor.getPosition()
    line = position.lineNumber
    column = position.column - 1

    node_id = get_node_id_by_pos(line, column)
    node_dom = pydom.Element(document.getElementById(node_id))
    remove_highlights()
    node_dom._js.scrollIntoView(to_js({"behavior": "smooth", "block": "center"}))
    node_dom.add_class("hghlight")

    document.getElementById("status-bar").innerText = f"Line: {line}, Column: {column}"
    document.getElementById("render-footer").innerText = f"id: {node_id}"


def get_default_content() -> str:
    content = localStorage.getItem(EDITOR_CONTENT_KEY)
    return content or DEFAULT_CONTENT


def get_node_id_by_pos(line, column) -> str:
    render_pannel = document.getElementById(RENDER_BODY_ELEMENT_ID)
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
        key=lambda x: (
            x[1].start.line,
            x[1].start.column,
            -x[1].end.line,
            -x[1].end.column,
        ),
    ):
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
    list(
        map(
            POS.pop,
            [
                pos
                for pos in POS
                if isinstance(pos, cst.SimpleWhitespace) or isinstance(pos, cst.Newline)
            ],
        )
    )
    list(
        map(
            IDDICT.pop, [pos for pos in IDDICT if isinstance(pos, cst.SimpleWhitespace)]
        )
    )


class DisplayNodes:
    def __init__(self, editor, root_node):
        self.editor = editor
        self.root_node = root_node
        self.indent_level = 0
        self.indent_str = " " * 2

    def as_html(self):
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
            yield pydom.create("span", classes=("pynone",), html="None")
        else:
            yield pydom.create("span", html=repr(e))

    @display_as_html.register(str)
    def _(self, e, id_prefix: str):
        yield pydom.create("span", classes=("pystr",), html=repr(e))

    @display_as_html.register(int)
    @display_as_html.register(float)
    def _(self, e, id_prefix: str):
        yield pydom.create("span", classes=("pynum",), html=repr(e))

    @display_as_html.register(list)
    @display_as_html.register(set)
    @display_as_html.register(tuple)
    def _(self, e: list, id_prefix: str):
        o, c = str(type(e)())
        if not len(e):
            yield pydom.create("span", html=f"{o}{c}")
            return

        yield pydom.create("span", html=f"{o}\n{self.text('')}")
        with self.indent():
            for n, elem in enumerate(e):
                for child in self.display_as_html(elem, f"{id_prefix}[{n}]"):
                    yield child
                    yield pydom.create("span", html=",\n")

        yield pydom.create("span", html=self.text(c))

    @display_as_html.register(cst.CSTNode)
    def _(self, e, id_prefix: str):
        global MODULE, POS, IDDICT
        id_ = f"{id_prefix}.{type(e).__name__}"
        pos = POS.get(e)
        div = pydom.create("div", classes=("cstnode",))
        div.id = IDDICT[e]
        if pos:
            add_event_listener(
                div._js, "click", lambda ev: did_cst_click(ev, pos, self.editor)
            )
        div.create("span", classes=("cstnodename",), html=type(e).__name__)
        div.create("span", html="(\n")
        with self.indent():
            for attr in e.__dataclass_fields__:
                if attr == "__slots__":
                    continue
                div.create("span", html=f"{self.text(attr)}=")
                for child in self.display_as_html(getattr(e, attr), id_prefix=id_):
                    div.append(child)
                div.create("span", html=",\n")

        div.create("span", html=self.text(")"))
        yield div


def render_module_object(editor, module, output):
    pre = pydom.create("pre")
    for node in DisplayNodes(editor, module).as_html():
        pre.append(node)
    output.innerHTML = ""
    output.appendChild(pre._js)


document.getElementById("libcst-version").innerHTML = f"(LibCST {cst._version.version})"
ed = editor.create(
    document.getElementById("editor"),
    to_js(
        {"language": "python", "automaticLayout": True, "value": get_default_content()}
    ),
)
ed.onDidChangeModelContent(create_proxy(lambda _: render_cst(ed)))
ed.onDidChangeCursorPosition(create_proxy(lambda _: scroll_to_cst_node(ed)))
render_cst(ed)
