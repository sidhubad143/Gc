import os

import numpy as np
import tensorflow as tf
import tensorflow_hub as hub
from tensorflow import keras

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MODEL PATHS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_DIR = os.path.dirname(__file__)

NSFW_MODEL_PATH   = os.path.join(_DIR, 'nsfw_model',   'nsfw_mobilenet2.224x224.h5')
OBJECT_MODEL_PATH = os.path.join(_DIR, 'object_model', 'ssd_mobilenet_v2_coco.h5')

# Media dir — same as scrapped/ in repo root
MEDIA_DIR = os.path.join(_DIR, '..', '..', 'scrapped')

IMAGE_DIM = 224


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MEDIA HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_media_path(user_id: int, file_id: str) -> str:
    """
    Standardized path for downloaded images.

    Usage in plugin:
        path = get_media_path(message.from_user.id, file.file_id)
        await client.download_media(message, file_name=path)
        result = detect_nsfw(path)   # auto-deletes after scan
    """
    os.makedirs(MEDIA_DIR, exist_ok=True)
    return os.path.join(MEDIA_DIR, f"{user_id}_{file_id}.jpg")


def clean_media_folder() -> bool:
    """
    MEDIA_DIR (scrapped/) saaf karda — sari downloaded images delete.
    __init__.py startup te already scrapped/ clean hundi hai,
    par bot chal rahe vich bhi manually call kar sakte:
        from Powers.utils.predict import clean_media_folder
        clean_media_folder()
    """
    try:
        if not os.path.exists(MEDIA_DIR):
            os.makedirs(MEDIA_DIR, exist_ok=True)
            return True

        deleted = 0
        for filename in os.listdir(MEDIA_DIR):
            file_path = os.path.join(MEDIA_DIR, filename)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
                    deleted += 1
                elif os.path.isdir(file_path):
                    os.rmdir(file_path)
            except Exception:
                pass

        from Powers import LOGGER
        LOGGER.info(f"[clean_media_folder] Deleted {deleted} files from {MEDIA_DIR}")
        return True

    except Exception as e:
        try:
            from Powers import LOGGER
            LOGGER.error(f"[clean_media_folder] Failed: {e}")
        except Exception:
            pass
        return False

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COCO CLASS IDs for weapons/drugs detection
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# COCO dataset class indices (0-indexed)
WEAPON_CLASS_IDS = {
    # Directly available in COCO
    43: "knife",
    76: "scissors",
}

# Drugs not in COCO — handled via keyword detection on labels
DRUG_KEYWORDS = [
    "syringe", "needle", "pill", "pills", "tablet",
    "powder", "cocaine", "drugs", "marijuana", "weed",
    "injection", "vial", "bottle"
]

WEAPON_KEYWORDS = [
    "gun", "pistol", "rifle", "weapon", "firearm",
    "knife", "blade", "sword", "grenade", "bomb",
    "explosive", "ammunition", "bullet"
]

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LOAD MODELS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def load_nsfw_model():
    return tf.keras.models.load_model(
        NSFW_MODEL_PATH,
        custom_objects={'KerasLayer': hub.KerasLayer},
        compile=False
    )


def load_object_model():
    """
    Load object detection model (SSD MobileNet V2 COCO).
    Returns None if model file not found — detection will be skipped.
    """
    if not os.path.exists(OBJECT_MODEL_PATH):
        return None
    try:
        return tf.keras.models.load_model(
            OBJECT_MODEL_PATH,
            custom_objects={'KerasLayer': hub.KerasLayer},
            compile=False
        )
    except Exception:
        return None


