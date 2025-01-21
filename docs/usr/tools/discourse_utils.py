#!/usr/bin/python3

import glob
import markdown
import os
import re
import shutil
import subprocess
import sys
import tempfile
import yaml

from jinja2 import Environment, FileSystemLoader


def ask_yes_no_question(prompt):
    while True:
        response = input(prompt).lower()
        if response == "yes":
            return True
        elif response == "no":
            return False
        else:
            print("Please enter yes or no.")


def commit_and_push(git_directory, commit_message):
    orig_dir = os.getcwd()
    os.chdir(git_directory)
    subprocess.run(["git", "add", "."])
    subprocess.run(["git", "commit", "-m", commit_message])
    subprocess.run(["git", "push"])
    os.chdir(orig_dir)


def debug_print(debug_flag, message):
    if debug_flag:
        print(message)


def find_topic(mdir, tnum, dbug):
    mdfiles = glob.glob(os.path.join(mdir, f"*{tnum}*.md"))

    if mdfiles:
        debug_print(
            dbug,
            f"File matching topic number {tnum} found: {mdfiles[0]}",
        )
        return mdfiles[0]
    else:
        sys.exit(f"No files matching topic number {tnum} found.")


def get_tabbed_content(markdown, version, view):
    """
    Retrieve specific content from the markdown document based on version and view.

    Parameters:
    - markdown (str): The input markdown document.
    - version (str): The version string, e.g. "v3.4 Snap".
    - view (str): The view type, e.g. "UI" or "CLI".

    Returns:
    - str: The filtered content of the markdown document.
    """

    buffer = ""
    copytab = False
    intab = False

    for line in markdown.splitlines():
        if "[tabs]" in line:
            pass
        elif "[/tabs]" in line:
            pass
        elif "[/tab]" in line:
            copytab = False
            intab = False
        elif "[tab " in line:
            intab = True
            if "view=" in line:
                if version in line and view in line:
                    copytab = True
            elif version in line:
                copytab = True
        elif copytab == True:
            buffer += line + "\n"
        elif intab == False:
            buffer += line + "\n"

    return buffer


def load_sidebar_content(directory):
    sidebar_content_file = os.path.join(directory, "sidebar-content.html")
    if os.path.exists(sidebar_content_file):
        with open(sidebar_content_file, "r") as file:
            sidebar_content = file.read()
            return sidebar_content


def make_html(markdown_content, title, git_root, html_filename, is_ui_view):
    markdown_content = re.sub(
        r'<!-- "nohtml begin-nohtml" -->.*?<!-- "nohtml end-nohtml" -->',
        "",
        markdown_content,
        flags=re.DOTALL,
    )
    markdown_content = re.sub(
        r"\(/t/([\w-]+)/\d+\)",
        r"(\1.html)",
        markdown_content,
    )
    html_content = markdown.markdown(
        markdown_content, extensions=["tables", "fenced_code", "sane_lists"]
    )
    css_filename = os.path.join(git_root, "html-support/css/stylesheet.css")
    custom_css_path = os.path.join(git_root, "html-support/css/custom.css")
    with open(custom_css_path, "r") as custom_css_file:
        custom_css = custom_css_file.read()
    custom_html_path = os.path.join(git_root, "html-support/templates/custom.html")
    with open(custom_html_path, "r") as custom_html_file:
        custom_html = custom_html_file.read()
    jinja2_template_path = os.path.join(git_root, "html-support/templates")
    env = Environment(loader=FileSystemLoader(jinja2_template_path))
    template = env.get_template("template.html")
    sidebar_content_path = os.path.join(git_root, "html-support/templates/")
    sidebar_content = load_sidebar_content(sidebar_content_path)

    # Render the template with the data
    rendered_html = template.render(
        title=title,
        css_filename=css_filename,
        custom_css=custom_css,
        custom_html=custom_html,
        is_ui_view=is_ui_view,
        sidebar_content=sidebar_content,
        html_content=html_content,
        html_filename=html_filename,
    )

    return rendered_html


def parse_args():
    parser = argparse.ArgumentParser(description="discobot automated editing tool")
    parser.add_argument("topic_number", type=int, help="A discourse topic number")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("-s", action="store_true", help="Enable stormrider mode")
    parser.add_argument(
        "--html_version",
        type=str,
        default=None,
        help="Specify HTML version. If given, only processes HTML, only for this version.",
    )
    return parser.parse_args()


def read_config():
    home = os.path.expanduser("~")
    config_path = os.path.join(home, ".config", "disced.conf")

    if not os.path.exists(config_path):
        sys.exit(f"Config file {config_path} not found.")

    with open(config_path, "r") as f:
        try:
            config = yaml.safe_load(f)
            return config
        except yaml.YAMLError as e:
            sys.exit(f"Error parsing YAML config file: {e}")


def stage_files(path):
    try:
        tdir = tempfile.mkdtemp()
        spath = os.path.join(tdir, os.path.basename(path))
        shutil.copy(path, dpath)
        return spath  # Return the path to the staged (copied) file
    except FileNotFoundError:
        sys.exit(f"File {path} not found.")
    except IOError as e:
        sys.exit(f"An error occurred while staging {path}: {e}")
