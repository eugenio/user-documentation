import argparse
import codecs
import datetime
import json
import os
import subprocess
import webbrowser
from os import listdir
from os.path import isfile, join, isdir

import logger

try:
    import frontmatter
except ImportError, e:
    logger.error("The 'python-frontmatter' package is not available\n" +
                 "Install it with 'pip install python-frontmatter'")
    quit()

COMMAND_STATUS = "status"
COMMAND_UPDATE = "update"
COMMAND_CLEAN = "clean"
COMMAND_REMOVE_SUFFIX = "removeHelpSuffix"

MAIN_LANGUAGE = "en"

FRONTMATTER_CATEGORIES = "helpCategories"
FRONTMATTER_TITLE = "title"
FRONTMATTER_OUTDATED = "outdated"

FILE_CATEGORIES_ORDER = "_scripts/categories.json"
FILE_STATUS = "status.md"


def get_language_file_path(language):
    """
    :param language: string
    :return: string: path to where the language file lies
    """
    return "_scripts/localization/{}.json".format(language)


def read_file(filename, encoding="UTF-8"):
    """
    :param filename: string
    :param encoding: string: the encoding of the file to read (standart: `UTF-8`)
    :return: list of strings: the lines of the file
    """
    f1 = codecs.open(filename, encoding=encoding)
    lines = f1.read()
    f1.close()
    return lines


def write_file(filename, content):
    """
    writes the lines to the file in `UTF-8`

    :param filename: string
    :param content: list: the lines to write
    """
    codecs.open(filename, "w", encoding='utf-8').writelines(content)


def get_local_file_path(language, page):
    """
    :param language: string
    :param page: string
    :return: String: path without '/' at the beginning
    """
    return "{lang}/{page}".format(lang=language, page=page)


def get_relative_file_link(language, page):
    """
    :param language: string
    :param page: string
    :return: String: path with '/' at the beginning, but without '.md' at the end
    """
    # remove .md at the end
    return "/{lang}/{page}".format(lang=language, page=page)[:-3]


def get_file_link(language, page):
    """
    :param language: string
    :param page: string
    :return: string: link directly to the github page
    """
    filepath = get_local_file_path(language=language, page=page)
    return "https://github.com/JabRef/help.jabref.org/blob/gh-pages/{file}".format(file=filepath)


def get_current_branch():
    """
    :return: string: the current git branch
    """
    return subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD']).strip("\n")


def get_current_hash_short():
    """
    :return: string: the current git hash (short)
    """
    return subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).strip("\n")


def get_other_languages():
    """
    :return: list of strings: all but the main language
    """
    return [f for f in listdir(".") if
        isdir(join(".", f)) and not f.startswith("_") and not f.startswith(".") and not f.startswith("css") and not f.startswith(MAIN_LANGUAGE)]


def get_all_languages():
    """
    :return: list: of strings all languages with the main language at the beginning
    """
    languages = get_other_languages()
    languages.insert(0, MAIN_LANGUAGE)
    return languages


def get_help_pages_in(language):
    """
    :param language: string
    :return: list of strings: all help pages (including redirecting pages)
    """
    return [f for f in listdir(language) if isfile(join(language, f)) and f.endswith(".md") and not f == "index.md" and not f == "cpl-v10.md"]


def get_categories_order():
    """
    :return: list of strings and lists: the category order
    """
    return json.loads(read_file(FILE_CATEGORIES_ORDER))


def get_localization(language, key):
    """
    :param language: string
    :param key: string
    :return: String: the localization or key if you cannot find the localization
    """
    file_path = get_language_file_path(language=language)
    try:
        translation = json.loads(read_file(file_path))[key]
        if not translation:
            logger.error("Language file '{lang}' has an empty key '{key}'".format(lang=language, key=key))
        else:
            return translation
    except IOError:
        logger.error("Cannot find language file '{}'".format(language))
    except ValueError:
        logger.error("Language file is no valid json file '{}'".format(language))
    except KeyError:
        logger.error("Language '{lang}' has no key '{key}'".format(lang=language, key=key))

    return key


def get_redirect_page_content(language, page):
    """
    :param language: string
    :param page: string
    :return: string: the formatted frontmatter of a redirecting page
    """
    return """---
redirect:   {path}
layout:     redirect
---
""".format(path=get_relative_file_link(language=language, page=page))


