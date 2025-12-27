from ai_context_studio.config.settings import APP_NAME, APP_VERSION, APP_AUTHOR
from ai_context_studio.ui.app import AIContextStudioApp

def main():
    print(f"\n{'='*60}")
    print(f"  {APP_NAME} v{APP_VERSION}")
    print(f"  by {APP_AUTHOR}")
    print(f"{'='*60}\n")

    app = AIContextStudioApp()
    app.mainloop()

if __name__ == "__main__":
    main()
