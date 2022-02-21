import os
import re
import shutil
import zipfile
import csv
import socket
from bs4 import BeautifulSoup, Tag, NavigableString
import json
import urllib.request
from pathlib import Path
from os import listdir
from os.path import isfile, join

input_dir = Path("D:/Desktop")
output = "D:/Desktop/anki.csv"
deck_name_dict = {
    'Spanish': 'AP Spanish',
    'Chemistry': 'AP Chemistry',
}

notes = []
extracted_locs = []
all_zips = []
notion_name = Path()
media_path = Path()


def parse_file(soup):
    content = soup.find("div", {"class": "page-body"}).children
    t = None
    for ele in content:
        if ele.name == 'h1':
            t = ele.text
        elif ele.name == 'ul':
            push_toggles(ele, t)


def get_deck_name(tag):
    global deck_name_dict

    try:
        deck_name = re.search('(?<=#)(.+?)(?=::|$)', tag).group(1)
    except AttributeError:
        deck_name = 'Default'
        print('bro are you sure you want this to be added to the default deck?')

    if deck_name in deck_name_dict:
        deck_name = deck_name_dict[deck_name]

    return deck_name


def push_toggles(toggles, tag):
    global notes
    deck = get_deck_name(tag)
    for toggle in toggles:
        obj = get_card_from_toggle(deck, tag, toggle)
        # print(obj['fields'])
        notes.append(obj)


def get_card_from_toggle(deck, tag, toggle):
    toggle = toggle.details

    header = list(toggle.summary.children)

    body_card = ""
    # remove first element aka summary
    body = list(toggle)[1:]

    media = {}

    for detail in body:
        if detail is not None:
            if hasattr(detail, 'name') and detail.name == "figure":
                image_path = detail.a.img.get("src")
                image_fname = Path(image_path).name
                full_path = media_path / image_fname
                anki_name = notion_name.stem + image_fname
                print(str(full_path.resolve()))
                media['picture'] = {'path': str(full_path.resolve()), 'filename': anki_name, 'fields': ['Extra']}
            else:
                body_card += process_card(detail)

    header_card = process_card(header)
    return {'deckName': deck,
            'modelName': "cloze",
            'fields': {'Text': header_card, 'Extra': body_card},
            'tags': [tag],
            "options": {
                "allowDuplicate": False,
                "duplicateScope": deck,
                "duplicateScopeOptions": {
                    "deckName": deck,
                    "checkChildren": False,
                    "checkAllModels": False
                }
            },
            **media
            }


def process_card(parent):
    global notion_name
    card = ""
    counter = 1
    for node in parent:
        if isinstance(node, NavigableString):
            card += node
        elif node.name == "code":
            cloze = process_card(list(node.children))

            if cloze is not None:
                if re.match("^\\d::", cloze):
                    counter = int(cloze[0])
                    cloze = cloze[3:len(cloze)]

                cloze = f"{{{{c{counter}::{cloze}}}}}"
                counter += 1
                card += cloze
            elif node.has_attr("class"):
                if node.get("class")[0] == "notion-text-equation-token":
                    math = node.find("annotation")
                    formula = math.text
                    card += f"\({formula}\)"

    return card


def write_file(out):
    global notes
    with open(out, "w") as csvfile:
        writer = csv.writer(csvfile)
        for card in notes:
            writer.writerow(card)


def parse_all_files(d):
    # https://stackoverflow.com/questions/3207219/how-do-i-list-all-files-of-a-directory
    onlyfiles = [f for f in listdir(d) if isfile(join(d, f))]
    reg = re.compile("Export-\w{8}-\w{4}-\w{4}-\w{4}-\w{12}.zip")

    global all_zips

    local_zips = list(filter(reg.match, onlyfiles))

    for z in local_zips:
        z = input_dir / z
        all_zips.append(z)
        global media_path, notion_name, extracted_locs
        archive = zipfile.ZipFile(z, "r")
        file_name = archive.namelist()[0]
        notion_name = Path(file_name)
        extracted_loc = z.parents[0] / z.stem
        archive.extractall(extracted_loc)
        media_path = extracted_loc / notion_name.stem

        extracted_locs.append(extracted_loc)

        with archive.open(file_name, mode="r") as fp:
            soup = BeautifulSoup(fp, "html.parser")
            parse_file(soup)


def request(action, **params):
    return {'action': action, 'params': params, 'version': 6}


def invoke(action, **params):
    request_json = json.dumps(request(action, **params)).encode('utf-8')
    print(request_json)

    a_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    location = ("localhost", 8765)
    result_of_check = a_socket.connect_ex(location)

    if result_of_check == 0:
        print("Port is open")
        response = json.load(urllib.request.urlopen(urllib.request.Request('http://localhost:8765', request_json)))

        if len(response) != 2:
            raise Exception('response has an unexpected number of fields')
        if 'error' not in response:
            raise Exception('response is missing required error field')
        if 'result' not in response:
            raise Exception('response is missing required result field')
        if response['error'] is not None:
            raise Exception(response['error'])
        return response['result']
    else:
        print("Port is not open")


def auto_send():
    # actions = [request('addNotes', notes=notes)]
    result = invoke('addNotes', notes=notes)
    # notes = invoke('getTags')
    print(result)


if __name__ == "__main__":
    parse_all_files(input_dir)
    auto_send()
    for loc in extracted_locs:
        shutil.rmtree(loc)

    i = input("Delete all? (Y/n) ")
    if i == "Y":
        for loc in all_zips:
            os.remove(loc)

    # write_file(output)
