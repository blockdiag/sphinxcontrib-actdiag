#!/usr/bin/env python
# encoding: utf-8
#
# Copyright (c) 2010 Doug Hellmann.  All rights reserved.
#
"""Spelling checker extension for Sphinx.
"""

import codecs
import imp
import itertools
import os
import re
import textwrap
import tempfile
import xmlrpclib

#from docutils import core
from docutils.frontend import OptionParser
from docutils.io import StringOutput
import docutils.nodes
from docutils.nodes import GenericNodeVisitor
from docutils.writers import Writer
from sphinx.builders import Builder
from sphinx.util.console import bold, darkgreen
from sphinx.util.console import purple, red, darkgreen, darkgray
from sphinx.util.nodes import inline_all_toctrees

import enchant
from enchant.tokenize import get_tokenizer, Filter, EmailFilter, WikiWordFilter, unit_tokenize

# TODO - Directive (or comment syntax?) to allow words to be ignored in a document
# TODO - Words with multiple uppercase letters treated as classes and ignored

class AcronymFilter(Filter):
    """If a word looks like an acronym (all upper case letters),
    ignore it.
    """
    def _skip(self, word):
        return (word == word.upper() # all caps
                or
                # pluralized acronym ("URLs")
                (word[-1].lower() == 's'
                 and
                 word[:-1] == word[:-1].upper()
                 )
                )

class ContractionFilter(Filter):
    """Strip common contractions from words.
    """
    def _split(self, word):
        if word.lower().endswith("'s"):
            return unit_tokenize(word[:-2])
        if word.lower().endswith("n't"):
            return unit_tokenize(word[:-3])
        if word.lower() == "i'm":
            return unit_tokenize(word[0])
        return unit_tokenize(word)

class IgnoreWordsFilter(Filter):
    """Given a set of words, ignore them all.
    """
    def __init__(self, tokenizer, word_set):
        self.word_set = word_set
        Filter.__init__(self, tokenizer)
    def _skip(self, word):
        return word in self.word_set

class PyPIFilterFactory(object):
    """Build an IgnoreWordsFilter for all of the names of packages on PyPI.
    """
    def __init__(self):
        client = xmlrpclib.ServerProxy('http://pypi.python.org/pypi')
        self.package_names = set(client.list_packages())
    def __call__(self, tokenizer):
        return IgnoreWordsFilter(tokenizer, self.package_names)

class PythonBuiltinsFilter(Filter):
    """Ignore names of built-in Python symbols.
    """
    def _skip(self, word):
        return word in __builtins__

class ImportableModuleFilter(Filter):
    """Ignore names of modules that we could import.
    """
    def __init__(self, tokenizer):
        Filter.__init__(self, tokenizer)
        self.found_modules = set()
        self.sought_modules = set()
    def _skip(self, word):
        if word not in self.sought_modules:
            self.sought_modules.add(word)
            try:
                imp.find_module(word)
            except UnicodeEncodeError:
                return False
            except ImportError:
                return False
            else:
                self.found_modules.add(word)
                return True
        return word in self.found_modules


class SpellingChecker(object):
    """Checks the spelling of blocks of text.

    Uses options defined in the sphinx configuration file to control
    the checking and filtering behavior.
    """

    def __init__(self, lang, suggest, word_list_filename, filters=[]):
        self.dictionary = enchant.DictWithPWL(lang, word_list_filename)
        self.tokenizer = get_tokenizer(lang, filters)
        self.suggest = suggest

    def check(self, text):
        """Generator function that yields bad words and suggested alternate spellings.
        """
        for word, pos in self.tokenizer(text):
            correct = self.dictionary.check(word)
            if correct:
                continue
            yield word, self.dictionary.suggest(word) if self.suggest else []
        return


TEXT_NODES = set([ 'block_quote',
                   'paragraph',
                   'list_item',
                   'term',
                   'definition_list_item',
                   ])


