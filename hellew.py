import replicate
from pymongo import MongoClient
import PyPDF2
import os
import google.generativeai as genai
import xml.etree.ElementTree as ET
import json
import tqdm
from groq import Groq
# import tts
import random
from PIL import Image
import random
import string
from rembg import remove
import re

client_groq = Groq(
    api_key=os.environ.get("GROQ_API_KEY"),
)
client = MongoClient('mongodb://localhost:27017/')
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
femalevoices=["us-female-1", "us-female-2", "us-female-3", "us-female-4", "us-female-5", "us-female-6", "us-female-7", "us-female-8", "us-female-9", "us-female-10"] #example for now
malevoices=["us-male-1", "us-male-2", "us-male-3", "us-male-4", "us-male-5", "us-male-6", "us-male-7", "us-male-8", "us-male-9", "us-male-10"] #example for now
def extract_xml(text):
    start = text.find("<characters>")
    end = text.find("</characters>") + len("</characters>")
    if start != -1 and end != -1:
        return text[start:end]
    else:
        return None
    
def xml_to_json(xml_string):
    root = ET.fromstring(xml_string)
    characters_list = []
    for character in root.findall('character'):
        name = character.find('name').text
        description = character.find('description').text
        gender = character.find('gender').text
        characters_list.append({
            "name": name,
            "description": description,
            "gender": gender
        })
    return json.dumps(characters_list, indent=4)



def get_character_info(character_name: str, novel_text: str) -> dict:
    instruction = f"""<novel>{novel_text}</novel>
    Generate detailed information for the character named {character_name}. 
    Return it in XML format as follows:
    <character>
    <name>{character_name}</name>
    <description>An elaborate and well-described description of the character's physical appearance</description>
    <gender>their gender (male or female)</gender>
    </character>
    """
    
    generation_config = {
        "temperature": 0.3,
        "top_p": 0.95,
        "top_k": 64,
        "max_output_tokens": 8192,
        "response_mime_type": "text/plain",
    }

    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        generation_config=generation_config,
    )

    chat_session = model.start_chat(history=[])
    response = chat_session.send_message(instruction).text
    
    import re

    # Extract the content within the <character> tags
    print(response)
    response = re.search(r'<character>.*?</character>', response, re.DOTALL)

    xml_data = ET.fromstring(response.group(0))
    character_info = {
        "name": xml_data.find("name").text,
        "description": xml_data.find("description").text,
        "gender": xml_data.find("gender").text
    }

    return character_info
import urllib.request
def get_or_create_character(db, character_name: str, novel_text: str) -> dict:
    characters_collection = db['characters']
    character = characters_collection.find_one({"name": character_name})
    
    if character is None:
        character_info = get_character_info(character_name, novel_text)
        image_online_link = generate_character(character_info["description"])
        #download the image
        #offline name should be random string of length 10
        offline_image_path = ''.join(random.choices(string.ascii_letters + string.digits, k=10)) + ".png"
        urllib.request.urlretrieve(image_online_link, offline_image_path)
        image = clear_background(offline_image_path)
        voicelist = femalevoices if character_info["gender"].lower() == "female" else malevoices
        voice = random.choice(voicelist)
        voicelist.remove(voice)
        
        character_doc = {
            "name": character_info["name"],
            "description": character_info["description"],
            "gender": character_info["gender"],
            "image": image_online_link,
            "voice": voice
        }
        
        characters_collection.insert_one(character_doc)
        return character_doc
    else:
        return character



