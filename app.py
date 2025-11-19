from flask import Flask, request, jsonify
import config
import os
config.ensure_config()


from models import db

app = Flask(__name__)
app.config["SECRET_KEY"] = config.SECRET_KEY
app.config["SQLALCHEMY_DATABASE_URI"] = config.DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize SQLAlchemy
db.init_app(app)

@app.route("/health")
def health():
	return jsonify({"status": "ok"})