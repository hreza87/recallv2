from flask import Flask

app = Flask(__name__)


@app.route("/")
def home():
    """Show a simple welcome message."""
    return "Recall is running."


if __name__ == "__main__":
    app.run(debug=True)