def get_index_header(title, more_questions, forum):
    """
    :param title: string
    :param more_questions: string
    :param forum: string
    :return: string: the formatted frontmatter + forum link of an index page
    """
    return u"""---
title: {title}
---

# {title}

<div class="panel panel-info">
  <div class="panel-heading">
    <strong>{more_questions}</strong>
  </div>
  <div class="panel-body">
    <a class="btn btn-default" role="button" href="http://discourse.jabref.org">{forum}</a>
  </div>
</div>\n\n""".format(title=title, more_questions=more_questions, forum=forum)


def is_redirect_page(language, page):
    """
    :param language: string
    :param page: string
    :return: boolean: True if this page is redirected to the main language one
    """
    with open(get_local_file_path(language=language, page=page)) as yaml_page:
        post = frontmatter.load(yaml_page)
        redirect_layout = post["layout"] == "redirect" if "layout" in post.keys() else False
        link = get_relative_file_link(language=MAIN_LANGUAGE, page=page)
        redirect_link = post["redirect"] == link if "redirect" in post.keys() else False
        return redirect_layout and redirect_link and not post.content


def is_old_help_page_redirecting_to_new_one(language, page):
    """
    :param language: string
    :param page: string
    :return: boolean True if this help page was renamed and is redirecting to the new one
    """
    with open(get_local_file_path(language=language, page=page)) as yaml_page:
        post = frontmatter.load(yaml_page)
        redirect_layout = post["layout"] == "redirect" if "layout" in post.keys() else False
        redirect_not_to_en = post["redirect"].startswith("/{}/".format(language)) if "redirect" in post.keys() else False
        return redirect_layout and redirect_not_to_en and not post.content


def create_redirect_page(language, page):
    """
    creates a page which redirects to the main language one

    :param language: string
    :param page: string
    """
    path = get_local_file_path(language=language, page=page)
    if is_old_help_page_redirecting_to_new_one(language=MAIN_LANGUAGE, page=page):
        with open(get_local_file_path(language=MAIN_LANGUAGE, page=page)) as yaml_page:
            post = frontmatter.load(yaml_page)
            new_page = post["redirect"].replace("/{}/".format(MAIN_LANGUAGE), "", 1) + ".md"
            write_file(filename=path, content=get_redirect_page_content(language=language, page=new_page))
    else:
        write_file(filename=path, content=get_redirect_page_content(language=MAIN_LANGUAGE, page=page))


def delete_redirecting_help_pages(language):
    """
    :param language: string
    :return: list of strings: deletes all pages which redirects to the page in the main language and returns their names
    """
    deleted_pages = []
    for page in get_help_pages_in(language=language):
        if is_redirect_page(language=language, page=page) or is_old_help_page_redirecting_to_new_one(language=language, page=page):
            deleted_pages.append(page)
            os.remove(get_local_file_path(language=language, page=page))
    return deleted_pages


def delete_all_generated_redirecting_pages(extended):
    """
    deletes all the generated pages (inlcuding status.md)

    :param extended: if True then the deleted pages will be printed
    """
    for language in get_all_languages():
        deleted_pages = []
        if language != MAIN_LANGUAGE:
            deleted_pages = delete_redirecting_help_pages(language=language)
        index = get_local_file_path(language=language, page="index.md")
        if os.path.isfile(index):
            os.remove(index)
            deleted_pages.append("index.md")
        num_deleted_pages = len(deleted_pages)
        logger.ok("Deleted {num_deleted_pages} page(s) for language '{lang}'".format(lang=language, num_deleted_pages=num_deleted_pages))
        if extended and num_deleted_pages != 0:
            logger.neutral("\t{}".format(deleted_pages))
    if os.path.isfile(FILE_STATUS):
        os.remove(FILE_STATUS)
        logger.ok("Delete the markdown status file")


def get_not_redirected_pages(main_language, secondary_language):
    """
    :param main_language: string
    :param secondary_language: string
    :return: list of strings: the pages which are in the `main_language` but not in the `second_language`
    """
    pages_main_language = get_help_pages_in(language=main_language)
    pages_this_language = get_help_pages_in(language=secondary_language)
    not_redirected_pages = []

    for page in pages_main_language:
        if page not in pages_this_language:
            not_redirected_pages.append(page)
    return not_redirected_pages


