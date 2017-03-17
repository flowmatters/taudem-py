
from . import commands as _commands
import settings

_me = __import__(__name__)
for c in _commands.commands:
	fn = c.generate()
	fn.__doc__ = c.doc_string()
	fn.__name__ = c.name
	setattr(_me,c.name,fn)

