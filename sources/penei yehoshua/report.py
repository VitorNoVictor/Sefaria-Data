#encoding=utf-8
import django
django.setup()
from sefaria.model import *
from sefaria import system
from sources.functions import *
import csv
from data_utilities.dibur_hamatchil_matcher import *
import os

class MaharshaLite:
    def __init__(self, book):
        self.server = "http://localhost:8000"
        self.book = book
        self.len_masechet = len(book.all_section_refs()) + 2 #how many sections in book
        self.current_daf = "2a"
        self.category = "gemara"
        self.category_set = set()
        self.rashi ='רש"י'
        self.rashbam = 'פרשב"ם'
        self.ran = 'ר"ן'
        self.rosh = 'רא"ש'
        self.tosafot = "תוס"
        self.dibbur_hamatchil = ['בד"ה', 'ד"ה', 'בא"ד', """ד'"ה"""]
        self.gemara = "גמ"
        self.shom = "שם"
        self.amud_bet = 'ע"ב'
        self.mishnah = ['במשנה', 'מתני']
        self.categories = ['rashi', 'tosafot', 'gemara', 'ran', 'rosh', 'rashbam']
        self.dh_dict = {self.current_daf: []}
        self.comm_dict = {self.current_daf: []}
        self.list_of_dafs = []
        self.links = []

    def determineCategory(self, comment):
        word = comment.split(" ")[0] if comment.split(" ")[0] != " " else comment.split(" ")[1]
        if self.rashi in word:
            self.category = 'rashi'
        elif self.tosafot in word:
            self.category = 'tosafot'
        elif self.gemara in word or word in self.mishnah:
            self.category = 'gemara'
        elif self.ran in word:
            self.category = 'ran'
        elif self.rosh in word:
            self.category = 'rosh'
        elif self.rashbam in word:
            self.category = "rashbam"
        elif word == 'בא"ד' or word == 'עוד בדבור זה':
            return "same_dh"
        return None

    # def get_alephs_bets(file):
    #     lines = " ".join(list(file))
    #     dappim = []
    #     aleph = "@11דף@22"
    #     bet = '@11ע"ב'
    #     how_many_alephs = len(lines.split(aleph)) - 1
    #     how_many_bets = len(lines.split(bet)) - 1
    #     return how_many_alephs, how_many_bets


    def get_dh(line):
        first_12_words = " ".join(line.split(" ")[0:12])
        chulay = u"כו'"
        if chulay in first_12_words:
            dh, comment = line.split(chulay, 1)
            dh += u" "+chulay

    def parseDH(self, comment, category, same_dh):
        orig_comment = comment
        if same_dh is None:
            comment = comment.replace("@22", " ").replace("@11", "")
            first_15_words = " ".join(comment.split(" ")[0:15])
            chulay = first_15_words.find("כו'")
            first_period = first_15_words.find(".")
            if chulay > 0:
                dh, comment = comment[0:chulay+5], comment[chulay+6:]
            elif first_period > 0:
                dh, comment = comment[0:first_period+1], comment[first_period+1:]
                comment = comment[1:] if comment[0] == " " else comment
            else:
                dh = first_15_words
                comment = " ".join(comment.split()[15:])
            self.prev_dh = dh
            self.addDHComment(dh, comment, category, same_dh)
        else:
            self.addDHComment(self.prev_dh, comment, category, same_dh)

    def setDaf(self, line, len_masechet):
        prev_num = AddressTalmud(1).toNumber("en", self.current_daf)
        orig_line = line
        line = line.replace("@11 ", "@11")
        aleph = "@11דף@22"
        bet = '@11ע"ב'
        daf_marker = ""
        if aleph in line:
            daf_value = getGematria(line.split(" ")[0].replace(aleph, ""))
            if line.split(" ")[2].find(bet) >= 0:
                daf_as_num = 2*daf_value
            else:
                daf_as_num = 2*daf_value - 1
            daf_marker = aleph
            # actual_text = ""
            # start_at = 3
            # if line.split(" ")[2] not in ['ע"ב', 'ע"א']:
            #     start_at = 2
            # for count, word in enumerate(line.split(" ")):
            #     if count >= start_at:
            #         actual_text += word + " "
        elif bet in line:
            daf_as_num = AddressTalmud(1).toNumber("en", self.current_daf)
            if "a" in self.current_daf:
                daf_as_num += 1
            elif "b" in self.current_daf:
                print orig_line
                print daf_as_num
            daf_marker = bet

        self.current_daf = AddressTalmud.toStr("en", daf_as_num)
        pos = line.find(daf_marker) + len(daf_marker)
        actual_text = " ".join(line.split()[1:])

        if daf_as_num <= prev_num:
            he_current = AddressTalmud.toStr("he", daf_as_num)
            he_prev = AddressTalmud.toStr("he", prev_num)
            #prev_line = " ".join(prev_line.split(" ")[0:5])
            #orig_line = " ".join(orig_line.split(" ")[0:5])
            print u"{} before {}\n".format(he_prev, he_current)
            self.dont_post = True
            #print u"The line starting: {} is {}\n".format(prev_line, he_prev)
            #print u"It came before the line starting {}, which is {}\n\n".format(orig_line, he_current)

        if daf_as_num > len_masechet:
            print "DAF EXTRA {} > {} in {}".format(self.current_daf, len_masechet, self.book.title)
            pass
        self.list_of_dafs.append(self.current_daf)

        if not self.current_daf in self.comm_dict.keys():
            self.comm_dict[self.current_daf] = []

        if not self.current_daf in self.dh_dict.keys():
            self.dh_dict[self.current_daf] = []

        return actual_text

    def addDHComment(self, dh, comment, category, same_dh):
        dh = removeAllTags(dh)
        comment = removeAllTags(comment)
        dh = dh.decode('utf-8')
        comment = comment.decode('utf-8')
        #self.dh1_dict[self.current_daf].append((category, dh))
        if same_dh:
            post_comment = comment
        else:
            if dh and not dh.endswith(" "):
                dh += " "
            post_comment = dh + comment

        post_comment = post_comment.strip()
        first_word = post_comment.split(" ")[0]
        post_comment = u"<b>{}</b> {}".format(first_word, " ".join(post_comment.split(" ")[1:]))
        self.comm_dict[self.current_daf].append(post_comment)
        self.category_set.add(category)
        self.dh_dict[self.current_daf].append((category, dh, len(self.comm_dict[self.current_daf])))


    def create_links(self):
        def dh_extract_method(str):
            if not str:
                return str
            first_word = str.split()[0]
            str = " ".join(str.split()[1:]) #remove the first word since it just indicates category
            chulay = u"כו'"
            if chulay in str:
                str = " ".join(str.split()[0:-1])
                assert not chulay in str
            for el in self.dibbur_hamatchil:
                str = str.replace(el.decode('utf-8'), u"")
            str = str.replace(u"<b>", u"").replace(u"</b>", u"")
            return str

        for daf in self.dh_dict.keys():
            match_dict = {} #for each category, what are the matches in order
            category_pos = {} #for each category, which comment are we at (first one's at 0)
            core_ref = "{} {}".format(self.book.title, daf)
            this_ref = "Penei Yehoshua on {}".format(core_ref)

            for category in self.category_set:
                match_dict[category] = []
                category_pos[category] = -1
                comments = [el[1] for el in self.dh_dict[daf] if el[0] == category]
                if not comments:
                    continue
                base_ref = ""
                if category == "gemara":
                    base_ref = core_ref
                elif category in self.categories:
                    base_ref = "{} on {}".format(category.capitalize(), core_ref)
                try:
                    base_ref = Ref(base_ref)
                    base_text = TextChunk(base_ref, lang='he')
                    base_tokenizer = lambda x: [el for el in x.split(" ") if el]
                    match_dict[category] = match_ref(base_text, comments, base_tokenizer=base_tokenizer, dh_extract_method=dh_extract_method)["matches"]
                except system.exceptions.InputError:
                    match_dict[category] = [None] * len(comments)
                    continue
                except IndexError:
                    print "{} but no {}".format(this_ref, base_ref)
                    match_dict[category] = [None] * len(comments)
                    continue

            for comment_n, comment in enumerate(self.comm_dict[daf]):
                category = self.dh_dict[daf][comment_n][0]
                category_pos[category] += 1
                curr_pos = category_pos[category]
                match = match_dict[category][curr_pos]
                if match:
                    base_ref = match.normal()
                    comment_ref = "{}:{}".format(this_ref, comment_n+1)
                    link = {
                        "refs": [comment_ref, base_ref],
                        "type": "Commentary",
                        "auto": True,
                        "generated_by": "penei_yehoshua_linker"
                    }
                    self.links.append(link)


    def parse(self, lines):
        for i, line in enumerate(lines):
            if line.startswith("@11") and " " in line: #second check to make sure this isn't a perek header
                aleph = "@11דף@22"
                bet = '@11ע"ב'
                if aleph in line or bet in line:
                    line = self.setDaf(line, self.len_masechet) #returns line without daf marker at beginning

                same_dh = self.determineCategory(line)
                self.parseDH(line, self.category, same_dh)


    def create_index(self):
        title = u"Penei Yehoshua on {}".format(book.title)
        he_title = u"פני יהושע על {}".format(book.get_title('he'))
        root = JaggedArrayNode()
        root.add_primary_titles(title, he_title)
        root.depth = 3
        root.add_structure(["Daf", "Comment"], address_types=["Talmud", "Integer"])
        root.validate()
        index = {
            "schema": root.serialize(),
            "title": title,
            "categories": ["Talmud", "Bavli", "Commentary", "Penei Yehoshua"],
            "collective_title": "Penei Yehoshua",
            "base_text_titles": [book.title],
            "dependence": "Commentary"
        }
        post_index(index, server=self.server)