class SpellingBuilder(Builder):
    """
    Spell checks a document
    """
    name = 'spelling'

    def init(self):
        self.docnames = []
        self.document_data = []

        filters = [ ContractionFilter,
                    EmailFilter,
                    ]
        if self.config.spelling_ignore_wiki_words:
            filters.append(WikiWordFilter)
        if self.config.spelling_ignore_acronyms:
            filters.append(AcronymFilter)
        if self.config.spelling_ignore_pypi_package_names:
            self.info('Retrieving package names from PyPI...')
            filters.append(PyPIFilterFactory())
        if self.config.spelling_ignore_python_builtins:
            filters.append(PythonBuiltinsFilter)
        if self.config.spelling_ignore_importable_modules:
            filters.append(ImportableModuleFilter)
        filters.extend(self.config.spelling_filters)

        project_words = os.path.join(self.srcdir, self.config.spelling_word_list_filename)
        self.checker = SpellingChecker(lang=self.config.spelling_lang,
                                       suggest=self.config.spelling_show_suggestions,
                                       word_list_filename=project_words,
                                       filters=filters,
                                       )
        self.output_filename = os.path.join(self.outdir, 'output.txt')
        self.output = codecs.open(self.output_filename, 'wt', encoding='UTF-8')

    def get_outdated_docs(self):
        return 'all documents'

    def prepare_writing(self, docnames):
        return

    def get_target_uri(self, docname, typ=None):
        return ''

    def format_suggestions(self, suggestions):
        if not self.config.spelling_show_suggestions or not suggestions:
            return u''
        return u'[' + u', '.join(u'"%s"' % s for s in suggestions) + u']'

    def write_doc(self, docname, doctree):
        for node in doctree.traverse(docutils.nodes.Text):
            if node.tagname == '#text' and  node.parent.tagname in TEXT_NODES:

                # Figure out the line number for this node by climbing the
                # tree until we find a node that has a line number.
                lineno = None
                parent = node
                seen = set()
                while lineno is None:
                    #self.info('looking for line number on %r' % node)
                    seen.add(parent)
                    parent = node.parent
                    if parent is None or parent in seen:
                        break
                    lineno = parent.line
                filename = self.env.doc2path(docname, base=None)

                # Check the text of the node.
                for word, suggestions in self.checker.check(node.astext()):
                    msg_parts = []
                    if lineno:
                        msg_parts.append(darkgreen('(line %3d)' % lineno))
                    msg_parts.append(red(word))
                    msg_parts.append(self.format_suggestions(suggestions))
                    msg = ' '.join(msg_parts)
                    self.info(msg)
                    self.output.write(u"%s:%s: (%s) %s\n" % (
                            self.env.doc2path(docname, None),
                            lineno, word,
                            self.format_suggestions(suggestions),
                            ))

                    # We found at least one bad spelling, so set the status
                    # code for the app to a value that indicates an error.
                    self.app.statuscode = 1
        return

    def finish(self):
        self.output.close()
        self.info('Spelling checker messages written to %s' % self.output_filename)
        return

def setup(app):
    app.info('Initializing Spelling Checker')
    app.add_builder(SpellingBuilder)
    # Report guesses about correct spelling
    app.add_config_value('spelling_show_suggestions', False, 'env')
    # Set the language for the text
    app.add_config_value('spelling_lang', 'en_US', 'env')
    # Set a user-provided list of words known to be spelled properly
    app.add_config_value('spelling_word_list_filename', 'spelling_wordlist.txt', 'env')
    # Assume anything that looks like a PyPI package name is spelled properly
    app.add_config_value('spelling_ignore_pypi_package_names', False, 'env')
    # Assume words that look like wiki page names are spelled properly
    app.add_config_value('spelling_ignore_wiki_words', True, 'env')
    # Assume words that are all caps, or all caps with trailing s, are spelled properly
    app.add_config_value('spelling_ignore_acronyms', True, 'env')
    # Assume words that are part of __builtins__ are spelled properly
    app.add_config_value('spelling_ignore_python_builtins', True, 'env')
    # Assume words that look like the names of importable modules are spelled properly
    app.add_config_value('spelling_ignore_importable_modules', True, 'env')
    # Add any user-defined filter classes
    app.add_config_value('spelling_filters', [], 'env')
    return
