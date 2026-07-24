import gradio as gr

from vibedraw.ui import CSS, build_demo


if __name__ == "__main__":
    demo = build_demo()
    demo.queue(default_concurrency_limit=1, max_size=8)
    demo.launch(
        server_name="127.0.0.1",
        server_port=7860,
        share=False,
        show_error=True,
        theme=gr.themes.Base(),
        css=CSS,
    )
