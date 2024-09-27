from PIL import Image
from rembg import remove

# Load the image
input_path = './out-0.webp'
output_path = './snap.png'

# Open the image file
with open(input_path, 'rb') as img_file:
    img_data = img_file.read()

# Remove the background
output = remove(img_data)

# Save the result to a new file with a transparent background
with open(output_path, 'wb') as out_file:
    out_file.write(output)

print(f"Image with background removed saved at {output_path}")
