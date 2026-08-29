.PHONY: test check

test:
	python -m unittest discover -s tests -v
	node --test browser-extension/tests/*.test.js

check:
	node --check browser-extension/background.js
	node --check browser-extension/content.js
	node --check browser-extension/popup.js
	node --check browser-extension/lib.js
