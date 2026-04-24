"""BGX Navigation Dashboard - Main application entry point."""

import os
from fasthtml.common import fast_app, serve
from src.routes import setup_routes


# Initialize the FastHTML app
app, rt = fast_app()

# Setup all routes
setup_routes(app, rt)


if __name__ == "__main__":
    # Support environment variables for deployment
    port = int(os.getenv("PORT", 5001))
    host = os.getenv("HOST", "0.0.0.0")
    serve(host=host, port=port)

