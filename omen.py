import replicate
from pymongo import MongoClient
import PyPDF2
import os
import google.generativeai as genai
import xml.etree.ElementTree as ET
import json
import tqdm
client = MongoClient('mongodb://localhost:27017/')

genai.configure(api_key=os.environ["GEMINI_API_KEY"])

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



def get_character_info(novel_text: str)->list:
    novel_text = "<book>"+novel_text+"</book>"
    instruction="""First, use chain of thought and think in a very verbose and spoken manner about the task at hand, clearly thinking step by step about what the answers should be.
    After extensive thinking, return a single XML list of the top 10 most mentioned characters throughout the novel and their descriptions and their genders ready for image generation models. Describe ONLY and only how they look and nothing about their personalities and remember that the descriptions must not be copy pastes but your own interpretations of how they look, and the descriptions are independent and hence must not reference or compare with any other character. The description should also be detailed enough that a image generation model should be able to produce an image that does justice to the character. 
    Return it in xml format as in the following
    <characters>
    <character>
    <name> character name </name>
    <description> An elaborate and well described description of the character physical appearance </description>
    <gender> their gender (male or female) </gender>
    </character>
    .
    .
    .
    </characters>
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

    chat_session = model.start_chat(
    history=[]
    )

    response = chat_session.send_message(novel_text+instruction).text

    response_text = extract_xml(response)

    #print(response_text)
    return(xml_to_json(response_text))

def get_scene_info(section_text: str, character_names: list) -> str:
        generation_config = {
        "temperature": 1,
        "top_p": 0.95,
        "top_k": 64,
        "max_output_tokens": 8192,
        "response_mime_type": "text/plain",
        }
        screenplay_prompt=f"""Your job is to return the entire scene properly structured in xml format, along with a max of 2-3 background settings and their descriptions. There should be atleast 5-6 dialogues for each scene, unless its with a narrator in which case we can have no character dialogue at all to set a scene. If a character in the dialogues is in the list:{character_names}, use only the EXACT name from the list. \nExample\n<scenes>\n<scene>\n<background> An extremely elaborate description of the background to be used </background>\n<dialogues>\n<character_name> Dialogue.... </character_name>\n<character_name> Dialogue.... </character_name>\n.\n.\n.\n</dialogues>\n</scene>\n.\n.\n.\n</scenes>
                        Example of a scene: 
                        <scene>
                            <background>The interior of the Dursleys' car, a somewhat battered family saloon. The windows are steamed up from the summer heat and the air is thick with the smell of cheap petrol and stale cigarettes.</background>
                            <dialogues>
                            <Uncle Vernon>"... roaring along like maniacs, the young hoodlums,"</Uncle Vernon>
                            <Harry Potter>"I had a dream about a motorcycle. It was flying. "</Harry Potter>
                            <Uncle Vernon>"MOTORCYCLES DON'T FLY!"</Uncle Vernon>
                            <Dudley>"(Sniggering)"</Dudley>
                            <Piers>"(Sniggering)"</Piers>
                            <Harry Potter>"I know they don't. It was only a dream."</Harry Potter>
                            </dialogues>
                        </scene>"""

        model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        generation_config=generation_config,
        # safety_settings = Adjust safety settings
        # See https://ai.google.dev/gemini-api/docs/safety-settings
        system_instruction="You are an experienced screen adapter for written novels. You will properly structure a script for a visual depiction of a section of a written novel as requested by the user.",
        )

        chat_session = model.start_chat(
        history=[]
        )

        response = chat_session.send_message("<novel>"+section_text+"</novel> "+screenplay_prompt).text

        #response contains text, and then a xml section with the starting and ending tag <scenes>
        #we need to extract the text between these tags
        print(response)
        response_text = response.split("<scenes>")[0] + "<scenes>" + response.split("<scenes>")[1].split("</scenes>")[0] + "</scenes>"

        return response_text

        

def clear_background(image_path: str) -> str:
    pass




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



def main(file_path: str):
    text = extract_text_from_pdf(file_path)
    pdf_name = file_path.split("/")[-1].split(".")[0]
    db = client[pdf_name.replace(" ", "_")]
    
    #within the database, we have a collection named characters, and scenes
    #characters collection will have the character info, and scenes will have the scenes info

    # Create collections for characters and scenes
    characters_collection = db['characters']
    scenes_collection = db['scenes']
    characters_collection.delete_many({})
    scenes_collection.delete_many({})

    characters = get_character_info(text) #returns a list of dicts where each dict has keys name, description, gender
    #print(type(characters))
    characters = json.loads(characters)
    #print(type(characters))
    #print(characters[0])

    #print(characters)
    
    characters = list(map(dict, characters))
    character_names = [character["name"] for character in characters]
    #print(character_names)
    
    # Insert character information into MongoDB
    
    for character in tqdm.tqdm(characters):
        #image = generate_character(character["description"])
        character_doc = {
            "name": character["name"],
            "description": character["description"],
            "gender": character["gender"],
            #"image": image
        }
        characters_collection.insert_one(character_doc)
    
    print(f"Inserted {len(characters)} characters into the database.")
    
    
    



    num_char_at_a_time=4096
    First=True
    screenplay=""
    print("Length of the text is ", len(text))
    for i in range(0, len(text), num_char_at_a_time):
        section_text = text[i:i+num_char_at_a_time]
        scene_text = get_scene_info(section_text, character_names)
        #if first call, keep the starting scenes tag, otherwise remove all <scenes> and </scenes> tags
        if First:
            scene_text = scene_text.strip().rstrip('</scenes>')
            First = False
        elif i + num_char_at_a_time < len(text):
            scene_text = scene_text.replace('<scenes>', '').replace('</scenes>', '').strip()
        else:
            scene_text = scene_text.lstrip('<scenes>').strip()
        if """```xml""" in scene_text:
            scene_text = scene_text.replace("```xml", "")
        screenplay += scene_text

        with open("screenplay.txt", "w") as file:
            file.write(screenplay)
    

    #now assuming I have a XML file with the screenplay, I need to generate the images for each scene and each character in the scene
    #the XML file will be in the following format
    #<scenes>
    #<scene>
    #<background> description of the background </background>
    #<dialogues>
    #<character> dialogue </character>
    #</dialogues>
    #</scene>
    #...
    #</scenes>

    
        
    
if __name__ == "__main__":
    test_pdf_path = "/home/ryyan/mecode/Harry Potter and the Sorcerers Stone.pdf"
    main(test_pdf_path)