def get_translated_pages(language):
    """
    :param language: string
    :return: list of strings: the pages which are translated (excluded the redirected pages)
    """
    translated_pages = []
    for page in get_help_pages_in(language=language):
        if not is_old_help_page_redirecting_to_new_one(language=language, page=page) and not is_redirect_page(language=language, page=page):
            translated_pages.append(page)
    return translated_pages


def get_old_help_pages_redirecting_to_new_one(language):
    """
    :param language: string
    :return: list of strings: the pages which redirect to the renamed page
    """
    old_help_pages = []
    for page in get_help_pages_in(language=language):
        if is_old_help_page_redirecting_to_new_one(language=language, page=page):
            old_help_pages.append(page)
    return old_help_pages


def get_not_translated_pages(main_language, secondary_language):
    """
    :param main_language: string
    :param secondary_language: string
    :return: list of strings: the pages which are redirected to the main language one
    """
    pages_main_language = get_help_pages_in(secondary_language)
    not_translated_pages = get_not_redirected_pages(main_language=main_language, secondary_language=secondary_language)

    for page in pages_main_language:
        if is_redirect_page(language=secondary_language, page=page):
            not_translated_pages.append(page)
    return not_translated_pages


def get_pages_not_in_main_language():
    """
    :return: list of strings: the pages that are not in the main language
    """
    main_not_translated_pages = {}
    for language in get_other_languages():
        not_translated_pages = get_not_translated_pages(main_language=language, secondary_language=MAIN_LANGUAGE)
        if not_translated_pages:
            main_not_translated_pages[language] = not_translated_pages
    return main_not_translated_pages


def get_outdated_pages(language):
    """
    :param language: string
    :return: list of strings: pages which are outdated and need to be revised (checks the frontmatter)
    """
    outdated_pages = []
    for page in get_help_pages_in(language=language):
        with open(get_local_file_path(language=language, page=page)) as yaml_page:
            post = frontmatter.load(yaml_page)
            if post[FRONTMATTER_OUTDATED] if FRONTMATTER_OUTDATED in post.keys() else False:
                outdated_pages.append(page)
    return outdated_pages


def check_language_status(language, extended):
    """
    checks the status of this language and prints it on the console (maybe call `update` before?)

    :param language: string
    :param extended: boolean: if the specific pages should be printed
    """
    outdated_pages = get_outdated_pages(language=language)
    num_outdated_pages = len(outdated_pages)

    if language == MAIN_LANGUAGE:
        main_not_translated_pages = get_pages_not_in_main_language()
        num_main_not_translated_pages = len(main_not_translated_pages)

        log = logger.ok if num_main_not_translated_pages == 0 and num_outdated_pages == 0 else logger.error
        log("Main Language: '{lang}'".format(lang=MAIN_LANGUAGE))
        if num_main_not_translated_pages == 0:
            logger.ok("\thas no conflicts")
        else:
            for key, value in main_not_translated_pages.iteritems():
                logger.error("\tlanguage '{lang}' has {count} additional page(s)".format(lang=key, count=len(value)))
                if extended and len(value) != 0:
                    logger.neutral("\t\t{pages}".format(pages=value))

    else:
        not_translated_pages = get_not_translated_pages(main_language=MAIN_LANGUAGE, secondary_language=language)
        num_not_translated_pages = len(not_translated_pages)
        not_redirected_pages = get_not_redirected_pages(main_language=MAIN_LANGUAGE, secondary_language=language)
        num_not_redirected_pages = len(not_redirected_pages)

        log = logger.ok if num_not_redirected_pages == 0 and num_not_translated_pages == 0 and num_outdated_pages == 0 else logger.error
        log("Language: '{lang}'".format(lang=language))

        log = logger.ok if num_not_translated_pages == 0 else logger.error
        log("\thas {num_not_translated_pages} not translated page(s)".format(num_not_translated_pages=num_not_translated_pages))
        if num_not_translated_pages != 0 and extended:
            logger.neutral("\t\t{not_translated_pages}".format(not_translated_pages=not_translated_pages))

        log = logger.ok if num_not_redirected_pages == 0 else logger.error
        log("\thas {num_not_redirected_pages} not redirected page(s)".format(num_not_redirected_pages=num_not_redirected_pages))
        if num_not_redirected_pages != 0 and extended:
            logger.neutral("\t\t{not_redirected_pages}".format(not_redirected_pages=not_redirected_pages))

    log = logger.ok if num_outdated_pages == 0 else logger.error
    log("\thas {num_outdated_pages} outdated page(s)".format(num_outdated_pages=num_outdated_pages))
    if num_outdated_pages != 0 and extended:
        logger.neutral("\t\t{outdated_pages}".format(outdated_pages=outdated_pages))