def dh_extract_method(str):
    if not str:
        return str
    orig_str = str
    first_word = str.split()[0]
    str = " ".join(str.split()[1:]) #remove the first word since it just indicates category
    chulay = u"כו'"
    dibbur_hamatchil = ['בד"ה', 'ד"ה', 'בא"ד', """ד'"ה"""]
    for el in dibbur_hamatchil:
        str = str.replace(el.decode('utf-8'), u"")
    str = str.replace(u"<b>", u"").replace(u"</b>", u"")
    str = str.split(chulay)[0]
    str = str.replace('""', '"')
    if len(str.split()) > 7:
        return u" ".join(str.split()[0:7])
    return str


def get_comments_and_map(comments, keyword):
    flags = {"Tosafot": [u"""תוספות""", u"""בתוספות""", u"""תוספת""", u"""תוס'""", u"""בתוס'"""],
             "Rashi": [u"""פירש"י""", u"""רש"י"""],
             "Gemara": [u"""מתניתין""", u"""במתניתין""", u"""בגמרא""", u"""גמרא""", u"""בגמ'"""]}
    relevant_comments = []
    map_comments_to_relevant_comments = {} #index comment is found in "comments"
                                          # to index comment is found in "relevant_comments"
    prev_flag = False
    same_text_flags = [u"""שם""", u"""בד"ה""", u"""שם בא"ד""", u"""בא"ד"""]
    for comm_n, comment in enumerate(comments):
        comment = comment.replace(u'""', u'"')
        first_word = comment.split()[0].replace("<b>", "").replace("</b>", "")
        first_two_words = u" ".join(comment.split()[0:2]).replace("<b>", "").replace("</b>", "")
        if prev_flag and (match_is_second_para(comment) or first_word in same_text_flags or
                          first_two_words in same_text_flags):
            relevant_comments.append(comment)
            map_comments_to_relevant_comments[len(relevant_comments) - 1] = comm_n
            prev_flag = True
        else:
            found = False
            for flag in flags[keyword]:
                if (first_word in flag or flag in first_word):
                    relevant_comments.append(comment)
                    map_comments_to_relevant_comments[len(relevant_comments) - 1] = comm_n
                    prev_flag = True
                    found = True
                    break
            if not found:
                prev_flag = False
    return relevant_comments, map_comments_to_relevant_comments

