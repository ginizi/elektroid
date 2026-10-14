# The project README.md and other resource files are generated from the documentation pages by executing `make` on this directory.

README=../README.md
CONTRIBUTING=../CONTRIBUTING.md

all: $(README) $(CONTRIBUTING) license.md

$(README): fork.md index.md license.md installation.md packaging.md cli.md api.md contributing.md
	echo '# Elektroid' > $(README)
	echo >> $(README)
	echo '[//]: # (Do not modify this file manually.)' >> $(README)
	echo '[//]: # (This file is generated from the docs directory by executing `make clean; make`.)' >> $(README)
	sed 's/](\([^)]*\.md\)/](docs\/\1/g' fork.md >> $(README)
	tail -n +4 index.md | sed "s^images/screenshot.png^docs/images/screenshot.png^" >> $(README)
	tail -n +7 license.md >> $(README)
	tail -n +7 installation.md >> $(README)
	tail -n +7 packaging.md >> $(README)
	tail -n +7 cli.md >> $(README)
	tail -n +7 api.md | sed "s^https://github.com/dagargo/elektroid/tree/master/^^g" >> $(README)
	tail -n +7 contributing.md >> $(README)

$(CONTRIBUTING): contributing.md
	echo '[//]: # (Do not modify this file manually.)' > $(CONTRIBUTING)
	echo '[//]: # (This file is generated from the docs directory by executing `make clean; make`.)' >> $(CONTRIBUTING)
	tail -n +7 contributing.md | sed "s/^##/#/g" >> $(CONTRIBUTING)

license.md: license.md.in
	cat license.md.in > license.md
	echo '' >> license.md
	while read -r line; do echo "* $$line" >> license.md; done < libraries.md
	cat libraries.md | sed -r 's/\[([^\]*)\]\(([^\)]*)\)/<a href="\2">\1<\/a>/' > ../res/libraries.html

clean:
	rm -f $(README) license.md ../res/libraries.html