def create_markdown(extended):
    """
    creates a markdown file of the current status (maybe call `update` before?) and opens it (`status.md`)

    :param extended: boolean: it the specific pages should be included in the status report
    """
    main_not_translated_pages = get_pages_not_in_main_language()
    num_languages_main_not_translated_pages = len(main_not_translated_pages)
    num_main_not_translated_pages = 0
    for lang in main_not_translated_pages:
        num_main_not_translated_pages += len(lang)

    markdown_text = []
    date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    markdown_text.append("### Help pages status ({date} - Branch `{branch}` `{hash}`)\n".format(date=date,
        branch=get_current_branch(), hash=get_current_hash_short()))
    markdown_text.append("- Main language: `{main}`\n".format(main=MAIN_LANGUAGE))
    markdown_text.append("- Available languages: {other}\n".format(
        other=", ".join(["`{}`".format(num) for num in get_other_languages()])))

    if num_main_not_translated_pages != 0:
        markdown_text.append("- **The main language is missing {count_pages} additional page(s) in {count_language} languages**\n"
                .format(count_pages=num_main_not_translated_pages, count_language=num_languages_main_not_translated_pages))
        for key, value in main_not_translated_pages.iteritems():
            markdown_text.append("  - language `{lang}` has {count} additional page(s)\n".format(lang=key, count=len(value)))
            if extended and len(value) != 0:
                for page in value:
                    link = get_file_link(language=key, page=page)
                    markdown_text.append("    - [{page}]({link})\n".format(page=page, link=link))
        markdown_text.append("\n")

    markdown_text.append("\n| Language | translated | not translated | outdated | old pages | % translated | % outdated |\n")
    markdown_text.append(  "| -------- | ---------- | -------------- | -------- | --------- | ------------ | ---------- |\n")
    are_pages_outdated = False
    are_pages_not_translated = False
    for language in get_all_languages():
        num_pages_translated = len(get_translated_pages(language=language))
        num_pages_not_translated = len(get_not_translated_pages(main_language=MAIN_LANGUAGE, secondary_language=language))
        num_pages_outdated = len(get_outdated_pages(language=language))
        num_pages_old = len(get_old_help_pages_redirecting_to_new_one(language=language))
        percent_translated = int((1 - num_pages_not_translated / float(num_pages_not_translated + num_pages_translated)) * 100)
        percent_outdated = int((num_pages_outdated / float(num_pages_translated)) * 100)
        markdown_text.append("| {lang} | {translated} | {not_translated} | {outdated} | {old_pages} | {percent_translated} | {percent_outdated} |\n"
            .format(lang=language, translated=num_pages_translated, not_translated=num_pages_not_translated, outdated=num_pages_outdated,
            old_pages=num_pages_old, percent_translated=percent_translated, percent_outdated=percent_outdated))
        are_pages_outdated |= num_pages_outdated != 0
        are_pages_not_translated |= num_pages_not_translated != 0

    if extended:
        if are_pages_outdated:
            markdown_text.append("\n- Outdated page(s):\n")
            for language in get_all_languages():
                pages_outdated = get_outdated_pages(language=language)
                if len(pages_outdated) != 0:
                    markdown_text.append("  - `{language}`\n".format(language=language))
                    for page in pages_outdated:
                        link = get_file_link(language=language, page=page)
                        markdown_text.append("    - [{page}]({link})\n".format(page=page, link=link))

        if are_pages_not_translated:
            markdown_text.append("- Not translated page(s):\n")
            for language in get_other_languages():
                not_translated_pages = get_not_translated_pages(main_language=MAIN_LANGUAGE, secondary_language=language)
                if len(not_translated_pages) != 0:
                    markdown_text.append("  - `{language}`\n".format(language=language))
                    for page in not_translated_pages:
                        link = get_file_link(language=MAIN_LANGUAGE, page=page)
                        markdown_text.append("    - {page} ([en]({link}))\n".format(page=page, link=link))

    write_file(filename=FILE_STATUS, content=markdown_text)
    webbrowser.open(FILE_STATUS)