second_para_terms = ["ונראה", "ולפי", "ובספר", """לפ"ז""", "אבל", "שוב", "ואפשר",
    '\xd7\x95\xd7\x9e\xd7\x99\xd7\x94\xd7\x95', '\xd7\x9e\xd7\x99\xd7\x94\xd7\x95', '\xd7\x90\xd7\x9e\xd7\xa0\xd7\x9d', '\xd7\x95\xd7\x99\xd7\xa9', '\xd7\x90\xd7\x9a', '\xd7\x90\xd7\x9c\xd7\x90', '\xd7\x95\xd7\x9c\xd7\x9b\xd7\x90\xd7\x95\xd7\xa8\xd7\x94', '\xd7\x95\xd7\xa0\xd7\x9c\xd7\xa2"\xd7\x93', '\xd7\x95\xd7\xa2\xd7\x95\xd7\x93', '\xd7\x95\xd7\x9c\xd7\xa4"\xd7\x96', '\xd7\x9b\xd7\x9c', '\xd7\x92\xd7\x9d', '\xd7\x95\xd7\x9e\xd7\x94', '\xd7\x95\xd7\x9e"\xd7\xa9', '\xd7\x95\xd7\x94\xd7\xa0\xd7\x94', '\xd7\x95\xd7\x90\xd7\x9b\xd7\xaa\xd7\x99', '\xd7\x95\xd7\x91\xd7\x96\xd7\x94', '\xd7\xaa\xd7\x95', '\xd7\xa2\xd7\x95\xd7\x93']
