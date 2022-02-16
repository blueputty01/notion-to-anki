import re
import zipfile
import csv
from bs4 import BeautifulSoup, Tag, NavigableString
import json
import urllib.request
from pathlib import Path

file = "D:/Desktop/temp.zip"
output = "D:/Desktop/anki.csv"
deck_name_dict = {
    'Spanish': 'AP Spanish',
    'Chemistry': 'AP Chemistry',
}

notes = []
media = []
export_name = Path()
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

    if deck_name in deck_name_dict:
        deck_name = deck_name_dict[deck_name]

    return deck_name


def push_toggles(toggles, tag):
    global notes
    deck = get_deck_name(tag)
    for toggle in toggles:
        obj = {'deckName': deck,
               'modelName': "cloze",
               'fields': get_card_from_toggle(toggle),
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
               }
        # print(obj['fields'])
        notes.append(obj)


def get_card_from_toggle(toggle):
    toggle = toggle.details

    header = list(toggle.summary.children)

    body_card = ""
    # remove first element aka summary
    body = list(toggle)[1:]
    for detail in body:
        if detail is not None:
            body_card += process_card(detail)

    header_card = process_card(header)
    return {'Text': header_card, 'Extra': body_card}


def process_card(parent):
    global media, export_name
    card = ""
    counter = 1
    if hasattr(parent, 'name'):
        if parent.name == "figure":
            image_path = parent.a.img.get("src")
            image_fname = Path(image_path).name
            full_path = media_path / image_fname
            anki_name = export_name.stem + image_fname
            print(str(full_path.resolve()))
            media.append({'path': str(full_path.resolve()), 'filename': anki_name})
    else:
        for node in parent:
            if isinstance(node, NavigableString):
                card += node
            elif node.name == "code":
                cloze = process_card(list(node.children))

                if cloze is not None:
                    if re.match("^\\d::", cloze):
                        counter = int(cloze[0])
                        cloze = cloze[2:-1]

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


def parse(zip_folder):
    global media_path, export_name
    archive = zipfile.ZipFile(zip_folder, "r")
    file_name = archive.namelist()[0]
    export_name = Path(file_name)
    archive_path = Path("D:/Desktop/") / export_name
    archive.extractall(archive_path)
    media_path = archive_path / export_name.stem

    with archive.open(file_name, mode="r") as fp:
        soup = BeautifulSoup(fp, "html.parser")
        parse_file(soup)


def request(action, **params):
    return {'action': action, 'params': params, 'version': 6}


def invoke(action, **params):
    request_json = json.dumps(request(action, **params)).encode('utf-8')
    print(request_json)
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


def auto_send():
    actions = [request('addNotes', notes=notes)]
    global media
    for m in media:
        actions.append(request('storeMediaFile', filename=m['filename'], url=m['path']))
    result = invoke('multi', actions=actions)
    # notes = invoke('getTags')
    print(result)


if __name__ == "__main__":
    parse(file)
    auto_send()
    # write_file(output)
