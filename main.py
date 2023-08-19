import js
import libcst as cst


from pygments import highlight
from pygments.lexers import PythonLexer
from pygments.formatters import HtmlFormatter

def load():
    linkElement = js.document.createElement('link');
    linkElement.rel = 'stylesheet';
    linkElement.href = 'https://cdn.jsdelivr.net/npm/monaco-editor@0.41.0/min/vs/editor/editor.main.css';

    scriptElement = js.document.createElement('script');
    scriptElement.src = 'https://cdn.jsdelivr.net/npm/monaco-editor@0.41.0/min/vs/loader.js';
    scriptElement.setAttribute("onload", "load()")

    js.document.head.appendChild(linkElement);
    js.document.head.appendChild(scriptElement);

def click():
    js.console.log(js.editor.getModel().getValue())

def render_cst(module_text:str, **kwargs) -> None:
    parsed_module = cst.parse_module(module_text)
    lexer = PythonLexer()
    formatter = HtmlFormatter(style='colorful')
    highlighted_code = highlight(str(parsed_module), lexer, formatter)
    js.document.getElementById("renderPanel").innerHTML = highlighted_code
    return parsed_module



load()