second_para_terms = [term.decode('utf-8') for term in second_para_terms]

def match_is_second_para(comment):
    comment_first_word = comment.replace("<b>", "").replace("</b>", "").split()[0]
    for term in second_para_terms:
        if term == comment_first_word or term == u"""בא"ד""" or term == u"""שם בא"ד""":
            return True
    return False

def create_ranges(comments, matches):
    # first_segment = Ref("{} {}".format(title, AddressTalmud.toStr("en", daf))).all_segment_refs()[0]
    # if matches[0] is None:
    #     matches[0] = first_segment
    #what I need to do is to go through the comments and when I find one that is a second paragraph and its previous
    #comment ISN'T a second paragraph
    for match_n, match in enumerate(matches):
      if not match and matches[match_n-1]:
        next_one = match_n
        #when a match is a second paragraph, you want to include it but when it isn't, you want to leave it as None
        while next_one < len(matches) and not matches[next_one] and match_is_second_para(comments[next_one]):
            next_one += 1
        #if not matches[next_one] and next_one == len(matches) - 1:
        #    matches[next_one] = Ref("{} {}".format(title, AddressTalmud.toStr("en", daf))).all_segment_refs()[-1]
        if next_one != match_n:
            for i in range(match_n-1, next_one):
                matches[i] = matches[match_n-1]
    return matches

def create_ranged_link(links, range_counter, create_base_link):
    comm_link = links.pop()
    if create_base_link:
        base_link = links.pop()
    penei_ref = comm_link["refs"][1]
    assert penei_ref.startswith("Penei")
    segment = int(penei_ref.split(":")[-1])
    new_penei_ref = penei_ref + "-" + str(range_counter + segment)
    comm_link["refs"][1] = new_penei_ref
    links.append(comm_link)
    if create_base_link:
        base_link["refs"][1] = new_penei_ref
        links.append(base_link)


def create_ranged_links(matches, links, index_title, daf, comm_map, create_base_link=False):
    range_counter = 0
    prev_comm = None
    for match_n, comm_ref in enumerate(matches):
        if comm_ref and comm_ref == prev_comm:
            range_counter += 1
            prev_comm = comm_ref
        elif comm_ref and range_counter > 0:
            create_ranged_link(links, range_counter, create_base_link)
            range_counter = 0
            prev_comm = None
        if comm_ref and range_counter is 0 and comm_ref != prev_comm:
            penei_ref = "{} {}:{}".format(index_title, daf, match_n + 1 + comm_map[match_n])
            comm_link = {"refs": [comm_ref.normal(), penei_ref], "type": "Commentary", "auto": True,
                         "generated_by": "penei_yehoshua_batch_ii"}
            links.append(comm_link)
            if create_base_link:
                base_ref = ":".join(comm_ref.normal().split(" on ")[-1].split(":")[0:-1])
                base_link = {"refs": [base_ref, penei_ref], "type": "Commentary", "auto": True,
                             "generated_by": "penei_yehoshua_batch_ii"}
                links.append(base_link)

            prev_comm = comm_ref

    if prev_comm and range_counter > 0:
        create_ranged_link(links, range_counter, create_base_link)