def status(extended, markdown):
    """
    checks the current status (maybe call `update` before?)

    :param extended: boolean: if the specific pages should be included
    :param markdown: boolean: if a markdown file should be created
    """
    for language in get_all_languages():
        check_language_status(language=language, extended=extended)
    if markdown:
        create_markdown(extended=extended)


def generate_missing_redirects(language):
    """
    generates all the redirecting pages depending on the main page (including the old-to-new help pages)

    :return: list of strings: the redirected pages
    """
    if language == MAIN_LANGUAGE:
        return []
    redirected_pages = []
    for page in get_not_redirected_pages(main_language=MAIN_LANGUAGE, secondary_language=language):
        create_redirect_page(language=language, page=page)
        redirected_pages.append(page)
    return redirected_pages


def update_index(extended):
    """
    updates the index of all languages

    :param extended: boolean: if the pages which could not be processed be printed
    """
    def get_link_title_and_categories(language, page):
        """
        :param language: string
        :param page: string
        :return: (string, string, string): file link, title, categories
        """
        with open(get_local_file_path(language=MAIN_LANGUAGE, page=page)) as yaml_main_page:
            with open(get_local_file_path(language=language, page=page)) as yaml_page:
                main_post = frontmatter.load(yaml_main_page)
                post = frontmatter.load(yaml_page)

                file_link = get_relative_file_link(language=language, page=page)

                title = post[FRONTMATTER_TITLE] if FRONTMATTER_TITLE in post.keys() else ""
                if not title:
                    title = main_post[FRONTMATTER_TITLE] if FRONTMATTER_TITLE in main_post.keys() else ""

                categories = post[FRONTMATTER_CATEGORIES] if FRONTMATTER_CATEGORIES in post.keys() else []
                if not categories:
                    categories = main_post[FRONTMATTER_CATEGORIES] if FRONTMATTER_CATEGORIES in main_post.keys() else []

        return file_link, title, categories

    def create_index_file(order, index_file, index, indentation=2):
        """
        creates the index file out of the category order and the presorted pages

        :param order: list of strings: the order of the categories
        :param index_file: list of strings
        :param index: dict of strings and dicts: the presorted pages
        :param indentation: int: how much the category is indented
        """
        # 2 loops to write the link before subsections
        for key, value in sorted(index.iteritems()):
            if type(value) is not dict:
                index_file.append(u"- [{title}]({link})\n".format(title=value, link=key))

        last_category = ""
        for category in order:
            if type(category) is list:
                create_index_file(order=category, index_file=index_file, index=index[last_category],
                    indentation=indentation + 1)
            else:
                last_category = category
                if category not in index.keys():
                    logger.error("\tFollowing category is non-existent: {category}".format(category=category))
                    continue
                translated_category = get_localization(language=language, key=category)
                index_file.append(u"\n{indentation} {title}\n".format(indentation="#" * indentation, title=translated_category))
                create_index_file(order=[], index_file=index_file, index=index[category], indentation=indentation + 1)

        index_file.append("\n")

    for language in get_all_languages():
        renamed_pages = remove_help_suffix(language=language)
        redirected_pages = generate_missing_redirects(language=language)

        missing_frontmatter = []
        num_pages_on_index = 0
        index = {}
        for page in get_help_pages_in(language=language):
            if is_old_help_page_redirecting_to_new_one(language=language, page=page):
                continue

            file_link, title, categories = get_link_title_and_categories(language=language, page=page)
            if not title or not categories:
                missing_frontmatter.append(file_link)
                continue

            index_tmp = index
            for category in categories:
                if category not in index_tmp:
                    new_dict = {}
                    index_tmp[category] = new_dict
                    index_tmp = new_dict
                else:
                    index_tmp = index_tmp[category]

            index_tmp[file_link] = title
            num_pages_on_index += 1

        title = get_localization(language=language, key="Help contents")
        more_questions = get_localization(language=language, key="You can't find a solution to your problem? You still have questions?")
        forum_hint = get_localization(language=language, key="Use the online forum to get more support!")

        index_file = [get_index_header(title=title, more_questions=more_questions, forum=forum_hint)]
        create_index_file(order=get_categories_order(), index_file=index_file, index=index)
        write_file(language + "/index.md", index_file)

        num_missing_frontmatter = len(missing_frontmatter)
        num_redirected_pages = len(redirected_pages)
        num_renamed_pages = len(renamed_pages)

        logger.ok("Language: '{language}'".format(language=language))
        logger.ok("\tremoved the 'Help' suffix from {} pages".format(num_renamed_pages))
        if extended and num_renamed_pages != 0:
            logger.neutral("\t\t{}".format(renamed_pages))

        if language != MAIN_LANGUAGE:
            logger.ok("\tredirected {} page(s)".format(num_redirected_pages))
            if num_redirected_pages != 0 and extended:
                logger.neutral("\t\t{}".format(redirected_pages))

        log = logger.ok if num_missing_frontmatter == 0 else logger.error
        log("\t{} page(s) with missing frontmatter".format(num_missing_frontmatter))
        if extended and num_missing_frontmatter != 0:
            logger.neutral("\t\t{}".format(missing_frontmatter))

        logger.ok("\tcreated index with {} page(s)".format(num_pages_on_index))


