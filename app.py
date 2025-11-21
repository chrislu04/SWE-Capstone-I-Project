from flask import Flask, request, jsonify, render_template
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

@app.route("/onboarding", methods=["GET", "POST"])
def onboarding():
    if request.method == "POST":
        # Process the form data
        age = request.form.get("age")
        region = request.form.get("region")
        bio = request.form.get("bio")
        genres = request.form.getlist("genres")
        studios = request.form.get("studios")
        themes = request.form.get("themes")

        # For now, just return the collected data
        return jsonify({
            "age": age,
            "region": region,
            "bio": bio,
            "genres": genres,
            "studios": studios,
            "themes": themes
        })
    return render_template("onboarding.html")