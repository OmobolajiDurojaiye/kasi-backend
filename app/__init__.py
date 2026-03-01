from flask import Flask
from .config import Config
from .extensions import db, cors

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    cors.init_app(app)
    from .extensions import jwt, migrate
    jwt.init_app(app)
    migrate.init_app(app, db)

    # Register Blueprints
    from .modules.health.routes import health_bp
    app.register_blueprint(health_bp, url_prefix='/api/health')
    
    from .modules.auth.routes import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/api/auth')

    from .modules.invoices.routes import invoices_bp
    from .modules.invoices.routes import invoices_bp
    app.register_blueprint(invoices_bp, url_prefix='/api/invoices')
    
    from .modules.invoices.csv_routes import csv_bp
    app.register_blueprint(csv_bp, url_prefix='/api/invoices')

    # Import models to ensure they are registered with SQLAlchemy for migrations
    from .modules.invoices import models
    from .modules.products import models as product_models
    from .modules.telegram import models as telegram_models
    from .modules.services import models as service_models

    from .modules.products.routes import products_bp
    app.register_blueprint(products_bp, url_prefix='/api/products')
    
    from .modules.webhooks.routes import webhook_bp
    app.register_blueprint(webhook_bp, url_prefix='/api/webhooks')

    from .modules.telegram.routes import telegram_bp
    app.register_blueprint(telegram_bp, url_prefix='/api/telegram')
    
    from .modules.analytics.routes import analytics_bp
    app.register_blueprint(analytics_bp, url_prefix='/api/analytics')

    from .modules.admin.routes import admin_bp
    app.register_blueprint(admin_bp, url_prefix='/api/admin')

    from .modules.billing.routes import billing_bp
    app.register_blueprint(billing_bp, url_prefix='/api/billing')

    from .modules.services.routes import services_bp
    app.register_blueprint(services_bp, url_prefix='/api/services')

    from .modules.whatsapp.routes import whatsapp_bp
    app.register_blueprint(whatsapp_bp, url_prefix='/api/whatsapp')

    return app
