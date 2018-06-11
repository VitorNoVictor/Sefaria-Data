#encoding=utf-8
import requests
import django
django.setup()
from sefaria.model import *
from sefaria.system.exceptions import InputError
from num2words import num2words
from word2number import w2n
import os
import re
from collections import Counter
from sources.functions import post_index, post_text, convertDictToArray

SERVER = "http://ste.sefaria.org"

# def download_sheets(self):
#     indexes = library.get_indexes_in_category("Mishnah")
#     indexes = [library.get_index(i) for i in indexes]
#     for i in indexes:
#         title_for_url = " ".join(i.split()[1:]).lower()
#         chapters = i.all_section_refs()
#         for ch_num, chapter in enumerate(chapters):
#             mishnayot = chapter.all_segment_refs()
#             for mishnah_num, mishnah in enumerate(mishnayot):
#                 headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'}
#                 response = requests.get("http://learn.conservativeyeshiva.org/{}-chapter-{}-mishnah-{}.html".format(title_for_url, chapter, mishnah), headers=headers)
#                 print "sleeping"
#                 with open("{}.html".format(i), 'w') as f:
#                     f.write(response.content)

def parse(file, sefer, chapter, mishnah):
    def get_first_sentence(line):
        line = line.strip()
        end = line.find(". ")
        if end != -1:
            return line[0:end]+". "
        return line+" "

    def deal_with_sections(line, text):
        section = ""
        if line.startswith("Section"):
            section = " ".join(line.split()[0:2])
            section_num_as_word = " ".join(line.split()[1:2]).split(":", 1)[0]
            if section_num_as_word.find("-") in [1, 2]: #either 10-14 or 2-7 will be matched
                 #this is a range
                section_num_as_word = section_num_as_word.split("-")[0]
        if section:
            line = line.replace(section, "")
            try:
                section_num = w2n.word_to_num(section_num_as_word)
            except ValueError:
                print section_num_as_word
                return False
            if section_num - 1 in range(len(text)):
                first_sentence = get_first_sentence(mishnah_text[section_num - 1])
                line = "<b>{}</b>{}".format(first_sentence, line)
                if text[section_num - 1]:
                    text[section_num - 1] += "\n" + line
                else:
                    text[section_num - 1] = line
            else:
                return False
        elif text:
            text[-1] += " " + line
        else:
            text.append(line)
        return True

    currently_parsing = ""
    mishnah_text = []
    commentary_text = []
    questions_text = []
    found_mishnah = found_explanation = False # must find both, whereas intro is unnecessary
    explanation_sections_text = [] #After parsing "Section One: ...", this array will contain the line in position 0 of the array
    questions_sections_text = []
    with open(file) as f:
        lines = [line.replace("\n", "") for line in list(f) if line != "\n"]
        first_line = lines[0]
        # chapter_as_word = num2words(chapter).capitalize()
        mishnah_as_word = num2words(mishnah).capitalize()
        # if "Chapter {}".format(chapter_as_word) not in first_line or "Mishnah {}".format(mishnah_as_word) not in first_line:
        #     print "Problem in file {} in first line {}".format(file, first_line)
        #     return (commentary_text, mishnah_text)
        lines = lines[1:]
        for line_n, line in enumerate(lines):
            line = line.strip()
            if len(line.split()) < 10:
                line = line.split(", Part")[0]
            if "Questions for Further Thought" in line:
                currently_parsing = "QUESTIONS"
                questions_text.append(line)
            elif len(line.split()) < 7 and ("Mishna" in line or sefer == line):
                if "Mishnah {}".format(mishnah_as_word) != line and "Mishna" in line:
                    word = line.split()[-1] #Mishnah Five, Part One -> Five
                    try:
                        mishnah_inside_file = w2n.word_to_num(word)
                        complaint = "Mishnah word different than number: {} {}:{}".format(sefer, chapter, mishnah)
                        #print complaint
                    except ValueError:
                        pass
                currently_parsing = "MISHNAH"
            elif "Explanation" == line or "Introduction" == line:
                commentary_text.append("<b>"+line+"</b>")
                currently_parsing = line.upper()
            else:
                if currently_parsing == "INTRODUCTION":
                    commentary_text[-1] += "\n" + line
                elif currently_parsing == "QUESTIONS":
                    if questions_sections_text == []:
                        questions_sections_text = ["" for k in range(len(mishnah_text))]
                    section_num = deal_with_sections(line, questions_sections_text)
                    if section_num == False:  # there was just an error
                        print file
                        return (commentary_text + questions_text, mishnah_text)
                elif currently_parsing == "EXPLANATION":
                    if explanation_sections_text == []:
                        explanation_sections_text = ["" for k in range(len(mishnah_text))]
                    section_num = deal_with_sections(line, explanation_sections_text)
                    if section_num == False:  # there was just an error
                        print file
                        return (commentary_text + questions_text, mishnah_text)
                elif currently_parsing == "MISHNAH":
                    mishnah_text.append(line)

        assert commentary_text != mishnah_text != []
        return (commentary_text+questions_text, mishnah_text)



