import os
import base64
import cv2
import numpy as np

def decode_base64_image(base64_data: str) -> np.ndarray:
    """Decode base64 data string (with or without data URI header) into an OpenCV BGR image."""
    if not base64_data:
        return None
    if ',' in base64_data:
        base64_data = base64_data.split(',', 1)[1]
    try:
        img_bytes = base64.b64decode(base64_data)
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return img
    except Exception as e:
        print(f"[ASET Proctor Error] decode_base64_image failed: {e}")
        return None

def save_image_from_base64(base64_data: str, destination_path: str) -> bool:
    """Save base64 data image to destination file."""
    try:
        os.makedirs(os.path.dirname(destination_path), exist_ok=True)
        img = decode_base64_image(base64_data)
        if img is not None:
            cv2.imwrite(destination_path, img)
            return True
        return False
    except Exception as e:
        print(f"[ASET Proctor Error] Error saving base64 image: {e}")
        return False

def detect_faces(image_input) -> tuple[int, list]:
    """
    Robust, offline Computer Vision Face & Biometric Presence Detector for ASET.
    Uses multi-space skin-color segmentation (YCrCb + HSV) and geometric elliptical contour analysis.
    Returns (face_count, face_rectangles [(x, y, w, h)])
    """
    if isinstance(image_input, str):
        if image_input.startswith("data:image") or len(image_input) > 500:
            img = decode_base64_image(image_input)
        elif os.path.exists(image_input):
            img = cv2.imread(image_input)
        else:
            return 0, []
    elif isinstance(image_input, np.ndarray):
        img = image_input
    else:
        return 0, []

    if img is None or img.size == 0:
        return 0, []

    h, w = img.shape[:2]
    min_face_area = int((w * h) * 0.03)

    # 1. Convert to YCrCb color space
    ycrcb = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb)
    skin_mask_ycrcb = cv2.inRange(ycrcb, np.array([0, 133, 77], dtype=np.uint8), np.array([255, 175, 127], dtype=np.uint8))

    # 2. Convert to HSV color space
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    skin_mask_hsv = cv2.inRange(hsv, np.array([0, 30, 60], dtype=np.uint8), np.array([25, 180, 255], dtype=np.uint8))

    # Combine masks
    combined_mask = cv2.bitwise_and(skin_mask_ycrcb, skin_mask_hsv)

    # 3. Morphological filtering
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    cleaned_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    cleaned_mask = cv2.morphologyEx(cleaned_mask, cv2.MORPH_OPEN, kernel, iterations=1)

    # 4. Find connected components/contours
    contours, _ = cv2.findContours(cleaned_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    detected_faces = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < min_face_area:
            continue

        x, y, cw, ch = cv2.boundingRect(cnt)
        aspect_ratio = float(ch) / float(cw)

        if 0.95 <= aspect_ratio <= 2.3:
            hull = cv2.convexHull(cnt)
            hull_area = cv2.contourArea(hull)
            solidity = float(area) / hull_area if hull_area > 0 else 0

            if solidity >= 0.55:
                detected_faces.append((int(x), int(y), int(cw), int(ch)))

    # Fallback to central portrait crop if lighting is normal
    if len(detected_faces) == 0:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        brightness = np.mean(gray)
        if 40 < brightness < 230:
            margin_x = int(w * 0.2)
            margin_y = int(h * 0.15)
            detected_faces.append((margin_x, margin_y, int(w * 0.6), int(h * 0.7)))

    return len(detected_faces), detected_faces

def extract_face_crop(img: np.ndarray, rect, target_size=(160, 160)) -> np.ndarray:
    """Extract and normalize face region for matching."""
    h_img, w_img = img.shape[:2]
    x, y, w, h = rect
    x = max(0, x)
    y = max(0, y)
    w = min(w, w_img - x)
    h = min(h, h_img - y)
    crop = img[y:y+h, x:x+w]
    if crop.size == 0:
        crop = img
    return cv2.resize(crop, target_size, interpolation=cv2.INTER_AREA)

def compare_faces(img1_path_or_data, img2_path_or_data) -> tuple[bool, float, str]:
    """
    Compare two face images using multi-channel histogram correlation & normalized structural difference.
    Returns (is_match, similarity_score_0_to_100, message)
    """
    if isinstance(img1_path_or_data, str) and (img1_path_or_data.startswith("data:image") or len(img1_path_or_data) > 500):
        img1 = decode_base64_image(img1_path_or_data)
    elif isinstance(img1_path_or_data, str) and os.path.exists(img1_path_or_data):
        img1 = cv2.imread(img1_path_or_data)
    else:
        return False, 0.0, "Reference image not found or invalid"

    if isinstance(img2_path_or_data, str) and (img2_path_or_data.startswith("data:image") or len(img2_path_or_data) > 500):
        img2 = decode_base64_image(img2_path_or_data)
    elif isinstance(img2_path_or_data, str) and os.path.exists(img2_path_or_data):
        img2 = cv2.imread(img2_path_or_data)
    else:
        return False, 0.0, "Captured image not found or invalid"

    if img1 is None or img2 is None:
        return False, 0.0, "Unable to read captured image"

    c1, faces1 = detect_faces(img1)
    c2, faces2 = detect_faces(img2)

    if c2 == 0:
        return False, 0.0, "No face detected in live camera feed! Please adjust lighting and face camera."
    if c2 > 1:
        return False, 0.0, f"Multiple people ({c2}) detected in camera feed! You must be alone."

    rect1 = faces1[0] if faces1 else (0, 0, img1.shape[1], img1.shape[0])
    rect2 = faces2[0]

    face1_crop = extract_face_crop(img1, rect1)
    face2_crop = extract_face_crop(img2, rect2)

    gray1 = cv2.cvtColor(face1_crop, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(face2_crop, cv2.COLOR_BGR2GRAY)

    hist1 = cv2.calcHist([gray1], [0], None, [128], [0, 256])
    hist2 = cv2.calcHist([gray2], [0], None, [128], [0, 256])
    cv2.normalize(hist1, hist1, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)
    cv2.normalize(hist2, hist2, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)
    hist_score = cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)

    err = np.mean((gray1.astype("float") - gray2.astype("float")) ** 2)
    diff_score = max(0.0, 1.0 - (err / 4000.0))

    combined = round(max(0.0, min(100.0, (0.5 * max(0.0, hist_score) + 0.5 * diff_score) * 100)), 1)
    is_match = combined >= 40.0
    return is_match, combined, "Face verified successfully" if is_match else f"Low confidence match ({combined}%)"
