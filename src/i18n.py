###
# Copyright (c) 2010, Valentin Lorentz
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice,
#     this list of conditions, and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions, and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#   * Neither the name of the author of this software nor the name of
#     contributors to this software may be used to endorse or promote products
#     derived from this software without specific prior written consent.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
###

"""
Supybot internationalisation and localisation managment.
"""

__all__ = ['PluginInternationalization', 'internationalizeDocstring']

import re
import sys
import time
import threading
# Don't import conf here ; because conf needs this module

WAITING_FOR_MSGID = 1
IN_MSGID = 2
WAITING_FOR_MSGSTR = 3
IN_MSGSTR = 4

MSGID = 'msgid "'
MSGSTR = 'msgstr "'

def import_conf():
    import supybot.conf as conf
    globals().update({'conf': conf})
    conf.registerGlobalValue(conf.supybot, 'language',
	conf.registry.String('en', """Determines the bot's default language.
	Valid values are things like en, fr, de, etc."""))
    for key in i18nClasses:
	i18nClasses[key].loadLocale()

def get_plugin_dir(plugin_name):
    filename = None
    try:
	filename = sys.modules[plugin_name].__file__
    except KeyError: # It sometimes happens with Owner
	pass
    if filename == None:
	filename = sys.modules['supybot.plugins.' + plugin_name].__file__
    if filename.endswith(".pyc"):
	filename = filename[0:-1]
    
    allowed_files = ['__init__.py', 'config.py', 'plugin.py', 'test.py']
    for allowed_file in allowed_files:
	if filename.endswith(allowed_file):
	    return filename[0:-len(allowed_file)]
    return 

def getLocalePath(name, localeName, extension):
    if name != 'supybot':
	directory = get_plugin_dir(name) + 'locale'
    else:
	import ansi # Any Supybot plugin could fit
	directory = ansi.__file__[0:-len('ansi.pyc')] + 'locale'
    return '%s/%s.%s' % (directory, localeName, extension)

i18nClasses = {}
internationalizedCommands = {}
internationalizedFunctions = [] # No need to know there name

def reloadLocals():
    for pluginName in i18nClasses:
	i18nClasses[pluginName].loadLocale()
    for commandHash in internationalizedCommands:
	internationalizeDocstring(internationalizedCommands[commandHash])
    for function in internationalizedFunctions:
	function.loadLocale()
	

i18nSupybot = None
def PluginInternationalization(name='supybot'):
    # This is a proxy, that prevent Supybot against having more than one
    # internationalizer
    global i18nSupybot
    if name != 'supybot':
	return _PluginInternationalization(name)
    elif i18nSupybot == None:
	i18nSupybot = _PluginInternationalization('supybot')
    return i18nSupybot