def remove_help_suffix(language):
    """
    removes the help suffix from all pages and adds redirects in english, run `update` afterwards

    :param language: string
    :return: list of (string, string): (old page, new page)
    """
    renamed_files = []
    for page in get_help_pages_in(language=language):
        if page.endswith("Help.md") and not is_old_help_page_redirecting_to_new_one(language=language, page=page):
            new_page = page.replace("Help.md", ".md")
            old_path = get_local_file_path(language=language, page=page)
            new_path = get_local_file_path(language=language, page=new_page)
            os.rename(old_path, new_path)
            renamed_files.append((page, new_page))

            if language == MAIN_LANGUAGE:
                redirect = get_redirect_page_content(language=language, page=new_page)
                write_file(filename=old_path, content=redirect)

    return renamed_files


def remove_all_help_suffixes(extended):
    for language in get_all_languages():
        renamed_pages = remove_help_suffix(language=language)
        num_renamed_pages = len(renamed_pages)
        logger.ok("Language: '{language}'".format(language=language))
        logger.ok("\tremoved the 'Help' suffix from {} pages".format(num_renamed_pages))
        if extended and num_renamed_pages != 0:
            logger.neutral("\t\t{}".format(renamed_pages))


parser = argparse.ArgumentParser()

subparser = parser.add_subparsers(help='commands', dest='command')
parser_status = subparser.add_parser(COMMAND_STATUS, help="Lists the current status of the help pages.")
parser_status.add_argument("-e", "--extended", action="store_true", dest="extended", default=False,
    help="The output is much more sophisticated")
parser_status.add_argument("-m", "--markdown", action="store_true", dest="markdown", default=False,
    help="converts the output to markdown")

parser_update = subparser.add_parser(COMMAND_UPDATE, help="Generates all the missing redirection pages and updates the index files")
parser_update.add_argument("-e", "--extended", action="store_true", dest="extended", default=False,
    help="The output is much more sophisticated")

parser_clean = subparser.add_parser(COMMAND_CLEAN,
    help="Removes all the generated redirect files (CAUTION: index page may not work anymore")
parser_clean.add_argument("-e", "--extended", action="store_true", dest="extended", default=False,
    help="The output is much more sophisticated")

parser_suffix = subparser.add_parser(COMMAND_REMOVE_SUFFIX,
    help="Removes the 'Help' suffix from all pages and create redirects")
parser_suffix.add_argument("-e", "--extended", action="store_true", dest="extended", default=False,
    help="The output is much more sophisticated")

args = parser.parse_args()
if args.command == COMMAND_STATUS:
    status(extended=args.extended, markdown=args.markdown)
elif args.command == COMMAND_UPDATE:
    delete_all_generated_redirecting_pages(extended=args.extended)
    update_index(extended=args.extended)
elif args.command == COMMAND_CLEAN:
    delete_all_generated_redirecting_pages(extended=args.extended)
elif args.command == COMMAND_REMOVE_SUFFIX:
    remove_all_help_suffixes(extended=args.extended)