def get_scene_info(section_text: str, character_names: list) -> str:
        screenplay_prompt=f"""Your job is to return the entire scene properly structured in xml format, along with a max of 2-3 background settings and their descriptions. There should be atleast 5-6 dialogues for each scene, unless its with a narrator, who is also considered a character. If a character in the dialogues is in the list:{character_names}, use only the EXACT name from the list. \nExample\n<scenes>\n<scene>\n<background> An extremely elaborate description of the background to be used </background>\n<dialogues>\n<character_name> Dialogue.... </character_name>\n<character_name> Dialogue.... </character_name>\n.\n.\n.\n</dialogues>\n</scene>\n.\n.\n.\n</scenes>
                        Example of a scene: 
                        <scene>
                            <background>The interior of the Dursleys' car, a somewhat battered family saloon. The windows are steamed up from the summer heat and the air is thick with the smell of cheap petrol and stale cigarettes.</background>
                            <dialogues>
                            <dialogue id="Narrator">"The old fat man was thundering about, angry at the thought of wizards and witches."</dialogue>
                            <dialogue id="Uncle Vernon">"... roaring along like maniacs, the young hoodlums,"</dialogue>
                            <dialogue id="Harry Potter">"I had a dream about a motorcycle. It was flying. "</dialogue>
                            <dialogue id="Uncle Vernon">"MOTORCYCLES DON'T FLY!"</dialogue>
                            <dialogue id="Dudley">"(Sniggering)"</dialogue>
                            <dialogue id="Piers">"(Sniggering)"</dialogue>
                            <dialogue id="Harry Potter">"I know they don't. It was only a dream."</dialogue>
                            </dialogues>
                        </scene>
                        
                        <scene>
                            <background>A dimly lit street in the Muggle world, with old-fashioned street lamps casting a warm glow. The houses are small and ordinary, with neat gardens and tidy curtains. The atmosphere is quiet and suburban.</background>
                            <dialogues>
                            <dialogue id="Narrator">"The cat's tail twitched and its eyes narrowed."</dialogue>
                            <dialogue id="Albus Dumbledore">"I should have known."</dialogue>
                            <dialogue id="Albus Dumbledore">"Fancy seeing you here, Professor McGonagall."</dialogue>
                            <dialogue id="Professor McGonagall">"How did you know it was me?"</dialogue>
                            <dialogue id="Albus Dumbledore">"My dear Professor, I've never seen a cat sit so stiffly."</dialogue>
                            <dialogue id="Professor McGonagall">"You'd be stiff if you'd been sitting on a brick wall all day."</dialogue>
                            </dialogues>
                            </scene>

                            <scene>
                            <background>The platform, with the red-haired family saying their goodbyes. The mother is fussing over Ron, trying to clean his nose.</background>
                            <dialogues>
                                <dialogue id="Mrs. Weasley">Ron, you've got something on your nose.</dialogue>
                                <dialogue id="Ron">Weasley>Mom -- geroff!</dialogue>
                                <dialogue id="Fred">Aaah, has ickle Ronnie got somefink on his nosie?</dialogue>
                                <dialogue id="Ron">Weasley>Shut up,</dialogue>
                                <dialogue id="Mrs. Weasley">Where's Percy?</dialogue>
                                <dialogue id="Percy">Weasley>He's coming now.</dialogue>
                            </dialogues>
                        </scene>

        """

        chat_session = client_groq.chat.completions.create(
    messages=[
        {
            "role": "system",
            "content": "You are an experienced screen adapter for written novels. You will properly structure a script for a visual depiction of a section of a written novel as requested by the user. FOLLOW THE FORMAT and REFRAIN FROM saying anything except what is required of you, that is the XML."
        },

        {
            "role": "user",
            "content": "<novel>"+section_text+"</novel> "+screenplay_prompt,
        }
    ],
    model="llama3-70b-8192",

    temperature=0.3,
)

        response = chat_session.choices[0].message.content

        #response contains text, and then a xml section with the starting and ending tag <scenes>
        #we need to extract the text between these tags
        # print(response)
        response_text = response.split("<scenes>")[0] + "<scenes>" + response.split("<scenes>")[1].split("</scenes>")[0] + "</scenes>"

        return response_text


def check_xml_structure(xml_string):
    try:
        root = ET.fromstring(xml_string)
        # Pretty-print the XML structure
        ET.dump(root)
        print("XML structure is valid.")
        return True
    except ET.ParseError as e:
        print(f"XML structure is invalid: {e}")
        return False 

