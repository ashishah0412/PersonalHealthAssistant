# This program uses pytesseract to extract text from an image.
# It requires the Tesseract OCR engine to be installed on your system.

import pytesseract
from PIL import Image
import os

def extract_text_from_image(image_path):
    """
    Extracts text from an image file using the Tesseract OCR engine.

    Args:
        image_path (str): The path to the image file.

    Returns:
        str: The extracted text, or an error message if the operation fails.
    """
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'  # Update this path if necessary
    

    if not os.path.exists(image_path):
        return f"Error: Image file not found at '{image_path}'."

    try:
        # Open the image using Pillow (PIL)
        image = Image.open(image_path)

        # Use pytesseract to perform OCR on the image.
        # The image_to_string() function will return the recognized text.
        text = pytesseract.image_to_string(image)

        return text.strip()  # .strip() removes leading/trailing whitespace

    except pytesseract.TesseractNotFoundError:
        return "Error: Tesseract is not installed or not in your PATH. Please install it."
    except Exception as e:
        return f"An unexpected error occurred: {e}"

# --- Main execution block ---
if __name__ == "__main__":
    # Replace 'sample_image.png' with the path to your own image file.
    # The image should contain some text for the OCR to process.
    image_file = 'A4sizeSD.png'

    print(f"Attempting to extract text from '{image_file}'...")
    extracted_text = extract_text_from_image(image_file)

    if extracted_text.startswith("Error"):
        print(extracted_text)
    else:
        print("\n--- Extracted Text ---")
        print(extracted_text)
        print("----------------------")
