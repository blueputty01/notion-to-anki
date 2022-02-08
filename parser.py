import re
import zipfile
import csv
from bs4 import BeautifulSoup, Tag, NavigableString
import json
import urllib.request

file = "D:/Desktop/temp.zip"
output = "D:/Desktop/anki.csv"

cards = []


def parse_file(soup):
    content = soup.find("div", {"class": "page-body"}).children
    t = None
    for ele in content:
        if ele.name == 'h1':
            t = ele.text
        elif ele.name == 'ul':
            push_toggles(ele, t)


def get_deck_name(tag):
    try:
        deck_name = re.search('(?<=#)(.+?)(?=::|$)', tag).group(1)
    except AttributeError:
        deck_name = 'Default'

    return deck_name


def push_toggles(toggles, tag):
    global cards
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
        cards.append(obj)


def get_card_from_toggle(toggle):
    toggle = toggle.details

    header = list(toggle.summary.children)

    body_card = ""
    if toggle.p is not None:
        # remove first element aka summary
        body = list(toggle.children)[1:]
        for detail in body:
            if detail is not None:
                body_card += process_card(detail)

    header_card = process_card(header)
    return {'Text': header_card, 'Extra': body_card}


def process_card(parent):
    card = ""
    counter = 1
    for node in parent:
        if isinstance(node, NavigableString):
            card += node
        elif node.name == "code":
            cloze = process_card(list(node.children))

            if cloze is not None:
                if type(cloze[-1]) == int:
                    counter = int(cloze[-1])
                    cloze = cloze[0, -1]

                cloze = f"{{{{c{counter}::{cloze} }}}}"
                counter += 1
                card += cloze
        else:
            if node.has_attr("class"):
                if node.get("class")[0] == "notion-text-equation-token":
                    math = node.find("annotation")
                    formula = math.text
                    card += f"\({formula}\)"

    return card


def write_file(out):
    global cards
    with open(out, "w") as csvfile:
        writer = csv.writer(csvfile)
        for card in cards:
            writer.writerow(card)


def parse(zip_folder):
    archive = zipfile.ZipFile(zip_folder, "r")
    file_name = archive.namelist()[0]

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
    notes = invoke('addNotes', notes=cards)
    # notes = invoke('getTags')
    print(notes)


if __name__ == "__main__":
    parse(file)
    auto_send()
    # write_file(output)
