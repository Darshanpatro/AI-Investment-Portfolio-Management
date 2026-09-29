"""
Application entry point.

Run with:  python app.py
This will create the SQLite database (if it doesn't exist), load
sample market data, build the RAG knowledge index, and start the Flask
development server.
"""

import os
import traceback
from flask import Flask, render_template
from flask_login import LoginManager

from config import Config
from database.database import db
from database.models import User


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "warning"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # --- Blueprints ---------------------------------------------------
    from routes.auth import auth_bp
    from routes.portfolio import portfolio_bp
    from routes.analytics import analytics_bp
    from routes.risk import risk_bp
    from routes.alerts import alerts_bp
    from routes.ai import ai_bp
    from routes.knowledge import knowledge_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(portfolio_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(risk_bp)
    app.register_blueprint(alerts_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(knowledge_bp)

    # --- Graceful error handling (no stack traces shown to users) -----
    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors.html", code=404, message="Page not found."), 404

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors.html", code=403, message="You don't have access to that page."), 403

    @app.errorhandler(500)
    def server_error(e):
        app.logger.error("Internal server error:\n" + traceback.format_exc())
        return render_template("errors.html", code=500, message="Something went wrong on our end. Please try again."), 500

    # --- One-time startup data loading ---------------------------------
    with app.app_context():
        os.makedirs(os.path.join(Config.BASE_DIR, "database"), exist_ok=True)
        db.create_all()

        from services.market_data_service import load_market_data_into_db
        loaded = load_market_data_into_db()
        if loaded:
            app.logger.info(f"Loaded {loaded} historical market data rows.")

        from services.rag_service import sync_knowledge_documents_table
        from database.models import KnowledgeDocument
        if KnowledgeDocument.query.count() == 0:
            docs = sync_knowledge_documents_table(Config.KNOWLEDGE_DOCS_DIR)
            app.logger.info(f"Indexed {len(docs)} knowledge base documents.")

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
