from app import create_app
import os

app = create_app()

if __name__ == "__main__":
    # Usa porta definida no ambiente ou padrão 3333
    port = int(os.environ.get("PORT", 3333))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG", "false").lower() == "true")