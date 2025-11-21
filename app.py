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

@app.route("/recommendations/beginner")
def beginner_recommendations():
    recommendations = [
        {
            "title": "Death Note",
            "description": "A high school student discovers a supernatural notebook that allows him to kill anyone by writing their name in it."
        },
        {
            "title": "Attack on Titan",
            "description": "In a world where humanity resides within enormous walled cities to protect themselves from giant man-eating humanoids known as Titans, a young man vows to exterminate the Titans after they breach his hometown's wall."
        },
        {
            "title": "Fullmetal Alchemist: Brotherhood",
            "description": "Two brothers search for the Philosopher's Stone after an attempt to revive their deceased mother goes awry and leaves them with damaged bodies."
        },
        {
            "title": "My Hero Academia",
            "description": "In a world where most people have superpowers, a young boy without any enrolls in a prestigious hero academy to learn what it really means to be a hero."
        },
        {
            "title": "Demon Slayer: Kimetsu no Yaiba",
            "description": "A young man becomes a demon slayer to find a cure for his sister, who has been turned into a demon."
        }
    ]
    return render_template("beginner_recommendations.html", recommendations=recommendations)