class _PluginInternationalization:
    """Internationalization managment for a plugin."""
    def __init__(self, name='supybot'):
	self.name = name
	self.currentLocaleName = None
	i18nClasses.update({name: self})
	if name != 'supybot' and not 'conf' in globals():
	    # if conf is loadable but not loaded
	    import_conf()
	self.loadLocale()
    
    def loadLocale(self, localeName=None):
	"""(Re)loads the locale used by this class."""
	if localeName is None and 'conf' in globals():
	    localeName = conf.supybot.language()
	elif localeName is None:
	    localeName = 'en'
	self.currentLocaleName = localeName
	
	self._loadL10nCode()

	try:
	    translationFile = open(getLocalePath(self.name, localeName, 'po'),
				   'ru') # ru is the mode, not the beginning
				         # of 'russian' ;)
	    self._parse(translationFile)
	except IOError: # The translation is unavailable
	    self.translations = {}
	    return

    def _parse(self, translationFile):
	"""A .po files parser.

	Give it a file object."""
	step = WAITING_FOR_MSGID
	self.translations = {}
	for line in translationFile:
	    line = line[0:-1] # Remove the ending \n
	    
	    if line.startswith(MSGID):
		# Don't check if step is WAITING_FOR_MSGID
		untranslated = ''
		translated = ''
		data = line[len(MSGID):-1]
		if len(data) == 0: # Multiline mode
		    step = IN_MSGID
		else:
		    untranslated += data
		    step = WAITING_FOR_MSGSTR
		    
		    
	    elif step is IN_MSGID and line.startswith('"') and \
			              line.endswith('"'):
		untranslated += line[1:-1]
	    elif step is IN_MSGID and untranslated == '': # Empty MSGID
		step = WAITING_FOR_MSGID
	    elif step is IN_MSGID: # the MSGID is finished
		step = WAITING_FOR_MSGSTR
		
		
	    if step is WAITING_FOR_MSGSTR and line.startswith(MSGSTR):
		data = line[len(MSGSTR):-1]
		if len(data) == 0: # Multiline mode
		    step = IN_MSGSTR
		else:
		    self._addToDatabase(untranslated, data)
		    step = WAITING_FOR_MSGID
		    
		    
	    elif step is IN_MSGSTR and line.startswith('"') and \
			               line.endswith('"'):
		translated += line[1:-1]
	    elif step is IN_MSGSTR: # the MSGSTR is finished
		step = WAITING_FOR_MSGID
		if translated == '':
		    translated = untranslated
		self._addToDatabase(untranslated, translated)
    
    def _addToDatabase(self, untranslated, translated):
	untranslated = self._unescape(untranslated)
	translated = self._unescape(translated)
	self.translations.update({untranslated: translated})
    
    def _unescape(self, string):
	import supybot.utils as utils
	return utils.str.normalizeWhitespace(str.replace(string, '\\n', '\n'))
    
    def __call__(self, untranslated):
	if untranslated.__class__ == internationalizedString:
	    return untranslated._original
	untranslated = __import__('supybot').utils.str.normalizeWhitespace(untranslated)
	if not 'conf' in globals():
	    return untranslated
	if self.currentLocaleName != conf.supybot.language():
	    # If the locale has been changed
	    reloadLocals()
	try:
	    string = self._translate(untranslated)
	    return self._addTracker(string, untranslated)
	except KeyError:
	    pass
	return untranslated
    
    def _translate(self, string):
	if string.__class__ == internationalizedString:
	    return string._internationalizer(string.untranslated)
	else:
	    return self.translations[string]
    
    def _addTracker(self, string, untranslated):
	if string.__class__ == internationalizedString:
	    return string
	else:
	    string = internationalizedString(string)
	    string._original = untranslated
	    string._internationalizer = self
	    return string

    def _loadL10nCode(self):
	if self.name != 'supybot':
	    return
	try:
	    execfile(self._getL10nCodePath())
	except IOError: # File doesn't exist
	    pass
	
	functions = locals()
	functions.pop('self')
	self._l10nFunctions = functions
	    # Remove old functions and come back to the native language
    
    def _getL10nCodePath(self):
	"""Returns the path to the code localization file.

	It contains functions that needs to by fully (code + strings)
	localized"""
	if self.name != 'supybot':
	    return
	return getLocalePath('supybot', self.currentLocaleName, 'py')
    
    def localizeFunction(self, name):
	"""Returns the localized version of the function.

	Should be used only by the internationalizedFunction class"""
	if self.name != 'supybot':
	    return
	if hasattr(self, '_l10nFunctions') and \
	    self._l10nFunctions.has_key(name):
	    return self._l10nFunctions[name]
    
    def internationalizeFunction(self, name):
	"""Decorates functions and internationalize their code.

	Only useful for Supybot core functions"""
	if self.name != 'supybot':
	    return
	class FunctionInternationalizer:
	    def __init__(self, parent, name):
		self._parent = parent
		self._name = name
	    def __call__(self, obj):
		obj = internationalizedFunction(self._parent, self._name, obj)
		obj.loadLocale()
		return obj
	return FunctionInternationalizer(self, name)

class internationalizedFunction:
    """Proxy for functions that need to be fully localized.

    The localization code is in locale/LOCALE.py"""
    def __init__(self, internationalizer, name, function):
	self._internationalizer = internationalizer
	self._name = name
	self.__call__ = function
	self._origin = function
	internationalizedFunctions.append(self)
    def loadLocale(self):
	self.__call__ = self._internationalizer.localizeFunction(self._name)
	if self.__call__ == None:
	    self.restore()
    def restore(self):
	self.__call__ = self._origin

class internationalizedString(str):
    pass
#    def __init__(self, *args, **kwargs):
#	self.__parent.__init__(*args, **kwargs)
#	self._original = str(self)
#	self._internationalizer = None

def internationalizeDocstring(obj):
    """Decorates functions and internationalize their docstring.

    Only useful for commands (commands' docstring is displayed on IRC)"""
    if sys.modules[obj.__module__].__dict__.has_key('_'):
	internationalizedCommands.update({hash(obj): obj})
	obj.__doc__=sys.modules[obj.__module__]._.__call__(obj.__doc__)
	# We use _.__call__() instead of _() because of a pygettext warning.
    return obj
