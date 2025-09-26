import requests
import json
import os

# Your Gemini API key. Replace 'YOUR_API_KEY' with your actual key.
# This key allows your program to communicate with the Gemini API.
API_KEY = "AIzaSyDMQuUG--AgUmX05YLb6t6SDf3H902sjtA"

# The URL for the Gemini API. We are using the gemini-2.5-flash-preview-05-20 model.
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent?key={API_KEY}"

# The raw text extracted from the lab report.
lab_report_text = """
Regd. No.: XXXX54826XX

Labsmart Software

Sample Letterhead

Mr. Saubhik Bhaumik TT
Age/Sex  :27YRS/M Registered on: 17/10/2024 04:55 PM
Referred by: Self Collected on: 17/10/2024
Reg. no. 1001 Receivedon =: 17/10/2024
Reported on: 17/10/2024 04:55 PM
HAEMATOLOGY
COMPLETE BLOOD COUNT (CBC)

TEST VALUE UNIT REFERENCE
HEMOGLOBIN 15 g/dl 13-17
TOTAL LEUKOCYTE COUNT 5,100 cumm 4,800 - 10,800
DIFFERENTIAL LEUCOCYTE COUNT

NEUTROPHILS, 79 % 40-80

LYMPHOCYTE Lo 18 % 20-40

EOSINOPHILS 1 % 1-6

MONOCYTES Lo4 % 2-10

BASOPHILS 1 % <2
PLATELET COUNT 3.5 lakhs/cumm 15-41
TOTAL RBC COUNT 5 million/cumm 45-55
HEMATOCRIT VALUE, HCT 42 % 40-50
MEAN CORPUSCULAR VOLUME, MCV 84.0 fl 83-101
MEAN CELL HAEMOGLOBIN, MCH 30.0 Pg 27 - 32
MEAN CELL HAEMOGLOBIN CON, MCHC H_ 35.7 % 31.5-34.5

Clinical Notes:

A complete blood count (CBC) is used to evaluate overall health and detect a wide range of disorders, including anemia,
infection, and leukemia. There have been some reports of WBC and platelet counts being lower in venous blood than in
capillary blood samples, although still within these reference ranges.

causes of abnormal parameters

Sle Nets:

Mr. Sachin Sharma Dr. A. K. Asthana
DMLT, Lab Incharge Page 1 of 2 MBBS, MD Pathologist

NOT VALID FOR MEDICO LEGAL PURPOSE
Work timings: Monday to Sunday, 8 am to 8 pm

Please correlate clinically. Although the test results are checked thoroughly, in case of any unexpected test results which
could be due to machine error or typing error or any other reason please contact the lab immediately for a free evaluation.
"""

def parse_lab_report(report_text):
    """
    Sends the lab report text to the Gemini API for parsing and JSON generation.
    The API is instructed to create the JSON structure itself.

    Args:
        report_text (str): The raw text of the lab report.

    Returns:
        dict: A dictionary representing the parsed JSON data, or None on failure.
    """
    
    # The system instruction now contains a detailed description of the JSON structure.
    # This is how we guide the model to produce the desired output without a schema.
    system_instruction = {
        "parts": [{
            "text": """
            You are an expert at parsing medical lab reports and formatting the data into JSON.
            Your task is to extract all the key information from the provided lab report text and format it into a single JSON object.
            
            Strictly follow these rules:
            1. The final output MUST be a single JSON object.
            2. The JSON object MUST have the following top-level keys:
               - "reportDetails": An object containing details like "regNo", "registeredOn", "collectedOn", "receivedOn", and "reportedOn".
               - "patientDetails": An object with "name", "age" (as a number), and "sex".
               - "labDetails": An object with "labName", "labIncharge" (an object with name and qualification), and "pathologist" (an object with name and qualification).
               - "testResults": An array of objects. Each object in this array must contain "testName", "value", "unit", and "referenceRange".
               - "clinicalNotes": A string containing the clinical notes.
               - "abnormalParametersNotes": A string for notes on abnormal parameters.
            3. Extract all fields and populate the JSON object.
            4. For test results, parse each line in the "HAEMATOLOGY" section into a separate object within the "testResults" array.
            5. Clean the data. For example, remove extra words like "Lo" and "H_" from the value field and place them in the test name, if necessary.
            """
        }]
    }

    # The payload for the API request. Note the absence of the 'responseSchema'.
    payload = {
        "contents": [{"parts": [{"text": report_text}]}],
        "systemInstruction": system_instruction,
        "generationConfig": {
            "responseMimeType": "application/json",
        }
    }

    try:
        # Make the API request
        response = requests.post(API_URL, json=payload)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)

        # Parse the JSON response and return the content
        response_data = response.json()
        raw_json_string = response_data['candidates'][0]['content']['parts'][0]['text']
        return json.loads(raw_json_string)
    except requests.exceptions.RequestException as e:
        print(f"API request failed: {e}")
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        print(f"Error parsing API response: {e}")
        print("Raw response:", response.text)
    
    return None

# --- Main execution block ---
if __name__ == "__main__":
    print("Sending lab report text to Gemini for parsing...")
    
    parsed_report = parse_lab_report(lab_report_text)
    
    if parsed_report:
        print("\n--- Successfully Parsed Lab Report (JSON) ---")
        # Pretty-print the JSON for readability
        print(json.dumps(parsed_report, indent=4))
        print("---------------------------------------------")
    else:
        print("\nFailed to parse the lab report. Please check your API key and the console for errors.")
