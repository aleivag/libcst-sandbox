var editor; // the editor object, we will interact with this from python
var EDITOR_CONTENT_KEY = "editor-content"
var lastDecorations = null;


function py_proxy_render_cst() {
    var model_content = editor.getModel().getValue();
    localStorage.setItem(EDITOR_CONTENT_KEY, model_content);
    pyscript.interpreter.globals.get("render_cst")(model_content);
}


function py_proxy_scroll_to_cst_node_by_pos(event) {
    var position = editor.getPosition();
    var line = position.lineNumber;
    var column = position.column;
    var word = editor.getModel().getValueInRange(editor.getSelection());

    node_id = pyscript.interpreter.globals.get("get_node_id_by_pos")(line, column)
    console.info(node_id, event)
    setTimeout(() => document.getElementById(node_id).scrollIntoView({ behavior: 'smooth', block: 'center' }), 300);
    $(".hghlight").removeClass("hghlight")
    $(document.getElementById(node_id)).addClass("hghlight");
    document.getElementById('status-bar').innerText = `Line: ${line}, Column: ${column}, Word: ${word.length}`;
    document.getElementById('render-footer').innerText = `id: ${node_id}`;

}

function didCstClick(event, range) {
    event.stopPropagation();
    if (lastDecorations !== null) {
        lastDecorations.clear();
    }
    lastDecorations = editor.createDecorationsCollection([{options:{className: "hghlight"}, range}]);
    
}


function load() {
    var editorValue = localStorage.getItem(EDITOR_CONTENT_KEY) || [
        'def main(arg: None|str = None) -> int :',
        '    return 42',
        '',
        'if __name__ == "__main__":',
        '    main()'
    ].join('\n')

    require.config({ paths: { 'vs': 'https://cdn.jsdelivr.net/npm/monaco-editor@0.43.0/min/vs' } });

    require(['vs/editor/editor.main'], function () {
        // Create the editor instance
        editor = monaco.editor.create(document.getElementById('editor'), {
            value: editorValue,
            language: 'python',
            automaticLayout: true
        });

        editor.onDidChangeModelContent(py_proxy_render_cst);
        editor.onDidChangeCursorPosition(py_proxy_scroll_to_cst_node_by_pos)
        py_proxy_render_cst()
    });
}
