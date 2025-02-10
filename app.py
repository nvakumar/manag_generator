import os
import json
import requests
import base64
from flask import Flask, render_template, request, redirect, url_for, flash

app = Flask(__name__)
app.secret_key = "supersecretkey"  # For flash messages

# Store character data
CHARACTERS_FILE = "characters.json"
PROFILE_PICS_FOLDER = "static/profile_pics/"

# Ensure profile pictures directory exists
os.makedirs(PROFILE_PICS_FOLDER, exist_ok=True)

def load_characters():
    """Load characters from JSON file."""
    if os.path.exists(CHARACTERS_FILE):
        with open(CHARACTERS_FILE, "r") as file:
            return json.load(file)
    return {}

def save_characters(characters):
    """Save characters to JSON file."""
    with open(CHARACTERS_FILE, "w") as file:
        json.dump(characters, file, indent=4)

characters = load_characters()

@app.route('/')
def home():
    """Homepage showing all characters."""
    return render_template('index.html', characters=characters)

@app.route('/c_character', methods=['GET', 'POST'])
def create_character():
    """Route for creating a new character and generating a profile picture."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        appearance = request.form.get('appearance', '').strip()
        traits = request.form.get('traits', '').strip()

        if not name or not appearance or not traits:
            flash("All fields are required!", "error")
            return redirect(url_for('create_character'))

        # Generate AI manga image for profile picture
        prompt = f"Anime character portrait of {name}. Appearance: {appearance}, Traits: {traits}"

        try:
            response = requests.post(
                "http://127.0.0.1:7870/sdapi/v1/txt2img",
                json={"prompt": prompt, "steps": 30, "cfg_scale": 7.5, "width": 512, "height": 512, "sampler_index": "Euler a"}
            )

            response.raise_for_status()  # Raise error for non-200 status codes
            result = response.json()
            image_data = result.get("images", [None])[0]

            if not image_data:
                flash("Failed to generate character image!", "error")
                return redirect(url_for('create_character'))

            # Decode and save image
            image_decoded = base64.b64decode(image_data)
            character_id = str(len(characters) + 1)
            image_filename = f"profile_{character_id}.png"
            image_path = os.path.join(PROFILE_PICS_FOLDER, image_filename)

            with open(image_path, "wb") as image_file:
                image_file.write(image_decoded)

            profile_pic_url = "/" + image_path.replace("\\", "/")  # Fix for Windows paths

        except Exception as e:
            flash(f"Error generating profile picture: {str(e)}", "error")
            return redirect(url_for('create_character'))

        # Save character details with profile picture
        characters[character_id] = {"name": name, "appearance": appearance, "traits": traits, "profile_pic": profile_pic_url}
        save_characters(characters)

        flash("Character created successfully!", "success")
        return redirect(url_for('home'))

    return render_template('c_character.html')

@app.route('/generate_manga', methods=['POST'])
def generate_manga():
    """Generate a manga image for a story script using characters."""
    story_prompt = request.form.get('story_prompt', '').strip()

    if not story_prompt:
        flash("Story prompt is required!", "error")
        return redirect(url_for('home'))

    # Replace character names with their descriptions
    for character in characters.values():
        story_prompt = story_prompt.replace(
            character["name"],
            f"{character['name']}, {character['appearance']}, {character['traits']}"
        )

    try:
        response = requests.post(
            "http://127.0.0.1:7870/sdapi/v1/txt2img",
            json={"prompt": story_prompt, "steps": 30, "cfg_scale": 7.5, "width": 512, "height": 512, "sampler_index": "Euler a"}
        )

        response.raise_for_status()
        result = response.json()
        manga_image_url = "data:image/png;base64," + result.get("images", [None])[0]

        if not manga_image_url:
            flash("Error generating manga image!", "error")
            return redirect(url_for('home'))

    except Exception as e:
        flash(f"Error generating manga: {str(e)}", "error")
        return redirect(url_for('home'))

    return render_template('generate_manga.html', manga_image=manga_image_url)

@app.route('/delete_character', methods=['POST'])
def delete_character():
    """Route to delete a character."""
    character_key = request.form.get('character_key', '').strip()

    if character_key not in characters:
        flash("Character not found!", "error")
        return redirect(url_for('home'))

    # Delete profile picture file
    profile_pic_path = characters[character_key].get("profile_pic", "").lstrip("/")
    if profile_pic_path and os.path.exists(profile_pic_path):
        os.remove(profile_pic_path)

    del characters[character_key]
    save_characters(characters)

    flash("Character deleted successfully!", "success")
    return redirect(url_for('home'))

if __name__ == "__main__":
    app.run(debug=True, port=5004)
