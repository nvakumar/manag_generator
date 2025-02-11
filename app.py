import os
import json
import requests
import base64
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify  # Added jsonify

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
            print(f"Sending request to Stable Diffusion with prompt: {prompt}")

            response = requests.post(
                "http://127.0.0.1:7860/sdapi/v1/txt2img",  
                json={"prompt": prompt, "steps": 30, "cfg_scale": 7.5, "width": 512, "height": 512, "sampler_index": "Euler a"}
            )

            response.raise_for_status()
            result = response.json()
            print(f"API Response: {result}")

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

            profile_pic_url = "/" + image_path.replace("\\", "/")  

        except Exception as e:
            flash(f"Error generating profile picture: {str(e)}", "error")
            return redirect(url_for('create_character'))

        characters[character_id] = {"name": name, "appearance": appearance, "traits": traits, "profile_pic": profile_pic_url}
        save_characters(characters)

        flash("Character created successfully!", "success")
        return redirect(url_for('home'))

    return render_template('c_character.html')

@app.route('/generate_manga', methods=['POST'])
def generate_manga():
    """Generate a manga image using Stable Diffusion and ControlNet."""
    story_prompt = request.form.get('story_prompt', '').strip()
    reference_image = request.files.get('reference_image')

    if not story_prompt:
        return jsonify({"error": "Story prompt is required!"}), 400

    base64_image = None

    # ✅ Step 1: Convert Reference Image to Base64
    if reference_image:
        try:
            base64_image = base64.b64encode(reference_image.read()).decode('utf-8')
            print("✅ Image successfully converted to Base64")
        except Exception as e:
            print(f"❌ Error encoding image: {str(e)}")
            return jsonify({"error": f"Image processing error: {str(e)}"}), 500

    try:
        # ✅ Step 2: Define API Request
        request_data = {
            "prompt": f"{story_prompt}, anime style, high detail",
            "steps": 30,
            "cfg_scale": 7.5,
            "width": 512,
            "height": 512,
            "sampler_index": "Euler a"
        }

        # ✅ Step 3: Add ControlNet (If Image is Provided)
        if base64_image:
            request_data["alwayson_scripts"] = {
                "controlnet": {
                    "args": [
                        {
                            "enabled": True,
                            "input_image": base64_image,  # Send Base64 image instead of file path
                            "module": "canny",  # Make sure 'canny' is supported
                            "model": "control_v11p_sd15_canny",  # Ensure correct model is loaded
                            "weight": 1.0,
                            "resize_mode": 1,  # Resize to match dimensions
                            "threshold_a": 64,
                            "threshold_b": 128
                        }
                    ]
                }
            }
            print("✅ ControlNet settings added to request.")

        # ✅ Step 4: Send Request to Stable Diffusion
        print("📤 Sending request to Stable Diffusion API...")
        response = requests.post("http://127.0.0.1:7860/sdapi/v1/txt2img", json=request_data)
        response.raise_for_status()

        result = response.json()
        manga_image_url = "data:image/png;base64," + result.get("images", [None])[0]

        if not manga_image_url:
            return jsonify({"error": "Error generating manga image!"}), 500

        print("✅ Manga image successfully generated!")
    except requests.exceptions.RequestException as e:
        print(f"❌ API Request Error: {str(e)}")
        return jsonify({"error": f"API Request Error: {str(e)}"}), 500
    except json.JSONDecodeError:
        print("❌ Error: Invalid JSON response from API")
        return jsonify({"error": "Invalid response from API"}), 500

    return jsonify({"manga_image": manga_image_url})

@app.route('/edit_manga', methods=['POST'])
def edit_manga():
    """Apply inpainting to refine the manga panel."""
    manga_image = request.form.get('manga_image', '').strip()

    if not manga_image:
        flash("No image provided for inpainting!", "error")
        return redirect(url_for('home'))

    try:
        response = requests.post(
            "http://127.0.0.1:7860/sdapi/v1/img2img",  
            json={
                "init_images": [manga_image],
                "prompt": "Refined version of the given manga panel, fixing any artifacts or distortions",
                "steps": 50,
                "cfg_scale": 7.5,
                "denoising_strength": 0.5,
                "sampler_index": "Euler a"
            }
        )

        response.raise_for_status()
        result = response.json()
        inpainted_image_url = "data:image/png;base64," + result.get("images", [None])[0]

        if not inpainted_image_url:
            flash("Error inpainting manga image!", "error")
            return redirect(url_for('home'))

    except Exception as e:
        flash(f"Error inpainting manga: {str(e)}", "error")
        return redirect(url_for('home'))

    return render_template('generate_manga.html', manga_image=inpainted_image_url)

@app.route('/delete_character', methods=['POST'])
def delete_character():
    """Route to delete a character."""
    character_key = request.form.get('character_key', '').strip()

    if character_key not in characters:
        flash("Character not found!", "error")
        return redirect(url_for('home'))

    del characters[character_key]
    save_characters(characters)

    flash("Character deleted successfully!", "success")
    return redirect(url_for('home'))

if __name__ == "__main__":
    app.run(debug=True, port=5006)