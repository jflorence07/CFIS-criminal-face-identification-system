import os
import face_recognition as fr
import numpy as np

# Check if images folder exists
if not os.path.isdir("images"):
    print("❌ 'images' folder not found")
    exit()

# Load all known faces
known_encodings = []
known_face_ids = []

print("Loading known faces from images/ folder...\n")

for filename in os.listdir("images"):
    if not filename.startswith("user.") or not filename.endswith(".png"):
        continue
    
    try:
        parts = filename.split(".")
        if len(parts) >= 3:
            criminal_id = int(parts[1])
            image_path = os.path.join("images", filename)
            
            # Check if file exists and has size
            file_size = os.path.getsize(image_path)
            print(f"Loading {filename} (ID: {criminal_id}, Size: {file_size} bytes)")
            
            img = fr.load_image_file(image_path)
            vectors = fr.face_encodings(img)
            
            if vectors:
                known_encodings.append(vectors[0])
                known_face_ids.append(criminal_id)
                print(f"  ✓ Face encoding found (encoding shape: {vectors[0].shape})")
            else:
                print(f"  ❌ NO FACE DETECTED in {filename}")
                
    except Exception as e:
        print(f"  ❌ Error loading {filename}: {e}")

print(f"\n{'='*60}")
print(f"Total faces loaded: {len(known_encodings)}")
print(f"Face IDs: {known_face_ids}")

# Now compare each face with every other face
if len(known_encodings) > 1:
    print(f"\n{'='*60}")
    print("Comparing faces with each other:\n")
    
    for i in range(len(known_encodings)):
        for j in range(i+1, len(known_encodings)):
            distance = fr.face_distance([known_encodings[i]], known_encodings[j])[0]
            is_match = distance < 0.45
            print(f"User {known_face_ids[i]} vs User {known_face_ids[j]}: Distance = {distance:.4f} | Match: {'✓ YES' if is_match else '✗ NO'}")