# Load at startup
nsfw_model   = load_nsfw_model()
object_model = load_object_model()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# NSFW CLASSIFICATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def classify_nsfw(image_path: str) -> dict:
    """
    Returns probabilities for each NSFW category.
    {
        'drawings': 0.01,
        'hentai':   0.02,
        'neutral':  0.90,
        'porn':     0.05,
        'sexy':     0.02
    }
    """
    img = keras.preprocessing.image.load_img(
        image_path, target_size=(IMAGE_DIM, IMAGE_DIM)
    )
    img = keras.preprocessing.image.img_to_array(img) / 255.0
    img = np.expand_dims(img, axis=0)

    categories   = ['drawings', 'hentai', 'neutral', 'porn', 'sexy']
    predictions  = nsfw_model.predict(img)[0]

    return {cat: float(predictions[i]) for i, cat in enumerate(categories)}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# OBJECT DETECTION (weapons / drugs)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def classify_objects(image_path: str, confidence: float = 0.45) -> dict:
    """
    Detect weapons and drug-related objects in image.
    Returns:
    {
        'has_weapon': True/False,
        'has_drugs':  True/False,
        'detections': [{'label': 'gun', 'confidence': 0.87}, ...]
    }
    """
    result = {
        'has_weapon': False,
        'has_drugs':  False,
        'detections': []
    }

    if object_model is None:
        return result  # Model not loaded — skip silently

    try:
        img = keras.preprocessing.image.load_img(
            image_path, target_size=(IMAGE_DIM, IMAGE_DIM)
        )
        img = keras.preprocessing.image.img_to_array(img) / 255.0
        img = np.expand_dims(img, axis=0)

        raw = object_model.predict(img)

        # raw shape: (1, num_detections, 6) — [y1, x1, y2, x2, class_id, score]
        # Adjust based on your actual model output format
        detections = raw[0] if len(raw.shape) == 3 else raw

        for det in detections:
            score    = float(det[5]) if len(det) > 5 else float(det[4])
            class_id = int(det[4])   if len(det) > 5 else int(det[3])
            label    = WEAPON_CLASS_IDS.get(class_id, f"class_{class_id}").lower()

            if score < confidence:
                continue

            is_weapon = any(w in label for w in WEAPON_KEYWORDS)
            is_drug   = any(d in label for d in DRUG_KEYWORDS)

            if is_weapon or is_drug:
                result['detections'].append({
                    'label':      label,
                    'confidence': round(score, 3),
                    'type':       'weapon' if is_weapon else 'drug'
                })
                if is_weapon:
                    result['has_weapon'] = True
                if is_drug:
                    result['has_drugs'] = True

    except Exception:
        pass  # Detection failed — return empty result

    return result


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MAIN DETECT FUNCTION — use this in your bot
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def detect_nsfw(image_path: str) -> dict:
    """
    Full detection — NSFW + weapons + drugs.

    Returns:
    {
        'nsfw': {
            'drawings': 0.01, 'hentai': 0.02,
            'neutral': 0.90,  'porn': 0.05, 'sexy': 0.02
        },
        'is_nsfw':   True/False,   # porn/hentai > 40%
        'is_sexy':   True/False,   # sexy > 50%
        'has_weapon': True/False,
        'has_drugs':  True/False,
        'detections': [...]        # weapon/drug detections
    }
    """
    try:
        nsfw    = classify_nsfw(image_path)
        objects = classify_objects(image_path)

        result = {
            'nsfw':       nsfw,
            'is_nsfw':    (nsfw.get('porn', 0) + nsfw.get('hentai', 0)) > 0.40,
            'is_sexy':    nsfw.get('sexy', 0) > 0.50,
            'has_weapon': objects['has_weapon'],
            'has_drugs':  objects['has_drugs'],
            'detections': objects['detections'],
        }

        return result

    finally:
        # Always delete temp image
        try:
            os.remove(image_path)
        except Exception:
            pass


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# USAGE EXAMPLE (bot plugin vich)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# from Powers.utils.predict import detect_nsfw
#
# result = detect_nsfw("/tmp/photo.jpg")
#
# if result['is_nsfw']:
#     await message.delete()
#     await bot.send_message(chat_id, "🔞 NSFW content not allowed!")
#
# if result['has_weapon']:
#     await message.delete()
#     await bot.send_message(chat_id, "🔫 Weapon detected — not allowed!")
#
# if result['has_drugs']:
#     await message.delete()
#     await bot.send_message(chat_id, "💊 Drug-related content — not allowed!")
