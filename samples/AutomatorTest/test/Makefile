test: vizgrimoire.min.js
	cd test/jasmine; jasmine-headless-webkit -j jasmine.yml -c
	cd ../..

testci:
	cd test/jasmine; xvfb-run jasmine-headless-webkit -j jasmine.yml -c
	cd ../..