def clear_background(image_path: str)->str:
    with open(image_path, 'rb') as img_file:
        img_data = img_file.read()
    
    output = remove(img_data)
    output_path = f"clear_{image_path}"
    with open(output_path, 'wb') as out_file:
        out_file.write(output)
    return output_path



def generate_background(prompt: str) -> str:
    output = replicate.run(
        "black-forest-labs/flux-schnell",
        input={
            "prompt": prompt,
            "go_fast": True,
            "num_outputs": 1,
            "aspect_ratio": "16:9",
            "output_format": "webp",
            "output_quality": 80
        }
    )
    return output[0] #returns the image path (online link)

def generate_character(prompt: str) -> str:
    output = replicate.run(
        "black-forest-labs/flux-schnell",
        input={
            "prompt": prompt,
            "go_fast": True,
            "num_outputs": 1,
            "aspect_ratio": "1:1",
            "output_format": "webp",
            "output_quality": 80
        }
    )
    return output[0] #returns the image path (online link)


def extract_text_from_pdf(pdf_path: str) -> str:
    with open(pdf_path, 'rb') as file:
        reader = PyPDF2.PdfReader(file)
        text = ""
        for page in reader.pages:
            text += page.extract_text()
    return text

def process_scene(scene_xml: ET.Element, db, character_names):
    background = scene_xml.find("background").text
    dialogues = scene_xml.find("dialogues")

    for dialogue in dialogues:
        character_name = dialogue.tag
        if character_name not in character_names:
            character_names.append(character_name)
        if character_name != "Narrator":
            get_or_create_character(db, character_name)

    return character_names


def main(file_path: str):
    text = extract_text_from_pdf(file_path)
    pdf_name = file_path.split("/")[-1].split(".")[0]
    db = client[pdf_name.replace(" ", "_")]
    character_names = []
    
    characters_collection = db['characters']
    scenes_collection = db['scenes']
    characters_collection.delete_many({})
    scenes_collection.delete_many({})

    num_char_at_a_time = 2048
    First = True
    screenplay_file = "screenplay.txt"

    # Check if the screenplay file exists to resume from where it left off
    screenplay = "<scenes>"+"\n"
    if os.path.exists(screenplay_file):
        with open(screenplay_file, "r") as file:
            screenplay = file.read()

    # Ensure we start from where we left off in the text
    start_offset = len(screenplay) - len("<scenes>") if "<scenes>" in screenplay else 0
    print(f"Resuming from character {start_offset} out of {len(text)}")

    print("Length of the text is ", len(text))
    
    for i in tqdm.tqdm(range(0, len(text), num_char_at_a_time)):
        section_text = text[i:i+num_char_at_a_time]
        while True:
            scene_text = get_scene_info(section_text, character_names)

            if First:
                scene_text = scene_text.strip().rstrip('</scenes>')
                First = False
            elif i + num_char_at_a_time < len(text):
                scene_text = scene_text.replace('<scenes>', '').replace('</scenes>', '').strip()
            else:
                scene_text = scene_text.lstrip('<scenes>').strip()

            if "xml" in scene_text:
                scene_text = scene_text.replace("xml", "")

            pattern = re.compile(r'(<scene>.*?</scene>)', re.DOTALL)
            matches = pattern.findall(scene_text)
            scene_text = ' '.join(matches)
            print("SCENE TEXT:", scene_text, "\n\n\n\n")

            if check_xml_structure("<scenes>" + scene_text + "</scenes>"):
                # If valid XML, break the while loop and continue
                break
            else:
                print(f"Invalid scene XML, retrying scene from offset {i}")

        # Incrementally save valid scene_text to the screenplay file
        with open(screenplay_file, "a") as file:
            file.write(scene_text)

    # Close the screenplay with </scenes> at the end
    with open(screenplay_file, "a") as file:
        file.write("</scenes>")
  
    
if __name__ == "__main__":
    test_pdf_path = "/home/ryyan/mecode/Harry Potter and the Sorcerers Stone.pdf"
    main(test_pdf_path)