def create_index(text, sefer):
    index = library.get_index("Mishnah " + sefer)
    root = SchemaNode()
    en_title = "Mishnah Yomit on {}".format(index.title)
    he_title = u"משנה יומית על {}".format(index.get_title('he'))
    root.add_primary_titles(en_title, he_title)

    if "Introduction" in text.keys():
        intro = JaggedArrayNode()
        intro.add_shared_term("Introduction")
        intro.key = "intro"
        intro.add_structure(["Paragraph"])
        root.append(intro)

    default = JaggedArrayNode()
    default.key = "default"
    default.default = True
    default.add_structure(["Perek", "Mishnah", "Comment"])
    root.append(default)
    root.validate()
    index = {
        "title": en_title,
        "schema": root.serialize(),
        "categories": ["Mishnah", "Commentary", "Mishnah Yomit"],
        "dependence": "Commentary",
        "base_text_titles": [index.title],
        "collective_title": "Mishnah Yomit",
        "base_text_mapping": "many_to_one"
    }
    #post_index(index, server=SERVER)


def check_all_mishnayot_present_and_post(text, sefer, file_path):
    def post_(text, path):
        send_text = {
            "language": "en",
            "text": text,
            "versionTitle": "Mishnah Yomit",
            "versionSource": "http://learn.conservativeyeshiva.org/mishnah/"
        }
        #post_text(path, send_text, server=SERVER)
    #first check that all chapters present
    index = library.get_index("Mishnah " + sefer)
    en_title = "Mishnah Yomit on {}".format(index.title)
    translation = dict(text)
    for ch in text.keys():
        if ch == "Introduction":
            post_(text[ch], "{}, Introduction".format(en_title))
            text.pop(ch)
            translation.pop(ch)
            continue
        actual_mishnayot = [el.sections[1] for el in Ref("Mishnah {} {}".format(sefer, ch)).all_segment_refs()]
        our_mishnayot = text[ch].keys()
        if our_mishnayot != actual_mishnayot:
            actual_mishnayot = set(actual_mishnayot)
            our_mishnayot = set(our_mishnayot)
            missing = actual_mishnayot - our_mishnayot
            wrong = our_mishnayot - actual_mishnayot
            # print file_path
            # print "Sefer: {}, Chapter: {}".format(sefer, ch)
            # print "Missing: {}".format(missing)
            # print "Wrong: {}".format(wrong)
            # print
        text[ch] = zip(*convertDictToArray(text[ch], empty=("", "")))
        translation[ch] = list(text[ch][1])
        text[ch] = list(text[ch][0])
        while "" in text[ch]:
            i = text[ch].index("")
            text[ch][i] = []
    text = convertDictToArray(text)
    translation = convertDictToArray(translation)
    post_(text, en_title)
    for ch, chapter in enumerate(translation):
        for m, mishnah in enumerate(chapter):
            translation[ch][m] = " ".join(mishnah)
    post_(translation, index.title)



if __name__ == "__main__":
    parsed_text = {}
    for category in os.listdir("."):
        if not os.path.isdir(category):
            continue
        sefarim = os.listdir(category)
        for sefer in sefarim:
            current_path = "./{}/{}".format(category, sefer)
            if not os.path.isdir(current_path):
                continue
            if sefer not in parsed_text.keys():
                parsed_text[sefer] = {}
            files = os.listdir(current_path)
            found_ref = Counter()
            for file in files:
                file_path = current_path + "/" + file
                if "Copy" in file or not file.endswith(".txt"):
                    continue
                if file.startswith("Introduction"):
                    f = open(file_path)
                    lines = list(f)[1:]
                    parsed_text[sefer]["Introduction"] = [line.replace("\n", "") for line in lines if line != "\n"]
                    f.close()
                elif file.startswith(sefer):
                    try:
                        ref_form = Ref("Mishnah " + file.replace("-", ":").replace(".txt", "")) #Berakhot 3-13.txt --> Mishnah Berakhot 3:13
                        found_ref[ref_form.normal()] += 1
                        chapter, mishnah = ref_form.sections[0], ref_form.sections[1]
                        if chapter not in parsed_text[sefer].keys():
                            parsed_text[sefer][chapter] = {}
                        parsed_text[sefer][chapter][mishnah] = parse(file_path, sefer, chapter, mishnah)
                    except InputError as e:
                        print file_path
                        print "FIle problem with {}".format(file)

            most_common_value = found_ref.most_common(1)[0]
            assert most_common_value[1] == 1, "{} has {}".format(most_common_value[0], most_common_value[1])
            create_index(parsed_text[sefer], sefer)
            check_all_mishnayot_present_and_post(parsed_text[sefer], sefer, current_path)