if __name__ == "__main__":
    files = os.listdir("batch ii")
    for file_n, file in enumerate(files):
        print file
        links = []
        comments_per_daf = {}
        index_title = file.split(" - ")[0]
        prev_daf = "2a"
        curr_text = []
        with open("batch ii/{}".format(file)) as open_file:
            if "Shabbat" not in file:
                continue
            for line in open_file:
                if not line.startswith(index_title):
                    continue
                ref, comment = line.split(",", 1)
                if comment[0] == '"':
                    comment = comment[1:]
                if comment[-1] == '"':
                    comment = comment[:-1]
                daf = ref.split()[-1].split(":")[0]
                if daf == prev_daf:
                    curr_text.append(comment.decode('utf-8'))
                else:
                    comments_per_daf[prev_daf] = curr_text
                    curr_text = [comment.decode('utf-8')]
                    prev_daf = daf
            comments_per_daf[daf] = curr_text
            #strip comments out that start with Rashi and create mapping
            comm_maps = {"Tosafot": {}, "Rashi": {}, "Gemara": {}}
            comments_by_type = {"Tosafot": {}, "Rashi": {}, "Gemara": {}}
            for daf, comments in comments_per_daf.items():
                comments = [c[:-2] for c in comments if c != "\r\n"]
                for type in ["Tosafot", "Rashi", "Gemara"]:
                    comments_by_type[type], comm_maps[type] = get_comments_and_map(comments, type)
                ref = index_title.split(" on ")[-1] + " " + daf
                tosafot_ref = "Tosafot on {}".format(ref)
                rashi_ref = "Rashi on {}".format(ref)
                base_text = TextChunk(Ref(ref), lang='he')
                tosafot_base_text = TextChunk(Ref(tosafot_ref), lang='he')
                rashi_base_text = TextChunk(Ref(rashi_ref), lang='he')
                comm_matches = {"Tosafot": [], "Rashi": []}
                if comments_by_type["Tosafot"]:
                    comm_matches["Tosafot"] = match_ref(tosafot_base_text, comments_by_type["Tosafot"], lambda x: x.split(), dh_extract_method=dh_extract_method)
                if comments_by_type["Rashi"]:
                    comm_matches["Rashi"] = match_ref(rashi_base_text, comments_by_type["Rashi"], lambda x: x.split(), dh_extract_method=dh_extract_method)

                for comm_type, matches in comm_matches.items():
                    comm_map = comm_maps[comm_type]
                    if not matches or not comm_map:
                        continue
                    matches = create_ranges(comments_by_type[comm_type], matches["matches"])
                    create_ranged_links(matches, links, index_title, daf, comm_map, create_base_link=True)

                matches = match_ref(base_text, comments_by_type["Gemara"], lambda x: x.split(), dh_extract_method=dh_extract_method)
                matches = create_ranges(comments_by_type["Gemara"], matches["matches"])
                if comm_maps["Gemara"]:
                    create_ranged_links(matches, links, index_title, daf, comm_maps["Gemara"])
                # for match_n, gemara_ref in enumerate(matches):
                #     if gemara_ref:
                #         penei_ref = "{} {}:{}".format(index_title, daf, match_n+1)
                #         link = {"refs": [gemara_ref.normal(), penei_ref], "type": "Commentary", "auto": True, "generated_by": "penei_yehoshua_batch_ii"}
                #         links.append(link)
            post_link(links, server="http://shmuel.sandbox.sefaria.org")








    #1. make sure local database is up-to-date with prod and then maybe get Penei Yehoshua on {} CSVs
    #2. go over each CSV and gather all comments on each daf, and use base text as the daf itself from Gemara
    #3.

    # files = [f for f in os.listdir(".") if f.endswith(".txt")]
    # for file in files:
    #     title = file[0:-4]
    #     try: #the try except clause allows us to test that book exists and isn't one of the commentaries that we don't want in director
    #         book = library.get_index(title)
    #         print book.title
    #         parser = MaharshaLite(book)
    #         with open(file) as f:
    #             parser.create_index()
    #             # parser.parse(list(f))
    #             # parser.create_links()
    #             # #post_link(parser.links, server=parser.server)
    #             # for daf, text in parser.comm_dict.items():
    #             #     parser.comm_dict.pop(daf)
    #             #     parser.comm_dict[AddressTalmud(daf).toNumber("en", daf)] = text
    #             # text = convertDictToArray(parser.comm_dict)
    #             # send_text = {
    #             #     "text": text,
    #             #     "language": "he",
    #             #     "versionTitle": "P'nei Yehoshua",
    #             #     "versionSource": "www.sefaria.org"
    #             # }
    #             # #post_text("Penei Yehoshua on {}".format(title), send_text, server=parser.server)
    #     except system.exceptions.BookNameError as e:
    #         print e

