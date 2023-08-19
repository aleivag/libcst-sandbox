var editor; // the editor object, we will interact with this from python

function py_proxy_render_cst() {
    var model_content = editor.getModel().getValue();
    pyscript.interpreter.globals.get("render_cst")(model_content)
}

function load() {
    require.config({ paths: { 'vs': 'https://cdn.jsdelivr.net/npm/monaco-editor@0.27.0/min/vs' } });
    require(['vs/editor/editor.main'], function () {
        // Create the editor instance
        editor = monaco.editor.create(document.getElementById('editor-container'), {
            value: [
                'def main(arg: None|str = None) -> int :',
                '    return 42',
                '',
                'if __name__ == "__main__":',
                '    main()'
            ].join('\n'),
            language: 'python',
            automaticLayout: true
        });

        editor.onDidChangeModelContent(py_proxy_render_cst);
        py_proxy_render_cst()

        // pyscript.interpreter.globals
    });
}